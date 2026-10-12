"""End-to-end tests on invented listening histories (run with: python -m pytest)."""
import json
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests'))

from make_sample_export import write_export                       # noqa: E402
from make_dashboard import main                                    # noqa: E402
from spotify_dashboard.load import ExportError, load_export        # noqa: E402
from spotify_dashboard.transform import build_tables               # noqa: E402
from spotify_dashboard.validate import check_workbook              # noqa: E402


@pytest.fixture(scope='module')
def sample(tmp_path_factory):
    path = tmp_path_factory.mktemp('data') / 'sample.zip'
    write_export(path)
    return path


def test_builds_a_complete_workbook(sample, tmp_path):
    out = tmp_path / 'out.twbx'
    assert main([str(sample), '-o', str(out)]) == 0
    with zipfile.ZipFile(out) as z:
        names = set(z.namelist())
        xml = z.read('spotify_listening.twb').decode('utf-8')
    for key in ('plays', 'artists', 'sessions'):
        assert f'Data/Extracts/{key}.hyper' in names
        assert f'Data/spotify/{key}.csv' in names
    assert check_workbook(xml) == []
    for page in ('Overview', 'Artists &amp; tracks', 'Skipping', 'Sessions &amp; devices'):
        assert f'<dashboard name="{page}">' in xml


def test_tables_follow_the_data(sample):
    plays, artists, sessions, meta = build_tables(load_export(sample))
    assert meta['years'] == [2024, 2025, 2026]
    assert set(plays.country_name) == {'Brazil', 'Japan'}          # 'ZZ' plays borrow a neighbour's country
    assert plays.is_skipped_forward.isin([0, 1]).all()
    assert len(sessions) > 0 and sessions.hours.gt(0).all()


def test_background_audio_is_detected_but_favourites_are_not(sample):
    plays, artists, sessions, meta = build_tables(load_export(sample))
    assert [b['artist'] for b in meta['background']] == ['Deep Sleep Sounds']


def test_background_overrides(sample):
    *_, meta = build_tables(load_export(sample), force_background=['Artist A'],
                            never_background=['Deep Sleep Sounds'])
    assert [b['artist'] for b in meta['background']] == ['Artist A']


def test_no_background_audio(tmp_path):
    path = tmp_path / 'plain.zip'
    write_export(path, white_noise=False)
    out = tmp_path / 'plain.twbx'
    assert main([str(path), '-o', str(out)]) == 0
    with zipfile.ZipFile(out) as z:
        xml = z.read('spotify_listening.twb').decode('utf-8')
    assert check_workbook(xml) == []
    assert 'ABOUT THIS DATA' in xml                                  # no switch, an info card instead
    assert 'param="[Parameters].[Parameter 2]"' not in xml
    assert 'WHAT IS BACKGROUND AUDIO?' not in xml


def test_background_switch_shown_when_detected(sample, tmp_path):
    out = tmp_path / 'bg.twbx'
    assert main([str(sample), '-o', str(out)]) == 0
    with zipfile.ZipFile(out) as z:
        xml = z.read('spotify_listening.twb').decode('utf-8')
    assert 'param="[Parameters].[Parameter 2]"' in xml
    assert 'Deep Sleep Sounds' in xml


def test_unzipped_folder_works(sample, tmp_path):
    with zipfile.ZipFile(sample) as z:
        z.extractall(tmp_path / 'export')
    assert len(load_export(tmp_path / 'export')) > 1000


def test_basic_account_export_is_rejected_with_a_helpful_message(tmp_path):
    folder = tmp_path / 'basic'
    folder.mkdir()
    (folder / 'StreamingHistory_music_0.json').write_text(json.dumps(
        [{'endTime': '2024-01-01 10:00', 'artistName': 'A', 'trackName': 'B', 'msPlayed': 1000}]))
    with pytest.raises(ExportError, match='Extended streaming history'):
        load_export(folder)


def test_exact_duplicates_are_dropped(tmp_path):
    rec = {'ts': '2024-05-01T10:00:00Z', 'platform': 'ios', 'ms_played': 200000, 'conn_country': 'GB',
           'master_metadata_track_name': 'T', 'master_metadata_album_artist_name': 'A',
           'master_metadata_album_album_name': 'X', 'spotify_track_uri': 'spotify:track:1',
           'reason_start': 'clickrow', 'reason_end': 'trackdone', 'shuffle': False, 'skipped': None,
           'offline': False, 'incognito_mode': False}
    path = tmp_path / 'dup.zip'
    with zipfile.ZipFile(path, 'w') as z:
        z.writestr('Streaming_History_Audio_2024_0.json', json.dumps([rec, rec, {**rec, 'ms_played': 1000}]))
    assert len(load_export(path)) == 2
