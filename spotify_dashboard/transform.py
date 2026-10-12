"""Raw Spotify plays -> the three tables the dashboard reads (plays, artists, sessions) + metadata."""
import numpy as np
import pandas as pd
import pytz

SESSION_GAP_SECONDS = 30 * 60

REASON = {'trackdone': 'Played to the end', 'endplay': 'Stopped', 'fwdbtn': 'Skipped forward',
          'backbtn': 'Went back', 'playbtn': 'Play pressed', 'logout': 'Logged out',
          'remote': 'Remote control', 'appload': 'App opened', 'clickrow': 'Clicked a row',
          'trackerror': 'Track error', 'unexpected-exit': 'App exited',
          'unexpected-exit-while-paused': 'App exited while paused', 'persisted': 'Resumed',
          'unknown': 'Unknown'}

LEN_BINS = [0, .25, .5, 1, 1.5, 2, 3, 4, 6, 1e6]          # session length buckets, in hours


def device_family(p):
    p = str(p)
    low = p.lower()
    if p.startswith('iOS') or low == 'ios' or 'iphone' in low or 'ipad' in low:
        return 'iPhone / iPad'
    if 'android' in low:
        return 'Android'
    if 'webplayer' in low or 'web_player' in low:
        return 'Web player'
    if 'sonos' in low or 'partner' in low or 'cast' in low or 'tv' in low or 'car' in low:
        return 'Speaker / TV / car'
    if 'windows' in low or 'os x' in low or 'osx' in low or 'mac' in low or 'linux' in low:
        return 'Computer'
    if low in ('not_applicable', 'none', 'nan', ''):
        return 'Unrecorded'
    return 'Other'


def country_timezone(code):
    """Main time zone for a country (the first, most populous entry in the tz database)."""
    try:
        return pytz.country_timezones[code][0]
    except (KeyError, IndexError):
        return None


COUNTRY_NAMES = {'GB': 'United Kingdom', 'KR': 'South Korea', 'KP': 'North Korea', 'CZ': 'Czechia',
                 'CD': 'DR Congo', 'CG': 'Republic of the Congo'}


def country_name(code):
    if code in (None, 'ZZ') or pd.isna(code):
        return 'Unknown'
    return COUNTRY_NAMES.get(code) or pytz.country_names.get(code, code)


def background_artists(music):
    """Artists played on repeat in the background (sleep sounds, white noise, pet playlists...).

    Rule: at least 300 plays, under 2% of them skipped forward, and at least 60% of all plays
    packed into that artist's three busiest months. Ordinary favourites get skipped now and then
    and are spread over time, so they don't qualify.
    """
    m = music.assign(ym=music.ts_local.dt.strftime('%Y-%m'), skip=music.reason_end.eq('fwdbtn'))
    a = m.groupby('artist').agg(plays=('artist', 'size'), skip=('skip', 'mean'))
    top3 = m.groupby(['artist', 'ym']).size().groupby(level=0).apply(lambda s: s.nlargest(3).sum())
    a['top3_share'] = top3 / a.plays
    return set(a[(a.plays >= 300) & (a.skip < 0.02) & (a.top3_share >= 0.6)].index)


