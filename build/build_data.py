#!/usr/bin/env python3
"""Build GeoBaseball's players.js + locations.js (unsnapped) from scratch.

Inputs (in build/data/, see README):
  people.json            from fetch_people.py (every player in a 1947+ season)
  war_bat.txt, war_pitch.txt   Baseball Reference war_daily_*.txt
  fielding.json, awards.json   fetched by this script on first run (cached)
External gazetteers (paths as args):
  GNIS DomesticNames_National.txt (US towns) and GeoNames cities500.txt (world towns)

usage: python3 build_data.py <DomesticNames_National.txt> <cities500.txt>
"""
import csv, json, os, re, sys, subprocess, unicodedata, urllib.parse
from collections import defaultdict, Counter
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, 'data')
OUT = os.path.dirname(HERE)
GNIS, GEONAMES = sys.argv[1:3]
DEBUT_FROM = 1947          # the era rule: careers that started with or after Jackie Robinson
WHEEL_TOP = 120            # the wheel draws from a region's top N by WAR
MIN_POOL = 12              # a region needs this many players to be a drop location
FULL_SEASON = 162          # career games (or innings pitched) to count: no cup-of-coffee guys

def J(name): return json.load(open(os.path.join(DATA, name)))
def get(url):
    for _ in range(4):
        r = subprocess.run(['curl', '-s', '-m', '120', url], capture_output=True, text=True)
        try: return json.loads(r.stdout)
        except Exception: pass
    print('FAIL', url[:120], file=sys.stderr); return {}

# ---------------------------------------------------------------- regions
STATES = {'AL':'Alabama','AK':'Alaska','AZ':'Arizona','AR':'Arkansas','CA':'California','CO':'Colorado','CT':'Connecticut',
 'DE':'Delaware','FL':'Florida','GA':'Georgia','HI':'Hawaii','ID':'Idaho','IL':'Illinois','IN':'Indiana','IA':'Iowa','KS':'Kansas',
 'KY':'Kentucky','LA':'Louisiana','ME':'Maine','MD':'Maryland','MA':'Massachusetts','MI':'Michigan','MN':'Minnesota',
 'MS':'Mississippi','MO':'Missouri','MT':'Montana','NE':'Nebraska','NV':'Nevada','NH':'New Hampshire','NJ':'New Jersey',
 'NM':'New Mexico','NY':'New York','NC':'North Carolina','ND':'North Dakota','OH':'Ohio','OK':'Oklahoma','OR':'Oregon',
 'PA':'Pennsylvania','RI':'Rhode Island','SC':'South Carolina','SD':'South Dakota','TN':'Tennessee','TX':'Texas','UT':'Utah',
 'VT':'Vermont','VA':'Virginia','WA':'Washington','WV':'West Virginia','WI':'Wisconsin','WY':'Wyoming',
 'DC':'District of Columbia','PR':'Puerto Rico','VI':'U.S. Virgin Islands','GU':'Guam'}
