"""Add a phone layout to every dashboard of a generated workbook.

The desktop dashboards are a fixed 1400 x 900 canvas of floating zones. On a phone, Tableau Public
would shrink or side-scroll that canvas, so this module adds a Tableau "Phone" device layout to each
dashboard: one column, fit to the screen width, scrolling vertically.

    from spotify_dashboard.mobile import add_phone_layouts
    xml = add_phone_layouts(xml)

or, to update an existing workbook file:

    python -m spotify_dashboard.mobile spotify_listening.twbx
"""
import copy
import re
import sys
import uuid
import zipfile
from pathlib import Path

from lxml import etree

PHONE_W = 375                         # design width in px; the layout stretches to the device width
BG, CARD, RAIL = '#0B0B0C', '#181818', '#000000'
GAP = 10                              # vertical space between blocks, px

# heights in px
H_BRAND = (34, 30, 22)
H_HEADER = 96                         # room for a two-line subtitle
H_NAV_ROW = 38
H_PARAM = 58
H_KPI_CAPTION, H_KPI_VALUE = 24, 46
H_CHART = 290
H_CHART_FOR = {'Top tracks': 470, 'Top artists': 360, 'How tracks ended': 320}   # long label lists need room
KPI_ACCENT = '#1ED760'
H_LEGEND = 100
H_FOOTER = 48


def _style(bg=None, pad=None):
    st = etree.Element('zone-style')
    if bg:
        etree.SubElement(st, 'format', attr='background-color', value=bg)
    etree.SubElement(st, 'format', attr='border-style', value='none')
    if pad is not None:
        etree.SubElement(st, 'format', attr='padding', value=str(pad))
        etree.SubElement(st, 'format', attr='margin', value='0')
    return st


class _Builder:
    """Tiny tiled-layout engine: nested vertical/horizontal containers with fixed-height rows."""

    def __init__(self, zones_by_id, next_id):
        self.src = zones_by_id
        self.next_id = next_id

    def new_id(self):
        self.next_id += 1
        return self.next_id

    def item(self, zid, height, bg=CARD, pad=None):
        z = copy.deepcopy(self.src[zid])
        for ch in z.findall('zone-style'):
            z.remove(ch)
        z.append(_style(bg, pad))
        return {'el': z, 'h': height}

    def row(self, children, height):
        return {'row': children, 'h': height}

    def col(self, children):
        return {'col': children, 'h': sum(c['h'] for c in children)}

    def gap(self, h=GAP, bg=BG, width=None):
        """A spacer; with a width it is a fixed-width column inside a row (e.g. a KPI accent bar)."""
        node = {'gap': True, 'h': h, 'bg': bg}
        if width is not None:
            node['fw'] = width
        return node


def _place(node, x, y, w, total_h, b):
    """Return an etree zone for node placed at px box (x, y, w, node['h'])."""
    h = node['h']
    pos = lambda: {'x': str(round(x / PHONE_W * 100000)), 'y': str(round(y / total_h * 100000)),
                   'w': str(round(w / PHONE_W * 100000)), 'h': str(round(h / total_h * 100000))}
    if 'gap' in node:
        z = etree.Element('zone', id=str(b.new_id()), **{'type-v2': 'empty'})
        z.append(_style(node.get('bg', BG)))
    elif 'el' in node:
        z = node['el']
        for k in ('x', 'y', 'w', 'h', 'is-fixed', 'fixed-size'):
            z.attrib.pop(k, None)
    elif 'row' in node:
        z = etree.Element('zone', id=str(b.new_id()), param='horz', **{'type-v2': 'layout-flow'})
        kids = node['row']
        fixed = sum(k['fw'] for k in kids if 'fw' in k)
        flex = [k for k in kids if 'fw' not in k]
        cw = (w - fixed) / len(flex) if flex else 0
        xx = x
        for k in kids:
            kw = k.get('fw', cw)
            child = _place(dict(k, h=h), xx, y, kw, total_h, b)
            if 'fw' in k:                                   # fixed width inside a horizontal container
                child.set('is-fixed', 'true')
                child.set('fixed-size', str(int(kw)))
            z.append(child)
            xx += kw
        z.append(_style(BG))
    else:
        z = etree.Element('zone', id=str(b.new_id()), param='vert', **{'type-v2': 'layout-flow'})
        yy = y
        for k in node['col']:
            child = _place(k, x, yy, w, total_h, b)
            child.set('is-fixed', 'true')
            child.set('fixed-size', str(int(k['h'])))
            z.insert(len(z), child)
            yy += k['h']
        z.append(_style(BG))
    z.attrib.update(pos())
    # keep zone-style as the last child, as Tableau writes it
    for st in z.findall('zone-style')[:-1]:
        z.remove(st)
    return z


