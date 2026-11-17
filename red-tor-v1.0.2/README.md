# Red Tor

![Red Tor logo](assets/logo.png)

Red Tor is a desktop interface for a **local Tor service**, designed for **Kali Linux** (Debian family). It is not Tor Browser, does not route or firewall the whole computer, and has not undergone a security audit. Its app connection badge means only that the configured Tor service/SOCKS endpoint passed the app's verification; it is not a guarantee of anonymity.

## What the app actually does

- **Tor Connection:** connects to the local SOCKS service and, when available, an authenticated loopback control port. Circuit nodes are read from Tor's control port; the app shows no invented circuit if Tor is disconnected or control data is unavailable.
- **Circuit map:** relay order comes from Tor. Relay locations are approximate GeoIP estimates, not precise server addresses or physical packet routes. Destination geolocation is optional and off by default; enabling it sends the current Tor-reported target hostname to the selected GeoIP provider through Tor.
- **Network Monitor:** reads daemon-wide byte counters only when the authenticated control port exposes them. Otherwise it clearly reports app-side Python-request counters; Chromium browser traffic is not included in those fallback counters.
- **Browse:** embeds Chromium with the local SOCKS proxy configured and blocks requests until the app verifies a Tor session. It is not Tor Browser and does not reproduce Tor Browser's anti-fingerprinting protections.
- **Diagnostics:** makes a Tor-routed HTTPS check only. It does not query your direct IP, compare direct and Tor IPs, or perform a DNS leak test.
- **Privacy Tools:** clears this app's browser session and can disconnect this app. It does not firewall or stop traffic from other applications.
- **Terminal:** a real root shell behind a pseudo-terminal (pty): interactive commands, sudo password prompts, Ctrl+C and long output all behave like a system console. Commands run with root privileges on this machine.
- **Local Notes:** saves plaintext notes on this device only. It has no messaging transport and never attaches a Tor circuit to a note.
- **Settings:** saves exit-country preference and explicit map/GeoIP options. Exit-country changes require the authenticated control port.

If Tor is unavailable, the app reports that state, blocks its browser request path, and does not display synthetic relay, destination, IP, or traffic results. Startup progress is based on completed desktop-interface initialization phases; it does not measure Tor bootstrap progress. Tor is not auto-connected by the app.

## Install on Linux

From the extracted project directory, the single system-wide Debian-family install command is:

```bash
sudo bash install.sh
```

`sudo apt install.sh` is **wrong** — apt tries to install a package named `install.sh` and downloads nothing. To open the tool afterwards, run `red-tor` or use the menu entry; the app itself does not need sudo (running it with sudo also works, but is unnecessary).

It installs the Linux dependencies, places the app under `/opt/red-tor`, creates the `red-tor` command and desktop menu entry, and enables login autostart for the invoking desktop user. On Debian-family Linux, if `/etc/tor/torrc` has no active control port, the installer adds a loopback-only `127.0.0.1:9051` control port with cookie authentication and restarts an active Tor service. Existing active control-port directives are preserved. Red Tor currently expects the loopback controller at `127.0.0.1:9051`; if your Tor config uses a different port or authentication method, the app may remain in SOCKS-only mode until that config matches. A newly added `debian-tor` group membership takes effect after you log out and back in.

For other Linux distributions, use `bash install.sh` without `sudo` for a persistent per-user install when compatible PyQt5/QtWebEngine binary wheels are available. The same script creates login autostart. The app itself starts disconnected; you choose when to connect.

## Login autostart

Red Tor opens by itself at login because the installer registers a desktop autostart entry — this is intentional, not a bug. If you do not want that behavior, remove the entry without touching the app or your data:

```bash
bash disable-autostart.sh
```

## Data and migration

Local Notes and preferences remain in `~/.silent-tor/` for upgrade compatibility. On first Tor launch, existing Tor runtime data/logs are copied into the Red Tor state directory under `${XDG_STATE_HOME:-~/.local/state}/red-tor/`. Migration itself does not delete source data; the per-user installer removes its dedicated old app folder only after copying Tor runtime data. The separate `~/.silent-tor/` notes/settings folder is preserved.

## Offline checks

```bash
python3 -m compileall -q tor_core.py red_tor.py gui tests
python3 -m unittest discover -s tests -v
bash -n install.sh install-system.sh install-user.sh install-deps.sh run.sh uninstall-user.sh
```


## Project license

A project-wide license has not been selected. Choose and add an owner-approved license before inviting public reuse or redistribution.
