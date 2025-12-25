#!/usr/bin/env python3
# Copyright 2015 The Prometheus Authors
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import argparse
import logging
import os
import re
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
from typing import Dict, Optional, Tuple

# Constants
METRIC_NAMESPACE = "node"
METRIC_SUBSYSTEM = "network"
DEFAULT_PORT = 9100
PROC_NET_DEV_PATH = "/proc/net/dev"

try:
    from pyroute2 import IPRoute
    HAS_PYROUTE2 = True
except ImportError:
    HAS_PYROUTE2 = False

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Command line arguments
parser = argparse.ArgumentParser(description='Network device stats collector')
parser.add_argument('--collector.netdev.netlink', 
                    action='store_true', 
                    default=True,
                    help='Use netlink to gather stats instead of /proc/net/dev.')
parser.add_argument('--collector.netdev.label-ifalias', 
                    action='store_true', 
                    default=False,
                    help='Add ifAlias label')
parser.add_argument('--collector.netdev.device-exclude', 
                    type=str, 
                    default='',
                    help='Regexp of net devices to exclude')
parser.add_argument('--collector.netdev.device-include', 
                    type=str, 
                    default='',
                    help='Regexp of net devices to include')
parser.add_argument('--port', 
                    type=int, 
                    default=DEFAULT_PORT,
                    help='Port to listen on for HTTP requests')

args = parser.parse_args()

# Create nested namespace structure to handle dot notation in argument names
nested_args = argparse.Namespace()
for attr_name in dir(args):
    if not attr_name.startswith('_'):  # Skip private attributes
        parts = attr_name.split('.')
        current = nested_args
        for part in parts[:-1]:
            if not hasattr(current, part):
                setattr(current, part, argparse.Namespace())
            current = getattr(current, part)
        setattr(current, parts[-1], getattr(args, attr_name))
args = nested_args


class DeviceFilter:
    """Device filter class to include/exclude network devices"""
    
    def __init__(self, exclude_regex: str, include_regex: str):
        self.exclude_regex = re.compile(exclude_regex) if exclude_regex else None
        self.include_regex = re.compile(include_regex) if include_regex else None
    
    def ignored(self, device_name: str) -> bool:
        """Check if a device should be ignored"""
        if self.include_regex:
            return not self.include_regex.match(device_name)
        if self.exclude_regex:
            return self.exclude_regex.match(device_name)
        return False


def get_net_dev_stats(filter: Optional[DeviceFilter] = None) -> Tuple[Dict[str, Dict[str, int]], Optional[Exception]]:
    """Get network device statistics"""
    if args.collector.netdev.netlink and HAS_PYROUTE2:
        return netlink_stats(filter)
    return proc_net_dev_stats(filter)


def netlink_stats(filter: Optional[DeviceFilter] = None) -> Tuple[Dict[str, Dict[str, int]], Optional[Exception]]:
    """Get network statistics using netlink"""
    metrics = {}
    
    try:
        with IPRoute() as ipr:
            links = ipr.get_links()
            
            for link in links:
                attrs = dict(link['attrs'])
                name = attrs.get('IFLA_IFNAME')
                
                if not name:
                    logger.debug("No interface name, skipping")
                    continue
                
                if filter and filter.ignored(name):
                    logger.debug(f"Ignoring device: {name}")
                    continue
                
                stats = link.get('stats64', link.get('stats', {}))
                if not stats:
                    logger.debug(f"No stats for device {name}, skipping")
                    continue
                
                # Map Linux kernel stats to our metric names
                metrics[name] = {
                    "receive_packets": stats.get('rx_packets', 0),
                    "transmit_packets": stats.get('tx_packets', 0),
                    "receive_bytes": stats.get('rx_bytes', 0),
                    "transmit_bytes": stats.get('tx_bytes', 0),
                    "receive_errors": stats.get('rx_errors', 0),
                    "transmit_errors": stats.get('tx_errors', 0),
                    "receive_dropped": stats.get('rx_dropped', 0),
                    "transmit_dropped": stats.get('tx_dropped', 0),
                    "multicast": stats.get('multicast', 0),
                    "collisions": stats.get('collisions', 0),
                    
                    # Detailed rx_errors
                    "receive_length_errors": stats.get('rx_length_errors', 0),
                    "receive_over_errors": stats.get('rx_over_errors', 0),
                    "receive_crc_errors": stats.get('rx_crc_errors', 0),
                    "receive_frame_errors": stats.get('rx_frame_errors', 0),
                    "receive_fifo_errors": stats.get('rx_fifo_errors', 0),
                    "receive_missed_errors": stats.get('rx_missed_errors', 0),
                    
                    # Detailed tx_errors
                    "transmit_aborted_errors": stats.get('tx_aborted_errors', 0),
                    "transmit_carrier_errors": stats.get('tx_carrier_errors', 0),
                    "transmit_fifo_errors": stats.get('tx_fifo_errors', 0),
                    "transmit_heartbeat_errors": stats.get('tx_heartbeat_errors', 0),
                    "transmit_window_errors": stats.get('tx_window_errors', 0),
                    
                    # For cslip etc
                    "receive_compressed": stats.get('rx_compressed', 0),
                    "transmit_compressed": stats.get('tx_compressed', 0),
                    "receive_nohandler": stats.get('rx_nohandler', 0),
                }
        
        return metrics, None
        
    except Exception as e:
        logger.error(f"Error getting netlink stats: {e}")
        return {}, e


