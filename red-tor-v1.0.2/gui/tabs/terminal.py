"""Red Tor - real terminal tab.

A genuine Kali-style terminal: commands typed here run on this system as root.
The shell runs behind a pseudo-terminal (pty), so sudo password prompts,
interactive programs and long output all behave like a real console.
"""
import codecs
import os
import re
import signal
import subprocess
from datetime import datetime

from PyQt5.QtCore import Qt, QSocketNotifier, pyqtSignal
from PyQt5.QtGui import QFont, QTextCursor
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QPlainTextEdit, QFileDialog, QMessageBox,
)

from gui.theme import (
    CREAM_LIGHT, DARK_TEXT, MUTED, PURPLE_PALE, TEAL, TAN_DARK, RED_HARD, AMBER,
)

# Strip ANSI/VT escape sequences (colors, cursor moves) so output stays
# readable in the plain-text console widget.
_ANSI_RE = re.compile(
    r"\x1b\[[0-9;?]*[a-zA-Z]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b[=>]|\x1b\(B")


class TerminalTab(QWidget):
    """Root shell terminal — commands run directly on this system."""

    lineEvent = pyqtSignal(str)

    MAX_BLOCKS = 4000

    def __init__(self, main_win):
        super().__init__()
        self.main_win = main_win
        self.tor = main_win.tor
        self._master = None
        self._proc = None
        self._notifier = None
        self._decoder = codecs.getincrementaldecoder("utf-8")("replace")
        self._build()
        self._start_shell()
        self.tor.add_listener(self._on_activity)

    # ---- UI ----
    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(10)
        title = QLabel("Terminal")
        title.setFont(QFont("Sans", 18, QFont.Bold))
        title.setStyleSheet(f"color: {TEAL};")
        layout.addWidget(title)

        warn = QLabel(
            "Kali-style ROOT terminal — every command runs on this system with "
            "root privileges. Double-check a command before pressing Enter.")
        warn.setWordWrap(True)
        warn.setStyleSheet(
            f"color: {RED_HARD}; background: {CREAM_LIGHT}; padding: 8px 12px; "
            f"border: 1px solid {RED_HARD}; border-radius: 4px; font-weight: 600;")
        layout.addWidget(warn)

        toolbar = QHBoxLayout()
        self.status = QLabel("Starting root shell…")
        self.status.setStyleSheet(f"color: {MUTED};")
        toolbar.addWidget(self.status)
        toolbar.addStretch()
        self.restart_btn = QPushButton("Restart shell")
        self.restart_btn.clicked.connect(self._restart_shell)
        toolbar.addWidget(self.restart_btn)
        export_btn = QPushButton("Export…")
        export_btn.clicked.connect(self._export_log)
        toolbar.addWidget(export_btn)
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self._clear)
        toolbar.addWidget(clear_btn)
        layout.addLayout(toolbar)

        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setMaximumBlockCount(self.MAX_BLOCKS)
        self.output.setFont(QFont("DejaVu Sans Mono", 9))
        # Light console (matches the rest of the white theme): white paper,
        # near-black text, subtle border — like a classic z.ai code block.
        self.output.setStyleSheet(
            f"QPlainTextEdit {{ background: {CREAM_LIGHT}; color: {DARK_TEXT}; "
            f"border: 1px solid {TAN_DARK}; padding: 10px; "
            f"selection-background-color: {PURPLE_PALE}; selection-color: {DARK_TEXT}; "
            f"font-family: 'DejaVu Sans Mono','Liberation Mono',monospace; }}")
        layout.addWidget(self.output, 1)

        prompt = QHBoxLayout()
        label = QLabel("root>")
        label.setStyleSheet(f"color: {RED_HARD}; font-weight: bold;")
        prompt.addWidget(label)
        self.command = QLineEdit()
        self.command.setFont(QFont("DejaVu Sans Mono", 9))
        self.command.setPlaceholderText(
            "Type any Kali command (nmap, apt, systemctl, whoami …) and press Enter")
        self.command.returnPressed.connect(self._send_command)
        prompt.addWidget(self.command, 1)
        run_btn = QPushButton("Run")
        run_btn.clicked.connect(self._send_command)
        prompt.addWidget(run_btn)
        layout.addLayout(prompt)

    # ---- Shell lifecycle ----
    def _start_shell(self):
        """Spawn a root shell behind a pty.

        If Red Tor already runs as root (common on Kali), bash starts
        directly; otherwise sudo is used and its password prompt appears
        right here in the console — type the password and press Enter.
        """
        import pty
        if self._proc is not None:
            return
        self._master, slave = pty.openpty()
        env = dict(os.environ)
        env.update({
            "TERM": "xterm-256color",
            "COLORTERM": "",
            "HOME": env.get("HOME", "/root"),
            "SHELL": "/bin/bash",
            "LANG": env.get("LANG", "C.UTF-8"),
        })
        if os.geteuid() == 0:
            argv = ["bash", "-i"]
            note = "root shell (running as root)"
        else:
            argv = ["sudo", "-E", "bash", "-i"]
            note = "root shell via sudo (password prompt appears below)"

        def _child_setup():
            # New session, then adopt the pty slave as the controlling
            # terminal: without TIOCSCTTY sudo refuses to prompt for a
            # password ("no tty present") and interactive shells detach.
            os.setsid()
            try:
                import fcntl
                import termios
                fcntl.ioctl(slave, termios.TIOCSCTTY, 0)
            except Exception:
                pass

        try:
            self._proc = subprocess.Popen(
                argv,
                stdin=slave, stdout=slave, stderr=slave,
                preexec_fn=_child_setup,
                env=env,
                cwd=os.path.expanduser("~"),
            )
        except OSError as exc:
            os.close(self._master)
            os.close(slave)
            self._master = None
            self._append(f"[Red Tor] Could not start a root shell: {exc}")
            self._append("[Red Tor] Open a system terminal and run: sudo bash install.sh")
            self.status.setText("Shell unavailable")
            return
        os.close(slave)  # child owns the slave now
        self._notifier = QSocketNotifier(self._master, QSocketNotifier.Read, self)
        self._notifier.activated.connect(self._on_pty_read)
        self._decoder.reset()
        self._append("═══ Red Tor root terminal ═══")
        self._append(f"[Red Tor] {note}.")
        self._append("[Red Tor] Commands run as root on this machine — be careful.")
        self._append("[Red Tor] Type a command below and press Enter (Ctrl+C works too).")
        self.status.setText(f"Root shell running (pid {self._proc.pid})")

    def _stop_shell(self):
        # Disable the read notifier BEFORE closing the master fd, otherwise
        # Qt fires one last read on an invalid socket and warns.
        if self._notifier is not None:
            try:
                self._notifier.setEnabled(False)
                self._notifier.deleteLater()
            except RuntimeError:
                pass  # underlying C++ object already gone
            self._notifier = None
        proc = self._proc
        if proc is None:
            if self._master is not None:
                os.close(self._master)
                self._master = None
            return
        self._proc = None
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGHUP)
        except Exception:
            pass
        try:
            proc.wait(timeout=2)
        except Exception:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except Exception:
                pass
            proc.wait(timeout=2)
        if self._master is not None:
            try:
                os.close(self._master)
            except OSError:
                pass
            self._master = None

    def _restart_shell(self):
        self._stop_shell()
        self._start_shell()

    def _on_pty_read(self):
        try:
            data = os.read(self._master, 65536)
        except OSError:
            self._notifier = None
            self._shell_exited()
            return
        if not data:
            self._notifier = None
            self._shell_exited()
            return
        text = self._decoder.decode(data)
        text = _ANSI_RE.sub("", text)
        # Emulate a console: \r rewrites the current line (progress bars),
        # \n moves to the next one.
        cursor = self.output.textCursor()
        cursor.movePosition(QTextCursor.End)
        for ch in text:
            if ch == "\r":
                cursor.movePosition(QTextCursor.StartOfBlock, QTextCursor.KeepAnchor)
                cursor.removeSelectedText()
            else:
                cursor.insertText(ch)
        self.output.setTextCursor(cursor)
        self.output.ensureCursorVisible()

    def _shell_exited(self):
        if self._proc is not None and self._proc.poll() is None:
            return  # spurious read; shell still alive
        self._stop_shell()
        self.status.setText("Shell exited")
        self._append("[Red Tor] Root shell exited. Click 'Restart shell' for a new one.")

    # ---- Input ----
    def _send_command(self):
        raw = self.command.text()
        if not raw:
            return
        self.command.clear()
        if self._proc is None or self._master is None:
            self._append("[Red Tor] No shell running. Click 'Restart shell' first.")
            return
        try:
            os.write(self._master, raw.encode("utf-8") + b"\n")
        except OSError as exc:
            self._append(f"[Red Tor] Failed to send command: {exc}")
        if raw.strip() == "clear":
            # pty echo arrives after; clear on next tick keeps output sane
            from PyQt5.QtCore import QTimer
            QTimer.singleShot(120, self._clear)

    def _send_raw(self, data):
        """Send raw bytes (used for interactive prompts like sudo passwords)."""
        if self._proc is not None and self._master is not None:
            try:
                os.write(self._master, data)
            except OSError as exc:
                self._append(f"[Red Tor] Write failed: {exc}")

    # ---- App activity (clearly marked, keeps the shell transcript usable) ----
    def _on_activity(self, level, message):
        self.lineEvent.emit(
            f"[app {datetime.now().strftime('%H:%M:%S')}] {level}: {message}")

    # ---- Utilities ----
    def _append(self, line):
        self.output.appendPlainText(str(line))
        self.output.moveCursor(QTextCursor.End)

    def _clear(self):
        self.output.clear()

    def _export_log(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export terminal log", "red-tor-terminal.txt",
            "Text files (*.txt);;All files (*)")
        if not path:
            return
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                stream.write(f"Red Tor terminal log · {datetime.now().isoformat()}\n\n")
                stream.write(self.output.toPlainText())
            self.status.setText(f"Saved: {path}")
        except OSError as exc:
            QMessageBox.warning(self, "Export failed", str(exc))

    def refresh(self):
        pass

    def shutdown(self):
        """Kill the child shell and release the pty on window close."""
        self.tor.remove_listener(self._on_activity)
        self._stop_shell()
