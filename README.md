# DIY Underwater ROV Platform

![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python)
![Platform](https://img.shields.io/badge/Platform-Raspberry%20Pi%20%7C%20Windows-informational)
![Last Commit](https://img.shields.io/github/last-commit/presMart/rov-base)

A fully self-contained, Raspberry Pi-powered underwater Remotely Operated Vehicle (ROV) platform designed for exploration, sensing, and future extensibility. Built with modular hardware, robust motor control, real-time telemetry, and a cross-platform control GUI.

---

## Overview

This project implements a tethered, camera-equipped ROV capable of receiving live motor commands and transmitting telemetry over Wi-Fi. It features:

- Real-time video streaming from onboard camera
- Gamepad-controlled thrust commands with deadzone/burst support
- Voltage and environmental monitoring with safe shutdown logic
- Configurable GUI dashboard for control, diagnostics, and logging
- Modular, fully documented codebase using modern Python best practices

Designed as a foundation for future projects including DIY sonar, underwater communication experiments, and modular payload systems.

>  **Tethering Strategy**: The ROV is *not* tethered to shore. Instead, it connects to a nearby surface float which houses a Wi-Fi relay. This dramatically increases operating range (up to ~150m line-of-sight), reduces tether drag, and eliminates the need for a long, expensive shore-to-ROV cable.

---

## Hardware & Architecture

- **Compute**: Raspberry Pi Zero 2 W (onboard)
- **Power**: Dual 3S LiPo packs in parallel, inline fusing, remote toggle
- **ESCs**: Brushed + brushless ESCs controlled via PCA9685 and pigpio
- **Sensors**:
  - Depth: 30 PSI analog pressure transducer (via ADS1115)
  - Environment: DHT22 temp/humidity sensors per enclosure
  - Voltage: ADC with multi-threshold failsafe logic
- **Communication**:
  - TCP socket (JSONL) over local Wi-Fi
  - GUI host runs on Windows laptop
- **Tether**: Short, low-drag tether connects ROV to a floating Wi-Fi relay, not to shore
- **Video**: MJPEG stream served over HTTP by PiCamera2, displayed in GUI via OpenCV/Qt

---

## Software Highlights

### Python Backend (Onboard)

- `main.py`: Initializes all hardware, runs async control loop
- `controller.py`: Unified motor interface with burst/thrust limiting
- `monitoring.py`: Voltage + DHT environment sensors with tiered failsafes
- `communication.py`: Async TCP server for commands + telemetry
- `depth_monitor.py`: Translates analog pressure to depth telemetry

### GUI Application (Shore-side)

- PyQt6-based dashboard with modular panels:
  - **Video feed** (reconnectable MJPEG parser)
  - **Telemetry** (voltage, depth, temps, motor thrusts)
  - **Logging** (live scrollable output panel)
  - **Gamepad input** (with estop, lockout logic)
- `telemetry_client.py`: Thread-safe socket client with reconnect logic
- `input_controller.py`: Polls joystick, sends smoothed thrust commands

---

## Live Testing + Future Plans

This ROV was developed and tested in a short sprint to simulate real-world usage, including waterproofing, power integration, and runtime telemetry.

### Planned Extensions:

- **DIY sonar for fish detection**
- **Blue-laser optical comms from ROV to surface**
- **Sensor expansion (IMU, leak detection, acoustic modems)**

All future features will follow the same documented, modular format.

---

## Getting Started

### Prerequisites

- Raspberry Pi Zero 2 W (or compatible Pi)
- Python 3.11 (used in dev), Python ≥3.9 minimum
- `pigpiod` daemon running on the Pi (`sudo pigpiod`)
- GUI host system with PyQt6 installed (Windows recommended for full GUI functionality)

### Install Dependencies

On the **Pi**:
```bash
cd rov-core/rov
pip install -r requirements.txt
```

On the **GUI host**:
```bash
cd rov-core/gui
pip install -r requirements.txt
```

### Launching the System

On the Pi (ROV):
```bash
python3 -m rov.main
```

On the GUI (Shore-side):
```bash
python -m gui.main
```

### Optional: Auto-Start on Boot (Pi)
You can use the included `rov-init.sh` and a systemd unit to run the ROV software automatically:

1. Copy `rov-init.sh` to `/home/pi/rov-init.sh` and make it executable:
```bash
chmod +x /home/pi/rov-init.sh
```

2. Create a systemd service (e.g. `/etc/systemd/system/rov-main.service`) and enable it:
```ini
[Unit]
Description=ROV ESC + Telemetry Service
After=network.target

[Service]
ExecStart=/home/pi/rov-init.sh
Restart=always
User=pi
WorkingDirectory=/home/pi/rov-core/rov

[Install]
WantedBy=multi-user.target
```
```bash
sudo systemctl enable rov-main.service
sudo systemctl start rov-main.service
```

---

## Repo Structure

```
rov-core/
├── config.json
├── config.py
├── logging_setup.py
├── requirements.txt
│
├── gui/
│   ├── __init__.py
│   ├── main.py
│   ├── requirements.txt
│   ├── communication/
│   │   ├── __init__.py
│   │   └── telemetry_client.py
│   ├── input/
│   │   ├── __init__.py
│   │   ├── input_controller.py
│   │   └── gamepad_input.py
│   ├── panels/
│   │   ├── __init__.py
│   │   ├── app_window.py
│   │   ├── video_panel.py
│   │   ├── telemetry_panel.py
│   │   ├── logging_panel.py
│   │   └── burst_control_panel.py
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── logger.py
│
├── rov/
│   ├── __init__.py
│   ├── brushless_gpio_controller.py
│   ├── camera_streamer.py
│   ├── communication.py
│   ├── controller.py
│   ├── main.py
│   ├── requirements.txt
│   ├── rov-init.sh
│   ├── utils.py
│   ├── sensors/
│   │   ├── __init__.py
│   │   ├── depth_monitor.py
│   │   └── monitoring.py
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── esc_power_manager.py
```

---

## License

MIT License — free for personal, academic, or commercial use with attribution.