def proc_net_dev_stats(filter: Optional[DeviceFilter] = None) -> Tuple[Dict[str, Dict[str, int]], Optional[Exception]]:
    """Get network statistics from /proc/net/dev"""
    metrics = {}
    
    try:
        with open('/proc/net/dev', 'r') as f:
            lines = f.readlines()
        
        # Skip header lines
        for line in lines[2:]:
            parts = line.strip().split(':')
            if len(parts) != 2:
                continue
            
            name = parts[0].strip()
            stats = list(map(int, parts[1].strip().split()))
            
            if filter and filter.ignored(name):
                logger.debug(f"Ignoring device: {name}")
                continue
            
            # Map /proc/net/dev stats to our metric names
            # See: https://www.kernel.org/doc/Documentation/filesystems/proc.txt
            metrics[name] = {
                "receive_bytes": stats[0],
                "receive_packets": stats[1],
                "receive_errors": stats[2],
                "receive_dropped": stats[3],
                "receive_fifo": stats[4],
                "receive_frame": stats[5],
                "receive_compressed": stats[6],
                "receive_multicast": stats[7],
                "transmit_bytes": stats[8],
                "transmit_packets": stats[9],
                "transmit_errors": stats[10],
                "transmit_dropped": stats[11],
                "transmit_fifo": stats[12],
                "transmit_colls": stats[13],
                "transmit_carrier": stats[14],
                "transmit_compressed": stats[15],
            }
        
        return metrics, None
        
    except Exception as e:
        logger.error(f"Error parsing /proc/net/dev: {e}")
        return {}, e


def get_net_dev_labels() -> Tuple[Optional[Dict[str, Dict[str, str]]], Optional[Exception]]:
    """Get network device labels"""
    if not args.collector.netdev.label_ifalias:
        return None, None
    
    labels = {}
    
    try:
        net_class_path = '/sys/class/net'
        if not os.path.exists(net_class_path):
            return labels, None
        
        for iface in os.listdir(net_class_path):
            ifalias_path = os.path.join(net_class_path, iface, 'ifalias')
            if os.path.exists(ifalias_path):
                with open(ifalias_path, 'r') as f:
                    ifalias = f.read().strip()
                if ifalias:
                    labels[iface] = {'ifalias': ifalias}
        
        return labels, None
        
    except Exception as e:
        logger.error(f"Error getting netdev labels: {e}")
        return None, e


