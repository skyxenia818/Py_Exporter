from prometheus_client.core import GaugeMetricFamily
import threading

# 定义需要收集的内存指标
MEM_METRICS = [
    "MemTotal",
    "MemFree",
    "MemAvailable",
    "Buffers",
    "Cached",
    "SwapCached",
    "Active",
    "Inactive",
    "Active(anon)",
    "Inactive(anon)",
    "Active(file)",
    "Inactive(file)",
    "Unevictable",
    "Mlocked",
    "SwapTotal",
    "SwapFree",
    "Dirty",
    "Writeback",
    "AnonPages",
    "Mapped",
    "Shmem",
    "Slab",
    "SReclaimable",
    "SUnreclaim",
    "KernelStack",
    "PageTables",
    "NFS_Unstable",
    "Bounce",
    "WritebackTmp",
    "CommitLimit",
    "Committed_AS",
    "VmallocTotal",
    "VmallocUsed",
    "VmallocChunk",
    "Percpu",
    "HardwareCorrupted",
    "AnonHugePages",
    "ShmemHugePages",
    "ShmemPmdMapped",
    "CmaTotal",
    "CmaFree",
    "HugePages_Total",
    "HugePages_Free",
    "HugePages_Rsvd",
    "HugePages_Surp",
    "Hugepagesize",
    "Hugetlb",
    "DirectMap4k",
    "DirectMap2M",
    "DirectMap1G"
]

class MemCollector():
    def __init__(self):
        self._lock = threading.Lock()
        self._last_stats = {}  # { metric_name: value }

    def collect(self):
        metric = GaugeMetricFamily(
            "node_memory_bytes",
            "Memory information from /proc/meminfo.",
            labels=["memtype"]
        )

        current = {}

        with open("/proc/meminfo", "r") as f:
            for line in f:
                parts = line.split()
                if len(parts) < 2:
                    continue
                    
                memtype = parts[0][:-1]  # 移除末尾的冒号
                value = parts[1]
                
                # 只收集定义在MEM_METRICS中的指标
                if memtype in MEM_METRICS:
                    current[memtype] = float(value)

        with self._lock:
            for memtype, value in current.items():
                # 对于内存指标，我们不检查回退，因为内存使用是动态变化的
                metric.add_metric([memtype], value)
                self._last_stats[memtype] = value

        yield metric