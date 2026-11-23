#!/usr/bin/env python3
"""Every player in an MLB season 1947-2026, any birth country, from MLB StatsAPI -> data/people.json"""
import json, sys, subprocess
from concurrent.futures import ThreadPoolExecutor
def get(url):
    for _ in range(4):
        r = subprocess.run(['curl', '-s', '-m', '90', url], capture_output=True, text=True)
        try: return json.loads(r.stdout)
        except Exception: pass
    print('FAIL', url, file=sys.stderr); return {}
def season(y): return y, get(f'https://statsapi.mlb.com/api/v1/sports/1/players?season={y}').get('people', [])
people = {}
with ThreadPoolExecutor(max_workers=6) as ex:
    for y, ppl in ex.map(season, range(1947, 2027)):
        for p in ppl: people.setdefault(p['id'], p)
        print(y, len(ppl), len(people), file=sys.stderr)
keep = {}
for pid, p in people.items():
    pos = p.get('primaryPosition') or {}
    keep[pid] = {'id': pid, 'name': p.get('fullName') or '', 'first': p.get('useName') or p.get('firstName') or '',
                 'last': p.get('lastName') or '', 'city': p.get('birthCity') or '', 'st': p.get('birthStateProvince') or '',
                 'ctry': p.get('birthCountry') or '', 'pos': pos.get('abbreviation') or '',
                 'debut': (p.get('mlbDebutDate') or '')[:4], 'lastYr': (p.get('lastPlayedDate') or '')[:4]}
json.dump(keep, open('data/people.json', 'w'))
print('players', len(keep), file=sys.stderr)
