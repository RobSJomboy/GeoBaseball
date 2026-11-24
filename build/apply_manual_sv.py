"""Add hand-checked Street View spots (build/manual_sv.json) for places Google's cars never drove.

Venezuela and Cuba have no official coverage, so check_sv.py can't verify anything there. Every
town there was loaded in the embed and looked at by eye; only outdoor street/plaza photos made
manual_sv.json as {town key: [svLat, svLng]}.

usage: python3 apply_manual_sv.py <locations.js in> <locations.js out>
"""
import sys, os, json, re
src, dst = sys.argv[1:3]
L = json.loads(re.search(r'=(\{.*\});', open(src).read(), re.S).group(1))
M = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'manual_sv.json')))
for k, (la, lo) in M.items():
    if k in L: L[k] = L[k][:2] + [la, lo]
open(dst, 'w').write('window.GEO_LOCS=' + json.dumps(L, separators=(',', ':')) + ';\n')
print(f'applied {sum(k in L for k in M)} hand-checked towns', file=sys.stderr)
