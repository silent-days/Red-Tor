"""
Red Tor - local Tor integration and app data helpers.
Diagnostics verify a Tor-routed request only; they do not test IP/DNS leaks.

Linux-only by design.
"""
import os
import sys
import socket
import ipaddress
import re
import time
import json
import shutil
import threading
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Optional, List, Dict, Tuple, Callable
from urllib.parse import urlsplit

if not sys.platform.startswith("linux"):
    raise RuntimeError("Red Tor is a Linux-only tool. Detected: " + sys.platform)

try:
    from stem import Signal
    from stem.control import Controller
    STEM_AVAILABLE = True
except Exception:
    STEM_AVAILABLE = False
    Controller = None

try:
    import requests
    REQUESTS_AVAILABLE = True
except Exception:
    REQUESTS_AVAILABLE = False

try:
    import geoip2.database
    GEOIP_AVAILABLE = True
except Exception:
    GEOIP_AVAILABLE = False


# ---- Defaults ----
TOR_CONTROL_PORT = 9051
TOR_SOCKS_PORT = 9050
TOR_CONTROL_HOST = "127.0.0.1"
TOR_SOCKS_HOST = "127.0.0.1"

TOR_PROXIES = {
    "http":  f"socks5h://{TOR_SOCKS_HOST}:{TOR_SOCKS_PORT}",
    "https": f"socks5h://{TOR_SOCKS_HOST}:{TOR_SOCKS_PORT}",
}
CONTROL_PORT_REPAIR_HINT = (
    "Circuit paths, NEWNYM and exit-country controls need ControlPort 127.0.0.1:9051. "
    "On Debian-family Linux, rerun the updated source installer with 'sudo bash install.sh' "
    "and log out/in afterward so tor-cookie group membership takes effect."
)


def _tor_state_paths() -> Tuple[str, str, str]:
    """Return private Red Tor runtime paths, migrating legacy Tor data once."""
    home = os.path.expanduser("~")
    data_home = os.environ.get("XDG_DATA_HOME", os.path.join(home, ".local", "share"))
    state_home = os.environ.get("XDG_STATE_HOME", os.path.join(home, ".local", "state"))
    state_dir = os.path.join(state_home, "red-tor")
    data_dir = os.path.join(state_dir, "tor-data")
    log_dir = state_dir
    legacy_data = os.path.join(data_home, "silent-tor", "tor-data")
    legacy_log = os.path.join(state_home, "silent-tor", "tor.log")
    os.makedirs(state_dir, mode=0o700, exist_ok=True)
    if not os.path.exists(data_dir) and os.path.isdir(legacy_data):
        shutil.copytree(legacy_data, data_dir)
        os.chmod(data_dir, 0o700)
    log_path = os.path.join(log_dir, "tor.log")
    if not os.path.exists(log_path) and os.path.isfile(legacy_log):
        shutil.copy2(legacy_log, log_path)
        os.chmod(log_path, 0o600)
    return state_dir, data_dir, log_dir


def parse_stream_target(target: str) -> Optional[Dict]:
    """Parse Tor's controller-reported target endpoint without resolving it."""
    text = str(target or "").strip()
    if not text or any(ord(ch) < 33 for ch in text):
        return None
    if text.startswith("["):
        end = text.find("]")
        if end < 0 or text[end + 1:end + 2] != ":":
            return None
        host, port_text = text[1:end], text[end + 2:]
    else:
        host, separator, port_text = text.rpartition(":")
        if not separator:
            return None
    if not port_text.isdigit() or len(port_text) > 5 or not host:
        return None
    port = int(port_text)
    if not (1 <= port <= 65535):
        return None
    try:
        host = ipaddress.ip_address(host).compressed
    except ValueError:
        try:
            host = host.rstrip(".").encode("idna").decode("ascii").lower()
        except UnicodeError:
            return None
        labels = host.split(".")
        if (len(host) > 253 or not labels or any(
                not label or len(label) > 63 or
                not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?", label)
                for label in labels)):
            return None
    display_host = f"[{host}]" if ":" in host else host
    return {"host": host, "port": port,
            "display": f"{display_host}:{port}"}

