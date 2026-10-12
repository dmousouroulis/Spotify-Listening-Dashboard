# Spotify Listening Dashboard

Turn your Spotify listening history into an interactive Tableau dashboard: one command, no
dragging and dropping, nothing uploaded anywhere.

**Live example:** _add your Tableau Public link here_

The dashboard has four pages:

- **Overview:** hours, plays, artists and minutes per day, a month-by-month timeline, a weekday ×
  hour "listening clock", and your top 10 artists (click one to filter the page).
- **Artists & tracks:** your top artists over time, most-played tracks, new artists discovered each
  year, and how concentrated your taste is.
- **Skipping:** when you skip, how that changed over the years, how fast you bail, and how tracks end.
- **Sessions & devices:** session lengths, what you listened on, and the countries you listened in.

Every page has a **year filter**, plus a **background audio** switch if your history needs one (see
[below](#background-audio)). The title, date range and filter options all come from your own data.

---

## 1. Request your data from Spotify

You need your **Extended streaming history**, not the default "Account data" (which only covers
one year and leaves out the details the dashboard uses).

1. Sign in at [spotify.com/account/privacy](https://www.spotify.com/account/privacy/).
2. Under **Download your data**, tick **Extended streaming history** and select **Request data**.
3. Confirm the request from the email Spotify sends you.
4. Wait for a second email with a download link. Spotify says this can take **up to 30 days**,
   though it is often quicker. The link opens a page in your account where you can download a zip.
5. Download the zip. Its name doesn't matter, and you don't need to unzip it. Inside is a folder
   called `Spotify Extended Streaming History` with one `Streaming_History_Audio_*.json` file per year
   or so; the tool reads all of them and ignores the video history and the PDF.

Spotify occasionally renames these menus. If they have moved, look for "Privacy settings" and
"Download your data" in your account.

## 2. Set up (once)

You need **Python 3.10 or newer** ([python.org/downloads](https://www.python.org/downloads/)) and
**Tableau Public**, which is free ([public.tableau.com](https://public.tableau.com/app/discover)).

Download this project (the green **Code** button, then **Download ZIP**), unzip it, open a
terminal in that folder, and install the requirements:

```bash
python3 -m pip install -r requirements.txt
```

On Windows, use `py` instead of `python3` in these commands.

## 3. Build your dashboard

```bash
python3 make_dashboard.py path/to/my_spotify_data.zip
```

It takes from a few seconds to about a minute, depending on how much history you have, and writes
`spotify_listening.twbx` in the current folder:

```
Reading your Spotify export...
  132,597 plays found. Building tables...
Building the workbook...
Writing Tableau extracts...

Done in 12s: spotify_listening.twbx
  2016-03-24 to 2026-09-05  |  128,633 plays  |  5,322 hours  |  13,430 artists
  Background audio (hidden by default): Sleepy Dogs
```

No Spotify data handy? Make an invented two-year history to try it with:

```bash
python3 tests/make_sample_export.py sample_spotify_data.zip
python3 make_dashboard.py sample_spotify_data.zip
```

## 4. Open and publish

1. Open `spotify_listening.twbx` in Tableau Public. Your dashboard is ready.
2. To share it, choose **File → Save to Tableau Public As…** and sign in. Tableau gives you a link
   you can put on a portfolio or send to friends.

The workbook has been tested with Tableau Desktop Public Edition 2026.2.3.

---

## Background audio

Sleep sounds, white noise or a calming playlist for a pet, left playing for hours, can swamp the
charts. The tool flags these automatically and hides them by default, and only then adds a
**Background audio** switch to every page to bring them back. If nothing in your history is
flagged, there is no switch, just a short "About this data" note in its place.

An artist is flagged when **all** of these are true:

- at least 300 plays
- fewer than 2% of those plays were skipped
- at least 60% of the plays fall in that artist's three busiest months

Real favourites get skipped now and then and are spread over time, so they don't qualify.
When something is flagged, the sidebar names it. If the rule gets it wrong, override it:

```bash
python3 make_dashboard.py my_spotify_data.zip --not-background "Some Artist"
python3 make_dashboard.py my_spotify_data.zip --background "Rain Sounds"
```

## Options

| Option | What it does |
| --- | --- |
| `-o FILE` | Where to write the workbook (default `spotify_listening.twbx`) |
| `--note "TEXT"` | A short personal note in the sidebar (under the background-audio explanation, or the "About this data" card) |
| `--link URL` | Adds a "Make your own" link to the sidebar, e.g. to this project |
| `--timezone ZONE` | Use one time zone for every play (e.g. `Europe/London`) instead of each country's |
| `--background ARTIST` | Always treat an artist as background audio (repeatable) |
| `--not-background ARTIST` | Never treat an artist as background audio (repeatable) |
| `--csv FOLDER` | Also save the three tables as CSV files, for other tools |

## How it works

| Step | File |
| --- | --- |
| Read every `Streaming_History_Audio_*.json` in the export, drop exact duplicate rows | `spotify_dashboard/load.py` |
| Convert to local time, label devices and end reasons, find sessions and background audio, build three tables | `spotify_dashboard/transform.py` |
| Generate the dashboard workbook from your data | `spotify_dashboard/workbook.py` |
| Check every field, filter, sheet and action in the workbook resolves | `spotify_dashboard/validate.py` |
| Write the Tableau extracts (Tableau Public requires them) | `spotify_dashboard/extracts.py` |

Some definitions used in the charts:

- **Music only:** podcasts, audiobooks and video are left out.
- **Local time:** each play uses the main time zone of the country Spotify recorded for it. In
  countries with several zones (the US, Canada, Australia, Brazil, Russia and others) that is the
  most populous one, so plays elsewhere in the country are shifted by an hour or more. Use
  `--timezone` if you always listened in one place.
- **Skipped:** the track ended because you pressed "next". Spotify's own `skipped` field is only
  filled in from about 2022, so it isn't used.
- **Session:** a new session starts after more than 30 minutes without playing anything.

## Privacy

- Everything runs on your computer. The tool makes no network requests.
- Spotify's export includes the IP addresses you listened from; the tool never reads them, and they
  are not in the workbook.
- Once you publish to Tableau Public, the dashboard **and the data inside it** (every play, with
  dates, tracks and countries) are public. Check your Tableau Public settings if you don't want
  people to download the workbook.

## Troubleshooting

- **"This looks like Spotify's basic Account data export"**: you requested the default download.
  Request **Extended streaming history** instead (step 1).
- **`No module named ...`**: run the install command from step 2 again, in the same terminal.
- **Tableau shows an error when opening the file**: please
  [open an issue](../../issues) with the error text (the **Copy Error Message** button) and your
  Tableau Public version (**Tableau Public → About Tableau Public**).

## Development

```bash
python3 -m pip install -r requirements.txt pytest
python3 -m pytest
```

The tests build complete workbooks from invented histories, so no real listening data is needed.

---

Not affiliated with Spotify or Tableau. Released under the MIT License.
