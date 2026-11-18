"""Root-launch safety: Chromium flags for the Tor-routed browser engine."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import red_tor  # noqa: E402 - module-level env setup runs on import


class ChromiumFlagsTests(unittest.TestCase):
    def test_root_launch_gets_no_sandbox(self):
        flags = red_tor.build_chromium_flags(True)
        self.assertIn("--no-sandbox", flags)
        self.assertIn("--proxy-server=socks5://127.0.0.1:9050", flags)
        self.assertIn("--host-resolver-rules", flags)

    def test_normal_launch_keeps_sandbox(self):
        flags = red_tor.build_chromium_flags(False)
        self.assertNotIn("--no-sandbox", flags)
        self.assertIn("--proxy-server=socks5://127.0.0.1:9050", flags)
        self.assertIn("--host-resolver-rules", flags)

    def test_env_var_is_set_for_this_process(self):
        value = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "")
        self.assertIn("--proxy-server=socks5://127.0.0.1:9050", value)
        self.assertIn("--host-resolver-rules", value)


if __name__ == "__main__":
    unittest.main()
