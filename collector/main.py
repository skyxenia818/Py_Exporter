from prometheus_client import REGISTRY
from collector.cpu.cpu_collector import CpuCollector

register = REGISTRY
register.register(CpuCollector())

   
