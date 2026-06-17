"""Shared core for *streaming* sources — COG tile collections already published on a
public bucket, registered WITHOUT downloading.

Instead of bulk-fetching the bytes, read each tile's *header* via GDAL ``/vsicurl/`` and
record its 3857 bounds in ``store/source/<id>/bounds.csv`` with the ``/vsicurl/`` path
itself as the "filename". The aggregation stage then range-reads only the COG blocks it
needs straight over public HTTPS (``config.source_path`` passes the ``/vsicurl/`` path
through — no credentials, so it coexists with the signed-free R2 reads of locally-prepared
sources). No normalize (tiles are already COGs with CRS + nodata), no polygonize/tarball
(a streaming source has no local bytes to redistribute).

Two enumeration shapes pick a front-end CLI, each resolving a list of tile URLs then calling
``register_tiles`` here: a flat text urllist (``source_register_remote_urllist``, CUDEM) or a
tile-scheme GeoPackage (``source_register_remote_geopkg``, BlueTopo).
"""

import os
import sys

import rasterio
from rasterio.warp import transform_bounds

import utils


def to_vsicurl(url):
    """An http(s)/s3:// URL -> a GDAL ``/vsicurl/`` path (public range reads, no creds)."""
    if url.startswith("s3://"):
        bucket, key = url[len("s3://"):].split("/", 1)
        url = f"https://{bucket}.s3.amazonaws.com/{key}"
    return "/vsicurl/" + url


def bounds_3857(src):
    left, bottom, right, top = transform_bounds(src.crs, "EPSG:3857", *src.bounds)
    if right - left > 0.9 * 2 * utils.X_MAX_3857:  # antimeridian flip (e.g. Aleutians)
        left, right = right, left
    return left, bottom, right, top


def register_tiles(source, urls):
    """Read each tile's header via /vsicurl and write store/source/<source>/bounds.csv
    (filename = the /vsicurl path, plus 3857 bounds + pixel size). The covering re-filters
    precisely from these bounds, so a generous upstream BBOX prefilter is fine."""
    os.makedirs(f"store/source/{source}", exist_ok=True)
    lines = ["filename,left,bottom,right,top,width,height\n"]
    for i, url in enumerate(urls):
        path = to_vsicurl(url)
        with rasterio.open(path) as src:
            if src.crs is None:
                sys.exit(f"crs not defined on {path}")
            left, bottom, right, top = bounds_3857(src)
            lines.append(f"{path},{left},{bottom},{right},{top},{src.width},{src.height}\n")
        if (i + 1) % 100 == 0:
            print(f"  registered {i + 1}/{len(urls)}")
    with open(f"store/source/{source}/bounds.csv", "w") as f:
        f.writelines(lines)
    print(f"{source}: registered {len(urls)} remote tiles")


def _check():
    assert to_vsicurl("s3://b/k/x.tif") == "/vsicurl/https://b.s3.amazonaws.com/k/x.tif"
    assert to_vsicurl("https://h.example/x.tif") == "/vsicurl/https://h.example/x.tif"
    print("source_remote.py self-check ok")


if __name__ == "__main__":
    _check()
