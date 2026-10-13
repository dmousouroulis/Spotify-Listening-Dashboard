"""The phone layouts: every dashboard gets one, and it contains everything the desktop page shows."""
import sys
import zipfile
from pathlib import Path

from lxml import etree

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests'))

from make_sample_export import write_export                      # noqa: E402
from make_dashboard import main                                   # noqa: E402
from spotify_dashboard.mobile import add_phone_layouts, update_twbx  # noqa: E402
from spotify_dashboard.validate import check_workbook             # noqa: E402


def _workbook(tmp_path, **kw):
    export = tmp_path / 'sample.zip'
    write_export(export, **kw)
    out = tmp_path / 'out.twbx'
    assert main([str(export), '-o', str(out)]) == 0
    with zipfile.ZipFile(out) as z:
        return out, z.read('spotify_listening.twb').decode('utf-8')


def _check(xml):
    root = etree.fromstring(xml.encode('utf-8'))
    for dash in root.find('dashboards'):
        layouts = dash.findall('devicelayouts/devicelayout')
        assert [l.get('name') for l in layouts] == ['Phone']
        phone = layouts[0]
        assert phone.find('size').get('sizing-mode') == 'vscroll'
        desktop = {z.get('name') for z in dash.find('zones').iter('zone') if z.get('name')}
        mobile = {z.get('name') for z in phone.iter('zone') if z.get('name')}
        swapped = {'Listening clock': 'Listening clock (phone)'}            # phone-friendly version of the clock
        assert {swapped.get(n, n) for n in desktop} == mobile, dash.get('name')  # everything else is on the phone too
        for phone_only in mobile - desktop:                                  # Tableau Public needs these on desktop too
            raise AssertionError(f'{phone_only} is missing from the desktop page')
        names = [z.get('name') for z in phone.iter('zone') if z.get('name') and not z.get('type-v2')]
        assert len(names) == len(set(names)), dash.get('name')            # no chart appears twice
        ids = [z.get('id') for z in phone.iter('zone')]
        assert len(ids) == len(set(ids))
        params = [z for z in phone.iter('zone') if z.get('type-v2') == 'paramctrl']
        assert len(params) == len([z for z in dash.find('zones').iter('zone') if z.get('type-v2') == 'paramctrl'])
    assert check_workbook(xml) == []
    heights = {d.find('devicelayouts/devicelayout/size').get('maxheight') for d in root.find('dashboards')}
    assert len(heights) == 1                                          # same height on every page (see mobile.py)
    for dash in root.find('dashboards'):
        phone = dash.find('devicelayouts/devicelayout')
        for row in phone.iter('zone'):                                    # never three KPI numbers side by side
            if row.get('param') == 'horz':
                kpis_in_row = {z.get('name') for z in row.iter('zone') if (z.get('name') or '').startswith('KPI ')}
                assert len(kpis_in_row) <= 2
        accents = [z for z in phone.iter('zone') if z.get('type-v2') == 'empty' and z.get('fixed-size') == '3']
        kpis = {z.get('name') for z in phone.iter('zone') if (z.get('name') or '').startswith('KPI ')}
        assert len(accents) == len(kpis)                                  # every KPI card has its green accent


def test_generated_workbooks_have_phone_layouts(tmp_path):
    _, xml = _workbook(tmp_path)
    _check(xml)


def test_phone_layouts_without_background_audio(tmp_path):
    _, xml = _workbook(tmp_path, white_noise=False)
    _check(xml)


def test_adding_twice_keeps_one_phone_layout(tmp_path):
    out, xml = _workbook(tmp_path)
    update_twbx(out)                                                  # an existing file can be upgraded in place
    with zipfile.ZipFile(out) as z:
        _check(z.read('spotify_listening.twb').decode('utf-8'))
    _check(add_phone_layouts(xml))
