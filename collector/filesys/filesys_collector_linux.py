import os
import time
import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError

from prometheus_client.core import GaugeMetricFamily


STAT_TIMEOUT = 5          # 秒，等价 mount-timeout
STAT_WORKERS = 4          # 等价 stat-workers
STUCK_TTL = 300           # stuck mount 冷却时间（秒）


stuck_mounts = {}
stuck_lock = threading.Lock()


class FilesysCollector:
    def collect(self):
        size = GaugeMetricFamily(
            "node_filesystem_size_bytes",
            "Filesystem size in bytes.",
            labels=["device", "mountpoint", "fstype"],
        )
        free = GaugeMetricFamily(
            "node_filesystem_free_bytes",
            "Filesystem free space in bytes.",
            labels=["device", "mountpoint", "fstype"],
        )
        avail = GaugeMetricFamily(
            "node_filesystem_avail_bytes",
            "Filesystem space available to non-root.",
            labels=["device", "mountpoint", "fstype"],
        )
        files = GaugeMetricFamily(
            "node_filesystem_files",
            "Filesystem total file nodes.",
            labels=["device", "mountpoint", "fstype"],
        )
        files_free = GaugeMetricFamily(
            "node_filesystem_files_free",
            "Filesystem free file nodes.",
            labels=["device", "mountpoint", "fstype"],
        )
        readonly = GaugeMetricFamily(
            "node_filesystem_readonly",
            "Filesystem read-only status.",
            labels=["device", "mountpoint", "fstype"],
        )
        device_error = GaugeMetricFamily(
            "node_filesystem_device_error",
            "Filesystem device error.",
            labels=["device", "mountpoint", "fstype"],
        )

        mounts = parse_mountinfo()
        now = time.time()

        with ThreadPoolExecutor(max_workers=STAT_WORKERS) as executor:
            futures = {}

            for m in mounts:
                key = m["mountpoint"]

                with stuck_lock:
                    if key in stuck_mounts and now - stuck_mounts[key] < STUCK_TTL:
                        device_error.add_metric(
                            [m["device"], m["mountpoint"], m["fstype"]], 1
                        )
                        continue

                futures[
                    executor.submit(statfs_call, m["mountpoint"])
                ] = m

            for future, m in futures.items():
                labels = [m["device"], m["mountpoint"], m["fstype"]]

                try:
                    stats = future.result(timeout=STAT_TIMEOUT)

                    size.add_metric(labels, stats["size"])
                    free.add_metric(labels, stats["free"])
                    avail.add_metric(labels, stats["avail"])
                    files.add_metric(labels, stats["files"])
                    files_free.add_metric(labels, stats["files_free"])
                    readonly.add_metric(labels, 1 if is_readonly(m["options"]) else 0)
                    device_error.add_metric(labels, 0)

                except TimeoutError:
                    with stuck_lock:
                        stuck_mounts[m["mountpoint"]] = time.time()

                    device_error.add_metric(labels, 1)

                except Exception:
                    device_error.add_metric(labels, 1)

        yield size
        yield free
        yield avail
        yield files
        yield files_free
        yield readonly
        yield device_error

def parse_mountinfo():
    mounts = []

    with open("/proc/self/mountinfo", "r") as f:
        for line in f:
            parts = line.strip().split(" ")
            sep = parts.index("-")

            mount_point = parts[4].replace("\\040", " ")
            fs_type = parts[sep + 1]
            source = parts[sep + 2]
            options = parts[5]

            mounts.append({
                "device": source,
                "mountpoint": mount_point,
                "fstype": fs_type,
                "options": options,
            })

    return mounts


def is_readonly(options: str) -> bool:
    return "ro" in options.split(",")


def statfs_call(path):
    st = os.statvfs(path)
    return {
        "size": st.f_blocks * st.f_frsize,
        "free": st.f_bfree * st.f_frsize,
        "avail": st.f_bavail * st.f_frsize,
        "files": st.f_files,
        "files_free": st.f_ffree,
    }