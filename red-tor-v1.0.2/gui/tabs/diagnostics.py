"""Red Tor - Diagnostics tab.

Verifies one HTTPS request routed through Tor. It deliberately does not make
direct-IP probes or claim to test DNS resolver leakage.

All tests run in a worker thread so the UI does not freeze.
"""
import os
import threading
from datetime import datetime
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFont, QIcon, QColor, QTextCursor
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QPlainTextEdit, QGroupBox, QFrame, QSizePolicy, QMessageBox, QFileDialog,
)

from gui.theme import (
    CREAM, CREAM_LIGHT, CREAM_DARK, TAN, TAN_DARK, DARK_TEXT, MUTED,
    PURPLE, PURPLE_DARK, PURPLE_PALE, GREEN_OK, AMBER, RED_OFF, RED_HARD, BLUE_INFO, TEAL,
)
from gui import ICONS
from tor_core import run_leak_tests


def _icon(name):
    p = os.path.join(ICONS, name)
    return QIcon(p) if os.path.exists(p) else QIcon()


class DiagnosticsTab(QWidget):
    """Leak tests + system diagnostics."""

    lineEvent = pyqtSignal(str, str)   # (text, color)
    doneEvent = pyqtSignal(dict)

    def __init__(self, main_win):
        super().__init__()
        self.main_win = main_win
        self.tor = main_win.tor
        self._build()
        self.lineEvent.connect(self._append_line)
        self.doneEvent.connect(self._on_done)

    def _build(self):
        from gui.scroll_wrap import wrap_in_scroll
        # Scroll instead of squeeze: the requirements audit makes the page
        # taller than short windows; compressed labels overlap otherwise.
        content = wrap_in_scroll(self)
        v = QVBoxLayout(content)
        v.setContentsMargins(20, 20, 20, 20)
        v.setSpacing(12)

        title = QLabel("Diagnostics")
        title.setFont(QFont("Sans", 18, QFont.Bold))
        title.setStyleSheet(f"color: {TEAL};")
        v.addWidget(title)

        # Description
        desc = QLabel(
            "Check the Tor Project HTTPS endpoint through your configured Tor "
            "SOCKS proxy and show the Tor exit IP. No direct request is made "
            "to discover your home/public IP.")
        desc.setWordWrap(True)
        desc.setTextFormat(Qt.RichText)
        desc.setStyleSheet(f"color: {MUTED}; padding: 4px 0;")
        v.addWidget(desc)

        # Button row
        row = QHBoxLayout()
        self.run_btn = QPushButton("  Verify Tor Route")
        self.run_btn.setIcon(_icon("path.png"))
        self.run_btn.setMinimumHeight(40)
        self.run_btn.setStyleSheet(
            f"QPushButton {{ background: {PURPLE_PALE}; color: #111111; border: 1px solid {RED_OFF}; "
            f"font-weight: 600; padding: 8px 18px; border-radius: 4px; }}"
            f"QPushButton:hover {{ background: {PURPLE}; }}"
            f"QPushButton:disabled {{ background: {CREAM_DARK}; "
            f"color: {MUTED}; }}")
        self.run_btn.clicked.connect(self._run_tests)
        row.addWidget(self.run_btn)

        self.clear_btn = QPushButton("  Clear")
        self.clear_btn.setIcon(_icon("tor_off.png"))
        self.clear_btn.clicked.connect(lambda: self.output.clear())
        row.addWidget(self.clear_btn)

        self.export_btn = QPushButton("  Export Report")
        self.export_btn.setIcon(_icon("settings.png"))
        self.export_btn.clicked.connect(self._export_report)
        row.addWidget(self.export_btn)

        row.addStretch()
        self.last_run = QLabel("Last run: never")
        self.last_run.setStyleSheet(f"color: {MUTED};")
        row.addWidget(self.last_run)
        v.addLayout(row)

        # Summary cards
        sum_row = QHBoxLayout()
        sum_row.setSpacing(10)
        self.card_ip = QGroupBox("Tor Exit IP")
        ipg = QVBoxLayout(self.card_ip)
        self.card_ip_lbl = QLabel("--")
        self.card_ip_lbl.setAlignment(Qt.AlignCenter)
        self.card_ip_lbl.setFont(QFont("Sans", 14, QFont.Bold))
        ipg.addWidget(self.card_ip_lbl)
        sum_row.addWidget(self.card_ip)

        self.card_dns = QGroupBox("DNS probe (not run)")
        dnsg = QVBoxLayout(self.card_dns)
        self.card_dns_lbl = QLabel("--")
        self.card_dns_lbl.setAlignment(Qt.AlignCenter)
        self.card_dns_lbl.setFont(QFont("Sans", 14, QFont.Bold))
        dnsg.addWidget(self.card_dns_lbl)
        sum_row.addWidget(self.card_dns)

        self.card_geo = QGroupBox("Direct IP probe (disabled)")
        gg = QVBoxLayout(self.card_geo)
        self.card_geo_lbl = QLabel("--")
        self.card_geo_lbl.setAlignment(Qt.AlignCenter)
        self.card_geo_lbl.setFont(QFont("Sans", 14, QFont.Bold))
        gg.addWidget(self.card_geo_lbl)
        sum_row.addWidget(self.card_geo)
        v.addLayout(sum_row)

        # Output console - slate-on-light for daylight theme
        out_grp = QGroupBox("Detailed Report")
        og = QVBoxLayout(out_grp)
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setFont(QFont("Monospace", 9))
        self.output.setStyleSheet(f"""
            QPlainTextEdit {{
                background: #FFFFFF;
                color: #111111;
                border: 1px solid {TAN_DARK};
                padding: 8px;
                font-family: 'DejaVu Sans Mono', 'Liberation Mono', monospace;
                font-size: 9pt;
            }}
        """)
        og.addWidget(self.output)
        v.addWidget(out_grp, 1)

        # Requirements audit — every missing piece shows the one-command fix
        req_grp = QGroupBox("Tool requirements (auto-checked)")
        rg = QVBoxLayout(req_grp)
        self.req_area = QPlainTextEdit()
        self.req_area.setReadOnly(True)
        self.req_area.setMaximumHeight(120)
        self.req_area.setFont(QFont("Monospace", 8))
        self.req_area.setStyleSheet(f"""
            QPlainTextEdit {{
                background: #FFFFFF; color: #111111;
                border: 1px solid {TAN_DARK}; padding: 6px;
                font-family: 'DejaVu Sans Mono', monospace; font-size: 8pt;
            }}
        """)
        rg.addWidget(self.req_area)
        self.req_note = QLabel()
        self.req_note.setWordWrap(True)
        self.req_note.setStyleSheet(f"color: {MUTED}; font-size: 9pt;")
        rg.addWidget(self.req_note)
        v.addWidget(req_grp)

        # Tip
        tip = QLabel(
            "<b>Privacy note:</b> This verifies only the Tor-routed exit IP. "
            "It does not compare your direct IP or test DNS leaks. Those checks "
            "are deliberately marked NOT TESTED rather than guessed.")
        tip.setWordWrap(True)
        tip.setTextFormat(Qt.RichText)
        tip.setStyleSheet(
            f"background: {CREAM_DARK}; color: {AMBER}; padding: 8px 12px; "
            f"border: 1px solid {TAN_DARK}; border-radius: 3px; font-size: 9pt;")
        v.addWidget(tip)

    # ---- Verify the Tor route (worker thread) ----
    def _run_tests(self):
        if not self.tor.connected:
            QMessageBox.warning(
                self, "Tor Not Connected",
                "Connect to Tor first. Without a verified Tor session no network "
                "request will be made.")
            return
        self.run_btn.setEnabled(False)
        self.run_btn.setText("  Running...")
        self.lineEvent.emit(
            f"\n=== Tor route verification {datetime.now().strftime('%H:%M:%S')} ===\n",
            AMBER)

        def work():
            try:
                result = run_leak_tests(self.tor)
            except Exception as e:
                result = {"checks": [f"Tor verification failed: {e}"],
                          "tor_ip": None, "ip_check_tested": False,
                          "dns_tested": False, "dns_leak": None,
                          "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
            self.doneEvent.emit(result)

        threading.Thread(target=work, daemon=True).start()

    def _on_done(self, result):
        # Print each check line; plain lines stay dark so they remain readable
        # on the white console background.
        for line in result["checks"]:
            color = GREEN_OK if "Tor" in line else "#111111"
            self.lineEvent.emit(line + "\n", color)
        # This is the observed Tor exit IP, never the user's direct IP.
        if result.get("ip_check_tested") and result.get("tor_ip"):
            self.card_ip_lbl.setText(str(result["tor_ip"]))
            self.card_ip_lbl.setStyleSheet(f"color: {GREEN_OK}; font-weight: 800;")
        else:
            self.card_ip_lbl.setText("NOT VERIFIED")
            self.card_ip_lbl.setStyleSheet(f"color: {AMBER}; font-weight: 700;")
        # DNS leak card
        if result["dns_leak"]:
            self.card_dns_lbl.setText("LEAK!")
            self.card_dns_lbl.setStyleSheet(f"color: {RED_HARD}; font-weight: 800;")
        elif result.get("dns_tested"):
            self.card_dns_lbl.setText("No leak")
            self.card_dns_lbl.setStyleSheet(f"color: {GREEN_OK}; font-weight: 800;")
        else:
            self.card_dns_lbl.setText("NOT TESTED")
            self.card_dns_lbl.setStyleSheet(f"color: {AMBER}; font-weight: 700;")
        # Direct IP probing is deliberately disabled to avoid exposing it.
        self.card_geo_lbl.setText("NOT RUN (safe)")
        self.card_geo_lbl.setStyleSheet(f"color: {AMBER}; font-weight: 700;")
        # Reset button
        self.run_btn.setEnabled(True)
        self.run_btn.setText("  Verify Tor Route")
        self.last_run.setText(
            f"Last run: {result['ts'].split(' ', 1)[-1]}")

    def _append_line(self, text, color):
        safe = (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
        # Preserve leading indentation and column alignment, but keep single
        # spaces breakable so long lines wrap instead of overflowing.
        stripped = safe.lstrip(" ")
        indent = "&nbsp;" * (len(safe) - len(stripped))
        body = stripped.replace("\n", "<br>").replace("  ", "&nbsp;&nbsp;")
        self.output.appendHtml(f"<span style='color:{color};'>{indent}{body}</span>")
        self.output.moveCursor(QTextCursor.End)

    def _export_report(self):
        """Export the current diagnostics output as a timestamped text file."""
        text = self.output.toPlainText().strip()
        if not text:
            QMessageBox.information(
                self, "Nothing to export",
                "Run the leak tests first, then export the report.")
            return
        # Default to ~/.silent-tor/diagnostics-<timestamp>.txt
        home = os.path.expanduser("~/.silent-tor")
        try:
            os.makedirs(home, exist_ok=True)
        except Exception:
            pass
        default_name = os.path.join(
            home, f"diagnostics-{datetime.now().strftime('%Y%m%d-%H%M%S')}.txt")
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Diagnostics Report", default_name,
            "Text files (*.txt);;All files (*)")
        if not path:
            return
        try:
            header = (
                "Red Tor - Diagnostics Report\n"
                f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"Built by: Silent Days industry\n"
                "=" * 60 + "\n\n"
            )
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(header + text + "\n")
            QMessageBox.information(
                self, "Exported",
                f"Report saved to:\n{path}")
        except Exception as e:
            QMessageBox.warning(self, "Export Failed", f"Could not save:\n{e}")

    def refresh(self):
        """Re-check tool requirements each time the page is opened."""
        from gui.requirements_check import (
            check_requirements, installer_command, missing_count,
        )
        lines = []
        missing = 0
        for label, ok, detail in check_requirements():
            mark = "[ OK ]" if ok else "[ MISS ]"
            lines.append(f"{mark:9s} {label}: {detail}")
            missing += 0 if ok else 1
        self.req_area.setPlainText("\n".join(lines))
        if missing:
            self.req_note.setText(
                f"{missing} requirement(s) missing. The installer checks and "
                f"installs everything automatically — run: "
                f"{installer_command()}")
            self.req_note.setStyleSheet(
                f"color: {RED_HARD}; font-size: 9pt; font-weight: 600;")
        else:
            self.req_note.setText(
                "All requirements are installed. Red Tor can use every feature.")
            self.req_note.setStyleSheet(f"color: {GREEN_OK}; font-size: 9pt;")
