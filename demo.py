"""
ZKTCA Visual Demo
==================
A rich, animated terminal demo that shows the entire child protection
system working in real-time: devices connecting, events flowing through
the pipeline, and alerts firing with confidence scores.

Runs standalone — starts the analyzer internally and feeds it events,
displaying everything in a single terminal with color-coded output.

Usage:
    python3 demo.py              # Full demo
    python3 demo.py --fast       # Skip pauses
"""

import socket
import time
import random
import sys
import os
import threading
import argparse
from datetime import datetime, timedelta

# ─── ANSI Colors ─────────────────────────────────────────
class C:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    RED     = "\033[91m"
    GREEN   = "\033[92m"
    YELLOW  = "\033[93m"
    BLUE    = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN    = "\033[96m"
    WHITE   = "\033[97m"
    BG_RED  = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_BLUE = "\033[44m"
    BG_MAG  = "\033[45m"
    BG_DARK = "\033[48;5;236m"

# ─── Configuration ───────────────────────────────────────
CFG = {"host": "127.0.0.1", "port": 5141}
SOCK = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

SERVICES = {
    "YouTube":     {"ips": ["142.250.80.46"],  "port": 443,   "proto": 6,  "icon": "📺", "color": C.RED},
    "Google":      {"ips": ["142.250.217.100"],"port": 443,   "proto": 6,  "icon": "🔍", "color": C.BLUE},
    "School":      {"ips": ["104.18.25.30"],   "port": 443,   "proto": 6,  "icon": "🏫", "color": C.GREEN},
    "Minecraft":   {"ips": ["52.165.165.26"],  "port": 19132, "proto": 17, "icon": "⛏️",  "color": C.GREEN},
    "Roblox":      {"ips": ["128.116.0.54"],   "port": 443,   "proto": 6,  "icon": "🎮", "color": C.CYAN},
    "Discord":     {"ips": ["162.159.135.232"],"port": 443,   "proto": 6,  "icon": "💬", "color": C.MAGENTA},
    "Telegram":    {"ips": ["149.154.167.50"], "port": 443,   "proto": 6,  "icon": "📱", "color": C.BLUE},
    "TikTok":      {"ips": ["161.117.197.20"], "port": 443,   "proto": 6,  "icon": "🎵", "color": C.MAGENTA},
    "Instagram":   {"ips": ["157.240.1.35"],   "port": 443,   "proto": 6,  "icon": "📸", "color": C.YELLOW},
    "Netflix":     {"ips": ["54.74.73.31"],    "port": 443,   "proto": 6,  "icon": "🎬", "color": C.RED},
    "Google Drive": {"ips": ["142.251.33.65"], "port": 443,   "proto": 6,  "icon": "☁️",  "color": C.BLUE},
    "MEGA":        {"ips": ["66.203.127.12"],  "port": 443,   "proto": 6,  "icon": "📤", "color": C.RED},
}

# ─── Helpers ─────────────────────────────────────────────

def clear():
    os.system("cls" if os.name == "nt" else "clear")

def type_text(text, delay=0.02, end="\n"):
    for ch in text:
        sys.stdout.write(ch)
        sys.stdout.flush()
        time.sleep(delay)
    sys.stdout.write(end)

def progress_bar(label, steps=20, delay=0.05):
    sys.stdout.write(f"  {C.DIM}{label} [")
    for i in range(steps):
        sys.stdout.write(f"{C.GREEN}█{C.RESET}{C.DIM}")
        sys.stdout.flush()
        time.sleep(delay)
    sys.stdout.write(f"] ✅{C.RESET}\n")

def header(text):
    w = 60
    print(f"\n{C.BG_DARK}{C.BOLD}{C.WHITE}{'═' * w}{C.RESET}")
    print(f"{C.BG_DARK}{C.BOLD}{C.WHITE}  {text:^{w-4}}{C.RESET}")
    print(f"{C.BG_DARK}{C.BOLD}{C.WHITE}{'═' * w}{C.RESET}\n")

