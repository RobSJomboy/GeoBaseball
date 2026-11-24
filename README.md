# GeoBaseball

A GeoGuessr-style baseball game for the Jomboy Media community. You land on a real street in a
big leaguer's hometown, anywhere from Ohio to the Dominican Republic to Japan. Find the spot on the
map, then **name a player born there**. Nine rounds fill a nine-man lineup (C, 1B, 2B, 3B, SS, LF,
CF, RF, P), scored by career WAR.

Live: https://robsjomboy.github.io/GeoBaseball/

| File | What it is |
|---|---|
| `index.html` | The whole game: home, Street View round, result + draft, final |
| `players.js` | 13,629 players whose careers began in 1947 or later, grouped by birth state/country (`window.GB_DATA`) |
| `locations.js` | Birth town → `[lat, lng]` or `[lat, lng, svLat, svLng]` (town center + road-snapped drop point) |
| `build/` | Scripts that rebuild both data files |

## Rules

- **Pin in the right state or country** (inside its outline, or within 25 km of the town) → name a
  player born there. The autocomplete covers every player in the game but only shows name,
  positions and years, never birthplace. One shot.
  - Born there, and he played a spot you still need → he's yours.
  - Not born there → the game tells you where he's from, and the wheel picks from a 5-player window
    on that place's WAR list set by your pin's points (5,000 = #1–5, 4,000 ≈ #7–11, 0 ≈ #38–42).
  - Born there but every spot he played is filled → name someone else (doesn't burn your shot).
- **Right place but you pass, or the 45-second name clock runs out** → the wheel spins that place's top 15.
- **Wrong state or country, or no pin** → the wheel draws from that place's top 120 by career WAR.
  All wheel pools only include players who fit an open spot.
- **Era:** MLB debut 1947 or later, and at least a full season (162 games or 162 innings).
- **Points:** `5000 × e^(−km / 750)`.
- **Best possible nine:** one player per stop, nine different men, each at a spot he played; solved exactly.
- **Daily** is seeded by date (2:00 rounds, one try per browser). **Challenge a friend** links
  (`?trip=…&t=…&m=…`) replay the same nine stops.
- Share squares: 🟩 named him · 🟨 right place, wheel · 🟥 wrong place, wheel.

## Street View

- Google's keyless embed (`maps?layer=c&cbll=…&output=svembed`), the free route OpenGuessr uses.
  The iframe is shifted up 64px to hide Google's address box and widened 64px so its buttons don't
  sit under the guess map. The guess map is Leaflet on Google's tiles.
- The embed opens whatever panorama is nearest. Town-center points often sit on landmarks where
  people upload their own photos, sometimes indoors, so **drop points are snapped onto the nearest
  named road** (public OSRM `nearest`), where Google's car imagery runs. Scoring still measures to
  the town center.
- Countries marked `svMode: 'photo'` in `build_data.py` (thin or no Google car coverage) are snapped
  by a second, slower worker (`snap_roads.py --only-photo`) and then face the same check below.
- **Every drop is verified.** `build/check_sv.py` asks Google's public Street View thumbnail URL
  (no key) about each road point. It returns a real photo only where Google's own car imagery exists,
  and a ~250-byte blank otherwise, never user photos. `build/rescue_sv.py` searches rings up to
  800 m around failed towns. Only verified towns are drops.
- **Venezuela and Cuba** have no Google car coverage, so every town there was loaded in the embed and
  checked by eye (2026-11-24). Only outdoor street/plaza photos made `build/manual_sv.json`: 8 Cuban
  and 5 Venezuelan towns. Indoor ones (Remedios bell tower, Bejuma arcade) were rejected.
  These are user photos, so one can disappear if its owner deletes it; re-check now and then.

## Rebuilding the data

```bash
cd build
python3 fetch_people.py                         # MLB StatsAPI, every player in a 1947+ season -> data/people.json
curl -L -o data/war_bat.txt   https://www.baseball-reference.com/data/war_daily_bat.txt
curl -L -o data/war_pitch.txt https://www.baseball-reference.com/data/war_daily_pitch.txt
# gazetteers: USGS GNIS DomesticNames_National.txt and GeoNames cities500.txt
python3 build_data.py <DomesticNames_National.txt> <cities500.txt>   # fetches fielding + awards once, writes ../players.js ../locations.js
cp ../locations.js data/locations_raw.js
python3 snap_roads.py ../players.js data/locations_raw.js data/locations_snapped.js   # ~1 hour at OSRM's 1 req/s, resumable
python3 check_sv.py data/locations_snapped.js data/locations_verified.js
python3 rescue_sv.py data/locations_verified.js ../locations.js
python3 apply_manual_sv.py ../locations.js ../locations.js            # hand-checked Venezuela/Cuba spots
```

Bump `?v=` on the two script tags in `index.html` after replacing the data files.
