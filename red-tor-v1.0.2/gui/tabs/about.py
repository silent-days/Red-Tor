"""Red Tor - About tab."""
import os
import sys
from PyQt5.QtCore import Qt, PYQT_VERSION_STR, QT_VERSION_STR
from PyQt5.QtGui import QFont, QPixmap
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGroupBox, QGridLayout,
    QScrollArea, QFrame,
)

from gui.theme import (
    CREAM, CREAM_LIGHT, CREAM_DARK, TAN, TAN_DARK, DARK_TEXT, MUTED,
    PURPLE, PURPLE_DARK, PURPLE_LIGHT, PURPLE_PALE, TEAL, VIOLET_DARK,
)
from gui import ASSETS
from tor_core import STEM_AVAILABLE
import matplotlib


class AboutTab(QWidget):
    def __init__(self, main_win):
        super().__init__()
        self.main_win = main_win
        self._build()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 20, 20, 20)
        outer.setSpacing(10)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        outer.addWidget(scroll, 1)

        inner = QWidget()
        scroll.setWidget(inner)
        v = QVBoxLayout(inner)
        v.setSpacing(12)

        title = QLabel("About Red Tor")
        title.setFont(QFont("Sans", 18, QFont.Bold))
        title.setStyleSheet(f"color: {VIOLET_DARK};")
        v.addWidget(title)

        # Header
        h = QHBoxLayout()
        logo = QLabel()
        logo_path = os.path.join(ASSETS, "logo.png")
        if os.path.exists(logo_path):
            pix = QPixmap(logo_path).scaled(
                100, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            logo.setPixmap(pix)
        info_box = QVBoxLayout()
        name = QLabel("<b>Red Tor</b>  v1.0.2")
        name.setTextFormat(Qt.RichText)
        name.setFont(QFont("Sans", 12))
        name.setStyleSheet(f"color: {DARK_TEXT};")
        tagline = QLabel("Desktop interface for a local Tor service")
        tagline.setStyleSheet(f"color: {MUTED};")
        built = QLabel("Tor · Stem · PyQt5 · QtWebEngine · Matplotlib")
        built.setStyleSheet(f"color: {MUTED}; font-size: 9pt;")
        industry = QLabel("<b>Built by Silent Days industry</b>")
        industry.setTextFormat(Qt.RichText)
        industry.setStyleSheet(
            f"color: {PURPLE_DARK}; font-weight: 700; font-size: 11pt;")
        info_box.addWidget(name)
        info_box.addWidget(tagline)
        info_box.addWidget(built)
        info_box.addWidget(industry)
        h.addWidget(logo)
        h.addLayout(info_box)
        h.addStretch()
        v.addLayout(h)

        # Description
        desc = QGroupBox("What is Red Tor?")
        dl = QVBoxLayout(desc)
        desc_text = QLabel(
            "Red Tor is a desktop interface for a local Tor service, designed "
            "for Kali Linux (Debian family). "
            "It verifies the configured SOCKS endpoint and configures its Chromium "
            "view to use that proxy. It is not Tor Browser and has not had a security audit. "
            "Other apps and system traffic are outside Red Tor's control.\n\n"
            "The circuit view uses Tor control-port data when authenticated access exists. "
            "Relay locations are approximate GeoIP estimates. Diagnostics make a Tor-routed "
            "HTTPS check only; direct-IP comparisons and DNS leak tests are not implemented. "
            "If Tor is unavailable, the app reports no verified route and sends no diagnostic request."
        )
        desc_text.setWordWrap(True)
        desc_text.setTextFormat(Qt.RichText)
        dl.addWidget(desc_text)
        v.addWidget(desc)

        # Features
        feat = QGroupBox("Key Features")
        fl = QVBoxLayout(feat)
        features = [
            ("Tor service connection", "Control-port login plus Tor SOCKS verification"),
            ("Built-in browser", "Chromium configured for SOCKS; not Tor Browser"),
            ("Session-only profile", "No persistent cookies or disk cache"),
            ("Circuit view", "Available when authenticated control-port access exists"),
            ("Exit-country preference", "Requires Tor control-port access"),
            ("Destination lookup", "Optional public-target GeoIP request to ipapi.co through Tor"),
            ("Diagnostics", "Tor request check only; no direct IP or DNS leak test"),
            ("App-session disconnect", "Disconnects this app only; other apps are unaffected"),
            ("Network Monitor", "Tor-daemon counters when available; otherwise app-only request counts"),
            ("Transfer Stats", "Measured app-request rate chart on its own page"),
            ("Terminal", "Kali-style root terminal: commands run on this system as root"),
            ("Privacy Tools", "Session wipe, new identity, loopback port probe, exit-country control"),
            ("Linux desktop", "See README for install requirements and limitations"),
        ]
        for f, d in features:
            row = QHBoxLayout()
            check = QLabel("[+]")
            check.setStyleSheet(f"color: {TEAL}; font-weight: bold;")
            check.setFixedWidth(28)
            lbl = QLabel(f"<b>{f}</b>  -  <span style='color:{MUTED};'>{d}</span>")
            lbl.setTextFormat(Qt.RichText)
            lbl.setWordWrap(True)
            row.addWidget(check)
            row.addWidget(lbl, 1)
            fl.addLayout(row)
        v.addWidget(feat)

        # Silent Days industry contact
        sd = QGroupBox("Built by Silent Days industry")
        sdl = QGridLayout(sd)
        sdl.setHorizontalSpacing(20)
        sdl.setVerticalSpacing(8)
        contacts = [
            ("GitHub:",   "https://github.com/silent-days"),
            ("Email:",    "silentdayscyber@gmail.com"),
            ("WhatsApp:", "https://whatsapp.com/channel/0029Vb9LSr2BvvsXIrrx9z01"),
            ("Website:",  "https://silentdays-kf5rhbbk.manus.space/"),
        ]
        for i, (k, val) in enumerate(contacts):
            k_lbl = QLabel(k)
            k_lbl.setStyleSheet(f"color: {DARK_TEXT}; font-weight: 600;")
            v_lbl = QLabel(val)
            v_lbl.setStyleSheet(f"color: {TEAL};")
            v_lbl.setWordWrap(True)
            v_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
            sdl.addWidget(k_lbl, i, 0)
            sdl.addWidget(v_lbl, i, 1)
        v.addWidget(sd)

        # Privacy notice
        disc = QGroupBox("Privacy & Legal Notice")
        dl2 = QVBoxLayout(disc)
        disc_text = QLabel(
            "Red Tor is an un-audited desktop interface, not a hardened anonymity product. "
            "Tor does not make a user immune to traffic analysis, unsafe browser behavior, "
            "or mistakes in operational security. Do not use this app as the sole protection "
            "for high-risk activity or life-critical anonymity."
        )
        disc_text.setWordWrap(True)
        disc_text.setTextFormat(Qt.RichText)
        dl2.addWidget(disc_text)
        v.addWidget(disc)

        # Tech info
        tech = QGroupBox("Technical Information")
        tl = QGridLayout(tech)
        tl.setHorizontalSpacing(20)
        tl.setVerticalSpacing(6)
        tor = self.main_win.tor
        rows = [
            ("Tor binary:", tor.tor_binary or "not found on this system"),
            ("Tor installed:", "yes" if tor.is_tor_installed() else "no"),
            ("Control port:", "9051 (default)"),
            ("SOCKS port:", "9050 (default)"),
            ("Stem library:", "available" if STEM_AVAILABLE else "unavailable"),
            ("PyQt5:", f"{PYQT_VERSION_STR} / Qt {QT_VERSION_STR}"),
            ("Matplotlib:", matplotlib.__version__),
            ("Platform:", f"{sys.platform} (Linux-only enforced)"),
            ("Python:", sys.version.split()[0]),
            ("Settings/data:", "~/.silent-tor/ (kept for upgrade compatibility)"),
        ]
        for i, (k, val) in enumerate(rows):
            tl.addWidget(QLabel(k), i, 0)
            lbl = QLabel(str(val))
            lbl.setWordWrap(True)
            lbl.setStyleSheet(f"color: {TEAL};")
            tl.addWidget(lbl, i, 1)
        v.addWidget(tech)

        # Credits
        cred = QGroupBox("Credits")
        crl = QVBoxLayout(cred)
        credits_lbl = QLabel(
            "Red Tor uses these open-source projects:\n"
            " - The Tor Project (https://torproject.org) - Tor network\n"
            " - Stem (https://stem.torproject.org) - Tor controller library\n"
            " - PyQt5 (https://www.riverbankcomputing.com/software/pyqt/) - GUI toolkit\n"
            " - PyQtWebEngine - Chromium-based web engine (not Tor Browser)\n"
            " - Matplotlib (https://matplotlib.org) - plotting library\n"
            " - Tor Metrics Onionoo (https://metrics.torproject.org/onionoo.html) - relay GeoIP metadata\n"
            " - ipapi.co - optional destination GeoIP lookup (through Tor)\n")
        credits_lbl.setWordWrap(True)
        crl.addWidget(credits_lbl)
        v.addWidget(cred)

        # Footer
        foot = QLabel(
            "<i>Red Tor · Built by Silent Days industry · "
            "For legal and ethical use only.</i>")
        foot.setWordWrap(True)
        foot.setTextFormat(Qt.RichText)
        foot.setStyleSheet(
            f"color: {MUTED}; padding: 10px 0; "
            f"border-top: 1px solid {TAN_DARK};")
        v.addWidget(foot)

        v.addStretch()
