# 🛰️ TunnelSentinel

TunnelSentinel is an advanced SSH SOCKS5 tunnel monitor and auto-reconnector. Built for environments like Termux or Linux, it ensures persistent, stealthy SSH tunneling for secure browsing, tunneling zero-rated traffic, or routing proxy requests.

---

## 🔍 Features

- Monitors tunnel health using:
  - Local port status
  - VPS ping test
  - HTTP proxy routing test
- Auto-reconnects if tunnel dies
- Logs metrics to JSON and log file
- Configuration via `.ini` file or environment
- Lightweight – runs well on low-end devices
- Termux toast notifications
- Tracks uptime, reconnects, and latency

---

## ⚙️ Configuration (`tunnel_config.ini`)

```ini
[DEFAULT]
vps_ip = your-vps-ip
ssh_user = your-username
ssh_port = 443
local_port = 8080
ssh_key = ~/.ssh/id_rsa
ssh_password = 
ping_timeout = 2
check_interval = 30
test_url = http://elearning.uonbi.ac.ke