def generate_prometheus_metrics():
    """
    Generate Prometheus text format metrics from network device stats
    """
    metrics = []
    metrics.append(f"# HELP {METRIC_NAMESPACE}_{METRIC_SUBSYSTEM}_info Network device information")
    metrics.append(f"# TYPE {METRIC_NAMESPACE}_{METRIC_SUBSYSTEM}_info gauge")
    
    # Create device filter
    filter = DeviceFilter(
        args.collector.netdev.device_exclude,
        args.collector.netdev.device_include
    )
    
    # Get network stats
    stats, err = get_net_dev_stats(filter)
    if err:
        logger.error(f"Failed to get network stats: {err}")
        return ""
    
    # Get netdev labels
    labels, err = get_net_dev_labels()
    if err:
        logger.error(f"Failed to get netdev labels: {err}")
    
    # Define metric types mapping (most network stats are counters)
    metric_types = {
        # Traffic metrics (counters)
        "receive_bytes": "counter",
        "transmit_bytes": "counter",
        "receive_packets": "counter",
        "transmit_packets": "counter",
        "receive_multicast": "counter",
        "multicast": "counter",
        "receive_compressed": "counter",
        "transmit_compressed": "counter",
        "receive_nohandler": "counter",
        
        # Error metrics (counters)
        "receive_errors": "counter",
        "transmit_errors": "counter",
        "receive_dropped": "counter",
        "transmit_dropped": "counter",
        "collisions": "counter",
        "transmit_colls": "counter",
        "receive_length_errors": "counter",
        "receive_over_errors": "counter",
        "receive_crc_errors": "counter",
        "receive_frame_errors": "counter",
        "receive_fifo_errors": "counter",
        "receive_missed_errors": "counter",
        "transmit_aborted_errors": "counter",
        "transmit_carrier_errors": "counter",
        "transmit_fifo_errors": "counter",
        "transmit_heartbeat_errors": "counter",
        "transmit_window_errors": "counter",
        "receive_fifo": "counter",
        "receive_frame": "counter",
        "transmit_fifo": "counter",
        "transmit_carrier": "counter",
    }
    
    # Track which metrics we've already defined type for
    defined_metrics = set()
    
    for dev, dev_stats in stats.items():
        # Create label string
        label_dict = {'device': dev}
        
        # Add ifalias label if available
        if labels and dev in labels and 'ifalias' in labels[dev]:
            label_dict['ifalias'] = labels[dev]['ifalias']
        
        # Format labels for Prometheus
        if label_dict:
            label_str = '{' + ','.join([f'{k}="{v}"' for k, v in label_dict.items()]) + '}'
        else:
            label_str = ''
        
        for stat, value in dev_stats.items():
            metric_name = f"{METRIC_NAMESPACE}_{METRIC_SUBSYSTEM}_{stat}"
            
            # Add metric type if not already defined
            if metric_name not in defined_metrics:
                metric_type = metric_types.get(stat, "gauge")
                metrics.append(f"# HELP {metric_name} Network device {stat.replace('_', ' ')}")
                metrics.append(f"# TYPE {metric_name} {metric_type}")
                defined_metrics.add(metric_name)
            
            # Add metric line
            metrics.append(f"{metric_name}{label_str} {value}")
    
    # Add exporter info metric
    metrics.append(f"# HELP {METRIC_NAMESPACE}_exporter_info Information about the exporter")
    metrics.append(f"# TYPE {METRIC_NAMESPACE}_exporter_info gauge")
    metrics.append(f"{METRIC_NAMESPACE}_exporter_info{{version=\"1.0\"}} 1")
    
    return '\n'.join(metrics) + '\n'


class NetDevHTTPHandler(BaseHTTPRequestHandler):
    """
    HTTP handler to serve Prometheus metrics
    """
    
    def do_GET(self):
        parsed_path = urlparse(self.path)
        if parsed_path.path == '/metrics':
            # Generate metrics
            try:
                metrics = generate_prometheus_metrics()
                
                # Send response
                self.send_response(200)
                self.send_header('Content-Type', 'text/plain; version=0.0.4')
                self.end_headers()
                self.wfile.write(metrics.encode('utf-8'))
                
                # Log request
                self.log_message(f"GET {self.path} 200")
                
            except Exception as e:
                self.send_error(500, f"Error generating metrics: {str(e)}")
                self.log_error(f"GET {self.path} 500 - {str(e)}")
                
        elif parsed_path.path == '/':
            # Landing page
            response = f"""
            <html>
            <head><title>Python NetDev Exporter</title></head>
            <body>
                <h1>Python NetDev Exporter</h1>
                <p>Visit <a href="/metrics">/metrics</a> to see Prometheus metrics</p>
                <p>This exporter provides network device information similar to Node Exporter's netdev collector</p>
            </body>
            </html>
            """
            
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            self.wfile.write(response.encode('utf-8'))
            self.log_message(f"GET {self.path} 200")
            
        else:
            self.send_error(404, "Not Found")
            self.log_message(f"GET {self.path} 404")


def run_server(port=DEFAULT_PORT):
    """
    Run the HTTP server to expose metrics
    """
    server_address = ('', port)
    httpd = HTTPServer(server_address, NetDevHTTPHandler)
    logger.info(f"Starting Python NetDev Exporter on port {port}...")
    logger.info(f"Metrics available at http://localhost:{port}/metrics")
    logger.info("Press Ctrl+C to stop")
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("\nShutting down server...")
        httpd.server_close()
        logger.info("Server stopped")


if __name__ == '__main__':
    """Main function"""
    run_server(args.port)