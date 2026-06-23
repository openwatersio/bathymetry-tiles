// Run: node src/terrarium.test.mjs   (Node ≥22.18 strips the imported .ts)
import assert from "node:assert/strict";
import { unpackTerrarium, packTerrariumInto } from "./terrarium.ts";

const buf = new Uint8ClampedArray(4);
const roundtrip = (h) => {
  packTerrariumInto(buf, 0, h);
  return unpackTerrarium(buf[0], buf[1], buf[2]);
};

// pack→unpack recovers the height to within Terrarium's 1/256 m quantum
for (const h of [-10916, -200, -30.5, 0, 0.004, 4321, 8848.86]) {
  assert.ok(Math.abs(roundtrip(h) - h) <= 1 / 256, `roundtrip ${h}`);
}

// bilinear weights that re-encode equal corners must stay flat (no stair-step), and a
// midpoint must land exactly between two depths
const lerp = (a, b, w) => a * (1 - w) + b * w;
assert.equal(roundtrip(lerp(-50, -50, 0.5)), roundtrip(-50)); // flat region stays flat
const mid = roundtrip(lerp(-40, -60, 0.5));
assert.ok(Math.abs(mid - -50) <= 1 / 256, "midpoint interpolates");

// clamp: absurd heights saturate instead of wrapping the RGB
packTerrariumInto(buf, 0, 1e9);
assert.deepEqual([buf[0], buf[1], buf[2]], [255, 255, 255]);
packTerrariumInto(buf, 0, -1e9);
assert.deepEqual([buf[0], buf[1], buf[2]], [0, 0, 0]);

console.log("ok");
