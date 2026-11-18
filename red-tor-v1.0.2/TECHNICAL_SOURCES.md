# Technical source notes

- Stem's official API documents Tor circuit and stream status enumerations. The app reads current stream records only from an authenticated local Tor controller; the host/port shown in the UI is parsed from that controller-reported target and is not resolved by the parser. Only `SENTCONNECT` and `SUCCEEDED` records associated with the selected circuit are displayed as active targets. [Stem Controller API](https://stem.torproject.org/api/control.html) [Stem response API](https://stem.torproject.org/api/response.html)
- Tor Metrics Onionoo describes relay `country`, `country_name`, `region_name`, `city_name`, `latitude`, and `longitude` as values from GeoIP lookup of the relay's first onion-routing IP address. These are approximate database-derived locations, not exact physical server positions. The map labels them as estimates and never invents coordinates. [Onionoo protocol](https://metrics.torproject.org/onionoo.html)
- Destination-host geolocation is off by default. If explicitly enabled, Red Tor submits the active stream hostname to the configured provider through the verified Tor SOCKS proxy; failures do not trigger local DNS or direct-connection fallback. Relay geolocation uses the Tor SOCKS proxy as well.

The checked documentation pages:

- https://stem.torproject.org/api/control.html
- https://stem.torproject.org/api/response.html
- https://metrics.torproject.org/onionoo.html
