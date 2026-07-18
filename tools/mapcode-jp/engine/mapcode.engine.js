// mapcode.engine.js — Japanese Mapcode encode/decode (reverse-engineered, UNOFFICIAL)
// CommonJS port for Node (sweetbot-next). Browser version: ../mapcode.js
//
// Encode logic adapted from bespired/mapcode (MIT, (c) 2025 Joeri Kassenaar),
// derived from saibara.sakura.ne.jp's reverse-engineering of DENSO's マップコード.
// Decode is the inverse of the same grid math (written here).
//
// ⚠️ NOT the official DENSO algorithm — approximate, edges may differ.
// "マップコード" is a registered trademark of DENSO. Personal/community use only.
//
// Grid: zone (ZoneCoords table) → block (30×30) → unit (30×30) → core (10×10)

const ZoneCoords = require('./zonecoords.data.js');

const pad = (v, n) => ('000' + v).slice(-n);

// Find the zone box containing lat/lon. Returns zone key (string) or null.
function inZone(lat, lon) {
  for (const k of Object.keys(ZoneCoords)) {
    const [flat, flon, tlat, tlon] = ZoneCoords[k];
    if (lat >= flat && lat < tlat && lon >= flon && lon < tlon) return k;
  }
  return null;
}

// lat/lon -> { code, parts:{zone,block,unit,core} } or null if out of bounds
function encode(lat, lon) {
  const zoneKey = inZone(lat, lon);
  if (zoneKey === null) return null;
  const zone = Number(zoneKey);
  const [flat, flon, tlat, tlon] = ZoneCoords[zoneKey];
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
  const [flat, flon, tlat, tlon] = ZoneCoords[String(zone)];
  const dlat = tlat - flat, dlon = tlon - flon;

  const yblock = Math.floor(block / 30), xblock = block % 30;
  const bLat = flat + yblock * (dlat / 30), bLon = flon + xblock * (dlon / 30);

  const yunit = Math.floor(unit / 30), xunit = unit % 30;
  const uLat = bLat + yunit * (dlat / 900), uLon = bLon + xunit * (dlon / 900);

  const ycore = Math.floor(core / 10), xcore = core % 10;
  const cH = dlat / 8100, cW = dlon / 8100;
  const cLat = uLat + ycore * cH, cLon = uLon + xcore * cW;

  return { lat: cLat + cH / 2, lon: cLon + cW / 2, cellH: cH, cellW: cW };
}

function distMeters(a, b) {
  const R = 6371000, toRad = (d) => (d * Math.PI) / 180;
  const dLat = toRad(b.lat - a.lat), dLon = toRad(b.lon - a.lon);
  const s = Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(a.lat)) * Math.cos(toRad(b.lat)) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(s));
}

// Split a code string into base (car-nav ~30m) and high-precision *core suffix.
function splitCode(code) {
  const [base, core] = code.split('*');
  return { base: base.trim(), hi: core ? base.trim() + '*' + core : base.trim(), core: core || '' };
}

// full round-trip: encode -> decode -> offset from original pin
function generate(lat, lon) {
  const enc = encode(lat, lon);
  if (!enc) return { ok: false, reason: 'out_of_bounds' };
  const dec = decode(enc.parts);
  const offset = distMeters({ lat, lon }, dec);
  const { base, hi } = splitCode(enc.code);
  return { ok: true, code: enc.code, base, hi, parts: enc.parts, decoded: dec, offsetM: offset };
}

module.exports = { encode, decode, generate, distMeters, splitCode, inZone };
