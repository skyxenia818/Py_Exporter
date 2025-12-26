from prometheus_client.core import CounterMetricFamily
from collector.base_collector import BaseCollector
import time

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

class CpuCollector(BaseCollector):
    def collect(self):
        """
        Called by Prometheus on each scrape
        """
        metric = CounterMetricFamily(
            "node_cpu_seconds_total",
            "Seconds the CPUs spent in each mode.",
            labels=["cpu", "mode"],
        )

        with open("/proc/stat", "r") as f:
            for line in f:
                if not line.startswith("cpu"):
                    continue
                if line.startswith("cpu "):
                    continue  # skip total cpu line

                parts = line.split()
                cpu = parts[0][3:]  # cpu0 -> 0
                values = parts[1:]

                for mode, value in zip(CPU_MODES, values):
                    metric.add_metric(
                        [cpu, mode],
                        float(value),
                    )

        yield metric
