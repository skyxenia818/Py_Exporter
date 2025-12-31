from prometheus_client.core import CounterMetricFamily, GaugeMetricFamily
import threading
import os
import glob

# /proc/net/dev 中的字段（counter 类型）
NETWORK_COUNTER_FIELDS = [
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
        self._last_carrier = {}  # { device: carrier_value } 用于跟踪 carrier 变化

    def read_file_safe(self, path, default="0"):
        try:
            with open(path, "r") as f:
                return f.read().strip()
        except (IOError, OSError):
            return default

    def read_int_file(self, path, default=0):
        try:
            value = self.read_file_safe(path, str(default))
            return int(value)
        except (ValueError, TypeError):
            return default

    def collect(self):
        current = {}
        devices = set()
        # 存储设备信息用于 node_network_info
        device_info = {}  # { device: {address, broadcast, duplex, operstate, type} }

        # 读取 /proc/net/dev 获取 counter 指标
        with open("/proc/net/dev", "r") as f:
            for line in f:
                if ":" not in line:
                    continue

                parts = line.split(":")
                if len(parts) != 2:
                    continue

                device = parts[0].strip()
                values = parts[1].split()

                if len(values) < len(NETWORK_COUNTER_FIELDS):
                    continue

                devices.add(device)
                for field, value in zip(NETWORK_COUNTER_FIELDS, values):
                    current[(device, field)] = float(value)
                
                # 为设备设置默认信息（如果后续没有从 /sys 读取到）
                if device not in device_info:
                    device_info[device] = {
                        "address": "",
                        "broadcast": "",
                        "duplex": "unknown",
                        "operstate": "unknown",
                        "type": "0",
                    }

        # 读取 /sys/class/net/ 获取 gauge 指标
        sys_net_path = "/sys/class/net"
        if os.path.exists(sys_net_path):
            for device_dir in glob.glob(os.path.join(sys_net_path, "*")):
                device = os.path.basename(device_dir)
                devices.add(device)

                # 读取各种 gauge 指标
                operstate = self.read_file_safe(os.path.join(device_dir, "operstate"), "unknown")
                current[(device, "up")] = 1.0 if operstate == "up" else 0.0
                current[(device, "flags")] = float(self.read_int_file(os.path.join(device_dir, "flags"), 0))
                current[(device, "dormant")] = float(self.read_int_file(os.path.join(device_dir, "dormant"), 0))
                current[(device, "iface_id")] = float(self.read_int_file(os.path.join(device_dir, "ifindex"), 0))
                current[(device, "device_id")] = float(self.read_int_file(os.path.join(device_dir, "dev_id"), 0))
                current[(device, "mtu_bytes")] = float(self.read_int_file(os.path.join(device_dir, "mtu"), 0))
                
                # iface_link (指向的接口)
                link_target = os.path.basename(os.path.realpath(os.path.join(device_dir, "link"))) if os.path.exists(os.path.join(device_dir, "link")) else ""
                current[(device, "iface_link")] = 1.0 if link_target else 0.0
                
                # speed_bytes (需要转换，单位是 Mbps，转换为 bytes)
                speed_mbps = self.read_int_file(os.path.join(device_dir, "speed"), 0)
                current[(device, "speed_bytes")] = float(speed_mbps * 125000) if speed_mbps > 0 else 0.0
                
                current[(device, "net_dev_group")] = float(self.read_int_file(os.path.join(device_dir, "netdev_group"), 0))
                protocol_type = self.read_int_file(os.path.join(device_dir, "type"), 0)
                current[(device, "protocol_type")] = float(protocol_type)
                current[(device, "iface_link_mode")] = float(self.read_int_file(os.path.join(device_dir, "link_mode"), 0))
                current[(device, "name_assign_type")] = float(self.read_int_file(os.path.join(device_dir, "name_assign_type"), 0))
                current[(device, "address_assign_type")] = float(self.read_int_file(os.path.join(device_dir, "addr_assign_type"), 0))
                
                # transmit_queue_length
                tx_queue_len = self.read_int_file(os.path.join(device_dir, "tx_queue_len"), 0)
                current[(device, "transmit_queue_length")] = float(tx_queue_len)
                
                # carrier 相关
                carrier = self.read_int_file(os.path.join(device_dir, "carrier"), 0)
                current[(device, "carrier")] = float(carrier)

                # 收集设备信息用于 node_network_info
                # 从 /sys/class/net/<device>/address 读取 MAC 地址
                address = self.read_file_safe(os.path.join(device_dir, "address"), "")
                # broadcast 地址（通常从 ifconfig 或 ip 命令获取，这里简化处理）
                broadcast = ""
                # duplex 模式
                duplex = self.read_file_safe(os.path.join(device_dir, "duplex"), "unknown")
                
                device_info[device] = {
                    "address": address,
                    "broadcast": broadcast,
                    "duplex": duplex,
                    "operstate": operstate,
                    "type": str(protocol_type),
                }

        # 创建 counter 指标
        counter_metrics = {}
        for field in NETWORK_COUNTER_FIELDS:
            metric_name = f"node_network_{field}_total"
            counter_metrics[field] = CounterMetricFamily(
                metric_name,
                f"Network device statistic {field}.",
                labels=["device"],
            )

        # 创建 gauge 指标
        gauge_metrics = {
            "up": GaugeMetricFamily("node_network_up", "Value is 1 if operstate is 'up', 0 otherwise.", labels=["device"]),
            "flags": GaugeMetricFamily("node_network_flags", "Flags attribute of network device.", labels=["device"]),
            "carrier": GaugeMetricFamily("node_network_carrier", "Value is 1 if carrier is detected, 0 otherwise.", labels=["device"]),
            "dormant": GaugeMetricFamily("node_network_dormant", "Value is 1 if interface is dormant, 0 otherwise.", labels=["device"]),
            "iface_id": GaugeMetricFamily("node_network_iface_id", "Interface index.", labels=["device"]),
            "device_id": GaugeMetricFamily("node_network_device_id", "Device ID.", labels=["device"]),
            "mtu_bytes": GaugeMetricFamily("node_network_mtu_bytes", "MTU of network device.", labels=["device"]),
            "iface_link": GaugeMetricFamily("node_network_iface_link", "Value is 1 if interface has link, 0 otherwise.", labels=["device"]),
            "speed_bytes": GaugeMetricFamily("node_network_speed_bytes", "Speed of network device in bytes per second.", labels=["device"]),
            "net_dev_group": GaugeMetricFamily("node_network_net_dev_group", "Network device group.", labels=["device"]),
            "protocol_type": GaugeMetricFamily("node_network_protocol_type", "Protocol type of network device.", labels=["device"]),
            "iface_link_mode": GaugeMetricFamily("node_network_iface_link_mode", "Link mode of network device.", labels=["device"]),
            "name_assign_type": GaugeMetricFamily("node_network_name_assign_type", "Name assign type of network device.", labels=["device"]),
            "address_assign_type": GaugeMetricFamily("node_network_address_assign_type", "Address assign type of network device.", labels=["device"]),
            "transmit_queue_length": GaugeMetricFamily("node_network_transmit_queue_length", "Transmit queue length of network device.", labels=["device"]),
        }

        # node_network_info (info 类型指标，使用 GaugeMetricFamily 实现)
        network_info = GaugeMetricFamily(
            "node_network_info",
            "Non-numeric data from /sys/class/net/<iface>, value is always 1.",
            labels=["device", "address", "broadcast", "duplex", "operstate", "type"],
        )

        # carrier_changes 相关的 counter 指标
        carrier_changes_total = CounterMetricFamily(
            "node_network_carrier_changes_total",
            "Number of times the carrier state has changed.",
            labels=["device"],
        )
        carrier_up_changes_total = CounterMetricFamily(
            "node_network_carrier_up_changes_total",
            "Number of times the carrier state has changed to up.",
            labels=["device"],
        )
        carrier_down_changes_total = CounterMetricFamily(
            "node_network_carrier_down_changes_total",
            "Number of times the carrier state has changed to down.",
            labels=["device"],
        )

        # receive_nohandler_total (从 /proc/net/softnet_stat 读取，这里简化处理)
        receive_nohandler_total = CounterMetricFamily(
            "node_network_receive_nohandler_total",
            "Number of received packets dropped because no handler was found.",
            labels=["device"],
        )

        # process_network 指标（进程级别的网络统计，从 /proc/net/sockstat 读取）
        process_receive_bytes_total = CounterMetricFamily(
            "process_network_receive_bytes_total",
            "Total number of bytes received by processes.",
            labels=[],
        )
        process_transmit_bytes_total = CounterMetricFamily(
            "process_network_transmit_bytes_total",
            "Total number of bytes transmitted by processes.",
            labels=[],
        )

        with self._lock:
            # 处理 counter 指标
            for field in NETWORK_COUNTER_FIELDS:
                for device in devices:
                    key = (device, field)
                    value = current.get(key, 0.0)
                    last = self._last_stats.get(key)

                    if last is None or value >= last:
                        counter_metrics[field].add_metric([device], value)
                        self._last_stats[key] = value
                    else:
                        counter_metrics[field].add_metric([device], last)

            # 处理 gauge 指标
            for field, metric in gauge_metrics.items():
                for device in devices:
                    key = (device, field)
                    value = current.get(key, 0.0)
                    metric.add_metric([device], value)
                    self._last_stats[key] = value

            # 处理 carrier_changes
            for device in devices:
                key = (device, "carrier")
                current_carrier = current.get(key, 0.0)
                last_carrier = self._last_carrier.get(device)

                if last_carrier is not None and current_carrier != last_carrier:
                    # carrier 状态发生变化
                    changes = self._last_stats.get((device, "carrier_changes"), 0.0) + 1.0
                    self._last_stats[(device, "carrier_changes")] = changes
                    carrier_changes_total.add_metric([device], changes)

                    if current_carrier > last_carrier:
                        # carrier up
                        up_changes = self._last_stats.get((device, "carrier_up_changes"), 0.0) + 1.0
                        self._last_stats[(device, "carrier_up_changes")] = up_changes
                        carrier_up_changes_total.add_metric([device], up_changes)
                    else:
                        # carrier down
                        down_changes = self._last_stats.get((device, "carrier_down_changes"), 0.0) + 1.0
                        self._last_stats[(device, "carrier_down_changes")] = down_changes
                        carrier_down_changes_total.add_metric([device], down_changes)
                elif last_carrier is None:
                    # 首次记录
                    self._last_stats[(device, "carrier_changes")] = 0.0
                    self._last_stats[(device, "carrier_up_changes")] = 0.0
                    self._last_stats[(device, "carrier_down_changes")] = 0.0
                    carrier_changes_total.add_metric([device], 0.0)
                    carrier_up_changes_total.add_metric([device], 0.0)
                    carrier_down_changes_total.add_metric([device], 0.0)
                else:
                    # carrier 未变化，使用旧值
                    changes = self._last_stats.get((device, "carrier_changes"), 0.0)
                    up_changes = self._last_stats.get((device, "carrier_up_changes"), 0.0)
                    down_changes = self._last_stats.get((device, "carrier_down_changes"), 0.0)
                    carrier_changes_total.add_metric([device], changes)
                    carrier_up_changes_total.add_metric([device], up_changes)
                    carrier_down_changes_total.add_metric([device], down_changes)

                self._last_carrier[device] = current_carrier

            # receive_nohandler_total (简化处理，所有设备设为 0)
            for device in devices:
                receive_nohandler_total.add_metric([device], 0.0)

            # node_network_info
            for device in devices:
                info = device_info.get(device, {
                    "address": "",
                    "broadcast": "",
                    "duplex": "unknown",
                    "operstate": "unknown",
                    "type": "0",
                })
                network_info.add_metric(
                    [device, info["address"], info["broadcast"], info["duplex"], info["operstate"], info["type"]],
                    1.0
                )

        # 返回所有指标
        for metric in counter_metrics.values():
            yield metric
        for metric in gauge_metrics.values():
            yield metric
        yield network_info
        yield carrier_changes_total
        yield carrier_up_changes_total
        yield carrier_down_changes_total
        yield receive_nohandler_total
        yield process_receive_bytes_total
        yield process_transmit_bytes_total
