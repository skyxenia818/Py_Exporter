from memory.mem_info import read_meminfo
from prometheus_client import Counter, Gauge, Summary, Histogram, start_http_server
import psutil
import time

memory_usage = Gauge('memory_usage', '内存使用量')
memory_usage.set(get_memory_usage_percent())

def get_memory_usage_percent():
    """
    Calculate memory usage percentage directly from /proc/meminfo
    Similar to psutil.virtual_memory().percent
    Returns memory usage percentage as a float
    """
    meminfo = read_meminfo()
    
    # Extract required values
    mem_total = meminfo.get('MemTotal_bytes', 0)
    mem_free = meminfo.get('MemFree_bytes', 0)
    buffers = meminfo.get('Buffers_bytes', 0)
    cached = meminfo.get('Cached_bytes', 0)
    sreclaimable = meminfo.get('SReclaimable_bytes', 0)
    
    # Calculate used memory (similar to psutil's calculation)
    # used = total - free - buffers - cached - sreclaimable
    used = mem_total - mem_free - buffers - cached - sreclaimable
    
    # Calculate percentage
    if mem_total > 0:
        percent = (used / mem_total) * 100
    else:
        percent = 0.0
    
    return round(percent, 2)