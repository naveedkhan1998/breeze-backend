import os
import resource
import subprocess
import threading
from http.server import SimpleHTTPRequestHandler, HTTPServer

def set_memory_limit(max_mem_mb):
    # Set the maximum memory limit in bytes
    max_mem_bytes = max_mem_mb * 1024 * 1024
    resource.setrlimit(resource.RLIMIT_AS, (max_mem_bytes, max_mem_bytes))

def run_http_server(port=5000):
    class MyHandler(SimpleHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Celery worker is running")

    server_address = ('', port)
    httpd = HTTPServer(server_address, MyHandler)
    print(f"Starting httpd server on port {port}")
    httpd.serve_forever()

if __name__ == "__main__":
    max_memory_mb = 300  # Set the memory limit to 300 MB
    set_memory_limit(max_memory_mb)

    # Start the HTTP server in a separate thread
    http_server_thread = threading.Thread(target=run_http_server)
    http_server_thread.daemon = True
    http_server_thread.start()

    # Start the Celery worker
    celery_command = [
        "celery",
        "-A", "main",
        "worker",
        "--loglevel=INFO",
        "--time-limit=0"
    ]
    subprocess.run(celery_command)