# region code -> (display name, world-atlas name, GeoNames ISO2, Street View mode)
#   mode 'road' = Google car coverage: snap drops to the road. 'photo' = only user photos: keep the plaza point.
COUNTRIES = {
 'DOM':('Dominican Republic','Dominican Rep.','DO','road'), 'VEN':('Venezuela','Venezuela','VE','photo'),
 'CUB':('Cuba','Cuba','CU','photo'), 'CAN':('Canada','Canada','CA','road'), 'MEX':('Mexico','Mexico','MX','road'),
 'JPN':('Japan','Japan','JP','road'), 'PAN':('Panama','Panama','PA','road'), 'AUS':('Australia','Australia','AU','road'),
 'COL':('Colombia','Colombia','CO','road'), 'TWN':('Taiwan','Taiwan','TW','road'), 'CUW':('Curaçao','Curaçao','CW','road'),
 'KOR':('South Korea','South Korea','KR','photo'), 'NIC':('Nicaragua','Nicaragua','NI','photo'), 'DEU':('Germany','Germany','DE','road'),
 'BHS':('Bahamas','Bahamas','BS','road'), 'NLD':('Netherlands','Netherlands','NL','road'), 'ABW':('Aruba','Aruba','AW','road'),
 'GBR':('United Kingdom','United Kingdom','GB','road'), 'ITA':('Italy','Italy','IT','road'), 'BRA':('Brazil','Brazil','BR','road'),
 'FRA':('France','France','FR','road'), 'JAM':('Jamaica','Jamaica','JM','road'), 'ESP':('Spain','Spain','ES','road'),
 'HND':('Honduras','Honduras','HN','road'), 'ZAF':('South Africa','South Africa','ZA','road'),
}
CTRY_ALIAS = {'Dominican Republic':'DOM','DOM':'DOM','Venezuela':'VEN','VEN':'VEN','Cuba':'CUB','CUB':'CUB','Canada':'CAN',
 'Mexico':'MEX','MEX':'MEX','Japan':'JPN','Panama':'PAN','Panama Canal Zone':'PAN','Australia':'AUS','Colombia':'COL',
 'Taiwan':'TWN','Curacao':'CUW','South Korea':'KOR','Republic of Korea':'KOR','Nicaragua':'NIC','NCA':'NIC','Germany':'DEU',
 'West Germany':'DEU','Bahamas':'BHS','Netherlands':'NLD','Aruba':'ABW','England':'GBR','Scotland':'GBR','United Kingdom':'GBR',
 'Italy':'ITA','Brazil':'BRA','France':'FRA','Jamaica':'JAM','Spain':'ESP','Honduras':'HND','South Africa':'ZAF'}
FULL2ABBR = {v.lower(): k for k, v in STATES.items()}

def region_of(p):
    c = p['ctry']
    if c in ('Puerto Rico', 'PUR'): return 'PR'
    if c == 'U.S. Virgin Islands': return 'VI'
    if c == 'Guam': return 'GU'
    if c in ('USA', 'United States'):
        st = (p['st'] or '').strip()
        return st if st in STATES else FULL2ABBR.get(st.lower(), '')
    return CTRY_ALIAS.get(c, '')

people = {k: v for k, v in J('people.json').items() if v['debut'].isdigit() and int(v['debut']) >= DEBUT_FROM}
print('players debuting', DEBUT_FROM, 'or later:', len(people), file=sys.stderr)

# ---------------------------------------------------------------- WAR
def num(v):
    try: return float(v)
    except (TypeError, ValueError): return 0.0
war, ipouts, pa, brid, seasons = defaultdict(float), defaultdict(int), defaultdict(int), {}, defaultdict(set)
games = {False: defaultdict(int), True: defaultdict(int)}   # batting-file G, pitching-file G
for path, is_p in (('war_bat.txt', False), ('war_pitch.txt', True)):
    with open(os.path.join(DATA, path), newline='', encoding='utf-8', errors='replace') as f:
        for row in csv.DictReader(f):
            mid = (row.get('mlb_ID') or '').strip()
            if not mid or mid == 'NULL' or mid not in people: continue
            war[mid] += num(row.get('WAR'))
            if is_p: ipouts[mid] += int(num(row.get('IPouts')))
            else: pa[mid] += int(num(row.get('PA')))
            games[is_p][mid] += int(num(row.get('G')))
            bb = (row.get('player_ID') or '').strip()
            if bb and bb != 'NULL': brid.setdefault(mid, bb)
            yr = (row.get('year_ID') or '').strip()
            if yr.isdigit(): seasons[mid].add(int(yr))

