"""Move each town's Street View drop point onto the nearest named road.

Why: the keyless Street View embed opens the panorama nearest the point it's given. Town-center points
often sit on a landmark where people upload their own (sometimes indoor) photospheres; Google's car
imagery runs down the road centerline, so a point on a named street lands on official coverage.

Uses the public OSRM 'nearest' service (car profile), at most 1 request a second per its usage policy.
Regions whose players.js svMode is 'photo' (no Google car coverage: Venezuela, Cuba...) are snapped by a
second worker (--only-photo, own cache): uploaded photos taken on a street are outdoors, indoor ones aren't.

usage: python3 snap_roads.py <players.js> <locations.js in> <locations.js out>
Writes each snapped town as [lat, lng, svLat, svLng]; lat/lng (town center) stays the answer.
Resumable: progress is cached in snap_cache.json next to this script.
"""
import sys, os, json, re, time, subprocess

args = [a for a in sys.argv[1:] if not a.startswith('--')]
pjs, src, dst = args[:3]
ONLY_PHOTO = '--only-photo' in sys.argv   # second worker: the photo-only countries, own cache file
D = json.loads(re.search(r'=(\{.*\});', open(pjs, encoding='utf-8').read(), re.S).group(1))
mode = D.get('svMode', {})
L = json.loads(re.search(r'=(\{.*\});', open(src).read(), re.S).group(1))
here = os.path.dirname(os.path.abspath(__file__))
cache_p = os.path.join(here, 'snap_cache_photo.json' if ONLY_PHOTO else 'snap_cache.json')
cache = json.load(open(cache_p)) if os.path.exists(cache_p) else {}

want = (lambda m: m == 'photo') if ONLY_PHOTO else (lambda m: m == 'road')
todo = [k for k in L if k not in cache and want(mode.get(k.split('|')[0], 'road'))]
print(f'{len(todo)} towns to snap ({len(cache)} cached)', file=sys.stderr)
for i, k in enumerate(todo):
    la, lo = L[k][:2]
    url = f'https://router.project-osrm.org/nearest/v1/driving/{lo},{la}?number=5'
    res = None
    for attempt in range(4):
        r = subprocess.run(['curl', '-s', '-m', '20', '-A', 'GeoBaseball-build/1.0', url], capture_output=True, text=True)
        try:
            j = json.loads(r.stdout)
            if j.get('code') == 'Ok': res = j['waypoints']; break
        except Exception: pass
        time.sleep(3 * (attempt + 1))
    if res is not None:
        named = [w for w in res if w.get('name') and w['distance'] < 600]
        w = named[0] if named else (res[0] if res and res[0]['distance'] < 300 else None)
        cache[k] = [round(w['location'][1], 6), round(w['location'][0], 6)] if w else None
    if i % 25 == 0:
        json.dump(cache, open(cache_p, 'w')); print(f'  {i}/{len(todo)}', file=sys.stderr, flush=True)
    time.sleep(2.2 if ONLY_PHOTO else 1.05)
json.dump(cache, open(cache_p, 'w'))

other = os.path.join(here, 'snap_cache.json' if ONLY_PHOTO else 'snap_cache_photo.json')
both = {**(json.load(open(other)) if os.path.exists(other) else {}), **cache}
out, n = {}, 0
for k, v in L.items():
    s = both.get(k)
    out[k] = v[:2] + s if s else v[:2]; n += bool(s)
print(f'snapped {n} of {len(L)} towns', file=sys.stderr)
open(dst, 'w').write('window.GEO_LOCS=' + json.dumps(out, separators=(',', ':')) + ';\n')
