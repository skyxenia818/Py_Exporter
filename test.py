from prometheus_client import Counter, Gauge, Summary, Histogram, start_http_server
import psutil
import time
from memory.py_meminfo_collector import get_memory_usage_percent
from memory.mem_usage_percent import mem_usage
# 定义和注册指标
#memory_usage = Gauge('memory_usage', '内存使用量')
cpu_percent = Gauge('cpu_percent', 'CPU 使用率百分比')
cpu_freq_current = Gauge('cpu_freq_current', 'CPU 当前频率')
cpu_freq_min = Gauge('cpu_freq_min', 'CPU 最小频率')
cpu_freq_max = Gauge('cpu_freq_max', 'CPU 最大频率')
net_rx_bytes = Gauge('net_rx_bytes', '网络接收字节数')
net_tx_bytes = Gauge('net_tx_bytes', '网络发送字节数')

# 获取 CPU 频率信息
cpu_freq = psutil.cpu_freq()


# 设置初始值
cpu_freq_current.set(cpu_freq.current)
cpu_freq_min.set(cpu_freq.min)
cpu_freq_max.set(cpu_freq.max)

# 启动 HTTP 服务器，暴露 metrics 接口
start_http_server(8001)

while True:
    # 收集内存使用量指标
    memory_usage.set(get_memory_usage_percent())

    # 收集 CPU 使用率指标
    cpu_percent.set(psutil.cpu_percent())

    # 收集 CPU 频率指标
    cpu_freq = psutil.cpu_freq()
    cpu_freq_current.set(cpu_freq.current)




    # 等待 1 秒钟，再次进行收集
    time.sleep(1)