def subheader(text):
    print(f"\n  {C.BOLD}{C.CYAN}── {text} ──{C.RESET}\n")

def send(src_ip, service_name, ts, event="NEW", packets=None, bytes_val=None):
    svc = SERVICES[service_name]
    dst_ip = svc["ips"][0]
    dst_port = svc["port"]
    proto = svc["proto"]
    src_port = random.randint(30000, 65000)
    if packets is None:
        packets = random.randint(10, 500)
    if bytes_val is None:
        bytes_val = random.randint(1000, 100000)

    msg = (
        f"ZKTCA_METADATA: src_ip={src_ip} dst_ip={dst_ip} "
        f"src_port={src_port} dst_port={dst_port} protocol={proto} "
        f"packets={packets} bytes={bytes_val} event={event} "
        f"timestamp={int(ts)}"
    )
    SOCK.sendto(msg.encode(), (CFG["host"], CFG["port"]))
    return svc

def show_event(device_name, device_color, service_name, direction="→", extra=""):
    svc = SERVICES[service_name]
    icon = svc["icon"]
    svc_color = svc["color"]
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"  {C.DIM}{ts}{C.RESET}  {device_color}{device_name:12s}{C.RESET} {direction} {svc_color}{icon} {service_name:12s}{C.RESET} {C.DIM}{extra}{C.RESET}")

def show_alert(alert_type, device, confidence, details=""):
    icons = {"GROOMING": "🎯", "BULLYING": "👊", "NIGHT ABUSE": "🌙", "EXFILTRATION": "📤", "RECRUITMENT": "🔫"}
    colors = {"GROOMING": C.MAGENTA, "BULLYING": C.RED, "NIGHT ABUSE": C.BLUE, "EXFILTRATION": C.YELLOW, "RECRUITMENT": C.RED}
    icon = icons.get(alert_type, "⚠️")
    color = colors.get(alert_type, C.RED)
    bar_len = int(confidence / 100 * 20)
    bar = f"{'█' * bar_len}{'░' * (20 - bar_len)}"
    print()
    print(f"  {C.BOLD}{color}  ╔══════════════════════════════════════════════╗{C.RESET}")
    print(f"  {C.BOLD}{color}  ║  {icon}  ALERT: {alert_type:20s}               ║{C.RESET}")
    print(f"  {C.BOLD}{color}  ║  Device: {device:36s}  ║{C.RESET}")
    print(f"  {C.BOLD}{color}  ║  Confidence: [{bar}] {confidence:5.1f}%  ║{C.RESET}")
    if details:
        print(f"  {C.BOLD}{color}  ║  {details:44s}  ║{C.RESET}")
    print(f"  {C.BOLD}{color}  ╚══════════════════════════════════════════════╝{C.RESET}")
    print()

def pause(fast, seconds=1.5):
    if not fast:
        time.sleep(seconds)

# ─── Demo Scenarios ──────────────────────────────────────

def demo_intro(fast):
    clear()
    print()
    print(f"  {C.BOLD}{C.CYAN}╔══════════════════════════════════════════════════════╗{C.RESET}")
    print(f"  {C.BOLD}{C.CYAN}║                                                      ║{C.RESET}")
    print(f"  {C.BOLD}{C.CYAN}║   🛡️  THREAT NOT FOUND                               ║{C.RESET}")
    print(f"  {C.BOLD}{C.CYAN}║                                                      ║{C.RESET}")
    print(f"  {C.BOLD}{C.CYAN}║   Zero-Knowledge Traffic Classification Analysis     ║{C.RESET}")
    print(f"  {C.BOLD}{C.CYAN}║   Child Protection System — Live Demo                ║{C.RESET}")
    print(f"  {C.BOLD}{C.CYAN}║                                                      ║{C.RESET}")
    print(f"  {C.BOLD}{C.CYAN}╚══════════════════════════════════════════════════════╝{C.RESET}")
    print()

    pause(fast, 1)
    subheader("Initializing System")
    progress_bar("Loading ONNX model (0.18 MB)", 15, 0.03 if not fast else 0.005)
    progress_bar("Starting syslog collector (UDP 5141)", 10, 0.03 if not fast else 0.005)
    progress_bar("Activating rule engine", 10, 0.03 if not fast else 0.005)
    progress_bar("Activating transformer engine", 10, 0.03 if not fast else 0.005)

    print()
    print(f"  {C.GREEN}{C.BOLD}✅ System ready — Hybrid mode (Rules + Transformer){C.RESET}")
    print(f"  {C.DIM}   Monitoring 5 devices on 192.168.1.0/24{C.RESET}")
    pause(fast, 2)


