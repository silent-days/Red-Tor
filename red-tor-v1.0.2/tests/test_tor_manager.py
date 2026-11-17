import unittest
import os
import tempfile
import time
from unittest.mock import patch

import tor_core


class StateMigrationTests(unittest.TestCase):
    def test_legacy_tor_data_and_log_are_copied_not_deleted(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = os.path.join(tmp, "home")
            data_home = os.path.join(home, ".local", "share")
            state_home = os.path.join(home, ".local", "state")
            old_data = os.path.join(data_home, "silent-tor", "tor-data")
            old_log = os.path.join(state_home, "silent-tor", "tor.log")
            os.makedirs(old_data)
            os.makedirs(os.path.dirname(old_log))
            with open(os.path.join(old_data, "state"), "w") as stream:
                stream.write("old tor state")
            with open(old_log, "w") as stream:
                stream.write("old tor log")

            with patch.dict(os.environ, {
                "HOME": home,
                "XDG_DATA_HOME": data_home,
                "XDG_STATE_HOME": state_home,
            }):
                state_dir, data_dir, log_dir = tor_core._tor_state_paths()

            self.assertEqual(state_dir, os.path.join(state_home, "red-tor"))
            self.assertEqual(log_dir, state_dir)
            with open(os.path.join(data_dir, "state")) as stream:
                self.assertEqual(stream.read(), "old tor state")
            with open(os.path.join(log_dir, "tor.log")) as stream:
                self.assertEqual(stream.read(), "old tor log")
            self.assertTrue(os.path.isfile(os.path.join(old_data, "state")))
            self.assertTrue(os.path.isfile(old_log))
            self.assertEqual(os.stat(data_dir).st_mode & 0o777, 0o700)


class TorManagerConnectionTests(unittest.TestCase):
    def setUp(self):
        self.manager = tor_core.TorManager()

    def test_missing_stem_does_not_claim_connection(self):
        with patch.object(tor_core, "STEM_AVAILABLE", False):
            ok, message = self.manager.connect()
        self.assertFalse(ok)
        self.assertFalse(self.manager.connected)
        self.assertIn("Stem", message)

    def test_reuses_verified_socks_without_starting_duplicate_tor(self):
        class RefusedController:
            @staticmethod
            def from_port(**kwargs):
                raise ConnectionRefusedError("no control port")

        with patch.object(tor_core, "Controller", RefusedController), \
             patch.object(tor_core, "STEM_AVAILABLE", True), \
             patch.object(self.manager, "_verify_existing_socks", return_value=(True, "verified")), \
             patch.object(self.manager, "_start_tor") as start_tor:
            ok, message = self.manager.connect()

        self.assertTrue(ok)
        self.assertTrue(self.manager.connected)
        self.assertTrue(self.manager.socks_only)
        self.assertIsNone(self.manager.controller)
        self.assertIn("verified", message)
        self.assertIn("sudo bash install.sh", message)
        self.assertEqual(self.manager.last_error, "")
        self.assertEqual(self.manager.control_port_error, "no control port")
        start_tor.assert_not_called()

    def test_control_auth_waits_for_bootstrap_before_socks_and_gives_guidance(self):
        events = []
        self.manager.add_listener(lambda level, message: events.append((level, message)))

        class FakeController:
            @staticmethod
            def from_port(**kwargs):
                return FakeController()

            def authenticate(self, password=""):
                pass

            def get_info(self, key):
                if key == "status/bootstrap-phase":
                    return 'NOTICE BOOTSTRAP PROGRESS=100 TAG=done SUMMARY="Done"'
                raise AssertionError(f"unexpected get_info({key})")

            def close(self):
                pass

        with patch.object(tor_core, "Controller", FakeController), \
             patch.object(tor_core, "STEM_AVAILABLE", True), \
             patch.object(self.manager, "_verify_existing_socks",
                          return_value=(False, "Could not verify SOCKS endpoint: timed out")), \
             patch.object(self.manager, "_start_tor") as start_tor:
            ok, message = self.manager.connect()

        self.assertFalse(ok)
        self.assertFalse(self.manager.connected)
        self.assertIn("No second Tor process was started", message)
        self.assertIn("Guidance", message)
        self.assertIn("Connect again", message)
        start_tor.assert_not_called()
        self.assertTrue(any("waiting for Tor bootstrap" in text for _level, text in events))

    def test_socks_failure_hint_names_a_stuck_bootstrap_phase(self):
        hint = self.manager._socks_failure_hint(
            'NOTICE BOOTSTRAP PROGRESS=45 TAG=request_descriptors '
            'SUMMARY="Asking for network-status consensus"')
        self.assertIn("45", hint)
        self.assertIn("bridges", hint)
        self.assertIn("retry", hint.lower())

    def test_bootstrap_wait_returns_immediately_when_tor_reports_done(self):
        class DoneController:
            @staticmethod
            def get_info(key):
                assert key == "status/bootstrap-phase"
                return 'NOTICE BOOTSTRAP PROGRESS=100 TAG=done SUMMARY="Done"'

        started = time.monotonic()
        report = self.manager._wait_for_bootstrap(DoneController(), timeout=10)
        self.assertLess(time.monotonic() - started, 5)
        self.assertIn("PROGRESS=100", report)

    def test_manager_listener_emits_unformatted_message_for_single_timestamp_display(self):
        events = []
        self.manager.add_listener(lambda level, message: events.append((level, message)))
        self.manager._emit("INFO", "Connecting to Tor")
        self.assertEqual(events, [("INFO", "Connecting to Tor")])

    def test_socks_only_mode_has_no_fake_circuit_or_exit_country_success(self):
        self.manager.connected = True
        self.manager.socks_only = True
        self.assertIsNone(self.manager.refresh_circuit())
        ok, message = self.manager.set_exit_country("de")
        self.assertFalse(ok)
        self.assertIn("control-port", message)

    def test_disconnected_mode_has_no_fake_circuit(self):
        self.manager.connected = False
        self.assertIsNone(self.manager.refresh_circuit())
        self.assertIsNone(self.manager.current_circuit)

    def test_disconnected_fetch_does_not_make_a_network_request(self):
        self.manager.connected = False
        with patch.object(tor_core.requests, "get") as get:
            ok, message = self.manager.fetch_url("https://example.com")
        self.assertFalse(ok)
        self.assertIn("No request was attempted", message)
        get.assert_not_called()

    def test_disconnected_diagnostics_make_no_direct_request(self):
        self.manager.connected = False
        with patch.object(tor_core.requests, "get") as get:
            result = tor_core.run_leak_tests(self.manager)
        get.assert_not_called()
        self.assertIsNone(result["ip_leak"])
        self.assertFalse(result["dns_tested"])
        self.assertTrue(any("NOT TESTED" in line for line in result["checks"]))

    def test_disconnected_fetch_does_not_report_fake_success(self):
        self.manager.connected = False
        with patch.object(tor_core.requests, "get") as get:
            ok, message = self.manager.fetch_url("https://example.com")
        self.assertFalse(ok)
        self.assertIn("No request was attempted", message)
        get.assert_not_called()

    def test_authenticated_control_with_bad_socks_does_not_launch_duplicate(self):
        class AuthenticatedController:
            def authenticate(self):
                pass

            def close(self):
                pass

        class FakeController:
            @staticmethod
            def from_port(**kwargs):
                return AuthenticatedController()

        with patch.object(tor_core, "Controller", FakeController), \
             patch.object(tor_core, "STEM_AVAILABLE", True), \
             patch.object(self.manager, "_verify_existing_socks",
                          return_value=(False, "not a verified Tor exit")), \
             patch.object(self.manager, "_start_tor") as start_tor:
            ok, message = self.manager.connect()
        self.assertFalse(ok)
        self.assertFalse(self.manager.connected)
        self.assertIn("No second Tor process was started", message)
        start_tor.assert_not_called()

    def test_refresh_selects_real_built_general_circuit_without_rotating(self):
        class Circuit:
            def __init__(self, circuit_id, purpose, status="BUILT"):
                self.id, self.purpose, self.status = circuit_id, purpose, status
                self.path = [(f"FP{i}", f"Relay{i}") for i in range(3)]

        class Stream:
            circ_id = "2"
            status = "SUCCEEDED"
            target = "example.com:443"

        class FakeController:
            def get_circuits(self):
                return [Circuit("1", "MEASURE_TIMEOUT"), Circuit("2", "GENERAL")]

            def get_streams(self):
                return [Stream()]

            def signal(self, _signal):
                raise AssertionError("Refresh must not send NEWNYM")

        self.manager.controller = FakeController()
        self.manager.connected = True
        with patch.object(self.manager, "_geo_for_fp",
                          side_effect=lambda fp: ("de", "Frankfurt", 50.1, 8.6)):
            circuit = self.manager.refresh_circuit()
        self.assertEqual(circuit["id"], "2")
        self.assertTrue(circuit["active_stream"])
        self.assertEqual(circuit["stream_target"]["display"], "example.com:443")
        self.assertEqual([n["position"] for n in circuit["nodes"]], ["Entry", "Hop 2", "Exit"])
        self.assertTrue(all(n["lat"] is not None and n["lon"] is not None for n in circuit["nodes"]))

    def test_circuit_remains_visible_when_stream_metadata_is_unavailable(self):
        class Circuit:
            id, purpose, status = "7", "GENERAL", "BUILT"
            path = [("FP1", "Entry"), ("FP2", "Exit")]

        class FakeController:
            def get_circuits(self):
                return [Circuit()]

            def get_streams(self):
                raise RuntimeError("stream event unavailable")

        self.manager.connected = True
        self.manager.controller = FakeController()
        with patch.object(self.manager, "_geo_for_fp", return_value=("??", "Location unavailable", None, None)):
            circuit = self.manager.refresh_circuit()
        self.assertEqual(circuit["id"], "7")
        self.assertFalse(circuit["active_stream"])
        self.assertIsNone(circuit["stream_target"])

    def test_relay_geolocation_uses_tor_metrics_and_never_fabricates_zero_point(self):
        class Response:
            content = b"{}"

            def raise_for_status(self):
                pass

            def json(self):
                return {"relays": [{
                    "fingerprint": "A" * 40, "country": "de",
                    "city_name": "Frankfurt", "latitude": 50.11,
                    "longitude": 8.68,
                }]}

        self.manager.connected = True
        self.manager.map_lookup_enabled = True
        with patch.object(tor_core.requests, "get", return_value=Response()) as get:
            location = self.manager._geo_for_fp("A" * 40)
        self.assertEqual(location, ("de", "Frankfurt", 50.11, 8.68))
        self.assertIn("onionoo.torproject.org/details?", get.call_args.args[0])
        self.assertEqual(get.call_args.kwargs["proxies"], tor_core.TOR_PROXIES)

    def test_exit_ip_check_is_tor_only_and_never_compares_direct_ip(self):
        self.manager.connected = True
        with patch.object(self.manager, "get_my_ip_via_tor", return_value="198.51.100.10"), \
             patch.object(tor_core.requests, "get") as get:
            result = tor_core.run_leak_tests(self.manager)
        self.assertTrue(result["ip_check_tested"])
        self.assertEqual(result["tor_ip"], "198.51.100.10")
        self.assertIsNone(result["real_ip"])
        self.assertIsNone(result["ip_leak"])
        get.assert_not_called()

    def test_exit_ip_failure_reason_is_preserved_for_diagnostics(self):
        self.manager.connected = True
        with patch.object(tor_core.requests, "get",
                          side_effect=RuntimeError("SOCKS proxy timeout")):
            result = tor_core.run_leak_tests(self.manager)
        self.assertIsNone(result["tor_ip"])
        self.assertIn("SOCKS proxy timeout", self.manager.last_ip_check_error)
        self.assertTrue(any("SOCKS proxy timeout" in line for line in result["checks"]))

    def test_daemon_traffic_stats_are_labeled_and_sampled_from_control_port(self):
        class FakeController:
            def get_info(self, key):
                return {"traffic/read": "12345", "traffic/written": "6789"}[key]

        self.manager.connected = True
        self.manager.controller = FakeController()
        stats = self.manager.daemon_traffic_stats()
        self.assertEqual(stats["source"], "tor-daemon")
        self.assertEqual(stats["bytes_received"], 12345)
        self.assertEqual(stats["bytes_sent"], 6789)

    def test_destination_lookup_strips_url_secrets_and_keeps_missing_coords_unknown(self):
        class Response:
            content = b"{}"

            def raise_for_status(self):
                pass

            def json(self):
                return {"ip": "93.184.216.34", "country_name": "United States",
                        "country": "US", "city": "Example"}

        self.manager.connected = True
        with patch.object(tor_core.requests, "get", return_value=Response()) as get:
            result = self.manager.lookup_destination(
                "https://user:secret@example.com:443/path?token=do-not-send")
        self.assertEqual(result["host"], "example.com")
        self.assertIsNone(result["lat"])
        self.assertIsNone(result["lon"])
        self.assertEqual(get.call_args.args[0], "https://ipapi.co/example.com/json/")
        self.assertNotIn("secret", get.call_args.args[0])
        self.assertNotIn("token", get.call_args.args[0])

    def test_destination_lookup_rejects_private_ip_before_network(self):
        self.manager.connected = True
        with patch.object(tor_core.requests, "get") as get:
            result = self.manager.lookup_destination("127.0.0.1")
        self.assertFalse(result["via_tor"])
        self.assertIn("Private", result["error"])
        get.assert_not_called()


class StreamTargetParserTests(unittest.TestCase):
    def test_parse_domain_and_port_without_resolution(self):
        self.assertEqual(tor_core.parse_stream_target("EXAMPLE.com:443"),
                         {"host": "example.com", "port": 443, "display": "example.com:443"})

    def test_parse_ipv4_and_bracketed_ipv6(self):
        self.assertEqual(tor_core.parse_stream_target("198.51.100.8:8443")["host"], "198.51.100.8")
        parsed = tor_core.parse_stream_target("[2001:db8::1]:443")
        self.assertEqual(parsed["host"], "2001:db8::1")
        self.assertEqual(parsed["display"], "[2001:db8::1]:443")

    def test_reject_malformed_or_unsafe_stream_targets(self):
        for target in ("", "example.com", "example.com:0", "example.com:65536", "example.com:" + "9" * 5000,
                       "host name:443", "[2001:db8::1]443", "example.com:443\nBAD"):
            with self.subTest(target=target):
                self.assertIsNone(tor_core.parse_stream_target(target))

    def test_stream_target_is_not_geo_looked_up_by_default(self):
        self.assertFalse(tor_core.TorManager().destination_geolocation_enabled)


class LoadSettingsValidationTests(unittest.TestCase):
    def test_non_dict_settings_file_returns_empty_dict(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "settings.json")
            with open(path, "w") as f:
                f.write('["not", "a", "dict"]')
            with patch.object(tor_core, "SETTINGS_FILE", path):
                self.assertEqual(tor_core.load_settings(), {})

    def test_corrupt_settings_file_returns_empty_dict(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "settings.json")
            with open(path, "w") as f:
                f.write("{not json")
            with patch.object(tor_core, "SETTINGS_FILE", path):
                self.assertEqual(tor_core.load_settings(), {})

    def test_valid_settings_file_round_trips(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "settings.json")
            with patch.object(tor_core, "SETTINGS_FILE", path):
                tor_core.save_settings({"default_exit": "de"})
                self.assertEqual(tor_core.load_settings(), {"default_exit": "de"})


class TorManagerFixTests(unittest.TestCase):
    def setUp(self):
        self.manager = tor_core.TorManager()

    def test_mark_disconnected_clears_session_state(self):
        self.manager.connected = True
        self.manager.socks_only = False
        self.manager.current_circuit = {"id": "5"}
        self.manager._last_circuit_id = "5"
        self.manager.mark_disconnected()
        self.assertFalse(self.manager.connected)
        self.assertFalse(self.manager.socks_only)
        self.assertIsNone(self.manager.current_circuit)
        self.assertIsNone(self.manager._last_circuit_id)

    def test_track_transfer_counts_sent_and_received(self):
        from types import SimpleNamespace

        class Response:
            content = b"12345"
            request = SimpleNamespace(
                method="GET", url="https://check.torproject.org/api/ip",
                headers={"User-Agent": "RedTor"}, body=None)

        before_sent, before_recv = self.manager.bytes_sent, self.manager.bytes_received
        self.manager._track_transfer(Response())
        self.assertGreater(self.manager.bytes_sent, before_sent)
        self.assertEqual(self.manager.bytes_received, before_recv + 5)

    def test_authenticate_failure_closes_the_control_socket(self):
        closed = []

        class BrokenController:
            def authenticate(self):
                raise RuntimeError("bad cookie")

            def close(self):
                closed.append(True)

        class FakeController:
            @staticmethod
            def from_port(**kwargs):
                return BrokenController()

        with patch.object(tor_core, "Controller", FakeController), \
             patch.object(tor_core, "STEM_AVAILABLE", True), \
             patch.object(self.manager, "_verify_existing_socks",
                          return_value=(False, "no socks")), \
             patch.object(self.manager, "is_tor_installed", return_value=False), \
             patch.object(self.manager, "_start_tor") as start_tor:
            ok, message = self.manager.connect()
        self.assertFalse(ok)
        self.assertTrue(closed)
        start_tor.assert_not_called()

    def test_circuits_built_counts_distinct_circuits_not_refreshes(self):
        class Circuit:
            id, purpose, status = "9", "GENERAL", "BUILT"
            path = [("FP1", "Entry"), ("FP2", "Exit")]

        class FakeController:
            def get_circuits(self):
                return [Circuit()]

            def get_streams(self):
                return []

        self.manager.controller = FakeController()
        self.manager.connected = True
        with patch.object(self.manager, "_geo_for_fp",
                          return_value=("??", "Location unavailable", None, None)):
            self.manager.refresh_circuit()
            self.manager.refresh_circuit()
            self.assertEqual(self.manager.circuits_built, 1)
            Circuit.id = "10"
            self.manager.refresh_circuit()
        self.assertEqual(self.manager.circuits_built, 2)


if __name__ == "__main__":
    unittest.main()
