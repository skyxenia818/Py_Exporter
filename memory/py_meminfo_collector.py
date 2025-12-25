#!/usr/bin/env python3
"""
Python implementation of meminfo collector similar to Node Exporter
This script reads memory information from /proc/meminfo and exposes it as Prometheus metrics
"""

import argparse
import re
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

# Constants
METRIC_NAMESPACE = "node"
METRIC_SUBSYSTEM = "memory"
DEFAULT_PORT = 9100
PROC_MEMINFO_PATH = "/proc/meminfo"


def read_meminfo():
    """
    Read and parse /proc/meminfo file
    Returns a dictionary of memory metrics
    """
    meminfo = {}
    with open(PROC_MEMINFO_PATH, 'r') as f:
        for line in f:
            # Parse lines like "MemTotal:        8167848 kB"
            match = re.match(r'([^:]+):\s*(\d+)\s*(\S+)?', line)
            if match:
                key, value, unit = match.groups()
                # Convert to bytes if unit is kB
                if unit == 'kB':
                    value = int(value) * 1024
                else:
                    value = int(value)
                
                # Convert key to Prometheus format (snake_case with bytes suffix)
                prom_key = key.replace('(', '').replace(')', '')
                if unit == 'kB' or key in ['HugePages_Total', 'HugePages_Free', 'HugePages_Rsvd', 'HugePages_Surp']:
                    # For kB values, add _bytes suffix
                    if not prom_key.endswith('_bytes') and not prom_key.startswith('HugePages_'):
                        prom_key += '_bytes'
                
                meminfo[prom_key] = value
    return meminfo


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


def generate_prometheus_metrics(meminfo):
    """
    Generate Prometheus text format metrics from meminfo dictionary
    """
    metrics = []
    metrics.append(f"# HELP {METRIC_NAMESPACE}_{METRIC_SUBSYSTEM}_info Memory information from /proc/meminfo")
    metrics.append(f"# TYPE {METRIC_NAMESPACE}_{METRIC_SUBSYSTEM}_info gauge")
    
    for key, value in meminfo.items():
        # Determine metric type
        if key.endswith('_Total') or key.endswith('_total'):
            metric_type = 'counter'
        else:
            metric_type = 'gauge'
        
        # Create metric lines
        metric_name = f"{METRIC_NAMESPACE}_{METRIC_SUBSYSTEM}_{key}"
        metrics.append(f"# HELP {metric_name} Memory information field {key}")
        metrics.append(f"# TYPE {metric_name} {metric_type}")
        metrics.append(f"{metric_name} {value}")
    
    # Add exporter info metric
    metrics.append(f"# HELP {METRIC_NAMESPACE}_exporter_info Information about the exporter")
    metrics.append(f"# TYPE {METRIC_NAMESPACE}_exporter_info gauge")
    metrics.append(f"{METRIC_NAMESPACE}_exporter_info{{version=\"1.0\"}} 1")
    
    return '\n'.join(metrics) + '\n'


class MeminfoHTTPHandler(BaseHTTPRequestHandler):
    """
    HTTP handler to serve Prometheus metrics
    """
    
    def do_GET(self):
        parsed_path = urlparse(self.path)
        if parsed_path.path == '/metrics':
            # Read meminfo
            try:
                meminfo = read_meminfo()
                metrics = generate_prometheus_metrics(meminfo)
                
                # Send response
                self.send_response(200)
                self.send_header('Content-Type', 'text/plain; version=0.0.4')
                self.end_headers()
                self.wfile.write(metrics.encode('utf-8'))
                
                # Log request
                self.log_message(f"GET {self.path} 200")
                
            except Exception as e:
                self.send_error(500, f"Error reading meminfo: {str(e)}")
                self.log_error(f"GET {self.path} 500 - {str(e)}")
                
        elif parsed_path.path == '/':
            # Landing page
            response = f"""
            <html>
            <head><title>Python Meminfo Exporter</title></head>
            <body>
                <h1>Python Meminfo Exporter</h1>
                <p>Visit <a href="/metrics">/metrics</a> to see Prometheus metrics</p>
                <p>This exporter provides memory information similar to Node Exporter's meminfo collector</p>
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
    httpd = HTTPServer(server_address, MeminfoHTTPHandler)
    print(f"Starting Python Meminfo Exporter on port {port}...")
    print(f"Metrics available at http://localhost:{port}/metrics")
    print("Press Ctrl+C to stop")
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        httpd.server_close()
        print("Server stopped")


if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Memory information collector')
    parser.add_argument('--port', 
                        type=int, 
                        default=DEFAULT_PORT,
                        help='Port to listen on for HTTP requests')
    
    args = parser.parse_args()
    
    try:
        run_server(args.port)
    except OSError as e:
        if e.errno == 98:  # Address already in use
            print(f"Error: Port {args.port} is already in use. Please try a different port with --port option.")
            print(f"Example: python py-meminfo-collector.py --port {args.port + 1}")
        else:
            print(f"Error: {str(e)}")
        exit(1)