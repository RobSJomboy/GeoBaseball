"""Second chance for towns whose road-snapped drop point has no Google Street View.

Searches rings around the town center (150-800 m, 8 directions) for a point with official coverage
(same keyless thumbnail check as check_sv.py), snaps that point onto its road with OSRM, and keeps it
only if the snapped point passes the check too.

usage: python3 rescue_sv.py <locations_verified.js in> <locations.js out>
"""
import sys, os, json, re, math, subprocess, time
from concurrent.futures import ThreadPoolExecutor

src, dst = sys.argv[1:3]
L = json.loads(re.search(r'=(\{.*\});', open(src).read(), re.S).group(1))
UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 Chrome/124 Safari/537.36'

def has_sv(la, lo):
    url = (f'https://geo0.ggpht.com/cbk?cb_client=maps_sv.tactile&output=thumbnail&thumb=2&w=200&h=100&ll={la},{lo}&yaw=0&pitch=0')
    for _ in range(3):
        r = subprocess.run(['curl', '-s', '-m', '20', '-A', UA, '-o', '/dev/null', '-w', '%{http_code} %{size_download}', url], capture_output=True, text=True)
        try:
            c, n = map(int, r.stdout.split())
            if c == 200: return n >= 2000
        except ValueError: pass
    return False

def snap(la, lo):
    r = subprocess.run(['curl', '-s', '-m', '20', '-A', 'GeoBaseball-build/1.0',
                        f'https://router.project-osrm.org/nearest/v1/driving/{lo},{la}?number=3'], capture_output=True, text=True)
    time.sleep(1.05)
    try:
        ws = [w for w in json.loads(r.stdout)['waypoints'] if w['distance'] < 120]
        named = [w for w in ws if w.get('name')] or ws
        return (round(named[0]['location'][1], 6), round(named[0]['location'][0], 6)) if named else None
    except Exception: return None

def ring_points(la, lo):
    k = 1 / (111320 * math.cos(math.radians(la)))
    yield la, lo
    for rad in (150, 300, 500, 800):
        for a in range(0, 360, 45):
            yield la + rad * math.sin(math.radians(a)) / 110540, lo + rad * math.cos(math.radians(a)) * k

def find(item):
    k, v = item
    for la, lo in ring_points(v[0], v[1]):
        if has_sv(la, lo): return k, (la, lo)
    return k, None

failed = [(k, v) for k, v in L.items() if len(v) < 4]
print(f'{len(failed)} towns to rescue', file=sys.stderr)
with ThreadPoolExecutor(max_workers=4) as ex:
    found = list(ex.map(find, failed))
saved = 0
for k, hit in found:
    if not hit: continue
    s = snap(*hit)
    if s and has_sv(*s):
        L[k] = L[k][:2] + [s[0], s[1]]; saved += 1
print(f'rescued {saved} of {len(failed)}', file=sys.stderr)
print(f'{sum(len(v) == 4 for v in L.values())} of {len(L)} towns have verified Street View', file=sys.stderr)
open(dst, 'w').write('window.GEO_LOCS=' + json.dumps(L, separators=(',', ':')) + ';\n')