def _text_of(z):
    return ''.join(z.itertext())


def _phone_layout(dash, swaps, height=None):
    zones = dash.find('zones')
    flat = [z for z in zones.iter('zone')]
    by_id = {z.get('id'): z for z in flat}
    num = lambda z, k: int(z.get(k, '0'))
    max_id = max(int(z.get('id')) for z in flat)
    b = _Builder(by_id, max_id + 100)

    sheets = [z for z in flat if z.get('name') and not z.get('type-v2')]
    texts = [z for z in flat if z.get('type-v2') == 'text']
    named = {z.get('name'): z for z in sheets}

    blocks = []
    # brand: "N years" / "of listening" / date range
    if 'Brand years' in named:
        brand_text = next((t for t in texts if 'of listening' in _text_of(t)), None)
        parts = [b.item(named['Brand years'].get('id'), H_BRAND[0], RAIL, 0)]
        if brand_text is not None:
            parts.append(b.item(brand_text.get('id'), H_BRAND[1], RAIL, 0))
        if 'Brand range' in named:
            parts.append(b.item(named['Brand range'].get('id'), H_BRAND[2], RAIL, 0))
        blocks.append(b.col(parts))

    # page header: the large text block at the top of the content column
    header = sorted((t for t in texts if num(t, 'x') > 17000 and num(t, 'y') < 10000),
                    key=lambda t: -num(t, 'w'))
    if header:
        blocks += [b.gap(), b.item(header[0].get('id'), H_HEADER, BG, 4)]

    # navigation buttons, 2 x 2
    buttons = sorted((z for z in flat if z.find('button') is not None), key=lambda z: num(z, 'x'))
    if buttons:
        rows = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
        blocks.append(b.col([b.row([b.item(z.get('id'), H_NAV_ROW, BG, 2) for z in r], H_NAV_ROW) for r in rows]))

    # filters side by side
    params = sorted((z for z in flat if z.get('type-v2') == 'paramctrl'), key=lambda z: num(z, 'y'))
    if params:
        blocks += [b.gap(), b.row([b.item(z.get('id'), H_PARAM, RAIL, 4) for z in params], H_PARAM)]

    # KPI cards: caption text above each KPI sheet, 2 per row
    kpis = sorted((z for z in sheets if z.get('name', '').startswith('KPI ')), key=lambda z: num(z, 'x'))
    if kpis:
        cards = []
        for k in kpis:
            near = lambda t: abs(num(t, 'x') - num(k, 'x')) < 1500
            cap = [t for t in texts if near(t) and 0 < num(k, 'y') - num(t, 'y') < 4000]
            parts = []                                  # caption + number only: descriptions don't fit a phone card
            if cap:
                parts.append(b.item(cap[0].get('id'), H_KPI_CAPTION, CARD, 6))
            parts.append(b.item(k.get('id'), H_KPI_VALUE, CARD, 4))
            body = b.col(parts)
            cards.append(b.row([b.gap(body['h'], KPI_ACCENT, 3), body], body['h']))    # accent bar | card
        blocks.append(b.gap())
        for i in range(0, len(cards), 2):
            chunk = cards[i:i + 2]
            h = max(c['h'] for c in chunk)
            row = [chunk[0], b.gap(h, BG, 8), chunk[1]] if len(chunk) == 2 else chunk
            blocks.append(b.row(row, h))
            blocks.append(b.gap(8))

    # charts in reading order, each followed by its legend
    legends = {z.get('name'): z for z in flat if z.get('type-v2') == 'color'}
    phone_only = set(swaps.values())
    charts = sorted((z for z in sheets if not z.get('name').startswith(('KPI ', 'Brand '))
                     and z.get('name') not in phone_only),           # hidden desktop anchors (see _anchor_on_desktop)
                    key=lambda z: (round(num(z, 'y') / 3000), num(z, 'x')))     # rows, then left to right
    for c in charts:
        name = c.get('name')
        chart_h = H_CHART_FOR.get(name, H_CHART)
        if name in swaps and swaps[name] in named:       # e.g. the 3-hour listening clock
            item = b.item(named[swaps[name]].get('id'), chart_h, CARD, 10)
            item['el'].attrib.pop('show-title', None)    # the anchor hides its title on desktop; show it here
        else:
            item = b.item(c.get('id'), chart_h, CARD, 10)
        blocks += [b.gap(), item]
        if c.get('name') in legends:
            blocks.append(b.item(legends[c.get('name')].get('id'), H_LEGEND, CARD, 6))

    # optional "Make your own" link, then the footer note
    link = next((t for t in texts if 'Make your own' in _text_of(t)), None)
    footer = next((t for t in texts if 'Music only' in _text_of(t)), None)
    for t in (link, footer):
        if t is not None:
            blocks += [b.gap(), b.item(t.get('id'), H_FOOTER, BG, 6)]
    blocks.append(b.gap(20))
    if height is not None:                      # pad to the common height of all pages (see add_phone_layouts)
        extra = height - sum(x['h'] for x in blocks)
        if extra > 0:
            blocks.append(b.gap(extra))

    body = b.col(blocks)
    total_h = body['h']
    root = etree.Element('zone', id=str(b.new_id()), x='0', y='0', w='100000', h='100000', **{'type-v2': 'layout-basic'})
    root.append(_place(body, 0, 0, PHONE_W, total_h, b))
    root.append(_style(BG))

    layout = etree.Element('devicelayout', name='Phone')
    etree.SubElement(layout, 'size', maxheight=str(int(total_h)), minheight=str(int(total_h)),
                     **{'sizing-mode': 'vscroll'})
    zs = etree.SubElement(layout, 'zones')
    zs.append(root)
    return layout