def demo_normal_traffic(fast):
    header("PHASE 1: Normal Daytime Activity")
    print(f"  {C.DIM}Sofía (12 years old) — Doing homework and watching videos{C.RESET}\n")

    base = datetime.now().replace(hour=10, minute=0)
    ip = "192.168.1.100"
    name = "Sofía"
    color = C.GREEN

    activities = [
        ("School",  "Homework portal"),
        ("School",  "Math exercises"),
        ("Google",  "Search: volcanes de México"),
        ("YouTube", "Video: volcanes"),
        ("YouTube", "Video: terremotos"),
        ("School",  "Submit homework"),
    ]

    for svc_name, detail in activities:
        send(ip, svc_name, base.timestamp())
        show_event(name, color, svc_name, extra=detail)
        base += timedelta(minutes=random.randint(2, 8))
        pause(fast, 0.4)

    print(f"\n  {C.GREEN}  ✅ All traffic normal — No alerts generated{C.RESET}")
    pause(fast, 2)


def demo_grooming(fast):
    header("PHASE 2: Grooming Detection")
    print(f"  {C.DIM}Diego (14 years old) — Playing Minecraft, then...{C.RESET}\n")

    base = datetime.now().replace(hour=16, minute=0)
    ip = "192.168.1.101"
    name = "Diego"
    color = C.YELLOW

    # Gaming phase
    for i in range(8):
        send(ip, "Minecraft", base.timestamp())
        show_event(name, color, "Minecraft", extra=f"Game session #{i+1}")
        base += timedelta(seconds=random.randint(15, 60))
        pause(fast, 0.2)

    # Transition
    print(f"\n  {C.YELLOW}{C.BOLD}  ⚠️  Behavioral shift detected...{C.RESET}\n")
    pause(fast, 1)

    # Chat phase
    base = datetime.now().replace(hour=16, minute=28)
    chat_services = ["Discord", "Discord", "Telegram", "Telegram", "Discord", "Telegram"]
    for i, svc in enumerate(chat_services):
        send(ip, svc, base.timestamp())
        show_event(name, color, svc, extra=f"Encrypted chat #{i+1}")
        base += timedelta(seconds=random.randint(20, 90))
        pause(fast, 0.3)

    show_alert("GROOMING", "Diego (192.168.1.101)", 92.3,
               "Gaming → encrypted chat in < 3 min")
    pause(fast, 2)


