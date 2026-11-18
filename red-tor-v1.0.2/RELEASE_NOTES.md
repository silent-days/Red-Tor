# Red Tor — release notes

## v1.0.2 — the real browser-engine fix + clean Ctrl+C (round 6)

### Browser page said "engine not installed" although it was installed

- Field evidence (Kali screenshot + console log): the installer and the launcher probe both imported `PyQt5.QtWebEngineWidgets` fine, the window opened, Tor connected (LIVE) — yet the Browse page showed the "engine not installed" fallback, and the log printed Qt's "Qt WebEngine seems to be initialized from a plugin" warning.
- Root cause: the app creates `QApplication` first and imports the engine later (inside the Browse tab). Kali's distro PyQt5 aborts the QtWebEngineWidgets module init with `ImportError` when it loads after a `QApplication` built without `AA_ShareOpenGLContexts`. The pip wheels used in the sandbox tolerate late imports, which is why automated checks missed it.
- Fix in `red_tor.py`: `QCoreApplication.setAttribute(Qt.AA_ShareOpenGLContexts, True)` and a pre-load `import PyQt5.QtWebEngineWidgets` now run at module level, **before** QtWidgets and before any `QApplication` — the documented requirement for QtWebEngineWidgets. The Browse page now gets the real Chromium view; the requirements checklist flips to ✔.

### Ctrl+C in the launching terminal no longer crashes ("zsh: abort")