CLOCK, PHONE_CLOCK = 'Listening clock', 'Listening clock (phone)'
HOUR_BLOCK = 'Calculation_HourBlock'


def _new_uuid():
    return '{' + str(uuid.uuid4()).upper() + '}'


def _add_phone_clock(root):
    """Add a copy of the 24-hour listening clock that uses 3-hour blocks, which fit a phone screen.

    Returns {original sheet name: phone sheet name}, or {} if the workbook has no listening clock.
    """
    worksheets = root.find('worksheets')
    clock = next((w for w in worksheets if w.get('name') == CLOCK), None)
    if clock is None:
        return {}
    old = next((w for w in worksheets if w.get('name') == PHONE_CLOCK), None)
    if old is not None:                                   # rebuilding: replace the earlier copy
        worksheets.remove(old)
    inst = next(ci for ci in clock.iter('column-instance') if ci.get('column') == '[play_hour]')
    ds_name = inst.getparent().get('datasource')

    # 1. the 3-hour block field on the plays data source
    def block_column():
        col = etree.Element('column', caption='Hour block', datatype='integer', name=f'[{HOUR_BLOCK}]',
                            role='dimension', type='ordinal')
        etree.SubElement(col, 'calculation', formula='INT([play_hour] / 3) * 3', **{'class': 'tableau'})
        al = etree.SubElement(col, 'aliases')
        for h in range(0, 24, 3):
            etree.SubElement(al, 'alias', key=str(h), value=f'{h}h')
        return col
    ds = next(d for d in root.find('datasources') if d.get('name') == ds_name)
    for c in ds.findall('column'):
        if c.get('name') == f'[{HOUR_BLOCK}]':
            ds.remove(c)
    last_col = ds.findall('column')[-1]
    last_col.addnext(block_column())

    # 2. the phone sheet: same chart, hour block in place of the hour
    phone = copy.deepcopy(clock)
    phone.set('name', PHONE_CLOCK)
    for ci in phone.iter('column-instance'):
        if ci.get('column') == '[play_hour]':
            ci.set('column', f'[{HOUR_BLOCK}]')
            ci.set('name', f'[none:{HOUR_BLOCK}:ok]')
    for dep in phone.iter('datasource-dependencies'):
        if dep.get('datasource') == ds_name:
            hour = next(c for c in dep.findall('column') if c.get('name') == '[play_hour]')
            hour.addnext(block_column())
    text = etree.tostring(phone, encoding='unicode')
    text = (text.replace('[none:play_hour:ok]', f'[none:{HOUR_BLOCK}:ok]')
                .replace('Hours by weekday and hour of day', 'Hours by weekday, in 3-hour blocks')
                .replace('>Hour: <', '>Starting: <'))
    phone = etree.fromstring(text)
    phone.find('simple-id').set('uuid', _new_uuid())
    clock.addnext(phone)

    # 3. a window for the new sheet, like every other sheet has
    windows = root.find('windows')
    for w in list(windows):
        if w.get('class') == 'worksheet' and w.get('name') == PHONE_CLOCK:
            windows.remove(w)
    src = next(w for w in windows if w.get('class') == 'worksheet' and w.get('name') == CLOCK)
    win = copy.deepcopy(src)
    win.set('name', PHONE_CLOCK)
    sid = win.find('simple-id')
    if sid is not None:
        sid.set('uuid', _new_uuid())
    src.addnext(win)
    return {CLOCK: PHONE_CLOCK}