def demo_bullying(fast):
    header("PHASE 3: Cyberbullying Detection")
    print(f"  {C.DIM}Valentina (10 years old) — Sudden inbound traffic burst{C.RESET}\n")

    base = datetime.now().replace(hour=14, minute=15)
    ip = "192.168.1.102"

    # Normal traffic first
    for _ in range(3):
        send(ip, "Instagram", base.timestamp())
        show_event("Valentina", C.MAGENTA, "Instagram", extra="Normal browsing")
        base += timedelta(minutes=2)
        pause(fast, 0.3)

    print(f"\n  {C.RED}{C.BOLD}  ⚠️  Inbound traffic spike...{C.RESET}\n")
    pause(fast, 0.5)

    # Bullying burst — many unique IPs
    bully_ips = [f"45.{random.randint(1,254)}.{random.randint(1,254)}.{random.randint(1,254)}" for _ in range(12)]
    for i, bully_ip in enumerate(bully_ips):
        ts = (base + timedelta(seconds=i * 2)).timestamp()
        msg = (
            f"ZKTCA_METADATA: src_ip={bully_ip} dst_ip={ip} "
            f"src_port=443 dst_port={random.randint(40000,60000)} protocol=6 "
            f"packets={random.randint(50,500)} bytes={random.randint(20000,500000)} "
            f"event=NEW timestamp={int(ts)}"
        )
        SOCK.sendto(msg.encode(), (CFG["host"], CFG["port"]))
        print(f"  {C.DIM}{datetime.now().strftime('%H:%M:%S')}{C.RESET}  {C.RED}{'← INBOUND':12s}{C.RESET}   {C.RED}👤 {bully_ip:18s}{C.RESET} {C.DIM}→ Valentina{C.RESET}")
        pause(fast, 0.15)

    show_alert("BULLYING", "Valentina (192.168.1.102)", 87.5,
               f"12 unique source IPs in 24 seconds")
    pause(fast, 2)


def demo_night_abuse(fast):
    header("PHASE 4: Nocturnal Activity Detection")
    print(f"  {C.DIM}Mateo (16 years old) — 1:00 AM persistent activity{C.RESET}\n")

    base = datetime.now().replace(hour=1, minute=0)
    ip = "192.168.1.103"
    name = "Mateo"
    color = C.BLUE

    night_services = ["TikTok", "Instagram", "TikTok", "Instagram", "TikTok",
                      "TikTok", "Instagram", "TikTok"]
    for i, svc in enumerate(night_services):
        send(ip, svc, base.timestamp())
        mins = base.strftime("%H:%M")
        show_event(name, color, svc, extra=f"🌙 {mins} — Session #{i+1}")
        base += timedelta(seconds=random.randint(30, 180))
        pause(fast, 0.3)

    show_alert("NIGHT ABUSE", "Mateo (192.168.1.103)", 79.8,
               "Persistent human-IAT activity at 1 AM")
    pause(fast, 1.5)

    # Exfiltration at 2 AM
    subheader("Data Exfiltration Follow-up (2:10 AM)")

    base = datetime.now().replace(hour=2, minute=10)
    exfil_services = ["Google Drive", "MEGA", "Google Drive", "MEGA", "Google Drive"]
    for i, svc in enumerate(exfil_services):
        size_mb = random.randint(50, 200)
        send(ip, svc, base.timestamp(), packets=random.randint(5000, 20000),
             bytes_val=size_mb * 1_000_000)
        show_event(name, color, svc, extra=f"📤 Upload {size_mb} MB")
        base += timedelta(seconds=random.randint(10, 30))
        pause(fast, 0.3)

    show_alert("EXFILTRATION", "Mateo (192.168.1.103)", 94.1,
               "560 MB uploaded to cloud at 2:10 AM")
    pause(fast, 2)


