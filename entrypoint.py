import os
import subprocess
import sys
import time
import socket

def wait_for_db(host, port):
    print(f"Waiting for database at {host}:{port}...")
    while True:
        try:
            with socket.create_connection((host, port), timeout=1):
                print("Database started")
                break
        except (socket.error, socket.timeout):
            time.sleep(0.1)

def run_command(command):
    print(f"Running command: {' '.join(command)}")
    result = subprocess.run(command)
    if result.returncode != 0:
        print(f"Command failed with return code {result.returncode}")
        sys.exit(result.returncode)

if __name__ == "__main__":
    database_url = os.environ.get("DATABASE_URL", "")
    if database_url:
        # Simple parsing for 'postgres://user:pass@host:port/db'
        try:
            host_port = database_url.split("@")[1].split("/")[0]
            if ":" in host_port:
                host, port = host_port.split(":")
                port = int(port)
            else:
                host = host_port
                port = 5432
            wait_for_db(host, port)
        except Exception as e:
            print(f"Could not parse DATABASE_URL for waiting: {e}")

    # Run migrations
    run_command(["python", "manage.py", "migrate"])

    # Collect static (only if DEBUG is False/not set)
    if os.environ.get("DEBUG", "False").lower() not in ("true", "1"):
        run_command(["python", "manage.py", "collectstatic", "--no-input"])
    else:
        print("DEBUG is True. Skipping collectstatic...")

    # Execute the CMD passed as arguments
    if len(sys.argv) > 1:
        os.execvp(sys.argv[1], sys.argv[1:])
    else:
        # Default fallback
        os.execvp("gunicorn", ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000"])