def _anchor_on_desktop(dash, sheet):
    """Put a tiny copy of a phone-only sheet on the desktop page, behind the background.

    Tableau Public only renders sheets that are part of the desktop dashboard, so a sheet used
    only in the phone layout would show up blank on the web.
    """
    zones = dash.find('zones')
    for z in list(zones):
        if z.get('name') == sheet:
            zones.remove(z)
    new_id = max(int(z.get('id')) for z in zones.iter('zone')) + 1
    z = etree.Element('zone', h='1000', id=str(new_id), name=sheet, w='1000', x='0', y='0')
    z.set('show-title', 'false')
    z.append(_style(BG))
    zones[0].addnext(z)                         # right after the root: drawn first, so covered by the page background


def _register_viewpoints(root, dash, phone_sheets):
    """List phone-only sheets in the dashboard's window, like the sheets it already shows."""
    win = next((w for w in root.find('windows')
                if w.get('class') == 'dashboard' and w.get('name') == dash.get('name')), None)
    vps = win.find('viewpoints') if win is not None else None
    if vps is None:
        return
    for name in phone_sheets:
        if not any(v.get('name') == name for v in vps):
            vp = etree.SubElement(vps, 'viewpoint', name=name)
            etree.SubElement(vp, 'zoom', type='entire-view')


def add_phone_layouts(xml_text):
    """Return the workbook XML with a Phone device layout on every dashboard (replacing any existing one)."""
    root = etree.fromstring(xml_text.encode('utf-8'))
    swaps = _add_phone_clock(root)
    dashes = list(root.find('dashboards'))
    for dash in dashes:
        old = dash.find('devicelayouts')
        if old is not None:
            dash.remove(old)
        names = {z.get('name') for z in dash.find('zones').iter('zone')}
        for original, phone in swaps.items():
            if original in names:
                _anchor_on_desktop(dash, phone)
    # Tableau Public sizes the frame once and keeps it when you switch pages, so every
    # phone page gets the same height: the tallest one's.
    height = max(int(_phone_layout(d, swaps).find('size').get('maxheight')) for d in dashes)
    for dash in dashes:
        dls = etree.Element('devicelayouts')
        layout = _phone_layout(dash, swaps, height)
        dls.append(layout)
        used = {z.get('name') for z in layout.iter('zone') if z.get('name')}
        _register_viewpoints(root, dash, sorted(used & set(swaps.values())))
        anchor = dash.find('simple-id')
        if anchor is not None:
            anchor.addprevious(dls)
        else:
            dash.append(dls)
    return '<?xml version="1.0" encoding="utf-8" ?>\n' + etree.tostring(root, encoding='unicode')


def update_twbx(path, out=None):
    """Add phone layouts to an existing .twbx (written to out, or in place)."""
    path = Path(path)
    out = Path(out) if out else path
    with zipfile.ZipFile(path) as z:
        items = {n: z.read(n) for n in z.namelist()}
    twb = next(n for n in items if n.endswith('.twb'))
    items[twb] = add_phone_layouts(items[twb].decode('utf-8')).encode('utf-8')
    tmp = out.with_suffix('.tmp')
    with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as z:
        for n, data in items.items():
            z.writestr(n, data)
    tmp.replace(out)
    return out


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('usage: python -m spotify_dashboard.mobile WORKBOOK.twbx [OUTPUT.twbx]')
        sys.exit(1)
    print(f'Phone layouts added: {update_twbx(*sys.argv[1:3])}')