- Ctrl+C used to raise KeyboardInterrupt inside arbitrary Python frames (the splash pulse), tear the interpreter down while Chromium threads were alive, and end with a traceback + SIGABRT.
- Before the heavy imports, SIGINT is reset to its default (instant native kill). After the window exists, `_install_signal_quit()` maps SIGINT/SIGTERM to a graceful `window.close()` on the GUI thread (a periodic no-op timer lets Python signals run inside Qt's C++ loop), so the full closeEvent cleanup runs and the process exits 0 with no traceback.
- Integration tests launch the real app offscreen, send SIGINT and SIGTERM, and assert exit code 0 with no traceback.

### Other changes

- `run.sh` silences the harmless at-spi "Couldn't connect to accessibility bus" warning (`NO_AT_BRIDGE=1` unless the bridge was enabled on purpose).
- About page and README now state Red Tor is **designed for Kali Linux (Debian family)**; the README Terminal bullet was corrected (it is a real root shell behind a pty, not an allowlist view).

## v1.0.2 — light terminal, classic font, clearer first-run (round 5)

### The whole app is now white/light — including the Terminal

- The Terminal console was the last dark surface: its output box is now white paper with near-black monospace text and the same soft border as the rest of the light theme.

### Classic z.ai-style font

- Inter (Regular, Medium, SemiBold, Bold) is now bundled in `assets/fonts/` and registered at startup, so the whole UI renders in the clean modern sans used by z.ai-like interfaces — on any Linux, with no font installation needed.
- `gui.theme.FONT_STACK` falls back gracefully: Inter → Segoe UI → Noto Sans → DejaVu Sans.

### Browser "not loading" — explained on screen

- The browser routes every request through Tor and BLOCKS all pages while Tor is offline (that is the anti-leak design, not a bug). The Browse page now shows a prominent banner whenever Tor is disconnected: "Tor is not connected — every page stays blocked to protect your real IP", with a **Connect Tor** button that starts Tor right from the Browse page.

### Requirements installation — why nothing downloaded

- The command `sudo apt install.sh` is wrong: `apt` tries to install a package literally named `install.sh` and downloads nothing. The correct command is `sudo bash install.sh` (run from the extracted folder).
- Both installers now print a big "HOW TO OPEN RED TOR" block at the end with the correct open command (`red-tor`, no sudo) and the correct repair command (`sudo bash install.sh`).
- `install-system.sh`: `apt-get update` failure no longer aborts the whole install (cached package lists are used instead), and if QtWebEngine is still missing after the distro packages, the installer falls back to the official `PyQtWebEngine` + `PyQtWebEngine-Qt5` wheels from PyPI before failing.
- `install.sh` without sudo now announces that it is running the per-user installer.

## v1.0.2 — root-launch fix (round 4)

### Launching as root no longer breaks the browser

- Symptom: when Red Tor was started with `sudo` (or on a root desktop session), the window opened after the password prompt but the browser engine died with Chromium's "Running as root without --no-sandbox is not supported" error.
- `red_tor.py` now detects uid 0 and appends `--no-sandbox` to the Tor-routed Chromium flags **only for root launches** (`build_chromium_flags()`); normal users keep the full Chromium sandbox. A console note explains the trade-off when root mode is active.
- `run.sh` prints the same note when launched as root.
- The Browse page's **"Run installer"** button no longer opens a polkit password dialog when the app already runs as root — it runs `install.sh` directly.
- New tests (`tests/test_root_launch.py`) cover both flag branches: root gets `--no-sandbox` plus the SOCKS/DNS-lockdown flags, non-root keeps the sandbox.

### How to launch (unchanged rules)

- Install once: `sudo bash install.sh` — that is the only step that needs the password.
- Open the tool afterwards with `red-tor`, the menu entry, or `bash run.sh` — no password needed.
- If the tool is opened with `sudo` anyway, it now works: the browser starts (sandbox disabled as Chromium requires under root) and the Terminal page gets a direct root shell with no second password prompt.

## v1.0.2 — structure and requirements release (round 3)

### Requirements: auto-check + one-click repair

- New `gui/requirements_check.py` probes every runtime dependency (PyQt5, QtWebEngine, QtSvg, Matplotlib, Stem, Requests, PySocks, the `tor` binary, Python version) and names the exact package that is missing.
- The Browse page, when the engine is unavailable, no longer shows a bare "install pip package" hint: it lists every missing requirement with ✔/✘ status and offers a **"Run installer (fixes everything)"** button that elevates via `pkexec bash install.sh` (or shows the exact command when polkit is absent), plus a "Check again" button.
- Diagnostics gained a **"Tool requirements (auto-checked)"** section listing each item with its status and the single repair command when something is missing.
- `install-system.sh` now prints an OK/MISSING line per Debian package and installs only what is absent; `install-deps.sh` prints the same audit for Python packages before installing. Both remain idempotent.

### Pages: restructured

- **Transfer Stats is its own page.** The "Observed app-side transfer rate" chart moved off the Dashboard's bottom row; it samples counters on its own 2-second timer, so the graph keeps running while any page is open. The Dashboard's activity log now uses the full width.
- **Local Notes was removed** from the sidebar, the code (send.py, the message store in tor_core) and the tests, as requested.
- **Terminal is now a real Kali-style root terminal.** Commands run on this system as root through a pty: sudo password prompts appear in the console and work (the pty is adopted as the controlling terminal with TIOCSCTTY, without which sudo refuses to prompt); ANSI escapes are stripped so output stays readable; progress bars with `\r` rewrite their line like a real console. If Red Tor already runs as root, bash starts directly. A red warning banner reminds that every command has real effect, and Restart/Export/Clear controls remain. The child shell is killed on window close (new `TorManager.remove_listener` avoids callbacks into destroyed widgets).
- **Privacy Tools gained four working tools:** New Identity (browser session wipe + NEWNYM circuit request in one action), a loopback-only Tor ports probe (SOCKS 9050 / control 9051), a live exit-country selector that applies through the control port and requests a new circuit, and a clipboard wipe.
- **Current Circuit Path guidance:** in SOCKS-only mode the card now names the exact fix (`sudo bash install.sh`, then re-login for cookie-group access) instead of a vague explanation; the installer enables ControlPort 9051 + CookieAuthentication automatically when absent.
- Diagnostics and the Browse fallback are scroll-wrapped, so their new sections never squeeze or overlap at small window heights.

### Verification

- Offline unit tests: **36 passed** (two Local Notes tests retired with the feature). Compile checks pass for every Python file; `bash -n` passes for every script. GUI smoke offscreen: all 10 pages render, page-switch animations leave no leaked effects, the transfer chart samples counters, and the terminal's root shell stays alive with the sudo prompt visible. The programmatic layout audit reports no squeezed page and no unreachable content at the 1024×640 minimum (dashboard's horizontal scrollbar at that minimum width is visible and reachable; at the default 1280×740 nothing scrolls horizontally).

## v1.0.2 — bug-fix release

### Correctness

