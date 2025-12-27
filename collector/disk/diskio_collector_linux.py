from prometheus_client.core import CounterMetricFamily, GaugeMetricFamily

class DiskIOCollector:
    def collect(self):
        read_bytes = CounterMetricFamily(
            "node_disk_read_bytes_total",
            "The total number of bytes read successfully.",
            labels=["device"]
        )

        io_now = GaugeMetricFamily(
            "node_disk_io_now",
            "The number of I/Os currently in progress.",
            labels=["device"]
        )

        for s in self.read_diskstats():
            dev = s["device"]

            read_bytes.add_metric(
                [dev],
                s["sectors_read"] * 512.0
            )

            io_now.add_metric(
                [dev],
                s["io_in_progress"]
            )

        yield read_bytes
        yield io_now

    def read_diskstats(self):
        stats = []

        with open("/proc/diskstats", "r") as f:
            for line in f:
                parts = line.split()
                if len(parts) < 14:
                    continue

                stats.append({
                    "major": parts[0],
                    "minor": parts[1],
                    "device": parts[2],
                    "reads_completed": int(parts[3]),
                    "reads_merged": int(parts[4]),
                    "sectors_read": int(parts[5]),
                    "read_time_ms": int(parts[6]),
                    "writes_completed": int(parts[7]),
                    "writes_merged": int(parts[8]),
                    "sectors_written": int(parts[9]),
                    "write_time_ms": int(parts[10]),
                    "io_in_progress": int(parts[11]),
                    "io_time_ms": int(parts[12]),
                    "weighted_io_time_ms": int(parts[13]),
                })

        return stats

