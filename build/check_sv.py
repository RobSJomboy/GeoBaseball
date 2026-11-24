"""Keep only drop points that have Google's own Street View imagery.

Google's public Street View thumbnail URL (no key) returns a real photo when official car
coverage is near the point and a tiny blank image (~250-500 bytes) when it isn't. It never returns
user-uploaded photospheres, so a point that passes is outdoor street imagery. Drop points are
already snapped onto roads (snap_roads.py), so the embed opens that same car panorama.

usage: python3 check_sv.py <locations.js in> <locations.js out>
Points that fail keep only [lat, lng], which the game never uses as a drop.
Resumable via sv_check.json next to this script.
"""
import sys, os, json, re, subprocess
from concurrent.futures import ThreadPoolExecutor

src, dst = sys.argv[1:3]
L = json.loads(re.search(r'=(\{.*\});', open(src).read(), re.S).group(1))
here = os.path.dirname(os.path.abspath(__file__))
cp = os.path.join(here, 'sv_check.json')
cache = json.load(open(cp)) if os.path.exists(cp) else {}
UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 Chrome/124 Safari/537.36'
MIN_BYTES = 2000

def check(item):
    k, v = item
    url = (f'https://geo0.ggpht.com/cbk?cb_client=maps_sv.tactile&output=thumbnail&thumb=2&w=200&h=100'
           f'&ll={v[2]},{v[3]}&yaw=0&pitch=0')
    for _ in range(3):
        r = subprocess.run(['curl', '-s', '-m', '20', '-A', UA, '-o', '/dev/null', '-w', '%{http_code} %{size_download}', url],
                           capture_output=True, text=True)
        try:
            code, size = r.stdout.split(); code, size = int(code), int(size)
            if code == 200: return k, size
        except ValueError: pass
    return k, None

todo = [(k, v) for k, v in L.items() if len(v) == 4 and k not in cache]
print(f'{len(todo)} drop points to check ({len(cache)} cached)', file=sys.stderr)
with ThreadPoolExecutor(max_workers=4) as ex:
    for i, (k, size) in enumerate(ex.map(check, todo)):
        if size is not None: cache[k] = size
        if i % 100 == 0:
            json.dump(cache, open(cp, 'w')); print(f'  {i}/{len(todo)}', file=sys.stderr, flush=True)
json.dump(cache, open(cp, 'w'))

out, ok = {}, 0
for k, v in L.items():
    good = len(v) == 4 and cache.get(k, 0) >= MIN_BYTES
    out[k] = v if good else v[:2]; ok += good
print(f'{ok} of {len(L)} towns have verified Street View', file=sys.stderr)
open(dst, 'w').write('window.GEO_LOCS=' + json.dumps(out, separators=(',', ':')) + ';\n')
