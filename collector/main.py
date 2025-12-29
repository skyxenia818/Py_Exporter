from prometheus_client import REGISTRY
from collector.cpu.cpu_collector_linux import CpuCollector
from collector.disk.diskio_collector_linux import DiskIOCollector
from collector.filesys.filesys_collector_linux import FilesysCollector
from collector.memory.mem_collector_linux import MemCollector

register = REGISTRY
# register.register(CpuCollector())
# register.register(DiskIOCollector())
# register.register(FilesysCollector())
register.register(MemCollector())
