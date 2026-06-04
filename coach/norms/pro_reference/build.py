"""Orchestrate the GolfDB pro-reference build: download -> extract -> cache.

For each unique youtube_id in the (optionally sampled) manifest:
  * download the source video with yt-dlp (skip if already cached / failed),
  * extract every swing annotated on that video (extract.py),
  * append per-swing records to a JSONL cache (resumable),
  * delete the source video to keep disk bounded.

Link rot is expected (~10-30% of YouTube IDs). A failed download is logged to a
`failed.txt` set and skipped on resume; it never aborts the run.

This is offline data-generation tooling (like build_norms.py) -- it depends on
yt-dlp + an external clone of wmcnally/golfdb for golfDB.pkl. Run via the CLI at
the bottom; the aggregator (aggregate.py) turns the JSONL cache into
pro_reference.json.
"""
import json
import os
import subprocess
import sys
from collections import defaultdict
from typing import Dict, List, Optional

from coach.norms.pro_reference.manifest import build_manifest
from coach.norms.pro_reference.extract import extract_swing


def _read_done_ids(records_path: str) -> set:
    done = set()
    if os.path.exists(records_path):
        with open(records_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    done.add(int(json.loads(line)["id"]))
                except Exception:
                    continue
    return done


def _read_set(path: str) -> set:
    if not os.path.exists(path):
        return set()
    with open(path, "r", encoding="utf-8") as f:
        return {l.strip() for l in f if l.strip()}


def _append_set(path: str, value: str) -> None:
    with open(path, "a", encoding="utf-8") as f:
        f.write(value + "\n")


def download_source(youtube_id: str, dest_dir: str,
                    timeout: int = 240) -> Optional[str]:
    """Download one YouTube video (<=1080p mp4) to dest_dir/<id>.mp4.
    Returns the path, or None on any failure (link rot, geo-block, etc.)."""
    out_tmpl = os.path.join(dest_dir, "%(id)s.%(ext)s")
    final = os.path.join(dest_dir, f"{youtube_id}.mp4")
    if os.path.exists(final):
        return final
    cmd = [
        sys.executable, "-m", "yt_dlp",
        "-f", "bestvideo[height<=1080][ext=mp4]/best[ext=mp4]/best",
        "--no-playlist", "--no-progress", "--quiet",
        "-o", out_tmpl,
        f"https://www.youtube.com/watch?v={youtube_id}",
    ]
    try:
        subprocess.run(cmd, timeout=timeout, check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        return None
    return final if os.path.exists(final) else None


def run(pkl_path: str, work_dir: str, *,
        sample: Optional[List[Dict]] = None,
        min_vis: float = 0.5, max_videos: Optional[int] = None,
        keep_videos: bool = False) -> Dict:
    """Download + extract over the manifest (or a provided `sample` subset).
    Appends records to work_dir/records.jsonl. Returns run stats."""
    os.makedirs(work_dir, exist_ok=True)
    src_dir = os.path.join(work_dir, "src_videos")
    os.makedirs(src_dir, exist_ok=True)
    records_path = os.path.join(work_dir, "records.jsonl")
    failed_path = os.path.join(work_dir, "failed.txt")

    manifest = sample if sample is not None else build_manifest(pkl_path)
    done_ids = _read_done_ids(records_path)
    failed_yt = _read_set(failed_path)

    by_yt: Dict[str, List[Dict]] = defaultdict(list)
    for m in manifest:
        by_yt[m["youtube_id"]].append(m)

    stats = {"videos_attempted": 0, "videos_failed": 0,
             "swings_extracted": 0, "swings_rejected": 0, "swings_skipped": 0}
    yt_ids = list(by_yt)
    for i, yt in enumerate(yt_ids):
        entries = by_yt[yt]
        pending = [e for e in entries if e["id"] not in done_ids]
        if not pending:
            continue
        if yt in failed_yt:
            stats["swings_skipped"] += len(pending)
            continue
        if max_videos is not None and stats["videos_attempted"] >= max_videos:
            break
        stats["videos_attempted"] += 1
        print(f"[{i+1}/{len(yt_ids)}] {yt}: {len(pending)} swing(s) ...",
              flush=True)
        vid = download_source(yt, src_dir)
        if vid is None:
            stats["videos_failed"] += 1
            _append_set(failed_path, yt)
            print(f"    download FAILED (link rot?) -> skipped", flush=True)
            continue
        for e in pending:
            try:
                rec = extract_swing(vid, e, min_vis=min_vis)
            except Exception as ex:
                rec = None
                print(f"    id={e['id']} extract error: {ex}", flush=True)
            if rec is None:
                stats["swings_rejected"] += 1
                continue
            with open(records_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec) + "\n")
            done_ids.add(e["id"])
            stats["swings_extracted"] += 1
        if not keep_videos:
            try:
                os.remove(vid)
            except OSError:
                pass
        print(f"    done. running total: {stats['swings_extracted']} swings",
              flush=True)
    return stats


def _stable_key(s: str) -> str:
    """Deterministic hash (unlike Python's salted hash()) for reproducible,
    alphabetically-unbiased ordering across runs."""
    import hashlib
    return hashlib.md5(s.encode("utf-8")).hexdigest()


def _build_sample(pkl_path: str, per_view: int, prefer_full_speed: bool = True,
                  max_per_player_view: int = 1) -> List[Dict]:
    """Build a diverse sample: up to `per_view` swings per view, capped at
    `max_per_player_view` swings per (player, view), preferring slow==0 and
    spreading across players (deterministic hash order, not alphabetical)."""
    manifest = build_manifest(pkl_path)
    # order: full-speed first, then a stable pseudo-random player spread so the
    # sample isn't alphabetically front-loaded.
    manifest.sort(key=lambda m: (m["slow"] if prefer_full_speed else 0,
                                 _stable_key(m["player"] + str(m["id"]))))
    chosen: List[Dict] = []
    seen_pv = defaultdict(int)
    count_view = defaultdict(int)
    for m in manifest:
        v = m["view"]
        pv = (m["player"], v)
        if count_view[v] >= per_view:
            continue
        if seen_pv[pv] >= max_per_player_view:
            continue
        chosen.append(m)
        seen_pv[pv] += 1
        count_view[v] += 1
    return chosen


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="Build GolfDB pro reference cache")
    ap.add_argument("--pkl", required=True, help="path to golfDB.pkl")
    ap.add_argument("--work", required=True, help="work dir (cache + videos)")
    ap.add_argument("--per-view", type=int, default=0,
                    help="if >0, sample up to N swings per view (else full set)")
    ap.add_argument("--max-videos", type=int, default=None,
                    help="hard cap on videos downloaded this run")
    ap.add_argument("--min-vis", type=float, default=0.5)
    ap.add_argument("--keep-videos", action="store_true")
    args = ap.parse_args(argv)

    sample = (_build_sample(args.pkl, args.per_view)
              if args.per_view > 0 else None)
    stats = run(args.pkl, args.work, sample=sample, min_vis=args.min_vis,
                max_videos=args.max_videos, keep_videos=args.keep_videos)
    print("\nRUN STATS:", json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