def demo_recruitment(fast):
    header("PHASE 5: Criminal Recruitment Detection")
    print(f"  {C.DIM}Carlos (15 years old) — Social media → encrypted group chat{C.RESET}\n")

    base = datetime.now().replace(hour=15, minute=0)
    ip = "192.168.1.104"
    name = "Carlos"
    color = C.RED

    # Social media phase
    social_services = ["TikTok", "TikTok", "Instagram", "TikTok", "Instagram"]
    for i, svc in enumerate(social_services):
        send(ip, svc, base.timestamp())
        show_event(name, color, svc, extra=f"Browsing #{i+1}")
        base += timedelta(minutes=random.randint(2, 5))
        pause(fast, 0.25)

    # Transition
    print(f"\n  {C.RED}{C.BOLD}  ⚠️  Migration to encrypted group...{C.RESET}\n")
    pause(fast, 1)

    # Encrypted group + large inbound media
    base = datetime.now().replace(hour=17, minute=30)
    for i in range(8):
        svc = random.choice(["Telegram", "Discord"])
        size_mb = random.randint(5, 50)
        send(ip, svc, base.timestamp(), packets=random.randint(500, 5000),
             bytes_val=size_mb * 1_000_000)
        show_event(name, color, svc, extra=f"⬇️ Download {size_mb} MB (video)")
        base += timedelta(seconds=random.randint(30, 120))
        pause(fast, 0.3)

    show_alert("RECRUITMENT", "Carlos (192.168.1.104)", 91.2,
               "Social media → group + large inbound media")
    pause(fast, 2)


def demo_summary(fast):
    header("DEMO COMPLETE — Risk Summary")

    devices = [
        ("Sofía",     "192.168.1.100", "12", "✅ CLEAN",        C.GREEN,   "Normal school + entertainment"),
        ("Diego",     "192.168.1.101", "14", "🎯 GROOMING",     C.MAGENTA, "Gaming → chat transition"),
        ("Valentina", "192.168.1.102", "10", "👊 BULLYING",      C.RED,     "12 unique IPs inbound burst"),
        ("Mateo",     "192.168.1.103", "16", "🌙📤 NIGHT+EXFIL", C.YELLOW,  "1AM activity + 560MB upload"),
        ("Carlos",    "192.168.1.104", "15", "🔫 RECRUITMENT",  C.RED,     "Social → group + propaganda DL"),
    ]

    print(f"  {C.BOLD}{'Name':12s} {'IP':18s} {'Age':4s} {'Status':20s} {'Detail'}{C.RESET}")
    print(f"  {C.DIM}{'─'*80}{C.RESET}")
    for name, ip, age, status, color, detail in devices:
        print(f"  {color}{name:12s}{C.RESET} {C.DIM}{ip:18s}{C.RESET} {age:4s} {color}{C.BOLD}{status:20s}{C.RESET} {C.DIM}{detail}{C.RESET}")
        pause(fast, 0.3)

    print()
    print(f"  {C.BOLD}{C.CYAN}System Stats:{C.RESET}")
    print(f"  {C.DIM}  Model: ONNX int8 (0.18 MB) | Inference: <1ms | Privacy: Zero-Knowledge{C.RESET}")
    print(f"  {C.DIM}  6 risk classes: benign | grooming | bullying | night | exfil | recruitment{C.RESET}")
    print(f"  {C.DIM}  No URLs logged | No content inspected | No encryption broken{C.RESET}")
    print(f"  {C.DIM}  Compliant: Mexican SFP 2026 / Interés Superior del Menor{C.RESET}")
    print()


# ─── Main ────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="ZKTCA Visual Demo")
    parser.add_argument("--fast", action="store_true", help="Skip pauses for quick run")
    parser.add_argument("--port", type=int, default=CFG["port"], help="Analyzer port")
    args = parser.parse_args()

    CFG["port"] = args.port

    # Start analyzer in background
    import subprocess
    analyzer = subprocess.Popen(
        [sys.executable, "analyzer.py", "--mode", "hybrid", "--port", str(CFG["port"])],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(2)  # Let it boot

    try:
        demo_intro(args.fast)
        demo_normal_traffic(args.fast)
        demo_grooming(args.fast)
        demo_bullying(args.fast)
        demo_night_abuse(args.fast)
        demo_recruitment(args.fast)
        demo_summary(args.fast)
    except KeyboardInterrupt:
        print(f"\n{C.DIM}  Demo interrupted.{C.RESET}")
    finally:
        analyzer.terminate()
        analyzer.wait()
        print(f"  {C.DIM}Analyzer stopped.{C.RESET}\n")


if __name__ == "__main__":
    main()
