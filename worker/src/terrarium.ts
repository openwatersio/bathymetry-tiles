// Terrarium elevation packing: height = R*256 + G + B/256 - 32768 (metres).
// Resampling Terrarium safely means decode → interpolate height → re-encode; the
// packed bytes themselves can't be averaged (G wraps at 256 and corrupts the height).

export function unpackTerrarium(r: number, g: number, b: number): number {
  return r * 256 + g + b / 256 - 32768;
}

// Catmull-Rom cubic through p1,p2 (t in [0,1]); p0,p3 are the outer neighbours.
// Constant input -> constant output and a linear ramp stays linear, so a locally-flat
// source cell borrows slope from its neighbours instead of stepping — that's what keeps
// iso-depth edges smooth across coarse cells. Can overshoot slightly near sharp steps.
export function catmullRom(
  p0: number,
  p1: number,
  p2: number,
  p3: number,
  t: number,
): number {
  return (
    0.5 *
    (2 * p1 +
      (p2 - p0) * t +
      (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t +
      (3 * p1 - 3 * p2 + p3 - p0) * t * t * t)
  );
}

// Writes R,G,B,A straight into an RGBA buffer at byte offset `di` (avoids a per-pixel
// array allocation in the overzoom loop — ~260k pixels/tile).
export function packTerrariumInto(
  out: Uint8ClampedArray,
  di: number,
  height: number,
): void {
  let v = Math.round((height + 32768) * 256); // height in 1/256 m above the -32768 datum
  if (v < 0) v = 0;
  else if (v > 0xffffff) v = 0xffffff;
  out[di] = (v >> 16) & 0xff;
  out[di + 1] = (v >> 8) & 0xff;
  out[di + 2] = v & 0xff;
  out[di + 3] = 255;
}