EXIT_COUNTRIES = [
    ("--", "Auto (any country)"),
    ("us", "United States"),
    ("de", "Germany"),
    ("nl", "Netherlands"),
    ("fr", "France"),
    ("se", "Sweden"),
    ("ch", "Switzerland"),
    ("ro", "Romania"),
    ("ca", "Canada"),
    ("gb", "United Kingdom"),
    ("is", "Iceland"),
    ("jp", "Japan"),
    ("au", "Australia"),
    ("ru", "Russia"),
    ("sg", "Singapore"),
    ("fi", "Finland"),
    ("no", "Norway"),
    ("cz", "Czech Republic"),
    ("es", "Spain"),
    ("it", "Italy"),
    ("ua", "Ukraine"),
    ("at", "Austria"),
    ("be", "Belgium"),
    ("pl", "Poland"),
    ("tr", "Turkey"),
    ("br", "Brazil"),
    ("in", "India"),
    ("hk", "Hong Kong"),
]

# Headers that fingerprint the browser. The Browse tab scrubs these
# from outbound requests via a request interceptor.
FINGERPRINT_HEADERS = [
    "user-agent", "accept-language", "accept-encoding",
    "x-forwarded-for", "x-real-ip", "via",
    "forwarded", "true-client-ip", "cf-connecting-ip",
]


