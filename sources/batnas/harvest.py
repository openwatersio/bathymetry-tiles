#!/usr/bin/env python3
"""Refresh the BATNAS R2 mirror — a one-off acquisition tool (NOT part of the build).

BATNAS (Indonesia / BIG) has no static download URLs and its download is reCAPTCHA-login-
gated, so CI can't fetch it. Instead we mirror the raw sheets to R2 once and let the normal
`sources/batnas` recipe fetch that mirror over public HTTPS (see file_list.txt / Justfile).
Re-run this only when BIG publishes a new BATNAS version:

  1. Log in at https://tanahair.indonesia.go.id/ (free account), open Unduh → BATNAS, click
     any sheet and Download; copy the `token=...` value from that request (it lives ~1 h).
  2. BATNAS_TOKEN=<token> python harvest.py <out_dir>          # downloads the raw 5° sheets
  3. rclone copy <out_dir> r2:data/bathymetry/mirror/batnas --include '*.tif'
  4. regenerate file_list.txt if the sheet set / version changed.

Stdlib only — no deps, no pipeline coupling. Tiles: 6 arc-sec (~180 m), EPSG:4326 (not
embedded → the recipe's normalize assigns it), MSL elevation (seafloor negative, land positive).

  index:    GET /portal-web/batnas.json                  (public GeoJSON; properties.Penamaan)
  download: GET /api-inageo/unduh/batnas?token=<JWT>&filename=BATNAS_<Penamaan>_MSL_v<ver>.tif
"""

import concurrent.futures
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request


class TokenExpired(RuntimeError):
    """The download token returned 401 — distinct from a genuine 404 (no such sheet)."""

INDEX = "https://tanahair.indonesia.go.id/portal-web/batnas.json"
DOWNLOAD = "https://tanahair.indonesia.go.id/api-inageo/unduh/batnas"
VERSIONS = ["1.6", "1.5", "1.1"]  # newest first → take the latest version each sheet has
                                  # (the index carries no version; only the download endpoint knows)


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return r.read()


def sheets(bbox):
    feats = json.loads(get(INDEX))["features"]
    names = []
    for f in feats:
        p = f["properties"]
        if bbox and (p["xmax"] <= bbox[0] or p["xmin"] >= bbox[2]
                     or p["ymax"] <= bbox[1] or p["ymin"] >= bbox[3]):
            continue
        names.append(p["Penamaan"])
    return names


def fetch(token, penamaan, out_dir):
    for ver in VERSIONS:
        fn = f"BATNAS_{penamaan}_MSL_v{ver}.tif"
        q = urllib.parse.urlencode({"token": token, "filename": fn})
        try:
            data = get(f"{DOWNLOAD}?{q}")
        except urllib.error.HTTPError as e:
            if e.code == 401:  # token expired/invalid — abort, don't mistake it for "no data"
                raise TokenExpired("token returned 401 (expired/invalid)")
            continue  # 404 etc. → try the next version, else treat as no such sheet
        except Exception:
            continue
        if data[:2] in (b"II", b"MM"):  # a real TIFF, not an HTML error page
            with open(os.path.join(out_dir, fn), "wb") as f:
                f.write(data)
            return fn
    return None


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: BATNAS_TOKEN=<jwt> python harvest.py <out_dir>   (optional BBOX=W,S,E,N)")
    out_dir = sys.argv[1]
    token = os.environ.get("BATNAS_TOKEN")
    if not token:
        sys.exit("set BATNAS_TOKEN — log in at tanahair.indonesia.go.id, trigger a sheet\n"
                 "download, and copy the token=... from that request (valid ~1h).")
    bbox = os.environ.get("BBOX")
    bbox = [float(x) for x in bbox.split(",")] if bbox else None
    os.makedirs(out_dir, exist_ok=True)
    names = sheets(bbox)
    print(f"{len(names)} candidate sheet(s){' in ' + str(bbox) if bbox else ''}")
    # Parallel: 36 MB/sheet sequentially blew past the ~1 h token mid-run and silently skipped
    # the rest. 8 workers finish well inside the window; a 401 in any worker aborts loudly.
    got = 0
    expired = False
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(fetch, token, n, out_dir): n for n in names}
        for done, fut in enumerate(concurrent.futures.as_completed(futs), 1):
            try:
                if fut.result():
                    got += 1
            except TokenExpired:
                expired = True
            if done % 20 == 0:
                print(f"  {done}/{len(names)} ({got} written)")
    print(f"wrote {got}/{len(names)} sheet(s) to {out_dir}")
    if expired:
        sys.exit("token expired mid-harvest (401) — re-mint a fresh token and re-run to fill the\n"
                 "rest; the missing sheets were NOT 'no data', the token just lapsed.")
    if got == 0:
        sys.exit("nothing downloaded — token likely expired/invalid")


if __name__ == "__main__":
    main()
