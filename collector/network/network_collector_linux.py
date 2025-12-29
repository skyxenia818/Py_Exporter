from prometheus_client.core import CounterMetricFamily
import threading

NETWORK_FIELDS = [
    "receive_bytes",
    "receive_packets",
    "receive_errs",
    "receive_drop",
    "receive_fifo",
    "receive_frame",
    "receive_compressed",
    "receive_multicast",
    "transmit_bytes",
    "transmit_packets",
    "transmit_errs",
    "transmit_drop",
    "transmit_fifo",
    "transmit_colls",
    "transmit_carrier",
    "transmit_compressed",
]

class NetworkCollector():
    def __init__(self):
        self._lock = threading.Lock()
        self._last_stats = {}  # { (device, field): value }

    def collect(self):
        current = {}

        with open("/proc/net/dev", "r") as f:
            for line in f:
                # 跳过表头行
                if ":" not in line:
                    continue

                # 解析接口名和统计值
                parts = line.split(":")
                if len(parts) != 2:
                    continue

                device = parts[0].strip()
                values = parts[1].split()

                # 确保有足够的字段
                if len(values) < len(NETWORK_FIELDS):
                    continue

                for field, value in zip(NETWORK_FIELDS, values):
                    current[(device, field)] = float(value)

        # 为每个字段创建指标
        metrics = {}
        for field in NETWORK_FIELDS:
            metric_name = f"node_network_{field}_total"
            metrics[field] = CounterMetricFamily(
                metric_name,
                f"Network device statistic {field}.",
                labels=["device"],
            )

        with self._lock:
            for key, value in current.items():
                device, field = key
                last = self._last_stats.get(key)

                # 防 counter 回退
                if last is None or value >= last:
                    metrics[field].add_metric([device], value)
                    self._last_stats[key] = value
                else:
                    # 回退：继续暴露旧值
                    metrics[field].add_metric([device], last)

        for metric in metrics.values():
            yield metric

