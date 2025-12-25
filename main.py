#!/usr/bin/env python3
"""
Python implementation of Node Exporter similar functionality
This script combines memory and network device metrics collection
"""

import argparse
import logging
import sys
import os
import importlib.util
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
DEFAULT_PORT = 9100

# Helper function to import modules with hyphens in their names
def import_module_from_file(module_name, file_path):
    """
    Import a module from a file path
    """
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module

# Import the collectors
memory_collector_path = os.path.join(os.path.dirname(__file__), 'memory', 'py-meminfo-collector.py')
network_collector_path = os.path.join(os.path.dirname(__file__), 'network', 'py-netdev-collector.py')

memory_module = import_module_from_file('memory_collector', memory_collector_path)
network_module = import_module_from_file('network_collector', network_collector_path)

class CombinedHTTPHandler(BaseHTTPRequestHandler):
    """
    HTTP handler to serve combined Prometheus metrics from both memory and network collectors
    """
    
    def do_GET(self):
        parsed_path = urlparse(self.path)
        if parsed_path.path == '/metrics':
            # Generate combined metrics
            try:
                # Get memory metrics
                meminfo = memory_module.read_meminfo()
                memory_metrics = memory_module.generate_prometheus_metrics(meminfo)
                
                # Get network metrics
                network_metrics = network_module.generate_prometheus_metrics()
                
                # Combine metrics
                metrics = memory_metrics + network_metrics
                
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
            <head><title>Python Node Exporter</title></head>
            <body>
                <h1>Python Node Exporter</h1>
                <p>Visit <a href="/metrics">/metrics</a> to see Prometheus metrics</p>
                <p>This exporter provides combined memory and network device information similar to Node Exporter</p>
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
    Run the HTTP server to expose combined metrics
    """
    server_address = ('', port)
    httpd = HTTPServer(server_address, CombinedHTTPHandler)
    logger.info(f"Starting Python Node Exporter on port {port}...")
    logger.info(f"Metrics available at http://localhost:{port}/metrics")
    logger.info("Press Ctrl+C to stop")
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("\nShutting down server...")
        httpd.server_close()
        logger.info("Server stopped")


def main():
    """
    Main function that integrates both memory and network collectors
    """
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Node Exporter similar functionality')
    parser.add_argument('--port', 
                        type=int, 
                        default=DEFAULT_PORT,
                        help='Port to listen on for HTTP requests')
    
    args = parser.parse_args()
    
    try:
        run_server(args.port)
    except OSError as e:
        if e.errno == 98:  # Address already in use
            logger.error(f"Error: Port {args.port} is already in use. Please try a different port with --port option.")
            logger.error(f"Example: python main.py --port {args.port + 1}")
        else:
            logger.error(f"Error: {str(e)}")
        exit(1)


if __name__ == "__main__":
    main()

