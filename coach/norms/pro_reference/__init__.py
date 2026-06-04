"""GolfDB-derived TOUR-PRO reference, computed in OUR exact metric definitions.

This subpackage builds a per-phase tour-pro reference (the "ideal" tier) from
the GolfDB dataset (wmcnally/golfdb, CC BY-NC), to layer alongside the
CaddieSet mixed-skill "population" tier in coach/norms/norms.json.

Pipeline (see build.py): filter golfDB.pkl to real tour pros (manifest.py) ->
yt-dlp download source video -> crop by the shipped fractional bbox at NATIVE
resolution -> run OUR vision.pose at the shipped address/top/impact event
frames -> compute OUR metrics (exact angles; face-on sway as % shoulder width)
-> aggregate per (metric, view, phase) into pro_reference.json.

Only the DERIVED NUMBERS are vendored into the repo (not the CC BY-NC videos or
annotation table); see SOURCE.md for attribution.
"""
