"""Harvest CHS NONNA bathymetry tiles for a BBOX into store/source/<id>/.

NONNA has no static download URLs; data comes from a 3-step public *guest* API (no
account), reverse-engineered from the data.chs-shc.ca portal:

  1. POST /services/authorization/credentials/guest  (header ``tenant: nonna``) →
     an outer JWT whose payload carries ``carisServiceToken`` — the Bearer for the
     data APIs.
  2. GET /v1/feature/datastores/nonna/datasets/Bathymetry/features  (CQL bbox +
     ``RepresentationLevel``) → GeoJSON, one feature per 1° tile, each carrying a
     GeoTIFF ``objectLocation``. The server 301-redirects to a ``+``-encoded URL, so
     requests must follow redirects.
  3. POST /services/objectstore/download  (the objectId) → a zip holding the .tiff.

Tiles are EPSG:4326, Float32, vertical = **Chart Datum** (low-water); values are
elevation (seafloor negative, drying heights positive) → no negate. ``RepresentationLevel``
selects resolution: **2 = NONNA 100 m** (set NONNA_LEVEL to harvest another). BBOX is
required — all of Canada at 10 m is hundreds of GB.

Run from pipelines/:  BBOX="-67,43,-66,45" uv run python source_download_nonna.py nonna_100
Self-check (one live tile):  uv run python source_download_nonna.py --check
"""

import base64
import io
import json
import os
import sys
import zipfile

import requests

BASE = "https://data.chs-shc.ca"
PAGE = 5000


def guest_token():
    """(outer, caris): the outer JWT is the Bearer for /services/* (e.g. objectstore
    download); its nested ``carisServiceToken`` is the Bearer for /v1/feature/*."""
    r = requests.post(f"{BASE}/services/authorization/credentials/guest",
                      headers={"tenant": "nonna", "Content-Type": "application/json"}, timeout=60)
    r.raise_for_status()
    outer = r.json()["token"]
    payload = outer.split(".")[1]
    payload += "=" * (-len(payload) % 4)  # restore base64 padding
    caris = json.loads(base64.urlsafe_b64decode(payload))["carisServiceToken"]
    return outer, caris


def list_tiles(token, bbox, level):
    w, s, e, n = bbox
    cql = (f"INTERSECTS(geometry, POLYGON(({w} {s},{e} {s},{e} {n},{w} {n},{w} {s}))) "
           f"AND RepresentationLevel={level}")
    hdr = {"tenant": "nonna", "Authorization": f"Bearer {token}"}
    tiles, start = [], 1
    while True:
        r = requests.get(f"{BASE}/v1/feature/datastores/nonna/datasets/Bathymetry/features",
                         params={"expand": "properties.products,geometry", "filter.type": "cql",
                                 "filter.expression": cql, "range.count": PAGE, "range.start": start},
                         headers=hdr, timeout=120)  # requests follows the 301 by default
        r.raise_for_status()
        feats = r.json().get("features", [])
        tiles += feats
        if len(feats) < PAGE:
            return tiles
        start += len(feats)


def geotiff_ref(feat):
    """(objectLocation, cellName) of a feature's GeoTIFF product, or (None, None)."""
    props = feat.get("properties", {})
    for p in props.get("products", []):
        if p.get("productType") == "GeoTIFF" and p.get("fileReferences"):
            fr = p["fileReferences"][0]
            cell = props.get("cellName") or fr["fileName"].rsplit(".", 1)[0]
            return fr["objectLocation"], cell
    return None, None


def fetch_tiff(token, object_location, cell):
    """POST objectstore/download for one tile; return the .tiff bytes (unzipped)."""
    object_id = object_location.split("objects/", 1)[1]  # drop the buckets/Bathymetry/objects/ prefix
    body = [{"bucketId": "Bathymetry", "objectId": object_id, "fileName": f"{cell}.tiff",
             "locationType": "objectstore", "cellName": cell, "product": "GeoTIFF", "hashkey": ""}]
    r = requests.post(f"{BASE}/services/objectstore/download",
                      headers={"tenant": "nonna", "Authorization": f"Bearer {token}",
                               "Content-Type": "application/json"}, json=body, timeout=300)
    r.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        name = next(n for n in z.namelist() if n.lower().endswith((".tif", ".tiff")))
        return z.read(name)


def harvest(source, bbox, level, out_dir):
    outer, caris = guest_token()
    tiles = list_tiles(caris, bbox, level)        # /v1/feature → carisServiceToken
    print(f"{source}: {len(tiles)} tile(s) at RepresentationLevel={level} in {bbox}")
    os.makedirs(out_dir, exist_ok=True)
    written = 0
    for i, feat in enumerate(tiles):
        loc, cell = geotiff_ref(feat)
        if not loc:
            continue
        open(f"{out_dir}/{cell}.tif", "wb").write(fetch_tiff(outer, loc, cell))  # /services → outer JWT
        written += 1
        if i % 25 == 0 and i:
            print(f"  {i}/{len(tiles)}")
    print(f"{source}: wrote {written} GeoTIFF(s) to {out_dir}")
    return written


def main():
    if sys.argv[1:2] == ["--check"]:
        _check()
        return
    if len(sys.argv) != 2:
        sys.exit("usage: source_download_nonna.py <source-id>   (needs BBOX, optional NONNA_LEVEL)")
    source = sys.argv[1]
    bbox = os.environ.get("BBOX")
    if not bbox:
        sys.exit("NONNA needs BBOX=W,S,E,N (all of Canada at 10 m is hundreds of GB)")
    level = int(os.environ.get("NONNA_LEVEL", "2"))  # 2 = NONNA 100 m
    harvest(source, [float(x) for x in bbox.split(",")], level, f"store/source/{source}")


def _check():
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        # One 1° tile in the Bay of Fundy (NONNA100_4400N06700W) at level 2 (100 m).
        n = harvest("nonna_check", [-67.0, 43.9, -66.9, 44.1], 2, d)
        assert n >= 1, "expected at least one tile"
        tifs = [f for f in os.listdir(d) if f.endswith(".tif")]
        assert tifs, "no .tif written"
        assert os.path.getsize(f"{d}/{tifs[0]}") > 100_000, "tile suspiciously small"
    print("source_download_nonna self-check: ok")


if __name__ == "__main__":
    main()