# ---------------------------------------------------------------- fielding (career games by position)
fp = os.path.join(DATA, 'fielding.json')
if not os.path.exists(fp):
    ids = sorted(people, key=int); chunks = [ids[i:i + 40] for i in range(0, len(ids), 40)]
    def batch(ch):
        q = urllib.parse.urlencode({'personIds': ','.join(ch), 'hydrate': 'stats(group=[fielding],type=[career])'})
        return get(f'https://statsapi.mlb.com/api/v1/people?{q}').get('people', [])
    field = {}
    with ThreadPoolExecutor(max_workers=6) as ex:
        for i, ppl in enumerate(ex.map(batch, chunks)):
            for p in ppl:
                g = defaultdict(int)
                for s in p.get('stats', []):
                    for sp in s.get('splits', []):
                        ab = (sp.get('position') or {}).get('abbreviation')
                        if ab: g[ab] += sp['stat'].get('gamesPlayed') or 0
                field[str(p['id'])] = g
            if i % 50 == 0: print(f'fielding {i}/{len(chunks)}', file=sys.stderr)
    json.dump(field, open(fp, 'w'))
field = J('fielding.json')

# ---------------------------------------------------------------- awards (one request per award, all seasons)
ap = os.path.join(DATA, 'awards.json')
if not os.path.exists(ap):
    AW = {'MLBHOF':'HOF','ALMVP':'MVP','NLMVP':'MVP','ALCY':'CY','NLCY':'CY','MLBCY':'CY','ALROY':'ROY','NLROY':'ROY',
          'ALAS':'AS','NLAS':'AS','ALGG':'GG','NLGG':'GG','ALSS':'SS','NLSS':'SS','WSMVP':'WSMVP','WSCHAMP':'WS'}
    aw = defaultdict(lambda: defaultdict(set))
    for aid, tag in AW.items():
        for r in get(f'https://statsapi.mlb.com/api/v1/awards/{aid}/recipients').get('awards', []):
            pid = str((r.get('player') or {}).get('id') or '')
            if pid: aw[pid][tag].add(str(r.get('season') or ''))
    json.dump({k: {t: sorted(v) for t, v in d.items()} for k, d in aw.items()}, open(ap, 'w'))
awards = J('awards.json')

FIELD = ['C', '1B', '2B', '3B', 'SS', 'LF', 'CF', 'RF']
def positions(pid, p):
    g = {k: v for k, v in (field.get(pid) or {}).items() if v}
    lineup = {k: v for k, v in g.items() if k in FIELD}
    is_p = g.get('P', 0) >= 5 or ipouts.get(pid, 0) >= 60
    elig = set()
    if lineup:
        cut = max(20, 0.05 * sum(lineup.values()))
        elig = {k for k, v in lineup.items() if v >= cut}
        if not elig and not is_p: elig = {max(lineup.items(), key=lambda kv: kv[1])[0]}
    if is_p: elig.add('P')
    if not elig:
        prim = p['pos'] if p['pos'] in FIELD + ['P'] else ('CF' if p['pos'] == 'OF' else '1B')
        elig = {prim}
    return [x for x in FIELD + ['P'] if x in elig]

def accolades(pid):
    a = awards.get(pid) or {}
    out = []
    for tag, label in (('MVP','MVP'),('CY','Cy Young'),('ROY','ROY'),('AS','All-Star'),('GG','Gold Glove'),('SS','Silver Slugger'),('WSMVP','WS MVP')):
        n = len(a.get(tag, []))
        if n: out.append(f'{n}× {label}' if n > 1 else f'{label} {a[tag][0]}')
    return out, len(a.get('WS', [])), bool(a.get('HOF'))

# ---------------------------------------------------------------- players
def full_season(pid):
    return max(games[False].get(pid, 0), games[True].get(pid, 0)) >= FULL_SEASON or ipouts.get(pid, 0) >= FULL_SEASON * 3

