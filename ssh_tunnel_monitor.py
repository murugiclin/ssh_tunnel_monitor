import subprocess
import time
import logging
import os
import signal
import threading
import json
import socket
import configparser
import ping3
from datetime import datetime

# Configure logging (file, console, and JSON for demo)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("ssh_tunnel.log"),
        logging.StreamHandler()
    ]
)
json_log = []

# Load configuration from file or environment variables
CONFIG_FILE = "tunnel_config.ini"
def load_config():
    config = configparser.ConfigParser()
    defaults = {
        "vps_ip": os.getenv("VPS_IP", "your-vps-ip"),
        "ssh_user": os.getenv("SSH_USER", "user"),
        "ssh_port": os.getenv("SSH_PORT", "443"),
        "local_port": os.getenv("LOCAL_PORT", "8080"),
        "ssh_key": os.getenv("SSH_KEY", "~/.ssh/id_rsa"),
        "ssh_password": os.getenv("SSH_PASSWORD", ""),
        "ping_timeout": os.getenv("PING_TIMEOUT", "2"),
        "check_interval": os.getenv("CHECK_INTERVAL", "30"),
        "test_url": os.getenv("TEST_URL", "http://elearning.uonbi.ac.ke")
    }
    if os.path.exists(CONFIG_FILE):
        config.read(CONFIG_FILE)
        return {key: config.get("DEFAULT", key, fallback=val) for key, val in defaults.items()}
    return defaults

config = load_config()
VPS_IP = config["vps_ip"]
SSH_USER = config["ssh_user"]
SSH_PORT = int(config["ssh_port"])
LOCAL_PORT = int(config["local_port"])
SSH_KEY = config["ssh_key"]
SSH_PASSWORD = config["ssh_password"]
PING_TIMEOUT = float(config["ping_timeout"])
CHECK_INTERVAL = float(config["check_interval"])
TEST_URL = config["test_url"]

# Metrics for demo
metrics = {
    "start_time": datetime.now().isoformat(),
    "uptime_seconds": 0,
    "reconnect_attempts": 0,
    "successful_reconnects": 0,
    "last_latency": None
}

def save_metrics():
    """Save metrics to JSON log for demo visualization."""
    with open("tunnel_metrics.json", "w") as f:
        json.dump(metrics, f, indent=4)

def notify(message):
    """Send notification (Termux toast or print for demo)."""
    logging.info(f"Notification: {message}")
    if os.system("command -v termux-toast") == 0:
        subprocess.run(["termux-toast", message])
    # Optional: Add email notification (requires smtplib setup)
    # Example: send_email(subject="Tunnel Status", body=message)

def is_port_open(host, port, timeout=2):
    """Check if a port is open on the host."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            return s.connect_ex((host, port)) == 0
    except socket.error:
        return False

def is_ssh_alive():
    """Check tunnel health using port check, ping, and HTTP test."""
    checks = []
    
    # Check 1: Local SOCKS port
    try:
        cmd = ["ss", "-tuln"] if os.system("command -v ss") == 0 else ["netstat", "-tuln"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        checks.append(f":{LOCAL_PORT}" in result.stdout)
    except subprocess.CalledProcessError as e:
        logging.error(f"Port check failed: {e}")
        checks.append(False)
    
    # Check 2: Ping VPS
    try:
        latency = ping3.ping(VPS_IP, timeout=PING_TIMEOUT)
        metrics["last_latency"] = latency if latency else None
        checks.append(latency is not None)
    except Exception as e:
        logging.error(f"Ping check failed: {e}")
        checks.append(False)
    
    # Check 3: HTTP test through proxy (simulates zero-rated traffic)
    try:
        proxy_cmd = ["curl", "-s", "-x", f"socks5://127.0.0.1:{LOCAL_PORT}", TEST_URL]
        result = subprocess.run(proxy_cmd, capture_output=True, text=True, timeout=5)
        checks.append(result.returncode == 0)
    except subprocess.CalledProcessError as e:
        logging.error(f"HTTP test failed: {e}")
        checks.append(False)
    
    # Tunnel is alive if at least two checks pass
    alive = sum(checks) >= 2
    logging.info(f"Tunnel checks: Port={checks[0]}, Ping={checks[1]}, HTTP={checks[2]}, Alive={alive}")
    return alive

def start_ssh_tunnel():
    """Start the SSH tunnel with SOCKS proxy."""
    try:
        # Clean up old SSH processes
        os.system(f"pkill -f 'ssh -D {LOCAL_PORT}'")
        
        # Build SSH command with compression and keep-alive
        ssh_cmd = [
            "ssh", "-D", str(LOCAL_PORT), "-p", str(SSH_PORT), "-N", "-f",
            "-C", "-o", "ServerAliveInterval=10", "-o", "ServerAliveCountMax=3"
        ]
        if SSH_KEY:
            ssh_cmd.extend(["-i", SSH_KEY])
        ssh_cmd.append(f"{SSH_USER}@{VPS_IP}")
        
        # Use sshpass if password is provided
        if SSH_PASSWORD:
            if os.system("command -v sshpass") != 0:
                logging.error("sshpass not installed. Install: pkg install sshpass")
                return None
            ssh_cmd = ["sshpass", "-p", SSH_PASSWORD] + ssh_cmd
        
        # Start SSH tunnel
        process = subprocess.Popen(
            ssh_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        time.sleep(3)  # Wait for SSH to initialize
        if process.poll() is not None:
            error = process.stderr.read().decode() if process.stderr else "Unknown error"
            logging.error(f"SSH tunnel failed to start: {error}")
            return None
        logging.info(f"Started SSH tunnel with PID {process.pid}")
        notify(f"SSH tunnel started (PID {process.pid})")
        metrics["successful_reconnects"] += 1
        return process
    except Exception as e:
        logging.error(f"Failed to start SSH tunnel: {e}")
        return None

def update_metrics():
    """Update uptime metrics in background."""
    while True:
        if is_ssh_alive():
            metrics["uptime_seconds"] += CHECK_INTERVAL
        save_metrics()
        time.sleep(CHECK_INTERVAL)

def main():
    logging.info("Starting advanced SSH tunnel monitor")
    notify("SSH tunnel monitor started")
    
    # Start metrics update thread
    metrics_thread = threading.Thread(target=update_metrics, daemon=True)
    metrics_thread.start()
    
    # Initial SSH tunnel start
    process = start_ssh_tunnel()
    if not process:
        logging.error("Initial tunnel start failed. Exiting...")
        return
    
    while True:
        if not is_ssh_alive():
            logging.warning("SSH tunnel is down, attempting to reconnect...")
            metrics["reconnect_attempts"] += 1
            process = start_ssh_tunnel()
            if process:
                logging.info("SSH tunnel reconnected successfully")
                notify("SSH tunnel reconnected")
            else:
                logging.error("Failed to reconnect, retrying in 10s...")
                time.sleep(10)
        else:
            logging.info("SSH tunnel is alive")
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logging.info("Stopping SSH tunnel monitor")
        notify("SSH tunnel monitor stopped")
        os.system(f"pkill -f 'ssh -D {LOCAL_PORT}'")
        metrics["end_time"] = datetime.now().isoformat()
        save_metrics()
