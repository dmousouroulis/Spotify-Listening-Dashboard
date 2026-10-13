#!/usr/bin/env python3
"""Turn a Spotify Extended Streaming History export into a ready-to-open Tableau dashboard.

    python make_dashboard.py my_spotify_data.zip

Everything runs on your own computer; nothing is uploaded anywhere.
"""
import argparse
import sys
import tempfile
import time
import zipfile
from pathlib import Path

from spotify_dashboard import __version__
from spotify_dashboard.load import ExportError, load_export
from spotify_dashboard.transform import build_tables
from spotify_dashboard.validate import check_workbook
from spotify_dashboard.workbook import build
from spotify_dashboard.mobile import add_phone_layouts
from spotify_dashboard.extracts import write_extracts


def main(argv=None):
    p = argparse.ArgumentParser(
        description='Build a Tableau dashboard (.twbx) from your Spotify Extended Streaming History.')
    p.add_argument('export', help='the zip Spotify emailed you (my_spotify_data.zip), or the unzipped folder')
    p.add_argument('-o', '--output', default='spotify_listening.twbx', help='where to write the workbook '
                   '(default: spotify_listening.twbx)')
    p.add_argument('--timezone', help='use one time zone for every play, e.g. Europe/London. By default each '
                   'play uses the main time zone of the country it was played in.')
    p.add_argument('--note', help='a short personal note shown under the background-audio explanation')
    p.add_argument('--link', help='a URL for a "Make your own" link in the sidebar (e.g. this project on GitHub)')
    p.add_argument('--background', action='append', default=[], metavar='ARTIST',
                   help='always treat this artist as background audio (repeatable)')
    p.add_argument('--not-background', action='append', default=[], metavar='ARTIST',
                   help='never treat this artist as background audio (repeatable)')
    p.add_argument('--csv', metavar='FOLDER', help='also save the three tables as CSV files in FOLDER')
    args = p.parse_args(argv)

    t0 = time.time()
    try:
        print('Reading your Spotify export...')
        raw = load_export(args.export)
    except ExportError as e:
        print(f'\nError: {e}', file=sys.stderr)
        return 1

    print(f'  {len(raw):,} plays found. Building tables...')
    plays, artists, sessions, meta = build_tables(raw, timezone=args.timezone,
                                                  force_background=args.background,
                                                  never_background=args.not_background)

    print('Building the workbook...')
    xml = build(meta, note=args.note, link=args.link)
    xml = add_phone_layouts(xml)
    problems = check_workbook(xml)
    if problems:
        print('Internal check failed (please open an issue with this output):', file=sys.stderr)
        for x in problems[:20]:
            print('  ' + x, file=sys.stderr)
        return 2

    out = Path(args.output)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        print('Writing Tableau extracts...')
        tables = {'plays': plays, 'artists': artists, 'sessions': sessions}
        hyper = write_extracts(tables, tmp / 'Extracts')
        with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
            z.writestr('spotify_listening.twb', xml)
            for key, path in hyper.items():
                z.write(path, f'Data/Extracts/{key}.hyper')
            for key, df in tables.items():
                z.writestr(f'Data/spotify/{key}.csv', df.to_csv(index=False))

    if args.csv:
        folder = Path(args.csv)
        folder.mkdir(parents=True, exist_ok=True)
        for key, df in tables.items():
            df.to_csv(folder / f'{key}.csv', index=False)

    fg = plays[plays.is_background == 0]
    print(f'\nDone in {time.time() - t0:.0f}s: {out}')
    print(f'  {meta["first_play"]} to {meta["last_play"]}  |  {len(fg):,} plays  |  '
          f'{fg.hours_played.sum():,.0f} hours  |  {fg.artist.nunique():,} artists')
    if meta['background']:
        names = ', '.join(b['artist'] for b in meta['background'])
        print(f'  Background audio (hidden by default): {names}')
    print('\nOpen the file in Tableau Public, then File > Save to Tableau Public to publish it.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