# =========================================================================
# TorManager - local Tor connection and live control data
# =========================================================================
class TorManager:
    """High-level Tor control with activity events and traffic stats."""

    def __init__(self):
        self.controller: Optional[Controller] = None
        self.tor_process = None
        self.connected = False
        self.socks_only = False
        self.current_circuit: Optional[Dict] = None
        self.exit_country = "--"
        self._lock = threading.Lock()
        self.tor_binary = self._find_tor_binary()
        self.last_error = ""
        self.control_port_error = ""
        self.last_ip_check_error = ""
        self._listeners: List[Callable[[str, str], None]] = []
        self.bytes_sent = 0
        self.bytes_received = 0
        self.requests_count = 0
        self.circuits_built = 0
        self._last_circuit_id = None
        self._relay_geo_cache = {}
        self._geo_cache_lock = threading.Lock()
        self._relay_geo_failed_at = {}
        saved = load_settings()
        allowed_countries = {code for code, _name in EXIT_COUNTRIES}
        saved_country = saved.get("default_exit", "--")
        self.exit_country = saved_country if saved_country in allowed_countries else "--"
        self.map_lookup_enabled = bool(saved.get("map_lookup_enabled", True))
        self.destination_geolocation_enabled = bool(saved.get("destination_geolocation_enabled", False))
        self._destination_geo_cache = {}
        self.auto_check_exit_ip = bool(saved.get("auto_check_exit_ip", True))

    # ---- Event system ----
    def add_listener(self, fn: Callable[[str, str], None]):
        self._listeners.append(fn)

    def remove_listener(self, fn: Callable[[str, str], None]):
        """Detach a listener so destroyed widgets stop receiving events."""
        try:
            self._listeners.remove(fn)
        except ValueError:
            pass

    def _emit(self, level: str, message: str):
        for fn in self._listeners:
            try:
                fn(level, message)
            except Exception:
                pass

    # ---- Tor binary ----
    def _find_tor_binary(self) -> Optional[str]:
        for path in ["/usr/bin/tor", "/usr/local/bin/tor", "/usr/sbin/tor"]:
            if os.path.exists(path):
                return path
        try:
            r = subprocess.run(["which", "tor"], capture_output=True, text=True)
            if r.returncode == 0 and r.stdout.strip():
                return r.stdout.strip()
        except Exception:
            pass
        return None

    def is_tor_installed(self) -> bool:
        return self.tor_binary is not None

    # ---- Connection ----
    def connect(self, control_port: int = TOR_CONTROL_PORT,
                password: str = "", _retries: int = 0) -> Tuple[bool, str]:
        """Connect to a real local Tor control port; never report demo as live."""
        self.last_error = ""
        self.control_port_error = ""
        control_authenticated = False
        self.socks_only = False
        self._emit("INFO", f"Connecting to Tor (control port {control_port})...")
        if not STEM_AVAILABLE:
            self.connected = False
            self.last_error = "Python Stem is missing. Install python3-stem."
            return False, self.last_error
        controller = None
        try:
            controller = Controller.from_port(address=TOR_CONTROL_HOST, port=control_port)
            if password:
                controller.authenticate(password=password)
            else:
                controller.authenticate()
            control_authenticated = True
            # A Tor daemon that just booted (or one behind a slow/censored
            # network) accepts control connections long before it can carry
            # traffic. Wait for bootstrap before declaring SOCKS broken.
            self._emit("INFO", "Control port authenticated; waiting for Tor bootstrap before SOCKS verification...")
            bootstrap_report = self._wait_for_bootstrap(controller)
            socks_ok, socks_msg = self._verify_existing_socks()
            if not socks_ok:
                controller.close()
                raise RuntimeError(
                    "Control port authenticated but SOCKS verification failed: "
                    f"{socks_msg}{self._socks_failure_hint(bootstrap_report)}")
            self.controller = controller
            self.connected = True
            self.last_error = ""
            self.control_port_error = ""
            if self.exit_country != "--":
                ok, msg = self.set_exit_country(self.exit_country)
                if not ok:
                    self._emit("WARN", f"Saved exit-country preference was not applied: {msg}")
            self._emit("OK", f"Authenticated to Tor control port {control_port}.")
            self.refresh_circuit()
            return True, f"Connected to Tor control port {control_port}."
        except Exception as e:
            self.control_port_error = str(e)
            self.last_error = str(e)
            self._emit("WARN", f"Control port connection failed: {e}")
            if controller is not None and not control_authenticated:
                # authenticate() raised after from_port(); close the half-open
                # control socket so it does not leak.
                try:
                    controller.close()
                except Exception:
                    pass
            if control_authenticated:
                self.connected = False
                self.controller = None
                self.current_circuit = None
                return False, (
                    f"Tor control authenticated but SOCKS verification failed. "
                    f"No second Tor process was started. {e}")
            if _retries == 0:
                # A packaged Tor service commonly already owns SOCKS 9050 but
                # has no ControlPort. Verify the SOCKS endpoint as Tor before
                # ever trying to launch a second process on the same port.
                socks_ok, socks_msg = self._verify_existing_socks()
                if socks_ok:
                    self.connected = True
                    self.socks_only = True
                    self.controller = None
                    self.current_circuit = None
                    self.last_error = ""
                    self._emit("OK", "Verified the existing Tor SOCKS service. " + CONTROL_PORT_REPAIR_HINT)
                    return True, socks_msg + ". " + CONTROL_PORT_REPAIR_HINT
                if self.is_tor_installed():
                    self._emit("INFO", "No verified Tor SOCKS service found; starting a private Tor client...")
                    started, detail = self._start_tor()
                    if started:
                        return self.connect(control_port, password, _retries + 1)
                    self.last_error = detail
                    if socks_msg:
                        self.last_error += f" Existing SOCKS check: {socks_msg}"
            elif _retries > 0:
                _, _, log_dir = _tor_state_paths()
                log_path = os.path.join(log_dir, "tor.log")
                try:
                    with open(log_path, "r", errors="replace") as f:
                        tail = "".join(f.readlines()[-12:]).strip()
                    if tail:
                        self.last_error = f"{e}. Tor log: {tail[-1800:]}"
                except OSError:
                    pass
                self._stop_owned_tor()
            self.connected = False
            self.current_circuit = None
            self._emit("ERROR", "Tor unavailable. No synthetic circuit or route data was created.")
            if not self.is_tor_installed():
                return False, f"Could not connect to Tor ({e}). Tor is not installed. Install the Tor service and retry."
            return False, f"Could not connect to Tor control port {control_port}: {self.last_error}"

    @staticmethod
    def _request_bytes_sent(response) -> int:
        """Best-effort outbound size (request line + headers + body) in bytes."""
        try:
            request = getattr(response, "request", None)
            if request is None:
                return 0
            total = len((getattr(request, "method", "GET") + " " + str(request.url)
                         + " HTTP/1.1\r\n").encode("utf-8", "replace"))
            for header, value in (getattr(request, "headers", None) or {}).items():
                total += len(f"{header}: {value}\r\n".encode("utf-8", "replace"))
            body = getattr(request, "body", None)
            if body:
                total += len(body if isinstance(body, bytes)
                             else str(body).encode("utf-8", "replace"))
            return total
        except Exception:
            return 0

    def _track_transfer(self, response):
        """Record one completed Tor-proxied request's outbound/inbound sizes."""
        try:
            self.bytes_sent += self._request_bytes_sent(response)
            self.bytes_received += len(getattr(response, "content", None) or b"")
        except Exception:
            pass

    def _wait_for_bootstrap(self, controller, timeout: float = 75.0) -> str:
        """Wait until Tor reports bootstrap progress 100 (or the deadline).

        Returns the last observed bootstrap-phase report ("" when Tor does not
        expose it). Never touches the network directly.
        """
        deadline = time.monotonic() + timeout
        last = ""
        while time.monotonic() < deadline:
            try:
                report = str(controller.get_info("status/bootstrap-phase") or "")
            except Exception:
                # Unsupported or transiently unavailable: let SOCKS checks decide.
                return last
            match = re.search(r"PROGRESS=(\d+)", report)
            progress = int(match.group(1)) if match else 0
            if progress >= 100:
                return report
            if report != last:
                summary = ""
                idx = report.find("SUMMARY=")
                if idx >= 0:
                    summary = report[idx + len("SUMMARY="):].strip().strip('"')[:60]
                self._emit("INFO", f"Tor bootstrap: {progress}%"
                           + (f" ({summary})" if summary else ""))
                last = report
            if self.tor_process is not None and self.tor_process.poll() is not None:
                # The Tor process we launched has exited; surface it now.
                return last
            time.sleep(0.5)
        return last

    @staticmethod
    def _socks_failure_hint(bootstrap_report: str) -> str:
        """Human guidance for a SOCKS verification that failed after auth."""
        phase = ""
        if bootstrap_report:
            idx = bootstrap_report.find("SUMMARY=")
            if idx >= 0:
                phase = bootstrap_report[idx + len("SUMMARY="):].strip().strip('"')
        if phase and "done" not in phase.lower():
            progress_match = re.search(r"PROGRESS=(\d+)", bootstrap_report)
            percent = (progress_match.group(1) + "% ") if progress_match else ""
            return (" Guidance: Tor bootstrap is still at " + percent + "'" + phase[:60] + "'. "
                    "Check your internet connection; on a censored network "
                    "configure Tor bridges in torrc, wait a minute, then retry.")
        return (" Guidance: Tor may still be building circuits (slow or censored "
                "networks can need several minutes). Check your internet "
                "connection and press Connect again in a minute.")

    def _verify_existing_socks(self, attempts: int = 3,
                               per_attempt_timeout: int = 12) -> Tuple[bool, str]:
        """Verify the configured SOCKS endpoint is a real Tor exit, fail closed.

        A booting Tor daemon needs circuits before any request succeeds, so a
        transient failure is retried instead of hard-failing immediately.
        """
        if not REQUESTS_AVAILABLE:
            return False, "Python requests is unavailable."
        last_error = ""
        for attempt in range(1, attempts + 1):
            try:
                response = requests.get(
                    "https://check.torproject.org/api/ip",
                    proxies=TOR_PROXIES, timeout=per_attempt_timeout)
                response.raise_for_status()
                self._track_transfer(response)
                data = response.json()
                if data.get("IsTor") is True:
                    observed = data.get("IP", "")
                    return True, ("Connected through the existing Tor SOCKS service"
                                  + (f" (exit IP {observed})" if observed else "")
                                  + ". Control-port circuit management is unavailable.")
                last_error = "SOCKS endpoint did not verify as a Tor exit."
            except Exception as e:
                last_error = f"Could not verify SOCKS endpoint: {e}"
            if attempt < attempts:
                self._emit("INFO", (
                    f"SOCKS verification attempt {attempt} of {attempts} failed "
                    f"({last_error}). Tor may still be building circuits; retrying..."))
                time.sleep(3)
        return False, last_error

    def _start_tor(self) -> Tuple[bool, str]:
        """Launch Tor without root and wait until its control listener is reachable."""
        log_file = None
        try:
            if not self.tor_binary:
                return False, "Tor executable was not found. Install the tor package."
            state_dir, data_dir, log_dir = _tor_state_paths()
            os.makedirs(data_dir, mode=0o700, exist_ok=True)
            os.makedirs(log_dir, mode=0o700, exist_ok=True)
            os.chmod(data_dir, 0o700)
            os.chmod(log_dir, 0o700)
            log_path = os.path.join(log_dir, "tor.log")
            fd = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
            log_file = os.fdopen(fd, "a", buffering=1)
            cmd = [self.tor_binary,
                   "--ControlPort", f"{TOR_CONTROL_HOST}:{TOR_CONTROL_PORT}",
                   "--SocksPort", f"{TOR_SOCKS_HOST}:{TOR_SOCKS_PORT}",
                   "--DataDirectory", data_dir,
                   "--CookieAuthentication", "1",
                   "--Log", "notice stdout"]
            self.tor_process = subprocess.Popen(
                cmd, stdout=log_file, stderr=subprocess.STDOUT, close_fds=True)
            self._tor_log_handle = log_file
            log_file = None  # owned by manager until disconnect
            self._emit("INFO", f"Tor process started; waiting for 127.0.0.1:{TOR_CONTROL_PORT} (log: {log_path})")
            deadline = time.monotonic() + 25
            while time.monotonic() < deadline:
                if self.tor_process.poll() is not None:
                    break
                try:
                    with socket.create_connection((TOR_CONTROL_HOST, TOR_CONTROL_PORT), timeout=0.3):
                        self._emit("OK", "Tor control listener is ready.")
                        return True, "Tor control listener ready."
                except OSError:
                    time.sleep(0.25)
            try:
                with open(log_path, "r", errors="replace") as f:
                    tail = "".join(f.readlines()[-12:]).strip()
            except OSError:
                tail = ""
            code = self.tor_process.poll()
            self._stop_owned_tor()
            reason = f"Tor exited with status {code}." if code is not None else "Tor control listener did not become ready within 25 seconds."
            if tail:
                reason += " Tor log: " + tail[-1800:]
            return False, reason
        except Exception as e:
            self._stop_owned_tor()
            return False, f"Unable to launch Tor: {e}"
        finally:
            if log_file:
                log_file.close()

    def _stop_owned_tor(self):
        proc = self.tor_process
        self.tor_process = None
        if proc and proc.poll() is None:
            try:
                proc.terminate()
                proc.wait(timeout=5)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        handle = getattr(self, "_tor_log_handle", None)
        self._tor_log_handle = None
        if handle:
            try:
                handle.close()
            except Exception:
                pass

    def mark_disconnected(self):
        """Flag the session down immediately; resources close in disconnect()."""
        self.controller = None
        self.connected = False
        self.socks_only = False
        self.current_circuit = None
        self._last_circuit_id = None

    def disconnect(self):
        controller = self.controller
        self.mark_disconnected()
        try:
            if controller:
                controller.close()
        except Exception:
            pass
        self._stop_owned_tor()
        self._emit("INFO", "Tor disconnected.")

    # ---- Circuit ----
    def refresh_circuit(self) -> Dict:
        """Read live circuits and active stream targets from Tor's control port."""
        with self._lock:
            if self.connected and self.socks_only and not self.controller:
                self.current_circuit = None
                self._emit("WARN", "Circuit details are unavailable: the existing Tor service has no accessible control port.")
                return None
            if not self.controller:
                self.current_circuit = None
                return None

            try:
                circuits = [c for c in self.controller.get_circuits()
                            if c.status == "BUILT"
                            and getattr(c, "purpose", "GENERAL") == "GENERAL"
                            and len(getattr(c, "path", [])) >= 2]
                if not circuits:
                    self.current_circuit = None
                    self._emit("INFO", "No built general-purpose circuit is available yet.")
                    return None

                try:
                    streams = list(self.controller.get_streams())
                except Exception as stream_error:
                    streams = []
                    self._emit("WARN", f"Tor circuit is available, but stream targets could not be read: {stream_error}")
                stream_records = []
                active_statuses = {"SENTCONNECT", "SUCCEEDED"}
                for stream in streams:
                    status = str(getattr(stream, "status", "")).upper().rsplit(".", 1)[-1]
                    if status not in active_statuses:
                        continue
                    parsed = parse_stream_target(getattr(stream, "target", ""))
                    circ_id = str(getattr(stream, "circ_id", "0"))
                    if parsed and circ_id not in ("", "0"):
                        stream_records.append({**parsed, "status": status,
                                               "circuit_id": circ_id})
                active_ids = {item["circuit_id"] for item in stream_records}
                circuit = next((c for c in circuits if str(c.id) in active_ids), circuits[0])
                path = list(circuit.path)
            except Exception as e:
                self.last_error = str(e)
                self._emit("ERROR", f"Circuit refresh failed: {e}")
                self.current_circuit = None
                return None

        # GeoIP lookups hit the network; run them without the manager lock so
        # NEWNYM and traffic-counter reads are not blocked for many seconds.
        if self.map_lookup_enabled:
            with ThreadPoolExecutor(max_workers=min(3, max(1, len(path)))) as pool:
                locations = list(pool.map(lambda hop: self._geo_for_fp(hop[0]), path))
        else:
            locations = [self._geo_for_fp(hop[0]) for hop in path]

        nodes = []
        for i, ((fp, nickname), location) in enumerate(zip(path, locations)):
            position = ("Entry" if i == 0 else
                        "Exit" if i == len(path) - 1 else f"Hop {i + 1}")
            country, city, lat, lon = location
            nodes.append({
                "fingerprint": fp, "nickname": nickname,
                "country": country, "city": city,
                "lat": lat, "lon": lon,
                "position": position,
            })

        circuit_streams = [item for item in stream_records
                           if item["circuit_id"] == str(circuit.id)]
        # Prefer an established stream; otherwise show the pending Tor-reported target.
        stream_target = next((item for item in circuit_streams
                              if item["status"] == "SUCCEEDED"),
                             circuit_streams[0] if circuit_streams else None)
        if stream_target and self.destination_geolocation_enabled:
            cache_key = f"{stream_target['host']}:{stream_target['port']}"
            with self._geo_cache_lock:
                location = self._destination_geo_cache.get(cache_key)
            if location is None:
                location = self.lookup_destination(stream_target["host"])
                with self._geo_cache_lock:
                    self._destination_geo_cache[cache_key] = location
            stream_target = {**stream_target, "location": location}

        with self._lock:
            self.current_circuit = {
                "id": circuit.id, "nodes": nodes,
                "purpose": getattr(circuit, "purpose", "GENERAL"),
                "active_stream": bool(circuit_streams),
                "stream_targets": circuit_streams,
                "stream_target": stream_target,
                "built_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
            # Count distinct circuits, not refresh attempts.
            if str(circuit.id) != self._last_circuit_id:
                self._last_circuit_id = str(circuit.id)
                self.circuits_built += 1
        self._emit("OK", f"Live Tor circuit #{circuit.id} read from the control port.")
        return self.current_circuit

    def new_circuit(self) -> Dict:
        if not self.connected or not self.controller:
            self._emit("WARN", "Circuit rotation requires an authenticated Tor control port.")
            return None
        try:
            with self._lock:
                self.controller.signal(Signal.NEWNYM)
            self._emit("INFO", "NEWNYM requested. Tor may build a new circuit for the next stream.")
            time.sleep(0.5)
        except Exception as e:
            self.last_error = str(e)
            self._emit("ERROR", f"Tor circuit rotation request failed: {e}")
            return None
        return self.refresh_circuit()

    def set_exit_country(self, country_code: str) -> Tuple[bool, str]:
        if country_code not in {code for code, _name in EXIT_COUNTRIES}:
            return False, "Unsupported exit-country code."
        if self.socks_only and not self.controller:
            return False, "Exit-country selection requires Tor control-port access; this Tor service is SOCKS-only."
        if not self.controller:
            return False, "No live Tor control connection is available."
        try:
            with self._lock:
                if country_code == "--":
                    self.controller.set_conf("ExitNodes", "")
                    self.controller.set_conf("StrictNodes", "0")
                else:
                    self.controller.set_conf("ExitNodes", "{" + country_code + "}")
                    self.controller.set_conf("StrictNodes", "1")
                self.exit_country = country_code
            self._emit("INFO", f"Exit country preference set to: {country_code}")
            return True, f"Exit country set to {country_code}."
        except Exception as e:
            return False, f"Failed to set exit country: {e}"

    # Relays that returned no coordinates are not re-queried for this long.
    _GEO_FAILURE_RETRY_SECONDS = 600

    def _geo_for_fp(self, fingerprint: str) -> Tuple[str, str, float, float]:
        """Resolve public relay location from Tor Metrics via the verified Tor proxy.

        Onionoo reports GeoIP estimates, not a relay's physical server address.
        Only the relay's already-public fingerprint is sent to Tor Metrics.
        """
        with self._geo_cache_lock:
            cached = self._relay_geo_cache.get(fingerprint)
        if cached is not None:
            return cached
        unknown = ("??", "Location unavailable", None, None)
        with self._geo_cache_lock:
            failed_at = self._relay_geo_failed_at.get(fingerprint)
        if failed_at is not None and (time.monotonic() - failed_at) < self._GEO_FAILURE_RETRY_SECONDS:
            # A recent lookup already failed; do not hammer Tor Metrics on
            # every circuit refresh for relays without coordinates.
            return unknown
        result = unknown
        if not self.map_lookup_enabled:
            try:
                desc = self.controller.get_network_status(fingerprint)
                result = ((getattr(desc, "country", None) or "??").lower(),
                          "Location unavailable", None, None)
            except Exception:
                pass
            with self._geo_cache_lock:
                self._relay_geo_cache[fingerprint] = result
            return result
        try:
            if REQUESTS_AVAILABLE and self.connected:
                from urllib.parse import urlencode
                params = urlencode({
                    "lookup": fingerprint.replace(" ", ""),
                    "fields": "fingerprint,nickname,country,country_name,city_name,latitude,longitude",
                })
                response = requests.get(
                    "https://onionoo.torproject.org/details?" + params,
                    proxies=TOR_PROXIES, timeout=8)
                response.raise_for_status()
                relays = response.json().get("relays", [])
                relay = next((r for r in relays
                              if str(r.get("fingerprint", "")).replace(" ", "").upper()
                              == fingerprint.replace(" ", "").upper()), None)
                if relay:
                    city = relay.get("city_name") or relay.get("region_name") or "Location unavailable"
                    lat, lon = relay.get("latitude"), relay.get("longitude")
                    try:
                        lat, lon = float(lat), float(lon)
                        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                            lat, lon = None, None
                    except (TypeError, ValueError):
                        lat, lon = None, None
                    result = ((relay.get("country") or "??").lower(), city, lat, lon)
        except Exception:
            pass
        with self._geo_cache_lock:
            if result[2] is not None and result[3] is not None:
                self._relay_geo_cache[fingerprint] = result
                self._relay_geo_failed_at.pop(fingerprint, None)
            else:
                self._relay_geo_failed_at[fingerprint] = time.monotonic()
        return result

    # ---- Destination lookup ----
    def lookup_destination(self, host: str) -> Dict:
        """Look up a destination only through a verified Tor SOCKS proxy.
        Never resolve the user's target locally or retry it over direct internet.
        """
        raw_host = (host or "").strip()
        try:
            parsed = urlsplit(raw_host if "://" in raw_host else "//" + raw_host)
            host = parsed.hostname or ""
        except ValueError:
            host = ""
        result = {"host": host, "ip": "Unknown", "country": "Unknown",
                  "country_code": "--", "city": "Unknown", "lat": None,
                  "lon": None, "via_tor": False}
        if not host:
            result["error"] = "Enter a valid public hostname or IP address."
            return result
        try:
            address = ipaddress.ip_address(host)
            if not address.is_global:
                result["error"] = "Private, loopback and reserved IP addresses are not sent to the GeoIP provider."
                return result
            host = address.compressed
        except ValueError:
            try:
                host = host.rstrip(".").encode("idna").decode("ascii").lower()
            except UnicodeError:
                result["error"] = "Hostname could not be normalized safely."
                return result
            labels = host.split(".")
            if (len(host) > 253 or len(labels) < 2 or
                    any(not label or len(label) > 63 or
                        not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?", label)
                        for label in labels) or
                    host.endswith((".local", ".localhost", ".onion", ".test", ".invalid"))):
                result["error"] = "Enter a public domain or globally routable IP address."
                return result
        result["host"] = host
        if not (self.connected and REQUESTS_AVAILABLE):
            result["error"] = "A live Tor connection is required; no direct lookup was attempted."
            return result
        try:
            from urllib.parse import quote
            self.requests_count += 1
            r = requests.get("https://ipapi.co/" + quote(host, safe=".:") + "/json/",
                             proxies=TOR_PROXIES, timeout=15)
            r.raise_for_status()
            d = r.json()
            lat, lon = d.get("latitude"), d.get("longitude")
            try:
                lat, lon = float(lat), float(lon)
                if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                    lat, lon = None, None
            except (TypeError, ValueError):
                lat, lon = None, None
            result.update({"ip": d.get("ip", "Unknown"),
                           "country": d.get("country_name", "Unknown"),
                           "country_code": d.get("country", "--").lower(),
                           "city": d.get("city", "Unknown"),
                           "lat": lat, "lon": lon,
                           "via_tor": True})
            self._track_transfer(r)
            self._emit("OK", f"Destination lookup via Tor: {result['city']}, {result['country']}")
        except Exception as e:
            self.last_error = str(e)
            result["error"] = f"Tor-only lookup failed: {e}"
            self._emit("WARN", result["error"])
        return result
    def get_my_ip_via_tor(self) -> Optional[str]:
        self.last_ip_check_error = ""
        if not REQUESTS_AVAILABLE or not self.connected:
            self.last_ip_check_error = "A verified live Tor session and Requests are required."
            return None
        try:
            r = requests.get("https://check.torproject.org/api/ip",
                             proxies=TOR_PROXIES, timeout=15)
            r.raise_for_status()
            data = r.json()
            if data.get("IsTor") is not True:
                self.last_ip_check_error = "check.torproject.org did not confirm this request as a Tor exit."
                self._emit("WARN", self.last_ip_check_error)
                return None
            ip = data.get("IP")
            if not ip:
                self.last_ip_check_error = "check.torproject.org confirmed Tor but returned no IP address."
                self._emit("WARN", self.last_ip_check_error)
                return None
            self.requests_count += 1
            self._track_transfer(r)
            self._emit("OK", f"Exit IP via Tor: {ip}")
            return ip
        except Exception as exc:
            self.last_ip_check_error = f"Tor exit-IP request failed: {exc}"
            self._emit("WARN", self.last_ip_check_error)
            return None

    def fetch_url(self, url: str, timeout: int = 30) -> Tuple[bool, str]:
        if not REQUESTS_AVAILABLE:
            return False, "requests library not available"
        if not self.connected:
            return False, "Not connected to Tor. No request was attempted."
        try:
            r = requests.get(url, proxies=TOR_PROXIES, timeout=timeout)
            r.raise_for_status()
            self.requests_count += 1
            self._track_transfer(r)
            self._emit("OK", f"Fetched {url} via Tor ({len(r.content)} bytes).")
            return True, r.text[:5000]
        except Exception as e:
            self._emit("ERROR", f"Fetch failed for {url}: {e}")
            return False, str(e)

    # ---- Status ----
    def status(self) -> Dict:
        return {
            "connected": self.connected,
            "socks_only": self.socks_only,
            "tor_installed": self.is_tor_installed(),
            "tor_binary": self.tor_binary or "not found",
            "control_port": TOR_CONTROL_PORT,
            "socks_port": TOR_SOCKS_PORT,
            "exit_country": self.exit_country,
            "current_circuit": self.current_circuit,
            "last_error": self.last_error,
            "control_port_error": self.control_port_error,
            "bytes_sent": self.bytes_sent,
            "bytes_received": self.bytes_received,
            "requests_count": self.requests_count,
            "circuits_built": self.circuits_built,
        }

    def traffic_stats(self) -> Dict:
        return {
            "bytes_sent": self.bytes_sent,
            "bytes_received": self.bytes_received,
            "total": self.bytes_sent + self.bytes_received,
            "requests": self.requests_count,
            "circuits": self.circuits_built,
        }

    def daemon_traffic_stats(self) -> Dict:
        """Read Tor's daemon-wide byte counters when its control port permits it."""
        if self.connected and self.controller:
            try:
                with self._lock:
                    received = int(self.controller.get_info("traffic/read"))
                    sent = int(self.controller.get_info("traffic/written"))
                return {"bytes_received": received, "bytes_sent": sent,
                        "source": "tor-daemon", "available": True}
            except Exception as e:
                self._emit("WARN", f"Tor daemon traffic counters unavailable: {e}")
        if self.connected:
            return {"bytes_received": self.bytes_received, "bytes_sent": self.bytes_sent,
                    "source": "app-only", "available": True}
        return {"bytes_received": 0, "bytes_sent": 0,
                "source": "offline", "available": False}


SETTINGS_FILE = os.path.expanduser("~/.silent-tor/settings.json")


def load_settings() -> Dict:
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE) as f:
                saved = json.load(f)
            if isinstance(saved, dict):
                # A corrupt or hand-edited settings file must not crash startup.
                return saved
        except Exception:
            pass
    return {}


