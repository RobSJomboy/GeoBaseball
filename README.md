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
  - Not born there → the game tells you where he's from, and the wheel picks.
  - Born there but every spot he played is filled → name someone else (doesn't burn your shot).
- **Wrong state or country, no pin, or "I've got nobody"** → the wheel draws from that place's
  top 120 players by career WAR who fit an open spot.
- **Era:** only players whose MLB debut was 1947 or later (`DEBUT_FROM` in `build/build_data.py`).
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
- Countries with no Google car coverage (Venezuela, Cuba, Nicaragua, South Korea: `svMode: 'photo'`
  in `build_data.py`) keep the plaza point, where uploaded outdoor photos cluster. Some spots still
  show "No Street View available"; the swap button moves to another birth town in the same place.
- Coverage can't be checked ahead of time: the embed looks it up with a key that only works on
  Google's own pages.

## Rebuilding the data

```bash
cd build
python3 fetch_people.py                         # MLB StatsAPI, every player in a 1947+ season -> data/people.json
curl -L -o data/war_bat.txt   https://www.baseball-reference.com/data/war_daily_bat.txt
curl -L -o data/war_pitch.txt https://www.baseball-reference.com/data/war_daily_pitch.txt
# gazetteers: USGS GNIS DomesticNames_National.txt and GeoNames cities500.txt
python3 build_data.py <DomesticNames_National.txt> <cities500.txt>   # fetches fielding + awards once, writes ../players.js ../locations.js
cp ../locations.js data/locations_raw.js
python3 snap_roads.py ../players.js data/locations_raw.js ../locations.js   # ~1 hour at OSRM's 1 req/s, resumable
```

Bump `?v=` on the two script tags in `index.html` after replacing the data files.
