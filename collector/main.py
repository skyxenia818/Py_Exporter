from prometheus_client import REGISTRY
from collector.cpu.cpu_collector_linux import CpuCollector
from collector.disk.diskio_collector_linux import DiskIOCollector

register = REGISTRY
register.register(CpuCollector())
register.register(DiskIOCollector())