by_region, names, short = defaultdict(list), {}, 0
for pid, p in people.items():
    reg = region_of(p)
    if not reg: continue
    if not full_season(pid): short += 1; continue
    ys = seasons.get(pid) or ({int(p['debut'])} | ({int(p['lastYr'])} if p['lastYr'].isdigit() else set()))
    a, b = min(ys), max(ys)
    name = re.sub(r'\s+Sr\.$', '', p['name'])
    rec = {'id': int(pid), 'n': name, 'e': positions(pid, p), 'w': round(war.get(pid, 0.0), 1),
           'y': f'{a}-{b}' if a != b else str(a), 'c': p['city'].strip()}
    if brid.get(pid): rec['br'] = brid[pid]
    acc, ws, hof = accolades(pid)
    if acc: rec['aw'] = acc
    if ws: rec['ws'] = ws
    if hof: rec['hof'] = 1
    by_region[reg].append(rec)
for lst in by_region.values(): lst.sort(key=lambda r: (-r['w'], r['n']))
print(f'dropped {short} players with under {FULL_SEASON} career games / innings', file=sys.stderr)

# ---------------------------------------------------------------- geocoding
def norm(s):
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode().lower()
    s = re.sub(r"['`]", '', s).replace('.', ' ')
    s = re.sub(r'\bst\b', 'saint', s); s = re.sub(r'\bste\b', 'sainte', s)
    s = re.sub(r'\bft\b', 'fort', s); s = re.sub(r'\bmt\b', 'mount', s); s = re.sub(r'\bsto\b', 'santo', s)
    s = re.sub(r'\bsta\b', 'santa', s); s = re.sub(r'\bsn\b', 'san', s)
    s = re.sub(r'\b(city|town|township|village|borough|ciudad)\b', '', s)
    return re.sub(r'[^a-z0-9]+', ' ', s).strip()
idx = defaultdict(list)   # (region, normname) -> [(rank, lat, lng)]
def add(reg, name, t):
    n = norm(name)
    if n: idx[(reg, n)].append(t); idx[(reg, n.replace(' ', ''))].append(t)
fips_name = {v: k for k, v in STATES.items()}; fips_name['Virgin Islands'] = 'VI'
RANK = {'Populated Place': 0, 'Civil': 1, 'Census': 2}
with open(GNIS, encoding='utf-8-sig') as f:
    H = {h: i for i, h in enumerate(f.readline().rstrip('\n').split('|'))}
    for line in f:
        r = line.rstrip('\n').split('|')
        if r[H['feature_class']] not in RANK: continue
        st = fips_name.get(r[H['state_name']])
        try: la, lo = float(r[H['prim_lat_dec']]), float(r[H['prim_long_dec']])
        except ValueError: continue
        if st and la: add(st, r[H['feature_name']], (RANK[r[H['feature_class']]], la, lo, 0))
iso2reg = {v[2]: k for k, v in COUNTRIES.items()}
with open(GEONAMES, encoding='utf-8') as f:
    for line in f:
        r = line.rstrip('\n').split('\t')
        reg = iso2reg.get(r[8])
        if r[8] == 'PR': reg = 'PR'
        if not reg: continue
        la, lo, pop = float(r[4]), float(r[5]), int(r[14] or 0)
        t = (0 if r[7].startswith('PPLC') or r[7] == 'PPLA' else 1, la, lo, -pop)
        for nm in {r[1], r[2], *[x for x in r[3].split(',') if x][:30]}: add(reg, nm, t)
