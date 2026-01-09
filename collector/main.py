from prometheus_client import REGISTRY
from collector.cpu.cpu_collector_linux import CpuCollector
from collector.disk.diskio_collector_linux import DiskIOCollector
from collector.filesys.filesys_collector_linux import FilesysCollector
from collector.memory.mem_collector_linux import MemCollector
from collector.network.network_collector_linux import NetworkCollector

register = REGISTRY
register.register(CpuCollector())
register.register(DiskIOCollector())
register.register(FilesysCollector())
register.register(MemCollector())
register.register(NetworkCollector())
