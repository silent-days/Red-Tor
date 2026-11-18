"""Regression tests for the Kali distro-PyQt5 engine import order and
clean Ctrl+C / SIGTERM shutdown.

Kali's distro PyQt5 aborts the QtWebEngineWidgets module init with
ImportError when it is imported after a QApplication was built without
AA_ShareOpenGLContexts — the Browse page then claims the engine is "not
installed" even though the package is present. red_tor.py must set the
attribute and pre-load the engine before any QApplication exists.
"""
import os
import signal
import subprocess
import sys
import threading
import time
import unittest

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, APP_DIR)


class EngineImportOrderTests(unittest.TestCase):
    def test_share_opengl_contexts_set_before_qapp(self):
        import red_tor
        from PyQt5.QtCore import QCoreApplication, Qt
        self.assertTrue(
            QCoreApplication.testAttribute(Qt.AA_ShareOpenGLContexts),
            "AA_ShareOpenGLContexts must be set at red_tor import time, "
            "before any QApplication is constructed")

    def test_webengine_preloaded_before_qapp(self):
        from importlib.util import find_spec
        if find_spec("PyQt5.QtWebEngineWidgets") is None:
            self.skipTest("PyQtWebEngine is not installed in this test env")
        import red_tor  # noqa: F401
        self.assertIn("PyQt5.QtWebEngineWidgets", sys.modules,
                      "QtWebEngineWidgets must be pre-loaded at red_tor "
                      "import time (Kali aborts late imports)")


class SignalShutdownIntegrationTests(unittest.TestCase):
    """Launch the real app offscreen, send a signal, expect exit 0."""

    MARKER = "Red Tor v1.0.2 started"

    def _launch_signal_and_check(self, sig):
        env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
        proc = subprocess.Popen(
            [sys.executable, "red_tor.py"], cwd=APP_DIR, env=env,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        output = []

        def _reader():
            try:
                for line in proc.stdout:
                    output.append(line)
            except Exception:
                pass

        thread = threading.Thread(target=_reader, daemon=True)
        thread.start()
        try:
            deadline = time.time() + 90
            while time.time() < deadline:
                if proc.poll() is not None:
                    break
                if any(self.MARKER in ln for ln in output):
                    break
                time.sleep(0.2)
            self.assertIsNone(
                proc.poll(),
                "app exited before the signal:\n" + "".join(output[-30:]))
            proc.send_signal(sig)
            rc = proc.wait(timeout=30)
            text = "".join(output)
            self.assertEqual(
                rc, 0, f"exit code {rc} after {sig.name}:\n" + text[-2000:])
            self.assertNotIn("Traceback", text)
            self.assertNotIn("KeyboardInterrupt", text)
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait(timeout=10)

    def test_sigint_exits_cleanly(self):
        self._launch_signal_and_check(signal.SIGINT)

    def test_sigterm_exits_cleanly(self):
        self._launch_signal_and_check(signal.SIGTERM)


if __name__ == "__main__":
    unittest.main()
