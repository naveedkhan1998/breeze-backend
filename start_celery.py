import os
import resource
import subprocess

def set_memory_limit(max_mem_mb):
    # Set the maximum memory limit in bytes
    max_mem_bytes = max_mem_mb * 1024 * 1024
    resource.setrlimit(resource.RLIMIT_AS, (max_mem_bytes, max_mem_bytes))

if __name__ == "__main__":
    max_memory_mb = 300  # Set the memory limit to 300 MB
    set_memory_limit(max_memory_mb)

    # Start the Celery worker with solo pool
    celery_command = [
        "celery",
        "-A", "main",
        "worker",
        "--loglevel=INFO",
        "--time-limit=0",
        "--pool=solo"
    ]
    subprocess.run(celery_command)
