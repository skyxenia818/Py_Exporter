from prometheus_client.core import CounterMetricFamily
import threading

CPU_MODES = [
    "user",
    "nice",
    "system",
    "idle",
    "iowait",
    "irq",
    "softirq",
    "steal",
    "guest",
    "guest_nice",
]

class CpuCollector():
    def __init__(self):
        self._lock = threading.Lock()
        self._last_stats = {}  # { (cpu, mode): value }

    def collect(self):
        metric = CounterMetricFamily(
            "node_cpu_seconds_total",
            "Seconds the CPUs spent in each mode.",
            labels=["cpu", "mode"],
        )

        current = {}

        with open("/proc/stat", "r") as f:
            for line in f:
                if not line.startswith("cpu") or line.startswith("cpu "):
                    continue

                parts = line.split()
                cpu = parts[0][3:]
                values = parts[1:]

                for mode, value in zip(CPU_MODES, values):
                    current[(cpu, mode)] = float(value)

        with self._lock:
            for key, value in current.items():
                last = self._last_stats.get(key)

                # 防 counter 回退
                if last is None or value >= last:
                    metric.add_metric([key[0], key[1]], value)
                    self._last_stats[key] = value
                else:
                    # 回退：继续暴露旧值
                    metric.add_metric([key[0], key[1]], last)

        yield metric