def save_settings(settings: Dict):
    directory = os.path.dirname(SETTINGS_FILE)
    os.makedirs(directory, mode=0o700, exist_ok=True)
    os.chmod(directory, 0o700)
    tmp = SETTINGS_FILE + ".tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(settings, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, SETTINGS_FILE)
        os.chmod(SETTINGS_FILE, 0o600)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


# =========================================================================
# Diagnostics - Tor-routed verification only
# =========================================================================
def run_leak_tests(tor: "TorManager") -> Dict:
    """Verify the Tor exit IP only; never make a direct-IP or DNS probe."""
    out = {
        "tor_ip": None,
        "real_ip": None,
        "tor_country": None,
        "real_country": None,
        "dns_leak": None,
        "dns_tested": False,
        "ip_leak": None,
        "ip_check_tested": False,
        "checks": [],
        "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    if not (tor.connected and REQUESTS_AVAILABLE):
        out["checks"].append("Tor check: NOT RUN (no verified live Tor connection).")
    else:
        try:
            out["tor_ip"] = tor.get_my_ip_via_tor()
            if out["tor_ip"]:
                out["checks"].append("Tor check: verified by check.torproject.org over HTTPS.")
                out["ip_check_tested"] = True
                out["checks"].append(f"Tor exit IP: {out['tor_ip']}")
                out["checks"].append("Your direct public IP was not queried or revealed by this check.")
            else:
                detail = getattr(tor, "last_ip_check_error", "")
                out["checks"].append(
                    "Tor check: " + (detail or "endpoint did not confirm this request came through Tor."))
        except Exception as e:
            out["checks"].append(f"Tor check: FAILED ({e}).")
    out["checks"].append("Direct-IP leak comparison: NOT TESTED (intentionally disabled).")
    out["checks"].append("DNS leak: NOT TESTED (no resolver-observation service configured).")
    out["checks"].append("No direct network request was made by this diagnostic.")
    return out
