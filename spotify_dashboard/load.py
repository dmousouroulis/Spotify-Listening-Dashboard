"""Read a Spotify Extended Streaming History export (zip file or unzipped folder)."""
import json
import zipfile
from pathlib import Path

import pandas as pd

# Columns the rest of the pipeline relies on. Older or newer exports may lack some;
# missing ones are added as empty so the pipeline still runs.
FIELDS = ['ts', 'platform', 'ms_played', 'conn_country', 'master_metadata_track_name',
          'master_metadata_album_artist_name', 'master_metadata_album_album_name', 'spotify_track_uri',
          'episode_name', 'episode_show_name', 'audiobook_title', 'reason_start', 'reason_end',
          'shuffle', 'skipped', 'offline', 'incognito_mode']


class ExportError(Exception):
    """The input is not a usable Spotify extended streaming history export."""


def _is_audio_history(name):
    base = Path(name).name
    return base.startswith('Streaming_History_Audio') and base.endswith('.json')


def _is_basic_history(name):
    base = Path(name).name
    return base.startswith('StreamingHistory') and base.endswith('.json')


def _read_json_files(source):
    """Yield (name, parsed JSON) for every audio-history file in a zip or folder."""
    source = Path(source)
    if not source.exists():
        raise ExportError(f'Could not find "{source}".')
    if source.is_dir():
        names = [p for p in source.rglob('*.json')]
        audio = [p for p in names if _is_audio_history(p.name)]
        basic = [p for p in names if _is_basic_history(p.name)]
        for p in sorted(audio):
            with open(p, encoding='utf-8') as fh:
                yield p.name, json.load(fh)
    else:
        if not zipfile.is_zipfile(source):
            raise ExportError(f'"{source}" is not a zip file or a folder.')
        with zipfile.ZipFile(source) as zf:
            names = zf.namelist()
            audio = [n for n in names if _is_audio_history(n)]
            basic = [n for n in names if _is_basic_history(n)]
            for n in sorted(audio):
                with zf.open(n) as fh:
                    yield n, json.load(fh)
    if not audio:
        if basic:
            raise ExportError(
                'This looks like Spotify\'s basic "Account data" export (StreamingHistory*.json), which only '
                'covers one year and leaves out the fields this dashboard needs. Request "Extended streaming '
                'history" instead: see the README.')
        raise ExportError('No Streaming_History_Audio_*.json files found. Is this a Spotify '
                          '"Extended streaming history" export?')


def load_export(source):
    """Return one DataFrame of every audio play in the export, sorted by time (UTC)."""
    frames = []
    for name, data in _read_json_files(source):
        if isinstance(data, list) and data:
            frames.append(pd.DataFrame(data))
    if not frames:
        raise ExportError('The export contained history files, but they were empty.')
    df = pd.concat(frames, ignore_index=True)
    for c in FIELDS:
        if c not in df.columns:
            df[c] = None
    df = df[FIELDS].copy()
    df['ts'] = pd.to_datetime(df['ts'], utc=True, errors='coerce')
    df = df[df.ts.notna()]
    df['ms_played'] = pd.to_numeric(df['ms_played'], errors='coerce').fillna(0).astype('int64')
    # Spotify's export sometimes repeats a play verbatim (same second, track, duration, device, ...).
    # Only rows identical in every field are dropped; near-duplicates are kept.
    df = df.drop_duplicates()
    return df.sort_values('ts', kind='stable').reset_index(drop=True)
