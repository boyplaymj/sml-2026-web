// mapcode.js — Japanese Mapcode encode/decode (reverse-engineered, UNOFFICIAL)
//
// Encode logic adapted from bespired/mapcode (MIT, (c) 2025 Joeri Kassenaar),
// itself derived from saibara.sakura.ne.jp's reverse-engineering of DENSO's
// マップコード. Decode written here as the inverse of the same grid math.
//
// ⚠️ NOT the official DENSO algorithm. Results approximate the real mapcode and
// may differ at edges. "マップコード" is a registered trademark of DENSO — this
// file is for personal use only, not commercial redistribution. See README.md.
//
// Grid model: zone (from ZoneCoords table) → block (30×30) → unit (30×30) → core (10×10)

const Mapcode = (function () {
  const Z = () => window.ZoneCoords;
  const pad = (v, n) => ('000' + v).slice(-n);

  // Find the zone box that contains lat/lon. Returns zone key (string) or null.
  function inZone(lat, lon) {
    const zc = Z();
    for (const k of Object.keys(zc)) {
      const [flat, flon, tlat, tlon] = zc[k];
      if (lat >= flat && lat < tlat && lon >= flon && lon < tlon) return k;
    }
    return null;
  }

  // lat/lon -> { code, parts:{zone,block,unit,core}, cell:{...} }  or null if out of bounds
  function encode(lat, lon) {
    const zoneKey = inZone(lat, lon);
    if (zoneKey === null) return null;
    const zone = Number(zoneKey);
    const [flat, flon, tlat, tlon] = Z()[zoneKey];
    const dlat = tlat - flat, dlon = tlon - flon;

    const xblock = Math.floor(((lon - flon) / dlon) * 30);
    const yblock = Math.floor(((lat - flat) / dlat) * 30);
    const block = yblock * 30 + xblock;

    const bH = dlat / 30, bW = dlon / 30;
    const bLat = flat + yblock * bH, bLon = flon + xblock * bW;

    const xunit = Math.floor(((lon - bLon) / bW) * 30);
    const yunit = Math.floor(((lat - bLat) / bH) * 30);
    const unit = (yunit % 30) * 30 + (xunit % 30);

    const uH = dlat / 900, uW = dlon / 900;
    const uLat = bLat + yunit * uH, uLon = bLon + xunit * uW;

    const xcore = Math.floor(((lon - uLon) / uW) * 10);
    const ycore = Math.floor(((lat - uLat) / uH) * 10);
    const core = (ycore % 10) * 10 + (xcore % 10);

    // format string (zone 0 = Tokyo core has a compressed form)
    let code;
    if (zone === 0) {
      if (block === 0 && unit === 0) code = '*' + pad(core, 2);
      else if (block === 0) code = unit + '*' + pad(core, 2);
      else code = block + ' ' + pad(unit, 3) + '*' + pad(core, 2);
    } else {
      code = zone + ' ' + pad(block, 3) + ' ' + pad(unit, 3) + '*' + pad(core, 2);
    }

    return { code, parts: { zone, block, unit, core } };
  }

  // {zone,block,unit,core} -> center lat/lon of that core cell (inverse of encode)
  function decode(parts) {
    const { zone, block, unit, core } = parts;
    const [flat, flon, tlat, tlon] = Z()[String(zone)];
    const dlat = tlat - flat, dlon = tlon - flon;

    const yblock = Math.floor(block / 30), xblock = block % 30;
    const bLat = flat + yblock * (dlat / 30), bLon = flon + xblock * (dlon / 30);

    const yunit = Math.floor(unit / 30), xunit = unit % 30;
    const uLat = bLat + yunit * (dlat / 900), uLon = bLon + xunit * (dlon / 900);

    const ycore = Math.floor(core / 10), xcore = core % 10;
    const cH = dlat / 8100, cW = dlon / 8100;
    const cLat = uLat + ycore * cH, cLon = uLon + xcore * cW;

    // center of the core cell
    return { lat: cLat + cH / 2, lon: cLon + cW / 2, cellH: cH, cellW: cW };
  }

  // haversine metres
  function distMeters(a, b) {
    const R = 6371000, toRad = (d) => (d * Math.PI) / 180;
    const dLat = toRad(b.lat - a.lat), dLon = toRad(b.lon - a.lon);
    const s = Math.sin(dLat / 2) ** 2 +
      Math.cos(toRad(a.lat)) * Math.cos(toRad(b.lat)) * Math.sin(dLon / 2) ** 2;
    return 2 * R * Math.asin(Math.sqrt(s));
  }

  // full round-trip: encode -> decode -> offset from original pin
  function generate(lat, lon) {
    const enc = encode(lat, lon);
    if (!enc) return { ok: false, reason: 'out_of_bounds' };
    const dec = decode(enc.parts);
    const offset = distMeters({ lat, lon }, dec);
    return { ok: true, code: enc.code, parts: enc.parts, decoded: dec, offsetM: offset };
  }

  return { encode, decode, generate, distMeters, inZone };
})();

if (typeof window !== 'undefined') window.Mapcode = Mapcode;