def build_tables(raw, timezone=None, force_background=(), never_background=()):
    """Return (plays, artists, sessions, meta)."""
    df = raw.copy()

    # ---- where and when: unknown countries ('ZZ') borrow the nearest known one
    code = df.conn_country.where(~df.conn_country.isin(['ZZ', '']) & df.conn_country.notna())
    code = code.ffill().bfill()
    df['country_code'] = code
    df['country_name'] = code.map(country_name)
    if timezone:
        tzs = pd.Series(timezone, index=df.index)
    else:
        tzs = code.map(country_timezone).fillna('UTC')
    local = pd.Series(pd.NaT, index=df.index, dtype='datetime64[ns]')
    for tz in tzs.unique():
        idx = tzs.index[tzs == tz]
        local.loc[idx] = df.loc[idx, 'ts'].dt.tz_convert(tz).dt.tz_localize(None).astype('datetime64[ns]')
    df['ts_local'] = local

    # ---- what
    is_episode = df.episode_name.notna() | df.audiobook_title.notna()
    df['content_type'] = np.where(is_episode, 'Other', np.where(df.master_metadata_track_name.notna(), 'Music', 'Other'))
    clean = lambda s: s.astype('string').str.replace(r'[\r\n\t]+', ' ', regex=True).str.strip()
    df['artist'] = clean(df.master_metadata_album_artist_name)
    df['track'] = clean(df.master_metadata_track_name)

    # ---- sessions: a gap of more than 30 minutes between any two plays starts a new one
    gap = df.ts.diff().dt.total_seconds().fillna(1e12)
    df['session_id'] = (gap > SESSION_GAP_SECONDS).cumsum().astype('int64') + 1

    music = df[df.content_type.eq('Music') & df.artist.notna()].copy()
    if music.empty:
        raise ValueError('No music plays found in this export.')
    music['hours_played'] = music.ms_played / 3_600_000
    music['seconds_played'] = (music.ms_played / 1000).round(1)
    music['is_skipped_forward'] = music.reason_end.eq('fwdbtn').astype(int)
    music['reason_end_label'] = music.reason_end.map(REASON).fillna(music.reason_end).fillna('Unknown')
    first_month = music.groupby('artist').ts_local.transform('min').dt.strftime('%Y-%m')
    music['is_artist_debut_month'] = first_month.eq(music.ts_local.dt.strftime('%Y-%m')).astype(int)

    bg = (background_artists(music) | set(force_background)) - set(never_background)
    bool01 = lambda s: s.fillna(False).astype(bool).astype(int)

    plays = pd.DataFrame({
        'play_date': music.ts_local.dt.strftime('%Y-%m-%d'),
        'play_year': music.ts_local.dt.year,
        'play_hour': music.ts_local.dt.hour,
        'weekday_number': music.ts_local.dt.dayofweek + 1,
        'artist': music.artist,
        'track': music.track,
        'track_label': music.track.str.slice(0, 48) + '  ·  ' + music.artist,
        'hours_played': music.hours_played.round(5),
        'seconds_played': music.seconds_played,
        'country_name': music.country_name,
        'device_family': music.platform.map(device_family),
        'reason_end_label': music.reason_end_label,
        'is_skipped_forward': music.is_skipped_forward,
        'shuffle_on': bool01(music.shuffle),
        'offline': bool01(music.offline),
        'is_artist_debut_month': music.is_artist_debut_month,
        'plays': 1,
        'is_background': music.artist.isin(bg).astype(int),
    })
    s = plays.seconds_played
    plays['skip_bucket'] = np.where(plays.is_skipped_forward == 0, 0,
                                    np.select([s < 5, s < 10, s < 30, s < 60, s < 120], [1, 2, 3, 4, 5], 6))

    # ---- artists: all-time totals and a concentration curve that ignores background audio
    a = plays.groupby('artist').agg(total_hours=('hours_played', 'sum'), total_plays=('plays', 'sum'),
                                    skips=('is_skipped_forward', 'sum')).reset_index()
    a['skip_rate_pct'] = (a.skips / a.total_plays * 100).round(2)
    a['is_background'] = a.artist.isin(bg).astype(int)
    real = a[a.is_background == 0].sort_values('total_hours', ascending=False).copy()
    real['rank_excl_bg'] = np.arange(1, len(real) + 1)
    real['cumulative_share_excl_bg_pct'] = (real.total_hours.cumsum() / real.total_hours.sum() * 100).round(4)
    real['pct_of_artists_excl_bg'] = (real.rank_excl_bg / len(real) * 100).round(4)
    a = a.merge(real[['artist', 'rank_excl_bg', 'cumulative_share_excl_bg_pct', 'pct_of_artists_excl_bg']],
                on='artist', how='left')
    a['total_hours'] = a.total_hours.round(4)
    artists = a[['artist', 'total_hours', 'total_plays', 'skip_rate_pct', 'is_background', 'rank_excl_bg',
                 'cumulative_share_excl_bg_pct', 'pct_of_artists_excl_bg']]

    # ---- sessions (music plays only)
    g = music.groupby('session_id')
    sess = g.agg(session_start_local=('ts_local', 'min'), plays=('artist', 'size'),
                 hours=('hours_played', 'sum'), distinct_artists=('artist', 'nunique')).reset_index()
    top = (music.groupby(['session_id', 'artist']).size().rename('n').reset_index()
           .sort_values(['session_id', 'n'], ascending=[True, False]).drop_duplicates('session_id')
           .set_index('session_id').artist)
    sess['top_artist_by_plays'] = sess.session_id.map(top)
    sess['hours'] = sess.hours.round(4)
    sess['session_date'] = sess.session_start_local.dt.strftime('%Y-%m-%d')
    sess['session_year'] = sess.session_start_local.dt.year
    sess['start_hour'] = sess.session_start_local.dt.hour
    sess['length_bucket_order'] = pd.cut(sess.hours, bins=LEN_BINS, labels=range(1, 10), right=False).astype(int)
    sess['session_start_local'] = sess.session_start_local.dt.strftime('%Y-%m-%d %H:%M:%S')
    sessions = sess[['session_id', 'session_start_local', 'session_date', 'session_year', 'start_hour', 'hours',
                     'plays', 'distinct_artists', 'top_artist_by_plays', 'length_bucket_order']]

    # ---- metadata the workbook needs at build time
    fg = plays[plays.is_background == 0]
    bgp = plays[plays.is_background == 1]
    meta = {
        'years': sorted(int(y) for y in plays.play_year.unique()),
        'top_artists': list(fg.groupby('artist').hours_played.sum().nlargest(10).index),
        'background': [
            {'artist': art, 'plays': int(n), 'hours': float(h)}
            for art, n, h in (bgp.groupby('artist').agg(n=('plays', 'sum'), h=('hours_played', 'sum'))
                              .sort_values('h', ascending=False).itertuples())],
        'devices': sorted(plays.device_family.unique()),
        'first_play': plays.play_date.min(), 'last_play': plays.play_date.max(),
        'music_plays': int(len(plays)),
    }
    return plays, artists, sessions, meta