MANUAL = {('VI','saint thomas'):(18.3419,-64.9307),('VI','charlotte amalie'):(18.3419,-64.9307),('VI','frederiksted'):(17.7125,-64.8815),
  ('VI','christiansted'):(17.7466,-64.7032),('VI','saint croix'):(17.7466,-64.7032),('DC','washington'):(38.8977,-77.0365),
  ('NY','new york'):(40.7128,-74.0060),('NY','brooklyn'):(40.6501,-73.9496),('NY','bronx'):(40.8448,-73.8648),('NY','the bronx'):(40.8448,-73.8648),
  ('NY','queens'):(40.7282,-73.7949),('NY','manhattan'):(40.7831,-73.9712),('NY','staten island'):(40.5795,-74.1502),
  ('DOM','santo domingo'):(18.4733,-69.8866),('DOM','san pedro de macoris'):(18.4539,-69.3086),('DOM','santiago'):(19.4517,-70.6970),
  ('DOM','villa mella'):(18.5667,-69.9000),('DOM','haina'):(18.4157,-70.0333),('DOM','santo domingo centro'):(18.4733,-69.8866),
  ('DOM','guayubin'):(19.6167,-71.3333),('DOM','palenque'):(18.2614,-70.1550),('DOM','el seybo'):(18.7650,-69.0389),('DOM','el seibo'):(18.7650,-69.0389),
  ('DOM','nizao bani'):(18.2500,-70.2100),('VEN','san felix'):(8.3500,-62.6500),('VEN','puerto ordaz'):(8.2961,-62.7117),
  ('VEN','carabobo'):(10.1620,-68.0077),('VEN','lara'):(10.0678,-69.3474),('CUB','villa clara'):(22.4069,-79.9647),('CUB','las villas'):(22.4069,-79.9647),
  ('CUB','isla de la juventud'):(21.8833,-82.8000),('TWN','pingtung county'):(22.6690,120.4862),('PR','hato rey'):(18.4167,-66.0500),
  ('CA','west hills'):(34.1970,-118.6440),('CA','carmel'):(36.5552,-121.9233),('FL','lake worth'):(26.6168,-80.0684),
  ('CUB','havana'):(23.1365,-82.3540),('CUB','la habana'):(23.1365,-82.3540),('VEN','caracas'):(10.5061,-66.9146)}
locs, miss = {}, Counter()
for reg, lst in by_region.items():
    for p in lst:
        c = p['c']
        if not c: continue
        key = f'{reg}|{c}'
        if key in locs: continue
        n = norm(c.split(',')[0].split('(')[0])
        hit = MANUAL.get((reg, n))
        if not hit:
            cands = idx.get((reg, n)) or idx.get((reg, n.replace(' ', ''))) or []
            if cands: t = min(cands, key=lambda t: (t[0], t[3])); hit = (t[1], t[2])
        if hit: locs[key] = [round(hit[0], 5), round(hit[1], 5)]
        else: miss[key] += 1
born = Counter(f'{r}|{p["c"]}' for r, l in by_region.items() for p in l if p['c'])
print(f'towns geocoded {len(locs)}, missed {len(miss)} ({sum(born[k] for k in miss)} players)', file=sys.stderr)
for k in sorted(miss, key=lambda k: -born[k])[:25]: print('   MISS', k, born[k], file=sys.stderr)

# ---------------------------------------------------------------- emit
names_out = dict(STATES); names_out.update({k: v[0] for k, v in COUNTRIES.items()})
meta = {'built': '2026-11-23', 'debutFrom': DEBUT_FROM, 'fullSeason': FULL_SEASON, 'wheelTop': WHEEL_TOP, 'minPool': MIN_POOL,
        'players': sum(len(v) for v in by_region.values()),
        'source': 'MLB StatsAPI (bio, fielding, awards) + Baseball Reference career WAR'}
payload = {'meta': meta, 'names': names_out,
           'atlas': {k: v[1] for k, v in COUNTRIES.items()},
           'svMode': {k: v[3] for k, v in COUNTRIES.items()},
           'regions': dict(by_region)}
js = 'window.GB_DATA=' + json.dumps(payload, separators=(',', ':'), ensure_ascii=False) + ';\n'
open(os.path.join(OUT, 'players.js'), 'w').write(js)
open(os.path.join(OUT, 'locations.js'), 'w').write('window.GEO_LOCS=' + json.dumps(locs, separators=(',', ':')) + ';\n')
print(f'players.js {len(js)/1e6:.2f} MB, {meta["players"]} players in {len(by_region)} regions', file=sys.stderr)
for reg in sorted(by_region, key=lambda r: -len(by_region[r]))[:30]:
    l = by_region[reg]; print(f'   {reg:4} {len(l):5}  top: {l[0]["n"]} {l[0]["w"]}', file=sys.stderr)
