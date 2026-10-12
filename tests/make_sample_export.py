#!/usr/bin/env python3
"""Create a fake Spotify Extended Streaming History export, for trying the tool or running tests.

    python tests/make_sample_export.py sample_spotify_data.zip

The listener is invented: two years of plays in Brazil and Japan, some podcasts and an audiobook,
a few plays with an unknown country, and (optionally) a white-noise artist left on repeat.
"""
import json
import random
import sys
import zipfile
from datetime import datetime, timedelta, timezone

ARTISTS = {f'Artist {chr(65 + i)}': [f'Song {chr(65 + i)}{j}' for j in range(1, 13)] for i in range(40)}
PLATFORMS = ['iOS 17.2 (iPhone15,2)', 'Android OS 14 API 34 (Google, Pixel 8)', 'OS X 14.1.0 [arm 2]',
             'windows', 'WebPlayer (websocket RFC6455)', 'Partner sonos_one Sonos;One;;']
ENDS = ['trackdone'] * 6 + ['fwdbtn'] * 2 + ['endplay', 'backbtn', 'logout']


def make_records(seed=7, white_noise=True, start='2024-01-05'):
    rnd = random.Random(seed)
    t = datetime.fromisoformat(start).replace(hour=8, tzinfo=timezone.utc)
    end = t + timedelta(days=730)
    names = list(ARTISTS)
    weights = [1 / (i + 1) ** 0.9 for i in range(len(names))]          # a few favourites, a long tail
    recs = []
    while t < end:
        country = 'BR' if t.year == 2024 else 'JP'
        for _ in range(rnd.randint(3, 25)):                          # one listening session
            kind = rnd.random()
            rec = {'ts': t.strftime('%Y-%m-%dT%H:%M:%SZ'), 'platform': rnd.choice(PLATFORMS),
                   'conn_country': 'ZZ' if rnd.random() < 0.02 else country, 'ip_addr': '0.0.0.0',
                   'master_metadata_track_name': None, 'master_metadata_album_artist_name': None,
                   'master_metadata_album_album_name': None, 'spotify_track_uri': None,
                   'episode_name': None, 'episode_show_name': None, 'spotify_episode_uri': None,
                   'audiobook_title': None, 'audiobook_uri': None, 'audiobook_chapter_uri': None,
                   'audiobook_chapter_title': None, 'reason_start': 'clickrow',
                   'shuffle': rnd.random() < 0.3, 'skipped': None, 'offline': rnd.random() < 0.05,
                   'offline_timestamp': None, 'incognito_mode': False}
            if kind < 0.04:
                rec.update(episode_name='Episode', episode_show_name='A Podcast', ms_played=rnd.randint(60_000, 3_000_000),
                           reason_end='endplay')
            elif kind < 0.05:
                rec.update(audiobook_title='An Audiobook', ms_played=rnd.randint(60_000, 2_000_000), reason_end='endplay')
            else:
                artist = rnd.choices(names, weights)[0]
                song = rnd.choice(ARTISTS[artist])
                reason = rnd.choice(ENDS)
                ms = rnd.randint(1000, 30000) if reason == 'fwdbtn' else rnd.randint(150_000, 260_000)
                rec.update(master_metadata_track_name=song, master_metadata_album_artist_name=artist,
                           master_metadata_album_album_name=f'{artist} album', ms_played=int(ms),
                           spotify_track_uri=f'spotify:track:{abs(hash(song)) % 10**12:012d}', reason_end=reason)
            rec['ms_played'] = int(rec['ms_played'])
            recs.append(rec)
            t += timedelta(milliseconds=rec['ms_played'] + rnd.randint(1000, 20000))
        t += timedelta(hours=rnd.choice([2, 4, 6, 10, 20]), minutes=rnd.randint(0, 59))
    if white_noise:                                                   # a burst of sleep sounds, never skipped
        nt = datetime.fromisoformat('2025-03-01T21:00:00').replace(tzinfo=timezone.utc)
        for night in range(60):
            for k in range(8):
                recs.append({**recs[0], 'ts': (nt + timedelta(days=night, minutes=k * 4)).strftime('%Y-%m-%dT%H:%M:%SZ'),
                             'master_metadata_track_name': f'Rain {k}', 'master_metadata_album_artist_name': 'Deep Sleep Sounds',
                             'master_metadata_album_album_name': 'Rain', 'spotify_track_uri': f'spotify:track:rain{k}',
                             'episode_name': None, 'episode_show_name': None, 'audiobook_title': None,
                             'ms_played': 240000, 'reason_end': 'trackdone', 'conn_country': 'JP'})
    return recs


def write_export(path, **kw):
    recs = sorted(make_records(**kw), key=lambda r: r['ts'])
    half = len(recs) // 2
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('Spotify Extended Streaming History/Streaming_History_Audio_2024_0.json', json.dumps(recs[:half]))
        z.writestr('Spotify Extended Streaming History/Streaming_History_Audio_2025-2026_1.json', json.dumps(recs[half:]))
    return len(recs)


if __name__ == '__main__':
    out = sys.argv[1] if len(sys.argv) > 1 else 'sample_spotify_data.zip'
    print(f'{write_export(out):,} plays written to {out}')
