 <div align="center">

<img src="logo.png" alt="Red Tor Logo" width="190">

# Red Tor

**A Modern Linux Desktop Interface for Tor Connection Management**

Connect • Monitor • Browse • Manage

![Version](https://img.shields.io/badge/Version-1.0.2-e53935?style=for-the-badge)
![Platform](https://img.shields.io/badge/Platform-Linux-black?style=for-the-badge&logo=linux)
![Python](https://img.shields.io/badge/Python-3-blue?style=for-the-badge&logo=python)
![GUI](https://img.shields.io/badge/GUI-PyQt5-green?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)

</div>

---

## About Red Tor

**Red Tor** is a Linux desktop application that provides a graphical interface for connecting to and managing a local Tor service.

It brings Tor connection controls, circuit information, an embedded Tor-routed browser, network monitoring, diagnostics, and privacy utilities together in one desktop application.

Red Tor is designed primarily for **Kali Linux and other Debian-based Linux distributions**. It uses Python, PyQt5, QtWebEngine, and Stem to communicate with the local Tor service.

> **Important:** Red Tor is not the official Tor Browser. It does not provide Tor Browser's complete anti-fingerprinting protections, does not route or firewall the entire computer, and has not undergone an independent security audit. A successful connection status is not a guarantee of anonymity.

## Features

| Feature | Description |
|---|---|
| **Dashboard** | View Tor connection status, controls, and application activity. |
| **Tor Connection** | Connect to and manage a local Tor service. |
| **Circuit View** | Inspect relay information reported by Tor's control interface. |
| **Circuit Map** | Display approximate GeoIP locations of Tor relays. |
| **Embedded Browser** | Browse using Chromium through the configured local Tor SOCKS proxy. |
| **New Circuit** | Request a new Tor circuit when the authenticated control port is available. |
| **Exit Country** | Set a preferred exit country through Tor's control interface. |
| **Network Monitor** | View available Tor daemon traffic counters or labelled application-side counters. |
| **Transfer Stats** | Monitor observed application-side transfer-rate samples. |
| **Diagnostics** | Run a Tor-routed HTTPS connectivity check. |
| **Privacy Tools** | Clear the application's browser session and manage its connection. |
| **Settings** | Configure supported preferences and map options. |
| **Terminal** | Access an interactive root shell through a pseudo-terminal. |
| **Local Notes** | Save plain-text notes locally on the device. |
| **Light Interface** | Clean white theme, Inter typography, and animated navigation. |

## Application Interface

Red Tor includes the following sections:

- Dashboard
- Browse
- Circuit View
- Circuit Map
- Network Monitor
- Transfer Stats
- Diagnostics
- Privacy Tools
- Settings
- Terminal
- Local Notes
- About

## Technology Stack

- **Python 3** — Core application
- **PyQt5** — Desktop graphical interface
- **PyQtWebEngine** — Embedded Chromium browser
- **Stem** — Tor control interface
- **Requests** — HTTP requests
- **PySocks** — SOCKS proxy support
- **Matplotlib** — Charts and visualizations
- **Tor** — Onion-routing service

## Requirements

- Linux operating system
- Kali Linux / Debian / Ubuntu recommended
- Python 3
- Tor service
- Internet connection for installation and Tor bootstrap
- Desktop environment with GUI support

The installation script handles the required dependencies on supported systems.

---

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/silent-days/Red-Tor.git
```

### 2. Open the Project Directory

```bash
cd Red-Tor
```

### 3. Prepare the Installer

The installer scripts are located inside `red-tor-v1.0.2/`. Copy the root README into that directory before installation:

```bash
cp README.md red-tor-v1.0.2/README.md
```

### 4. Install Red Tor

```bash
cd red-tor-v1.0.2
sudo bash install.sh
```

**Note:** Use `sudo bash install.sh`, not `sudo apt install.sh`.

The installer performs the following tasks:

1. Checks and installs required dependencies.
2. Configures the local Tor control interface when needed.
3. Creates a backup before modifying the Tor configuration.
4. Installs the application under `/opt/red-tor`.
5. Creates the `red-tor` launcher.
6. Adds a desktop application menu entry.
7. Configures login autostart for the desktop user when supported.

### 5. Launch Red Tor

After installation, launch the application:

```bash
red-tor
```

You can also open **Red Tor** from your desktop application menu.

The application should normally be launched as your regular desktop user, not with `sudo`.

If the installer adds your account to the `debian-tor` group, log out and log back in for the group change to take effect.

## First Launch

1. Open Red Tor.
2. Go to the Dashboard.
3. Select **Connect to Tor**.
4. Wait for the connection verification.
5. Open the Browse section after a verified Tor connection.
6. Explore the circuit, monitoring, diagnostics, and privacy tools.

Red Tor starts disconnected. You choose when to connect. Its embedded browser blocks requests while the application has not verified a Tor session.

## Tor Configuration

Red Tor uses these default local endpoints:

| Service | Address | Purpose |
|---|---|---|
| SOCKS Proxy | `127.0.0.1:9050` | Routes supported application and browser traffic through Tor. |
| Control Port | `127.0.0.1:9051` | Authenticated local Tor control operations. |

The Debian-family installer configures a loopback-only control port with cookie authentication when the relevant active settings are absent.

Existing active control-port directives are preserved. If your Tor configuration uses a different port or authentication method, some control features may not be available.

## Data Locations

| Data | Location |
|---|---|
| System application | `/opt/red-tor/` |
| User state | `~/.local/state/red-tor/` |
| Tor data | `~/.local/state/red-tor/tor-data/` |
| Preferences and legacy-compatible settings | `~/.silent-tor/` |

Existing Tor runtime data and logs may be copied into the Red Tor state directory during migration. The separate `~/.silent-tor/` settings directory is preserved.

## Disable Login Autostart

The installer enables application startup when the desktop user logs in.

To disable it, run this from the extracted project directory:

```bash
cd red-tor-v1.0.2
bash disable-autostart.sh
```

## Development & Testing

Open the application source directory:

```bash
cd red-tor-v1.0.2
```

**Compile Python files**

```bash
python3 -m compileall -q tor_core.py red_tor.py gui tests
```

**Run unit tests**

```bash
python3 -m unittest discover -s tests -v
```

**Check shell script syntax**

```bash
bash -n install.sh install-system.sh install-user.sh install-deps.sh run.sh uninstall-user.sh disable-autostart.sh
```

## Security & Privacy Notes

Please understand these limitations before relying on Red Tor:

- **Not Tor Browser:** The embedded Chromium browser does not include Tor Browser's complete privacy and anti-fingerprinting protections.
- **Not system-wide protection:** Red Tor does not route or firewall all computer traffic. Other applications may still connect directly.
- **No anonymity guarantee:** Tor alone cannot prevent account identification, unsafe downloads, malware, or mistakes that reveal personal information.
- **Browser protection:** The embedded browser uses the configured SOCKS proxy and blocks requests while Tor is disconnected. This does not force every system process through Tor.
- **Diagnostics:** The diagnostics feature performs a Tor-routed HTTPS check. It is not a direct-IP comparison or a comprehensive DNS leak test.
- **Traffic statistics:** Application-side fallback counters do not include Chromium browser traffic.
- **Circuit map:** Relay locations are approximate GeoIP estimates, not exact physical server locations or packet routes. Destination geolocation is optional and disabled by default.
- **Terminal:** The Terminal page provides a real root shell. Commands can modify or delete system files and affect the operating system. Run only commands you understand.

For more information about Tor security, visit the [Official Tor Support](https://support.torproject.org/).

## License

Red Tor is released under the **MIT License**. See the [LICENSE](LICENSE) file for details.

## Repository

**GitHub:** https://github.com/silent-days/Red-Tor

If you find Red Tor useful, consider giving the repository a ⭐ star.

---

<div align="center">

**RED TOR**

*Connect • Monitor • Browse • Manage*

Developed by **Silent Days**

</div>