- Startup no longer crashes when `~/.silent-tor/settings.json` contains corrupt or non-object JSON; `load_settings()` validates the parsed type before returning it.
- Connection no longer fails while Tor is still booting: after control-port authentication, Red Tor waits for Tor's bootstrap phase to reach 100% (up to ~75 s, with live progress messages) before verifying the SOCKS endpoint, and the SOCKS check itself retries three times. A freshly started daemon or a slow/censored network previously produced "Control port authenticated but SOCKS verification failed … connection timed out" even though Tor was healthy and still building its first circuits.
- When SOCKS verification still fails, the error now includes concrete guidance: the exact bootstrap phase Tor is stuck at (e.g. 45%, "asking for consensus"), a bridge suggestion for censored networks, and a retry hint — the app still never starts a second Tor process in this situation.
- The Tor control socket is now closed when controller authentication raises, instead of leaking a half-open connection.
- The "Tracked sent" counter actually counts outbound bytes (request line + headers + body) for every Tor-proxied app request; previously `bytes_sent` stayed at 0 forever.
- The "Circuits:" counter counts distinct circuit IDs, not refresh attempts; refreshing the same circuit no longer inflates it.
- Relay GeoIP cache access is lock-protected, and failed location lookups back off for 10 minutes instead of re-querying Tor Metrics on every circuit refresh.
- GeoIP lookups run without holding the manager lock, so NEWNYM and traffic-counter reads are no longer blocked for seconds during a refresh.
- Turning the map lookup off no longer mutates cached circuit data in place; the live circuit is re-read from Tor instead.
- `disconnect()` flips session state before closing resources, and Stop is safe to invoke at any time from the menu.

### Interface

- Stop Tor closes the control socket and any owned Tor process in the background, so terminating a slow process can no longer freeze the window.
- Menu shortcuts no longer clash with conventional Save/Cut bindings: Start Tor is Ctrl+T and Stop Tor is Ctrl+Shift+T.
- Diagnostics report lines wrap instead of overflowing horizontally, and plain result lines are dark; they were nearly invisible white-on-white before.
- Dashboard terminal uses consistent `[x]` error prefixes and a readable default color for unknown levels.
- The browser address bar no longer resets while the user is typing; the Reload button doubles as Stop during a page load; localhost/127.0.0.1 addresses navigate instead of triggering a web search; the BBC quick link uses the canonical www host.
- The Network Monitor chart legend colors now match the download/upload series; the About page guards against a missing logo file; window close stops the circuit retry timer before pages are destroyed.

### Installer

- The system installer verifies `README.md` before staging; it staged the file but previously did not check for it.
- New `disable-autostart.sh` removes the login autostart entry for users who do not want Red Tor to open by itself at login. The app, notes and settings are not touched.

### 3D interface and animations

- New `gui/animations.py`: every sidebar page switch now animates with a fade plus a 14 px slide lift (230 ms, OutCubic easing). Rapid clicking cannot stack effects — each new transition stops the previous one and removes its graphics effect when it finishes, so repaints stay fast.
- Dashboard cards and the primary "Connect to Tor" button get soft drop shadows (`apply_depth_effects`), giving the layout real depth; effects are applied only to cheap-to-repaint surfaces (the world-map canvas and charts never get one, so their timer-driven repaints are unaffected).
- The primary CTA is now a raised red-gradient pill with a glowing bottom edge that visibly sinks when pressed; all buttons have gradient surfaces with a darker bottom border and a press-in state.
- New pulsing status light in the header: red while Tor is off, amber while connecting, green when verified — it breathes via a QPropertyAnimation instead of blinking.
- New rotating-arc spinner appears next to the Tor status while a connection attempt runs, and stops the moment the attempt finishes.
- Circuit changes animate: the path card lifts and fades when NEWNYM or a refresh produces a new circuit, so a rebuilt path reads as new.
- Progress-bar chunks and sidebar nav items use gradients with hover indentation for a more tactile feel.

### Browser privacy and site compatibility

- Browser DNS now resolves inside Tor: Chromium is pinned with `--host-resolver-rules="MAP * ~NOTFOUND , EXCLUDE 127.0.0.1"`, so no hostname ever touches the system or ISP resolver. Previously Chromium used `socks5://` with local DNS, which is why many blocked or DNS-poisoned sites failed to load even though Tor was connected. This is the same recipe Tor Browser uses.
- DNS-over-HTTPS is disabled (`--disable-features=DnsOverHttps`), so the engine cannot bypass the Tor-only resolution path; QUIC/UDP was already disabled.
- Chromium components no longer phone home outside the proxy: background networking, component updates, default apps, sync, hyperlink pings, crash reporting (Breakpad) and the media router are all disabled.
- The user agent no longer leaks the `QtWebEngine/x.y` token (it is stripped at runtime while keeping the real Chrome engine version, with a safe fallback). Many CDNs bot-check or block that token outright, which broke otherwise reachable sites. Accept-Language is fixed to `en-US,en;q=0.5` like Tor Browser, so the system locale does not leak through content negotiation.
- Existing protections are unchanged: off-the-record profile, no persistent cookies, no third-party cookies, and the request gate that blocks every browser request unless a verified Tor session is live.

