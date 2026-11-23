"""Geocode every birth city in players.js to a USGS GNIS town-center point.
usage: python3 geocode.py <DomesticNames_National.txt> <players.js> <out locations.js>"""
import sys, json, re, unicodedata, collections
gnis, pjs, out = sys.argv[1:4]
STATES = {}
raw = open(pjs, encoding='utf-8').read()
data = json.loads(raw[raw.index('{'):raw.rindex('}')+1])
names = data['stateNames']
fips_name = {v: k for k, v in names.items()}

def norm(s):
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode().lower()
    s = re.sub(r"['`]", '', s); s = s.replace('.', ' ')
    s = re.sub(r'\bst\b', 'saint', s); s = re.sub(r'\bste\b', 'sainte', s)
    s = re.sub(r'\bft\b', 'fort', s); s = re.sub(r'\bmt\b', 'mount', s)
    s = re.sub(r'\b(city|town|township|village|borough)\b$', '', s.strip())
    s = re.sub(r'[^a-z0-9]+', ' ', s).strip()
    return s

RANK = {'Populated Place': 0, 'Civil': 1, 'Census': 2}
idx = collections.defaultdict(list)  # (st, norm) -> [(rank, lat, lng, name)]
with open(gnis, encoding='utf-8-sig') as f:
    hdr = f.readline().rstrip('\n').split('|'); H = {h: i for i, h in enumerate(hdr)}
    for line in f:
        r = line.rstrip('\n').split('|')
        cls = r[H['feature_class']]
        if cls not in RANK: continue
        st = fips_name.get(r[H['state_name']])
        if not st: continue
        try: lat = float(r[H['prim_lat_dec']]); lng = float(r[H['prim_long_dec']])
        except ValueError: continue
        if lat == 0: continue
        t = (RANK[cls], lat, lng, r[H['feature_name']]); nn = norm(r[H['feature_name']])
        idx[(st, nn)].append(t); idx[(st, nn.replace(' ', ''))].append(t)

ALIAS = {'new york city': 'new york', 'bronx': 'the bronx', 'nyc': 'new york',
         'washington dc': 'washington', 'washington d c': 'washington'}
NYC = {'brooklyn': (40.6501, -73.9496), 'bronx': (40.8448, -73.8648), 'the bronx': (40.8448, -73.8648),
       'queens': (40.7282, -73.7949), 'manhattan': (40.7831, -73.9712), 'staten island': (40.5795, -74.1502),
       'new york': (40.7128, -74.0060)}
MANUAL = {('VI','saint thomas'):(18.3419,-64.9307),('VI','charlotte amalie'):(18.3419,-64.9307),
  ('VI','frederiksted'):(17.7125,-64.8815),('VI','christiansted'):(17.7466,-64.7032),('VI','saint croix'):(17.7466,-64.7032),
  ('MO','saint louis'):(38.6270,-90.1994),('IL','east saint louis'):(38.6245,-90.1509),('IL','e saint louis'):(38.6245,-90.1509),
  ('CA','west hills'):(34.1970,-118.6440),('CA','carmel'):(36.5552,-121.9233),('IN','la porte'):(41.6106,-86.7225),
  ('NY','rockville center'):(40.6587,-73.6412),('IA','des monies'):(41.5868,-93.6250),('IL','napierville'):(41.7508,-88.1535),
  ('CT','east windsor'):(41.9126,-72.6117),('NY','seneca falls'):(42.9106,-76.7966),('OH','new berlin'):(40.8128,-81.3398)}
locs, miss = {}, []
for st, arr in data['states'].items():
    for p in arr:
        c = (p.get('c') or '').strip()
        if not c: continue
        key = st + '|' + c
        if key in locs or key in [m[0] for m in miss]: continue
        n = norm(c); n = ALIAS.get(n, n)
        hit = None
        if st == 'NY' and n in NYC: hit = NYC[n]
        if st == 'DC': hit = (38.8977, -77.0365)
        if (st, n) in MANUAL: hit = MANUAL[(st, n)]
        if not hit:
            cands = idx.get((st, n)) or idx.get((st, n.replace(' ', ''))) or idx.get((st, norm(c.split('(')[0]))) or []
            if cands:
                cands.sort(key=lambda t: t[0]); best = cands[0][0]
                top = [t for t in cands if t[0] == best]
                # several same-name places: GNIS lists the main one first often; prefer one matching a Civil entry
                civ = [t for t in cands if t[0] == 1]
                pick = top[0]
                if len(top) > 1 and civ:
                    pick = min(top, key=lambda t: (t[1]-civ[0][1])**2 + (t[2]-civ[0][2])**2)
                hit = (pick[1], pick[2])
        if hit: locs[key] = [round(hit[0], 5), round(hit[1], 5)]
        else: miss.append((key, len(arr)))
cnt = collections.Counter(k for st, arr in data['states'].items() for p in arr for k in [st + '|' + (p.get('c') or '').strip()])
print('geocoded', len(locs), 'missed', len(miss), 'players missed', sum(cnt[k] for k, _ in miss), file=sys.stderr)
for k, _ in sorted(miss, key=lambda m: -cnt[m[0]])[:60]: print('  MISS', k, cnt[k], file=sys.stderr)
open(out, 'w').write('window.GEO_LOCS=' + json.dumps(locs, separators=(',', ':')) + ';\n')
