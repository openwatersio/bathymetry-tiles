// Run: node src/terrarium.test.mjs   (Node ≥22.18 strips the imported .ts)
import assert from "node:assert/strict";
import { unpackTerrarium, packTerrariumInto, catmullRom } from "./terrarium.ts";

// Catmull-Rom: hits the inner control points, keeps a flat region flat (no overshoot on
// constant input → no spurious band-edge fringe), and reproduces a linear ramp exactly.
assert.equal(catmullRom(3, 7, 9, 2, 0), 7); // t=0 → p1
assert.equal(catmullRom(3, 7, 9, 2, 1), 9); // t=1 → p2
assert.equal(catmullRom(5, 5, 5, 5, 0.37), 5); // constant stays constant
assert.ok(Math.abs(catmullRom(0, 1, 2, 3, 0.5) - 1.5) < 1e-12); // linear ramp → linear

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
