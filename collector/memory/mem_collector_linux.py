from prometheus_client.core import GaugeMetricFamily
import threading


class MemCollector:
    def __init__(self):
        self._lock = threading.Lock()
        self._last_stats = {}  # { metric_name: value }

    def collect(self):
        memtotal = GaugeMetricFamily(
            "node_memory_MemTotal_bytes",
            "Total memory in bytes.",
        )

        memfree = GaugeMetricFamily(
            "node_memory_MemFree_bytes",
            "Free memory in bytes.",
        )

        memavailable = GaugeMetricFamily(
            "node_memory_MemAvailable_bytes",
            "Available memory in bytes.",
        )

        buffers = GaugeMetricFamily(
            "node_memory_Buffers_bytes",
            "Memory used by buffers in bytes.",
        )

        cached = GaugeMetricFamily(
            "node_memory_Cached_bytes",
            "Memory used by cached files in bytes.",
        )

        swapcached = GaugeMetricFamily(
            "node_memory_SwapCached_bytes",
            "Memory used by cached swap in bytes.",
        )

        swaptotal = GaugeMetricFamily(
            "node_memory_SwapTotal_bytes",
            "Total swap memory in bytes.",
        )

        swapfree = GaugeMetricFamily(
            "node_memory_SwapFree_bytes",
            "Free swap memory in bytes.",
        )

        MEM_METRICS = [
            ("MemTotal", memtotal),
            ("MemFree", memfree),
            ("MemAvailable", memavailable),
            ("Buffers", buffers),
            ("Cached", cached),
            ("SwapCached", swapcached),
            ("SwapTotal", swaptotal),
            ("SwapFree", swapfree),
        ]

        current = {}

        with open("/proc/meminfo", "r") as f:
            for line in f:
                parts = line.split()
                if len(parts) < 2:
                    continue

                memtype = parts[0][:-1]
                value = parts[1]

                for metric_name, metric in MEM_METRICS:
                    if metric_name == memtype:
                        current[memtype] = float(value)

        with self._lock:
            for metric_name, metric in MEM_METRICS:
                value = current[metric_name]
                metric.add_metric(metric_name, value)
                self._last_stats[metric_name] = value

        yield memtotal
        yield memfree
        yield memavailable
        yield buffers
        yield cached
        yield swapcached
        yield swaptotal
        yield swapfree
