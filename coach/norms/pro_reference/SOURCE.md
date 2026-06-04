# Tour-pro reference — two files

This directory holds **two** tour-pro references:

1. **`golftec_reference.json` — AUTHORITATIVE** (the primary "ideal" tier).
   Hand-transcribed from GolfTEC's public **Tour Averages** chart and **SwingTRU
   Motion Study** (`build_golftec_reference.py`). Per the project decision
   (2026-06-04), **GolfTEC's published numbers are trusted over our GolfDB-deduced
   numbers wherever they conflict.** These are 3D measurements; each (metric,
   phase) is flagged `two_d_comparable_now` so the 2D app only compares where the
   body is square to the camera (≈ address) — rotated positions need the deferred
   two-camera 3D path.

2. **`pro_reference.json` — SECONDARY** (described below). It fills metrics
   GolfTEC doesn't publish (head sway, hand depth) and provides a *same-projection
   2D pro baseline* + variability bands for the rotated-position metrics until 3D
   exists.

---

`pro_reference.json` in this directory is **derived data** (per-phase percentile
bands) computed from real tour-professional swings in:

> **GolfDB: A Video Database for Golf Swing Sequencing**
> William McNally, Kanav Vats, Tyler Pinto, Chris Dragert, Alexander Wong,
> John McPhee. CVPR 2019 Workshop (CVSports).

- Source: https://github.com/wmcnally/golfdb
- License: **CC BY-NC 4.0 (NonCommercial)**.

## What is and isn't vendored

**Only the derived numbers** (`pro_reference.json`) are committed here. The
GolfDB videos, the YouTube source videos, and the `golfDB.pkl` annotation table
are **NOT** vendored — they are NonCommercial-licensed and are obtained/processed
locally by the build pipeline. This keeps the repo free of the NC-licensed
assets while retaining a citable, attributed tour-pro reference for
**personal / non-commercial** use.

## How it is produced

`coach/norms/pro_reference/` (`manifest.py` → `build.py` → `aggregate.py`):

1. `manifest.py` filters `golfDB.pkl` to real tour pros (drops `view=='other'`
   and a short list of celebrity non-pros), keeping face-on + down-the-line.
2. `build.py` downloads each source video with `yt-dlp`, crops the shipped
   fractional `bbox` at **native resolution**, and runs **our** `vision.pose`
   (MediaPipe) at the shipped GolfDB event frames (address = event 0, top =
   event 3, impact = event 5).
3. Metrics are computed with the **same** `metrics.geometry` primitives the
   production metric defs use, so the reference is in our exact definitions:
   - `shoulder_tilt_deg`, `hip_tilt_deg` (face-on), `spine_angle_deg` (DTL) —
     **exact angles**, directly comparable to the app's metrics (`confidence:
     high`).
   - `hip_sway_sw`, `head_sway_sw` — sway as a **fraction of address shoulder
     width** (scale-free, since pro heights are unknown). **Provisional**: needs
     the matching amateur-side %-shoulder-width redefinition before in-app use.
4. `aggregate.py` rolls per-swing records into per-phase p10/p25/p50/p75/p90
   bands with n, in a schema mirroring `norms.json`.

## Reproduce

```
# one-time: clone GolfDB (NC) outside the repo, get golfDB.pkl
git clone https://github.com/wmcnally/golfdb   # ships data/golfDB.pkl

# full set (downloads ~440 videos; resumable, link-rot tolerant):
python -m coach.norms.pro_reference.build \
    --pkl <path>/golfdb/data/golfDB.pkl --work <scratch>/proref_cache
python -m coach.norms.pro_reference.aggregate \
    --records <scratch>/proref_cache/records.jsonl
```

## Citation

    @inproceedings{mcnally2019golfdb,
      title={GolfDB: A Video Database for Golf Swing Sequencing},
      author={McNally, William and Vats, Kanav and Pinto, Tyler and Dragert,
              Chris and Wong, Alexander and McPhee, John},
      booktitle={Proceedings of the IEEE/CVF Conference on Computer Vision and
                 Pattern Recognition (CVPR) Workshops},
      year={2019}
    }
