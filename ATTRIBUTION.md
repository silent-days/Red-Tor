# Map data attribution

The offline world land background uses `natural-earth-110m-land.geojson`, a low-resolution Natural Earth land-polygon dataset. Natural Earth describes the 1:110m land layer as land polygons including major islands and makes its vector/raster map data public domain.

- Dataset page: https://www.naturalearthdata.com/downloads/110m-physical-vectors/110m-land/
- Public-domain terms: https://www.naturalearthdata.com/about/terms-of-use/
- Bundled GeoJSON source: https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_110m_land.geojson
- Dataset file SHA-256: `9e0729ee253ca7d7a5c4ae9395fb1902264c5377c52e224d13dd85010e2835d9`

The data is bundled so the geographic map background works offline; it is separate from the optional Tor relay GeoIP requests. Relay coordinates, when enabled, are approximate metadata obtained from Tor Metrics through the Tor SOCKS proxy. The map does not show the user's location or claim to trace packet routes.