### Layout: nothing clipped, nothing squeezed, everything scrolls

- Settings: the page now scrolls instead of compressing. At small window heights the plain layout squeezed labels until their text overlapped the exit-country combo box and the verification checkboxes, which read as garbled doubled lines.
- Network Monitor: wrapped in a scroll area — the right-side stat boxes ("Source totals", "Data source") and the chart legend were clipped beyond the window edge at the 1024 px minimum width.
- Local Notes: wrapped in a scroll area — the "Local Draft Safety" card at the bottom was unreachable below ~700 px window height.
- Dashboard and Tor Connection: horizontal scrollbars are now shown when needed instead of silently clipping content — the fourth stat card ("Session time"), the Quick Tools buttons and the map controls were cut off with no way to reach them.
- Dashboard stat cards, chart header and rate badge use slimmer padding and word wrapping so all four cards fit at the default window size; the transfer-rate header no longer forces the page 230 px wider than the window.
- About: the contact links, technical-information values, credits list and footer now wrap, so the page no longer needs 830 px of width (109 px of it was previously cut off at minimum width).
- A programmatic layout audit now runs over all 10 pages at the minimum window size: no page is vertically compressed (the text-overlap cause) and nothing is clipped without a reachable scrollbar; at the default 1280×740 size no page needs horizontal scrolling at all.

### Faster startup

- The splash screen now appears immediately: the heavy import chain (QtWebEngine inside the Browse tab) runs while the splash is already on screen instead of before it, so the wait to an interactive window feels like ~2 seconds instead of a long blank delay.

### Verification

- Offline unit tests: **38 passed** (the previous 28 plus 10 new regression tests covering these fixes: settings validation, byte counters, control-socket close on auth failure, distinct-circuit counting, session teardown, bootstrap-wait before SOCKS verification, and stuck-bootstrap guidance). Python compilation and shell syntax checks pass for every source and script. The GUI was smoke-tested offscreen: all 10 pages render, rapid page switching leaves no leaked graphics effects, and the status light, spinner and shadows render correctly.

## v1.0.1 — runtime and installer fixes

- Rebranded the desktop app, command, menu entry, icon and autostart entry to Red Tor, using the user's supplied red logo.
- Removed unused privileged routing/firewall UI, hidden Inbox/Landing pages, inert bridge/security-level state, demo-mode wording and synthetic message handling. Local Notes are offline-only and are never linked to a Tor circuit.
- Replaced timed fake boot percentage with animated progress tied to completed UI initialization phases. The splash distinguishes UI startup from Tor bootstrap; the app does not auto-connect.
- Circuit/stream/map, exit-IP checks and traffic counters use real Tor control/SOCKS data when available. No fallback creates fake circuits, destinations or rates. GeoIP positions are approximate estimates.
- Fixed the Debian/Ubuntu installer to install the separate QtSvg package, validate using the system Tor defaults file, and create the permanent `/opt/red-tor` install, launcher, desktop entry and invoking user's login autostart.
- Fixed missing palette imports in Diagnostics, Privacy Tools and Full Map. Fixed browser shutdown so the view/page is destroyed before its off-the-record profile, removing the WebEngine teardown warning in the tested close path.

## Verification

- Offline unit tests: **28 passed**. Python compilation and shell syntax checks pass.
- `sudo bash install.sh` completed in an isolated Ubuntu 24.04 ARM64 sandbox: distro dependencies installed, Tor config verified with the service defaults, venv import check passed, and launcher/menu/login-autostart files were created.
- Offscreen Qt/WebEngine smoke test passed using the installed `/opt/red-tor` environment: all 10 pages constructed, startup phases reached 100%, Tor remained disconnected, and browser page/profile were deleted cleanly on close without the profile warning.
- **Live Tor bootstrap was not verified:** the app-owned daemon reached only 10–14% in this sandbox and relay TLS handshakes ended with unexpected EOFs. No exit IP or circuit was claimed. Test on the target Linux network to verify Tor reachability; this sandbox result does not prove the user's network is blocked.

## Limitations

Red Tor is not Tor Browser and has not had a security audit. It does not protect the rest of the system, does not provide a system firewall kill switch, does not compare direct public IPs or test DNS leaks, and does not transmit Local Notes. GeoIP positions are estimates, not exact server locations or physical packet routes. The system installer was exercised on Ubuntu 24.04 ARM64, not on the user's Kali installation. A project-wide license has not been selected; choose an owner-approved license before public redistribution.
