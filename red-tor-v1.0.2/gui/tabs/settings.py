"""Advanced preferences that are actually applied by Red Tor."""
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QGroupBox, QComboBox, QCheckBox, QMessageBox

from gui.theme import CREAM_DARK, DARK_TEXT, MUTED, TEAL
from gui.scroll_wrap import wrap_in_scroll
from tor_core import EXIT_COUNTRIES, load_settings, save_settings


class SettingsTab(QWidget):
    def __init__(self, main_win):
        super().__init__()
        self.main_win = main_win
        self._build()
        self._load_saved()

    def _build(self):
        # Scroll instead of squeeze: at small window heights the plain
        # layout compressed labels until their text overlapped the combo
        # box and the checkbox rows, which read as garbled lines.
        content = wrap_in_scroll(self)
        outer = QVBoxLayout(content)
        outer.setContentsMargins(22, 20, 22, 20)
        outer.setSpacing(12)
        title = QLabel("Settings")
        title.setFont(QFont("Sans", 18, QFont.Bold))
        title.setStyleSheet(f"color: {TEAL};")
        outer.addWidget(title)
        intro = QLabel("Advanced app preferences. Only options that this build can apply are shown here; service-level bridge, authentication and torrc settings remain under your Linux Tor service.")
        intro.setWordWrap(True)
        intro.setStyleSheet(f"color: {MUTED}; background: {CREAM_DARK}; padding: 9px 12px;")
        outer.addWidget(intro)

        group = QGroupBox("Tor circuit preference")
        layout = QVBoxLayout(group)
        layout.addWidget(QLabel("Preferred exit country"))
        self.default_exit = QComboBox()
        for code, name in EXIT_COUNTRIES:
            self.default_exit.addItem(f"{name}  [{code.upper()}]", code)
        layout.addWidget(self.default_exit)
        self.status_note = QLabel("Applying an exit country requires an authenticated Tor control port. It does not guarantee a particular city or exit IP.")
        self.status_note.setWordWrap(True)
        self.status_note.setStyleSheet(f"color: {MUTED};")
        layout.addWidget(self.status_note)
        outer.addWidget(group)

        group = QGroupBox("Verification and map")
        options = QVBoxLayout(group)
        self.auto_ip = QCheckBox("Verify and show the Tor exit IP after connecting")
        self.auto_ip.setToolTip("Uses check.torproject.org over your Tor SOCKS connection. It never makes a direct-IP request.")
        options.addWidget(self.auto_ip)
        self.map_geo = QCheckBox("Load approximate relay locations from Tor Metrics over Tor")
        self.map_geo.setToolTip("Sends public relay fingerprints to Tor Metrics through the verified Tor proxy. It does not send your home IP.")
        options.addWidget(self.map_geo)
        self.destination_geo = QCheckBox("Geolocate active stream destination for the map (optional)")
        self.destination_geo.setToolTip("Off by default. When enabled, the current Tor-reported target hostname is sent to ipapi.co through Tor. No direct lookup is made.")
        options.addWidget(self.destination_geo)
        privacy_note = QLabel("Relay and destination coordinates are GeoIP estimates, not precise server addresses or physical packet routes. Destination geolocation is separately opt-in and discloses the active target hostname to ipapi.co through Tor.")
        privacy_note.setWordWrap(True)
        privacy_note.setStyleSheet(f"color: {MUTED};")
        options.addWidget(privacy_note)
        outer.addWidget(group)

        group = QGroupBox("Local Tor service endpoints")
        endpoints = QVBoxLayout(group)
        self.endpoint_note = QLabel(
            "SOCKS proxy: 127.0.0.1:9050\n"
            "Tor control port: 127.0.0.1:9051 (optional; required for circuit details and exit-country changes).\n"
            "If your Linux Tor service is SOCKS-only on Debian-family Linux, rerun the updated "
            "source installer with: sudo bash install.sh. It enables a loopback-only cookie-authenticated "
            "control port when missing. Log out and back in so cookie-group permissions apply. "
            "For a custom Tor service, configure ControlPort 127.0.0.1:9051 and CookieAuthentication 1; "
            "never expose the control port to a LAN or the internet.")
        self.endpoint_note.setWordWrap(True)
        self.endpoint_note.setStyleSheet(f"color: {DARK_TEXT};")
        endpoints.addWidget(self.endpoint_note)
        outer.addWidget(group)

        buttons = QHBoxLayout()
        buttons.addStretch()
        self.apply_btn = QPushButton("Save Preferences")
        self.apply_btn.setDefault(True)
        self.apply_btn.clicked.connect(self.apply_settings)
        buttons.addWidget(self.apply_btn)
        outer.addLayout(buttons)
        outer.addStretch(1)

    def _load_saved(self):
        settings = load_settings()
        code = settings.get("default_exit", "--")
        index = self.default_exit.findData(code)
        if index >= 0:
            self.default_exit.setCurrentIndex(index)
        self.auto_ip.setChecked(bool(settings.get("auto_check_exit_ip", True)))
        self.map_geo.setChecked(bool(settings.get("map_lookup_enabled", True)))
        self.destination_geo.setChecked(bool(settings.get("destination_geolocation_enabled", False)))
        self.main_win.tor.exit_country = self.default_exit.currentData()
        self.main_win.tor.auto_check_exit_ip = self.auto_ip.isChecked()
        self.main_win.tor.map_lookup_enabled = self.map_geo.isChecked()
        self.main_win.tor.destination_geolocation_enabled = self.destination_geo.isChecked()

    def apply_settings(self):
        tor = self.main_win.tor
        code = self.default_exit.currentData() or "--"
        settings = load_settings()
        settings.update({
            "default_exit": code,
            "auto_check_exit_ip": self.auto_ip.isChecked(),
            "map_lookup_enabled": self.map_geo.isChecked(),
            "destination_geolocation_enabled": self.destination_geo.isChecked(),
        })
        try:
            save_settings(settings)
        except Exception as exc:
            QMessageBox.warning(self, "Save Failed", f"Could not save preferences:\n{exc}")
            return

        tor.exit_country = code
        tor.auto_check_exit_ip = self.auto_ip.isChecked()
        geo_was_enabled = tor.map_lookup_enabled
        tor.map_lookup_enabled = self.map_geo.isChecked()
        if geo_was_enabled != tor.map_lookup_enabled:
            tor._relay_geo_cache.clear()
            tor._relay_geo_failed_at.clear()
        destination_geo_was_enabled = tor.destination_geolocation_enabled
        tor.destination_geolocation_enabled = self.destination_geo.isChecked()
        if destination_geo_was_enabled != tor.destination_geolocation_enabled:
            tor._destination_geo_cache.clear()
            if tor.controller:
                self.main_win.tor_panel.refresh_circuit_async()
        if not tor.map_lookup_enabled:
            if tor.connected and tor.controller:
                # Re-read the live circuit with lookups disabled instead of
                # mutating the cached circuit data in place.
                self.main_win.tor_panel.refresh_circuit_async()
        elif not geo_was_enabled and tor.controller:
            self.main_win.tor_panel.refresh_circuit_async()

        message = "Preferences saved."
        if tor.controller is not None:
            ok, detail = tor.set_exit_country(code)
            if not ok:
                QMessageBox.warning(self, "Exit Country Not Applied", f"Preference saved locally, but Tor rejected the live setting:\n{detail}")
                return
            self.main_win.tor_panel.new_circuit()
            message += " Exit-country preference applied; Tor was asked to use a new circuit."
        elif code != "--":
            message += " Exit-country preference is stored locally and needs an authenticated Tor control port."
        QMessageBox.information(self, "Saved", message)

    def refresh(self):
        if self.main_win.tor.controller is None:
            self.status_note.setText("Tor control port unavailable. Exit-country preferences are stored locally but cannot be applied to this service.")
        else:
            self.status_note.setText("Tor control port available. The chosen country can be applied; Tor may still select another relay if the preference cannot be met.")
