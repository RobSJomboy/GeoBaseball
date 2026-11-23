# GeoBaseball

A GeoGuessr-style game for the Jomboy Media community. You get dropped on a real street
in a town where a big leaguer was born. Guess where you are, then draft a player born
in that state. Nine rounds fill a nine-man lineup (C, 1B, 2B, 3B, SS, LF, CF, RF, P), and
the score is career WAR.

Standalone static site, kept separate from the Talkin' Baseball overlay in `../MLB_Geogussr`.
It shares that project's `players.js` (copied in, not linked).

| File | What it is |
|---|---|
| `index.html` | The whole game: home, Street View round, round result + draft, final |
| `players.js` | 5,619 live-ball-era players (copy of `MLB_Geogussr/players.js`) |
| `locations.js` | Birth town → lat/lng, 2,433 towns (built by `build/geocode.py`) |
| `build/geocode.py` | Rebuilds `locations.js` from USGS GNIS + `players.js` |

## How it plays

- **Street View** is Google's keyless embed (`maps?layer=c&cbll=…&output=svembed`), the same
  free route OpenGuessr uses. The iframe is shifted up 64px so Google's address box is
  off-screen, and 64px wider so its zoom buttons don't sit under the guess map.
- **Guess map** is Leaflet on Google's map tiles (also what OpenGuessr does).
- **Points:** `5000 × e^(−km / 450)`. 100 km ≈ 4,000, 1,000 km ≈ 540.
- **Right state** (pin inside the state's outline from `us-atlas`, or within 25 km of the town)
  → scout's choice: draft anyone born in that state. **Wrong state** → the wheel picks.
- A player can only go to a spot he actually played. If nobody from the state fits any open
  spot, out-of-position is allowed for that round.
- **Best possible nine:** one player per visited state, nine different men, solved exactly.
- **Daily challenge:** seeded by date, 2:00 rounds, moving allowed, one attempt per browser.
- **Challenge a friend:** `?seed=…&t=…&m=…` replays the exact same nine towns.
- **⟳ button:** if a spot shows "No Street View available", swaps to another birth town
  in the same state (up to 8 per round, same order for everyone on a seed).
- Game state lives in `localStorage` (`gb_*`), so a refresh resumes mid-round.

## Rebuilding locations

```bash
curl -LO https://prd-tnm.s3.amazonaws.com/StagedProducts/GeographicNames/DomesticNames/DomesticNames_National_Text.zip
unzip DomesticNames_National_Text.zip
python3 build/geocode.py Text/DomesticNames_National.txt players.js locations.js
```

Bump `?v=` on the script tags in `index.html` after replacing either data file.

## Hosting

Any static host works (GitHub Pages, Cloudflare Pages). Must be served over http(s):
the Street View embed doesn't load from a `file://` page.
