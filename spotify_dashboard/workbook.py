"""Tableau workbook generator: builds the dashboard XML (classic TWB format) for one listening history."""
import uuid
from xml.sax.saxutils import quoteattr, escape

GREEN = '#1ED760'; INK = '#191414'; MUTED = '#6A6A6A'; BG = '#0B0B0C'; CARD = '#181818'
RAIL = '#000000'; TXT = '#FFFFFF'; TXT2 = '#A7A7A7'; TXT3 = '#6F6F6F'; GRID = '#262626'; BLUE = '#509BF5'; SOFT = '#E8E8E8'
FONT = 'Tableau Book'; FONT_SB = 'Tableau Semibold'; FONT_LT = 'Tableau Light'

def uid():
    return '{' + str(uuid.uuid4()).upper() + '}'

def q(s):  # attribute quoting
    return quoteattr(s)

# ---------------------------------------------------------------- datasources
REMOTE = {'integer': 20, 'real': 5, 'string': 129, 'date': 133, 'datetime': 135}
AGG = {'integer': 'Sum', 'real': 'Sum', 'string': 'Count', 'date': 'Year', 'datetime': 'Year'}

DS = {
    'plays': dict(name='federated.0spotplays', caption='Plays', file='plays.csv', cols=[
        ('play_date', 'date'), ('play_year', 'integer'), ('play_hour', 'integer'), ('weekday_number', 'integer'),
        ('artist', 'string'), ('track', 'string'), ('track_label', 'string'), ('hours_played', 'real'),
        ('seconds_played', 'real'), ('country_name', 'string'), ('device_family', 'string'),
        ('reason_end_label', 'string'), ('is_skipped_forward', 'integer'), ('shuffle_on', 'integer'),
        ('offline', 'integer'), ('is_artist_debut_month', 'integer'), ('plays', 'integer'),
        ('is_background', 'integer'), ('skip_bucket', 'integer')]),
    'artists': dict(name='federated.0spotartists', caption='Artists (all-time)', file='artists.csv', cols=[
        ('artist', 'string'), ('total_hours', 'real'), ('total_plays', 'integer'), ('skip_rate_pct', 'real'),
        ('is_background', 'integer'), ('rank_excl_bg', 'real'), ('cumulative_share_excl_bg_pct', 'real'),
        ('pct_of_artists_excl_bg', 'real')]),
    'sessions': dict(name='federated.0spotsessions', caption='Sessions', file='sessions.csv', cols=[
        ('session_id', 'integer'), ('session_start_local', 'datetime'), ('session_date', 'date'),
        ('session_year', 'integer'), ('start_hour', 'integer'), ('hours', 'real'), ('plays', 'integer'),
        ('distinct_artists', 'integer'), ('top_artist_by_plays', 'string'), ('length_bucket_order', 'integer')]),
}

WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
SKIP_BUCKETS = ['Not skipped', '0-5 s', '5-10 s', '10-30 s', '30-60 s', '1-2 min', '2 min+']
LEN_BUCKETS = ['Under 15 min', '15-30 min', '30-60 min', '1-1.5 hr', '1.5-2 hr', '2-3 hr', '3-4 hr', '4-6 hr', 'Over 6 hr']
YEARS = ['All'] + [str(y) for y in range(2016, 2027)]
P_YEAR = '[Parameters].[Parameter 1]'
P_PET = '[Parameters].[Parameter 2]'

# field metadata: (ds, field) -> dict(caption, role, type, datatype, extra xml, default-format)
FIELDS = {}
def fld(ds, name, datatype, caption=None, role=None, ftype=None, fmt=None, formula=None, aliases=None):
    if role is None:
        role = 'measure' if datatype in ('integer', 'real') else 'dimension'
    if ftype is None:
        ftype = 'quantitative' if role == 'measure' else ('ordinal' if datatype in ('date', 'datetime', 'integer') else 'nominal')
    FIELDS[(ds, name)] = dict(name=name, datatype=datatype, caption=caption, role=role, type=ftype,
                              fmt=fmt, formula=formula, aliases=aliases)

for key, d in DS.items():
    for c, t in d['cols']:
        fld(key, c, t, caption=c.replace('_', ' ').capitalize())

# nicer captions / roles
F = FIELDS
def upd(ds, name, **kw):
    F[(ds, name)].update({k: v for k, v in kw.items()})
upd('plays', 'play_year', role='dimension', type='ordinal', caption='Year')
upd('plays', 'play_hour', role='dimension', type='ordinal', caption='Hour of day')
upd('plays', 'weekday_number', role='dimension', type='ordinal', caption='Weekday',
    aliases={i + 1: w for i, w in enumerate(WEEKDAYS)})
upd('plays', 'skip_bucket', role='dimension', type='ordinal', caption='Time before skipping',
    aliases={i: b for i, b in enumerate(SKIP_BUCKETS)})
upd('plays', 'hours_played', caption='Hours', fmt='n#,##0')
upd('plays', 'plays', caption='Plays', fmt='n#,##0')
upd('plays', 'artist', caption='Artist'); upd('plays', 'track', caption='Track'); upd('plays', 'track_label', caption='Track')
upd('plays', 'country_name', caption='Country'); upd('plays', 'device_family', caption='Device')
upd('plays', 'reason_end_label', caption='How the track ended')
upd('plays', 'play_date', caption='Date')
upd('artists', 'artist', caption='Artist')
upd('artists', 'rank_excl_bg', caption='Rank')
upd('artists', 'cumulative_share_excl_bg_pct', caption='Cumulative share of hours (%)', fmt='n#,##0')
upd('artists', 'pct_of_artists_excl_bg', caption='Share of artists (%)', fmt='n#,##0')
upd('artists', 'total_hours', caption='Hours', fmt='n#,##0.0')
upd('sessions', 'session_year', role='dimension', type='ordinal', caption='Year')
upd('sessions', 'start_hour', role='dimension', type='ordinal', caption='Start hour')
upd('sessions', 'session_id', role='dimension', type='ordinal', caption='Session')
upd('sessions', 'length_bucket_order', role='dimension', type='ordinal', caption='Session length',
    aliases={i + 1: b for i, b in enumerate(LEN_BUCKETS)})
upd('sessions', 'hours', caption='Hours', fmt='n#,##0.0')
upd('sessions', 'top_artist_by_plays', caption='Top artist')
upd('sessions', 'session_start_local', caption='Started')

# calculated fields
fld('plays', 'Calculation_Show', 'boolean', caption='In view (year & background filter)', role='dimension', ftype='nominal',
    formula=f'({P_YEAR}="All" OR STR([play_year])={P_YEAR}) AND ({P_PET}="Show background audio" OR [is_background]=0)')
fld('plays', 'Calculation_SkipRate', 'real', caption='Skip rate', fmt='p0.0%',
    formula='SUM([is_skipped_forward]) / SUM([plays])')
fld('plays', 'Calculation_ShuffleRate', 'real', caption='Shuffle rate', fmt='p0%',
    formula='SUM([shuffle_on]) / SUM([plays])')
fld('plays', 'Calculation_OfflineRate', 'real', caption='Offline rate', fmt='p0%',
    formula='SUM([offline]) / SUM([plays])')
fld('plays', 'Calculation_NewArtists', 'integer', caption='New artists discovered', fmt='n#,##0',
    formula='COUNTD(IF [is_artist_debut_month]=1 THEN [artist] END)')
fld('plays', 'Calculation_NewShare', 'real', caption='Hours on newly discovered artists', fmt='p0%',
    formula='SUM(IF [is_artist_debut_month]=1 THEN [hours_played] END) / SUM([hours_played])')
fld('plays', 'Calculation_PlayShare', 'real', caption='Share of plays', fmt='p0.0%',
    formula='SUM([plays]) / MIN({FIXED : SUM([plays])})')
fld('plays', 'Calculation_MinPerDay', 'real', caption='Minutes per listening day', fmt='n#,##0',
    formula='SUM([hours_played]) * 60 / COUNTD([play_date])')
fld('plays', 'Calculation_EndShare', 'real', caption='Played to the end', fmt='p0%',
    formula='SUM(IF [reason_end_label]="Played to the end" THEN 1 ELSE 0 END) / SUM([plays])')
fld('plays', 'Calculation_SkipKPI', 'real', caption='Skip rate', fmt='p0%',
    formula='SUM([is_skipped_forward]) / SUM([plays])')
fld('sessions', 'Calculation_AvgSessMin', 'real', caption='Average session (minutes)', fmt='n#,##0',
    formula='AVG([hours]) * 60')
fld('sessions', 'Calculation_MaxSess', 'real', caption='Longest session (hours)', fmt='n#,##0.0',
    formula='MAX([hours])')
_DAYS = "DATEDIFF('day', MIN([play_date]), MAX([play_date]))"
fld('plays', 'Calculation_SpanLabel', 'string', caption='Listening span', role='measure', ftype='nominal',
    formula=(f"IF {_DAYS} < 365 THEN STR(DATEDIFF('month', MIN([play_date]), MAX([play_date])) + 1) + ' months' "
             f"ELSEIF INT({_DAYS} / 365.25) = 1 THEN '1 year' "
             f"ELSE STR(INT({_DAYS} / 365.25)) + ' years' END"))
fld('plays', 'Calculation_RangeLabel', 'string', caption='Date range', role='measure', ftype='nominal',
    formula=("LEFT(DATENAME('month', MIN([play_date])), 3) + ' ' + DATENAME('year', MIN([play_date])) + ' – ' + "
             "LEFT(DATENAME('month', MAX([play_date])), 3) + ' ' + DATENAME('year', MAX([play_date]))"))
fld('sessions', 'Calculation_SessShow', 'boolean', caption='In view (year filter)', role='dimension', ftype='nominal',
    formula=f'{P_YEAR}="All" OR STR([session_year])={P_YEAR}')
fld('sessions', 'Calculation_Sessions', 'integer', caption='Sessions', fmt='n#,##0',
    formula='COUNTD([session_id])')
fld('artists', 'Calculation_ArtShow', 'boolean', caption='Excl. background audio', role='dimension', ftype='nominal',
    formula='[is_background]=0 AND NOT ISNULL([rank_excl_bg])')

PARAMS = [
    dict(name='[Parameter 1]', caption='Year', values=YEARS, default='All'),
    dict(name='[Parameter 2]', caption='Background audio', values=['Hide background audio', 'Show background audio'],
         default='Hide background audio'),
]

def field_col_xml(ds, name, with_calc=True):
    f = F[(ds, name)]
    a = f'<column'
    if f['caption']:
        a += f' caption={q(f["caption"])}'
    a += f' datatype={q(f["datatype"])}'
    if f['fmt']:
        a += f' default-format={q(f["fmt"])}'
    a += f' name={q("[" + name + "]")} role={q(f["role"])} type={q(f["type"])}'
    inner = ''
    if f['formula'] and with_calc:
        inner += f'<calculation class="tableau" formula={q(f["formula"])} />'
    if f['aliases']:
        inner += '<aliases>' + ''.join(f'<alias key={q(str(k))} value={q(v)} />' for k, v in f['aliases'].items()) + '</aliases>'
    return a + (f'>{inner}</column>' if inner else ' />')

def param_col_xml(p):
    vals = ''.join(f'<member value={q(chr(34) + v + chr(34))} />' for v in p['values'])
    dv = '"' + p['default'] + '"'
    return (f'<column caption={q(p["caption"])} datatype="string" name={q(p["name"])} param-domain-type="list" '
            f'role="measure" type="nominal" value={q(dv)}>'
            f'<calculation class="tableau" formula={q(dv)} /><members>{vals}</members></column>')

def datasource_xml(key):
    d = DS[key]
    conn = 'textscan.0' + key
    oid = d['file'].replace('.csv', '') + '_' + uuid.uuid5(uuid.NAMESPACE_DNS, key).hex.upper()
    cols = ''.join(f'<column datatype={q(t)} name={q(c)} ordinal="{i}" />' for i, (c, t) in enumerate(d['cols']))
    tbl = '[' + d['file'].replace('.', '#') + ']'
    relation = (f'<relation connection={q(conn)} name={q(d["file"])} table={q(tbl)} type="table">'
                f'<columns character-set="UTF-8" header="yes" locale="en_US" separator=",">{cols}</columns></relation>')
    recs = ''
    for i, (c, t) in enumerate(d['cols']):
        recs += (f'<metadata-record class="column"><remote-name>{c}</remote-name><remote-type>{REMOTE[t]}</remote-type>'
                 f'<local-name>[{c}]</local-name><parent-name>[{d["file"]}]</parent-name><remote-alias>{c}</remote-alias>'
                 f'<ordinal>{i}</ordinal><local-type>{t}</local-type><aggregation>{AGG[t]}</aggregation>'
                 f'<contains-null>true</contains-null></metadata-record>')
    fields = ''.join(field_col_xml(key, n) for (k, n) in F if k == key)
    return (f'<datasource caption={q(d["caption"])} inline="true" name={q(d["name"])} version="18.1">'
            f'<connection class="federated"><named-connections>'
            f'<named-connection caption={q(d["file"])} name={q(conn)}>'
            f'<connection class="textscan" directory="Data/spotify" filename={q(d["file"])} password="" server="" />'
            f'</named-connection></named-connections>{relation}<metadata-records>{recs}</metadata-records></connection>'
            f'<aliases enabled="yes" />{fields}{extract_xml(key)}'
            f'<layout dim-ordering="alphabetic" dim-percentage="0.5" measure-ordering="alphabetic" measure-percentage="0.4" show-structure="true" />'
            '</datasource>')

def extract_xml(key):
    d = DS[key]
    recs = ''
    for i, (c, t) in enumerate(d['cols']):
        recs += (f'<metadata-record class="column"><remote-name>{c}</remote-name><remote-type>{REMOTE[t]}</remote-type>'
                 f'<local-name>[{c}]</local-name><parent-name>[Extract]</parent-name><remote-alias>{c}</remote-alias>'
                 f'<ordinal>{i}</ordinal><local-type>{t}</local-type><aggregation>{AGG[t]}</aggregation>'
                 f'<contains-null>true</contains-null></metadata-record>')
    return (f'<extract count="-1" enabled="true" units="records">'
            f'<connection access_mode="readonly" authentication="auth-none" author-locale="en_US" class="hyper" '
            f'dbname="Data/Extracts/{key}.hyper" default-settings="hyper" schema="Extract" sslmode="" '
            f'tablename="Extract" update-time="10/12/2026 4:31:00 PM" username="tableau_internal_user">'
            f'<relation name="Extract" table="[Extract].[Extract]" type="table" />'
            f'<metadata-records>{recs}</metadata-records></connection></extract>')

def params_ds_xml():
    return ('<datasource hasconnection="false" inline="true" name="Parameters" version="18.1"><aliases enabled="yes" />'
            + ''.join(param_col_xml(p) for p in PARAMS) + '</datasource>')

# ---------------------------------------------------------------- field references in sheets
PREFIX = {'None': 'none', 'Sum': 'sum', 'Avg': 'avg', 'CountD': 'ctd', 'User': 'usr', 'Year': 'yr',
          'Month-Trunc': 'tmn', 'Quarter-Trunc': 'tqr', 'Min': 'min', 'Max': 'max', 'Attribute': 'attr'}

REFS = {}
class Ref:
    """A column-instance on a shelf: ds key, field, derivation, discrete/continuous."""
    def __init__(self, ds, field, deriv='None', cont=None):
        self.ds, self.field, self.deriv = ds, field, deriv
        f = F[(ds, field)]
        if cont is None:
            cont = deriv not in ('None', 'Year') or (deriv == 'None' and f['type'] == 'quantitative')
        self.cont = cont
        if cont:
            self.itype = 'quantitative'; suf = 'qk'
        else:
            self.itype = 'ordinal' if (f['type'] == 'ordinal' or deriv == 'Year') else 'nominal'
            suf = 'ok' if self.itype == 'ordinal' else 'nk'
        self.inst = f'[{PREFIX[deriv]}:{field}:{suf}]'
        REFS[self.full] = self
    @property
    def full(self):
        return f'[{DS[self.ds]["name"]}].{self.inst}'
    def inst_xml(self):
        return (f'<column-instance column={q("[" + self.field + "]")} derivation={q(self.deriv)} '
                f'name={q(self.inst)} pivot="key" type={q(self.itype)} />')

def R(ds, field, deriv=None, cont=None):
    f = F[(ds, field)]
    if deriv is None:
        if f['formula'] and f['role'] == 'measure':
            deriv = 'User'
        elif f['role'] == 'measure':
            deriv = 'Sum'
        else:
            deriv = 'None'
    return Ref(ds, field, deriv, cont)

SHOW = {'plays': 'Calculation_Show', 'sessions': 'Calculation_SessShow', 'artists': 'Calculation_ArtShow'}

def worksheet_xml(ws):
    ds = ws['ds']; dsname = DS[ds]['name']
    refs = []
    def collect(x):
        if isinstance(x, Ref): refs.append(x)
        elif isinstance(x, (list, tuple)):
            for y in x: collect(y)
    for k in ('rows', 'cols'):
        collect(ws.get(k, []))
    for k, v in ws.get('enc', {}).items():
        collect(v)
    import re as _re
    for k in ('tooltip', 'label_xml'):
        for m in _re.findall(r'&lt;(\[[^&]+?\]\.\[[^&]+?\])&gt;', ws.get(k, '') or ''):
            refs.append(REFS[m])
    show = R(ds, SHOW[ds])
    refs.append(show)
    topn = ws.get('topn')
    if topn:
        refs.append(topn[0])
    for s in ws.get('sorts', []):
        refs += [s[0], s[1]]
    for fr in ws.get('extra_filters', []):
        refs.append(fr[0])
    # dependencies
    fields_used = []
    for r in refs:
        if r.field not in fields_used: fields_used.append(r.field)
    # include fields referenced by calcs
    def calc_deps(name):
        f = F[(ds, name)]
        if not f['formula']: return
        for (k, n) in F:
            if k == ds and f'[{n}]' in f['formula'] and n not in fields_used:
                fields_used.append(n); calc_deps(n)
    for n in list(fields_used): calc_deps(n)
    insts = []
    for r in refs:
        if r.inst not in [i.inst for i in insts]: insts.append(r)
    uses_params = any('[Parameters]' in (F[(ds, n)]['formula'] or '') for n in fields_used)
    dsl = f'<datasource caption={q(DS[ds]["caption"])} name={q(dsname)} />'
    deps = ''
    if uses_params:
        dsl += '<datasource name="Parameters" />'
        deps += '<datasource-dependencies datasource="Parameters">' + ''.join(param_col_xml(p) for p in PARAMS) + '</datasource-dependencies>'
    deps += (f'<datasource-dependencies datasource={q(dsname)}>'
             + ''.join(field_col_xml(ds, n) for n in fields_used)
             + ''.join(i.inst_xml() for i in insts) + '</datasource-dependencies>')
    # filters
    filters = '' if ws.get('no_filter') else (f'<filter class="categorical" column={q(show.full)} context="true">'
               f'<groupfilter function="member" level={q(show.inst)} member="true" '
               f'user:ui-domain="database" user:ui-enumeration="inclusive" user:ui-marker="enumerate" /></filter>')
    slices = [] if ws.get('no_filter') else [show.full]
    for fr, members, exclude in ws.get('extra_filters', []):
        if exclude:
            inner = ''.join(f'<groupfilter function="member" level={q(fr.inst)} member={q(m)} />' for m in members)
            filters += (f'<filter class="categorical" column={q(fr.full)}><groupfilter function="except" '
                        f'user:ui-domain="database" user:ui-enumeration="exclusive" user:ui-marker="enumerate">'
                        f'<groupfilter function="level-members" level={q(fr.inst)} />{inner}</groupfilter></filter>')
        else:
            if len(members) == 1:
                filters += (f'<filter class="categorical" column={q(fr.full)}><groupfilter function="member" '
                            f'level={q(fr.inst)} member={q(members[0])} user:ui-domain="database" '
                            f'user:ui-enumeration="inclusive" user:ui-marker="enumerate" /></filter>')
        slices.append(fr.full)
    if topn:
        r, n, by = topn
        filters += (f'<filter class="categorical" column={q(r.full)}>'
                    f'<groupfilter count="{n}" end="top" function="end" units="records" user:ui-marker="end" user:ui-top-by-field="true">'
                    f'<groupfilter direction="DESC" expression={q(by)} function="order" user:ui-marker="order">'
                    f'<groupfilter function="level-members" level={q(r.inst)} user:ui-enumeration="all" user:ui-marker="enumerate" />'
                    f'</groupfilter></groupfilter></filter>')
        slices.append(r.full)
    sorts = ''.join(f'<sort class="computed" column={q(a.full)} direction={q(d)} using={q(b.full)} />'
                    for a, b, d in ws.get('sorts', []))
    agg = 'false' if ws.get('disagg') else 'true'
    view = (f'<view><datasources>{dsl}</datasources>{deps}{filters}{sorts}'
            f'{"<slices>" + "".join("<column>" + s + "</column>" for s in slices) + "</slices>" if slices else ""}'
            f'<aggregation value="{agg}" /></view>')
    # table style
    st = ws.get('style', '')
    bgc = ws.get('bg', CARD)
    base_style = ('<style>'
                  f'<style-rule element="axis"><format attr="color" value="{TXT3}" /><format attr="font-size" value="8" />'
                  f'<format attr="tick-color" value="{bgc}" /></style-rule>'
                  f'<style-rule element="axis-title"><format attr="color" value="{bgc}" /><format attr="font-size" value="1" /></style-rule>'
                  f'<style-rule element="header"><format attr="color" value="#D6D6D6" /><format attr="font-size" value="9" /></style-rule>'
                  f'<style-rule element="label"><format attr="color" value="{TXT2}" /><format attr="font-size" value="8" /></style-rule>'
                  f'<style-rule element="gridline"><format attr="line-visibility" scope="cols" value="off" />'
                  f'<format attr="stroke-color" scope="rows" value="{GRID}" /></style-rule>'
                  '<style-rule element="zeroline"><format attr="line-visibility" value="off" /></style-rule>'
                  f'<style-rule element="table-div"><format attr="stroke-color" value="{bgc}" /></style-rule>'
                  f'<style-rule element="header-div"><format attr="stroke-color" value="{bgc}" /></style-rule>'
                  f'<style-rule element="table"><format attr="background-color" value="{bgc}" /></style-rule>'
                  f'<style-rule element="pane"><format attr="background-color" value="{bgc}" /></style-rule>'
                  f'<style-rule element="title"><format attr="background-color" value="{bgc}" /></style-rule>'
                  f'<style-rule element="legend"><format attr="background-color" value="{bgc}" /><format attr="color" value="#D6D6D6" /></style-rule>'
                  f'<style-rule element="legend-title"><format attr="color" value="{TXT2}" /></style-rule>'
                  f'<style-rule element="worksheet"><format attr="font-family" value="{FONT}" />'
                  '<format attr="display-field-labels" scope="rows" value="false" />'
                  '<format attr="display-field-labels" scope="cols" value="false" />'
                  f'<format attr="background-color" value="{bgc}" /></style-rule>'
                  + ws.get('palette', '') + st + '</style>')
    enc = ''.join(f'<{k} column={q(v.full)} />' for k, v in ws.get('enc', {}).items() if k != 'tooltip2')
    pane_style = ''
    mk = ''
    if ws.get('mark_color'):
        mk += f'<format attr="mark-color" value="{ws["mark_color"]}" />'
    if ws.get('labels'):
        mk += '<format attr="mark-labels-show" value="true" />'
    if mk:
        pane_style += f'<style-rule element="mark">{mk}</style-rule>'

    label = ''
    if ws.get('label_xml'):
        label = f'<customized-label>{ws["label_xml"]}</customized-label>'
    tip = ''
    if ws.get('tooltip'):
        tip = f'<customized-tooltip>{ws["tooltip"]}</customized-tooltip>'
    pane = (f'<panes><pane selection-relaxation-option="selection-relaxation-allow"><view><breakdown value="auto" /></view>'
            f'<mark class={q(ws["mark"])} />{"<encodings>" + enc + "</encodings>" if enc else ""}'
            f'{tip}{label}{"<style>" + pane_style + "</style>" if pane_style else ""}</pane></panes>')
    def shelf(x):
        if not x: return ''
        if isinstance(x, Ref): return x.full
        if isinstance(x, tuple): return '(' + ' + '.join(r.full for r in x) + ')'
        return ' / '.join(r.full for r in x)
    rows = shelf(ws.get('rows')); cols = shelf(ws.get('cols'))
    title = ''
    if ws.get('title'):
        title = (f'<layout-options><title><formatted-text>'
                 f'<run fontcolor="{TXT}" fontname="{FONT_SB}" fontsize="12">{escape(ws["title"])}</run>'
                 + (f'<run fontcolor="{TXT2}" fontname="{FONT}" fontsize="9">Æ&#10;{escape(ws["subtitle"])}</run>' if ws.get('subtitle') else '')
                 + '</formatted-text></title></layout-options>')
    num = SHEETS.index(ws) + 1
    return (f'<worksheet name={q(ws["name"])}>{title}<table>{view}{base_style}{pane}'
            f'<rows>{rows}</rows><cols>{cols}</cols></table><simple-id uuid="{uid()}" />'
            '</worksheet>')

def run(text, size=10, color=INK, bold=False):
    return (f'<run{" bold=" + q("true") if bold else ""} fontcolor="{color}" fontname="{FONT}" '
            f'fontsize="{size}">{escape(text)}</run>')

# ---------------------------------------------------------------- sheets
P = 'plays'
hours = R(P, 'hours_played'); nplays = R(P, 'plays')
artist = R(P, 'artist'); track = R(P, 'track')
def lbl(*runs): return '<formatted-text>' + ''.join(runs) + '</formatted-text>'
def ref_txt(r): return '&lt;' + r.full + '&gt;'
NL = '<run>Æ&#10;</run>'

def kpi(name, ref, caption, ds=None):
    return dict(name=name, ds=ds or ref.ds, mark='Text', enc={'text': ref},
                tooltip=lbl(run(caption + ': ', 10, MUTED), f'<run bold="true" fontname="{FONT}" fontsize="10">{ref_txt(ref)}</run>'),
                style=f'<style-rule element="cell"><format attr="text-align" value="left" /><format attr="vertical-align" value="center" />'
                      f'<format attr="font-size" value="28" /><format attr="color" value="{TXT}" /><format attr="font-family" value="{FONT_LT}" /></style-rule>')

def tip(*pairs):
    out = []
    for i, (cap, r) in enumerate(pairs):
        if i: out.append(NL)
        out.append(run(cap + ': ', 10, MUTED))
        out.append(f'<run bold="true" fontname="{FONT}" fontsize="10">{ref_txt(r)}</run>')
    return lbl(*out)

month = R(P, 'play_date', 'Month-Trunc')
year = R(P, 'play_year'); hour = R(P, 'play_hour'); wday = R(P, 'weekday_number')
skiprate = R(P, 'Calculation_SkipRate'); shuffle = R(P, 'Calculation_ShuffleRate')
newart = R(P, 'Calculation_NewArtists'); newshare = R(P, 'Calculation_NewShare')
ctd_artist = R(P, 'artist', 'CountD', cont=True); ctd_track = R(P, 'track', 'CountD', cont=True)
minday = R(P, 'Calculation_MinPerDay'); share = R(P, 'Calculation_PlayShare')
device = R(P, 'device_family'); country = R(P, 'country_name'); reason = R(P, 'reason_end_label')
bucket = R(P, 'skip_bucket'); track_label = R(P, 'track_label')
endshare = R(P, 'Calculation_EndShare'); skipkpi = R(P, 'Calculation_SkipKPI')
sessions_n = R('sessions', 'Calculation_Sessions'); sess_avg = R('sessions', 'Calculation_AvgSessMin')
sess_max = R('sessions', 'Calculation_MaxSess')

heat_palette = (f'<style-rule element="mark"><encoding attr="color" field={q(hours.full)} type="custom-interpolated">'
                f'<color-palette custom="true" name="" type="ordered-sequential"><color>#1F1F1F</color><color>#0E5C2C</color>'
                f'<color>#1ED760</color></color-palette></encoding></style-rule>')
DEVICE_COLORS = {'iPhone / iPad': '#1ED760', 'Computer': '#509BF5', 'Web player': '#B49BC8', 'Android': '#F59B23',
                 'Speaker / TV / car': '#E8115B', 'Other': '#6F6F6F'}
dev_palette = (f'<style-rule element="mark"><encoding attr="color" field={q(device.full)} type="palette">'
               + ''.join(f'<map to="{c}"><bucket>{escape(chr(34) + k + chr(34))}</bucket></map>' for k, c in DEVICE_COLORS.items())
               + '</encoding></style-rule>')

def define_sheets(meta):
    global SHEETS, ARTIST_PALETTE
    TOP_ARTISTS = list(meta['top_artists'])[:10]
    ART_COLORS = ['#1ED760', '#509BF5', '#F59B23', '#E8115B', '#B49BC8', '#2DD4BF', '#FFD166', '#F573A0', '#7DD3FC', '#A3E635']
    ARTIST_PALETTE = (f'<style-rule element="mark"><encoding attr="color" field={q(artist.full)} type="palette">'
                      + ''.join(f'<map to="{c}"><bucket>{escape(chr(34) + a + chr(34))}</bucket></map>'
                                for a, c in zip(TOP_ARTISTS, ART_COLORS))
                      + '</encoding></style-rule>')

    SHEETS = [
        kpi('KPI Hours', hours, 'hours listened'),
        kpi('KPI Plays', nplays, 'tracks played'),
        kpi('KPI Artists', ctd_artist, 'different artists'),
        kpi('KPI Minutes', minday, 'minutes per listening day'),
        kpi('KPI Skip', skipkpi, 'skip rate'),
        kpi('KPI Shuffle', shuffle, 'shuffle rate'),
        kpi('KPI End', endshare, 'played to the end'),
        kpi('KPI Sessions', sessions_n, 'listening sessions'),
        kpi('KPI SessAvg', sess_avg, 'average session (minutes)'),
        kpi('KPI SessMax', sess_max, 'longest session (hours)'),
        dict(name='Hours per month', ds=P, mark='Area', cols=month, rows=hours, mark_color=GREEN,
             title='Hours per month', subtitle='How much you listened, month by month',
             tooltip=tip(('Month', month), ('Hours', hours), ('Plays', nplays))),
        dict(name='Listening clock', ds=P, mark='Square', rows=wday, cols=hour, enc={'color': hours}, palette=heat_palette,
             title='Listening clock', subtitle='Hours by weekday and hour of day (local time)',
             tooltip=tip(('Weekday', wday), ('Hour', hour), ('Hours', hours)),
             style='<style-rule element="gridline"><format attr="line-visibility" value="off" /></style-rule>'),
        dict(name='Top artists', ds=P, mark='Bar', rows=artist, cols=hours, mark_color=GREEN, labels=True,
             topn=(artist, 10, 'SUM([hours_played])'), sorts=[(artist, hours, 'DESC')], enc={'text': hours},
             title='Top 10 artists', subtitle='By hours listened. Click an artist to filter this page',
             tooltip=tip(('Artist', artist), ('Hours', hours), ('Plays', nplays))),
        dict(name='Artist trends', ds=P, mark='Line', cols=year, rows=hours, enc={'color': artist}, palette=ARTIST_PALETTE,
             topn=(artist, 6, 'SUM([hours_played])'),
             title='Top 6 artists over time', subtitle='Hours listened per year',
             tooltip=tip(('Artist', artist), ('Year', year), ('Hours', hours))),
        dict(name='Top tracks', ds=P, mark='Bar', rows=track_label, cols=nplays, mark_color=BLUE, labels=True, enc={'text': nplays},
             topn=(track_label, 12, 'SUM([plays])'), sorts=[(track_label, nplays, 'DESC')],
             title='Most played tracks', subtitle='Top 12 by number of plays',
             tooltip=tip(('Track', track_label), ('Plays', nplays), ('Hours', hours))),
        dict(name='New artists per year', ds=P, mark='Bar', cols=year, rows=newart, mark_color=GREEN, labels=True, enc={'text': newart},
             title='New artists discovered', subtitle='Artists heard for the first time, per year',
             tooltip=tip(('Year', year), ('New artists', newart), ('Hours on new artists', newshare))),
        dict(name='Concentration curve', ds='artists', mark='Line', disagg=True,
             cols=Ref('artists', 'pct_of_artists_excl_bg', 'None', cont=True),
             rows=Ref('artists', 'cumulative_share_excl_bg_pct', 'None', cont=True), mark_color=GREEN,
             title='How concentrated is your taste?', subtitle='Cumulative share of hours vs share of artists (all-time)',
             tooltip=tip(('Top % of artists', Ref('artists', 'pct_of_artists_excl_bg', 'None', cont=True)),
                         ('Share of hours', Ref('artists', 'cumulative_share_excl_bg_pct', 'None', cont=True)))),
        dict(name='Skip rate by hour', ds=P, mark='Bar', cols=hour, rows=skiprate, mark_color=GREEN,
             title='When do you skip?', subtitle='Share of plays skipped forward, by hour of day',
             tooltip=tip(('Hour', hour), ('Skip rate', skiprate), ('Plays', nplays))),
        dict(name='Skip and shuffle by year', ds=P, mark='Line', cols=year, rows=skiprate, mark_color=GREEN,
             title='Skipping over the years', subtitle='Share of plays skipped forward, per year',
             tooltip=tip(('Year', year), ('Skip rate', skiprate), ('Shuffle rate', shuffle))),
        dict(name='Time before skipping', ds=P, mark='Bar', cols=bucket, rows=nplays, mark_color=BLUE,
             extra_filters=[(bucket, ['0'], True)],
             title='How long before you bail?', subtitle='Skipped plays by seconds listened',
             tooltip=tip(('Listened for', bucket), ('Skips', nplays))),
        dict(name='How tracks ended', ds=P, mark='Bar', rows=reason, cols=share, mark_color=GREEN, labels=True, enc={'text': share},
             sorts=[(reason, nplays, 'DESC')], topn=(reason, 6, 'SUM([plays])'),
             title='How each track ended', subtitle='Share of all plays, top 6 reasons',
             tooltip=tip(('Ended by', reason), ('Share', share), ('Plays', nplays))),
        dict(name='Devices by year', ds=P, mark='Bar', cols=year, rows=hours, enc={'color': device}, palette=dev_palette,
             extra_filters=[(device, ['"Unrecorded"'], True)],
             title='What you listened on', subtitle='Hours per year by device',
             tooltip=tip(('Device', device), ('Year', year), ('Hours', hours))),
        dict(name='Countries', ds=P, mark='Bar', rows=country, cols=hours, mark_color=BLUE, labels=True, enc={'text': hours},
             topn=(country, 6, 'SUM([hours_played])'), sorts=[(country, hours, 'DESC')],
             title='Where you listened', subtitle='Hours by country (top 6)',
             tooltip=tip(('Country', country), ('Hours', hours))),
        dict(name='Session lengths', ds='sessions', mark='Bar', cols=R('sessions', 'length_bucket_order'),
             rows=R('sessions', 'Calculation_Sessions'), mark_color=GREEN, labels=True, enc={'text': R('sessions', 'Calculation_Sessions')},
             title='How long are your listening sessions?', subtitle='A new session starts after a 30-minute gap',
             tooltip=tip(('Length', R('sessions', 'length_bucket_order')), ('Sessions', R('sessions', 'Calculation_Sessions')))),
    ]

    SHEETS += [
        dict(name='Brand years', ds=P, mark='Text', enc={'text': Ref(P, 'Calculation_SpanLabel', 'User', cont=False)},
             no_filter=True, bg=RAIL,
             style=f'<style-rule element="cell"><format attr="text-align" value="left" /><format attr="vertical-align" value="center" />'
                   f'<format attr="font-size" value="19" /><format attr="color" value="{TXT}" /><format attr="font-family" value="{FONT_SB}" /></style-rule>'),
        dict(name='Brand range', ds=P, mark='Text', enc={'text': Ref(P, 'Calculation_RangeLabel', 'User', cont=False)},
             no_filter=True, bg=RAIL,
             style=f'<style-rule element="cell"><format attr="text-align" value="left" /><format attr="vertical-align" value="center" />'
                   f'<format attr="font-size" value="8" /><format attr="color" value="{TXT3}" /><format attr="font-family" value="{FONT}" /></style-rule>'),
    ]


# ---------------------------------------------------------------- dashboards
W, H = 1400, 900


def Z(x, y, w, h):
    return dict(x=round(x / W * 100000), y=round(y / H * 100000), w=round(w / W * 100000), h=round(h / H * 100000))


def zone_style(bg=None, pad=None, border=None, radius=None):
    f = ''
    if bg: f += f'<format attr="background-color" value="{bg}" />'
    if border:
        f += f'<format attr="border-color" value="{border}" /><format attr="border-style" value="solid" /><format attr="border-width" value="1" />'
    else:
        f += '<format attr="border-style" value="none" />'
    if pad is not None:
        f += f'<format attr="padding" value="{pad}" /><format attr="margin" value="0" />'
    return f'<zone-style>{f}</zone-style>'

def r(text, size=10, color=TXT, font=FONT):
    return f'<run fontcolor="{color}" fontname="{font}" fontsize="{size}">{escape(text)}</run>'

def link_run(text, url, size=8):
    return (f'<run fontcolor="{GREEN}" fontname="{FONT_SB}" fontsize="{size}" hyperlink={q(url)} underline="true">'
            f'{escape(text)}</run>')

CONTEXT = {}   # per-history text, set by build()

def ra(text, size=10, color=TXT, font=FONT):   # right-aligned run
    return f'<run fontalignment="2" fontcolor="{color}" fontname="{font}" fontsize="{size}">{escape(text)}</run>'

PAGES = ['Overview', 'Artists & tracks', 'Skipping', 'Sessions & devices']
CX, CW, GAP = 256, 1120, 16          # content column

class Dash:
    def __init__(self, name, subtitle):
        self.name, self.subtitle, self.zones, self.next_id, self.sheets = name, subtitle, [], 3, []
    def add(self, inner_xml, attrs, box):
        z = Z(*box)
        a = ' '.join(f'{k}={q(str(v))}' for k, v in attrs.items())
        self.zones.append(f'<zone h="{z["h"]}" id="{self.next_id}" {a} w="{z["w"]}" x="{z["x"]}" y="{z["y"]}">{inner_xml}</zone>')
        self.next_id += 1
    def sheet(self, name, box, show_title=True):
        self.sheets.append(name)
        attrs = {'name': name}
        if not show_title: attrs['show-title'] = 'false'
        self.add(zone_style(CARD, 14, None, 12), attrs, box)
    def sheet_with_legend(self, name, ref, box, legend_w):
        x, y, w, h = box
        self.blank(box, CARD, 12)
        self.sheets.append(name)
        self.add(zone_style(CARD, 14), {'name': name}, (x + 2, y + 2, w - legend_w - 4, h - 4))
        self.add(zone_style(CARD, 4), {'name': name, 'param': ref.full, 'type-v2': 'color'},
                 (x + w - legend_w - 6, y + 56, legend_w, h - 72))
    def kpi(self, sheet, caption, desc, box):
        x, y, w, h = box
        self.blank(box, CARD)
        self.blank((x, y, 3, h), GREEN)
        self.text(r(caption, 8, TXT2, FONT_SB), (x + 20, y + 16, w - 32, 20))
        self.sheets.append(sheet)
        self.add(zone_style(CARD, 0), {'name': sheet, 'show-title': 'false'}, (x + 14, y + 38, w - 28, 46))
        self.text(r(desc, 8, TXT3), (x + 20, y + 86, w - 32, h - 92))
    def text(self, runs_xml, box, bg=None, pad=0, radius=None):
        self.add(f'<formatted-text>{runs_xml}</formatted-text>' + zone_style(bg, pad, None, radius), {'type-v2': 'text'}, box)
    def blank(self, box, bg, radius=None):
        self.add(zone_style(bg, None, None, radius), {'type-v2': 'empty'}, box)
    def param(self, p, box):
        self.add(zone_style(RAIL, 2), {'param': p, 'type-v2': 'paramctrl'}, box)
    def chrome(self):
        self.blank((0, 0, 1400, 900), BG)
        # navigation rail
        self.blank((0, 0, 240, 900), RAIL)
        self.sheets.append('Brand years')
        self.add(zone_style(RAIL, 0), {'name': 'Brand years', 'show-title': 'false'}, (18, 24, 214, 38))
        self.text(r('of listening', 19, GREEN, FONT_SB), (24, 62, 210, 34))
        self.sheets.append('Brand range')
        self.add(zone_style(RAIL, 0), {'name': 'Brand range', 'show-title': 'false'}, (18, 96, 214, 24))
        self.blank((24, 132, 192, 1), GRID)
        self.text(r('FILTERS', 8, TXT3, FONT_SB), (24, 150, 192, 20))
        self.param(P_YEAR, (20, 172, 200, 58))
        if CONTEXT['has_bg']:
            # background audio was found: show the switch and explain it
            self.param(P_PET, (20, 236, 200, 58))
            self.blank((20, 314, 200, 300), '#141414', 12)
            self.blank((20, 314, 3, 300), GREEN)
            self.text(r('WHAT IS BACKGROUND AUDIO?', 8, GREEN, FONT_SB), (36, 328, 176, 22))
            self.text(r('Sleep sounds, white noise or pet playlists left on repeat can swamp the charts. '
                        'Artists played heavily, almost never skipped and in a short burst are flagged '
                        'automatically and hidden by default.', 9, TXT2),
                      (36, 352, 176, 130))
            self.text(CONTEXT['bg_runs'], (36, 486, 176, 114))
        else:
            # nothing to hide: no switch, just a short note on what the dashboard shows
            self.blank((20, 250, 200, 220), '#141414', 12)
            self.blank((20, 250, 3, 220), GREEN)
            self.text(r('ABOUT THIS DATA', 8, GREEN, FONT_SB), (36, 264, 176, 22))
            about = r('Built from your Spotify extended streaming history. Each chart counts music only, '
                      'and a listening session ends after 30 minutes of silence.', 9, TXT2)
            if CONTEXT.get('note'):
                about += NL + NL + r(CONTEXT['note'], 9, TXT2)
            self.text(about, (36, 288, 176, 176))
        if CONTEXT.get('link'):
            self.text(r('Make your own: ', 8, TXT2) + link_run(CONTEXT['link_label'], CONTEXT['link'], 8),
                      (24, 768, 200, 40))
        self.text(r('Music only; podcasts and audiobooks excluded. Times are local to the country of each play.', 8, TXT3),
                  (24, 820, 192, 56))
        # page header + page indicator
        self.text(r(self.name, 24, TXT, FONT_SB) + NL + r(self.subtitle, 10, TXT2), (CX, 22, 760, 70))
        crumbs = ''
        for i, p in enumerate(PAGES):
            if i: crumbs += ra('   ·   ', 9, TXT3)
            crumbs += ra(p, 9, GREEN if p == self.name else TXT3, FONT_SB if p == self.name else FONT)
        self.text(crumbs, (CX + CW - 520, 36, 520, 24))
    def xml(self):
        deps = '<datasources><datasource name="Parameters" /></datasources>' \
               '<datasource-dependencies datasource="Parameters">' + ''.join(param_col_xml(p) for p in PARAMS) + '</datasource-dependencies>'
        style = (f'<style><style-rule element="dashboard"><format attr="background-color" value="{BG}" /></style-rule>'
                 f'<style-rule element="parameter-ctrl"><format attr="background-color" value="#1F1F1F" />'
                 f'<format attr="color" value="{TXT}" /><format attr="font-size" value="9" /></style-rule>'
                 f'<style-rule element="parameter-ctrl-title"><format attr="color" value="{TXT2}" />'
                 f'<format attr="font-size" value="8" /><format attr="font-weight" value="bold" /></style-rule></style>')
        return (f'<dashboard name={q(self.name)}>{style}'
                f'<size maxheight="{H}" maxwidth="{W}" minheight="{H}" minwidth="{W}" sizing-mode="fixed" />{deps}'
                f'<zones><zone h="100000" id="1" type-v2="layout-basic" w="100000" x="0" y="0" />'
                + ''.join(self.zones) + f'</zones><simple-id uuid="{uid()}" /></dashboard>')
    def window(self):
        vps = ''.join(f'<viewpoint name={q(s)}><zoom type="entire-view" /></viewpoint>' for s in self.sheets)
        return (f'<window class="dashboard" maximized="true" name={q(self.name)}><viewpoints>{vps}</viewpoints>'
                f'<active id="-1" /><simple-id uuid="{uid()}" /></window>')

def cols(n, widths=None):
    """x positions and widths for n cards across the content column."""
    if widths is None:
        w = (CW - GAP * (n - 1)) // n
        widths = [w] * (n - 1) + [CW - GAP * (n - 1) - w * (n - 1)]
    xs, x = [], CX
    for w in widths:
        xs.append((x, w)); x += w + GAP
    return xs

def define_dashes():
    global DASHES
    d1 = Dash('Overview', 'How much, when and who: your listening at a glance')
    d1.chrome()
    KPIS = [('KPI Hours', 'HOURS LISTENED', 'Time actually played, not just started'),
            ('KPI Plays', 'TRACKS PLAYED', 'Every start counts, even a two-second skip'),
            ('KPI Artists', 'DIFFERENT ARTISTS', 'Heard at least once'),
            ('KPI Minutes', 'MINUTES PER DAY', 'Average across days with any listening')]
    for (x, w), (k, cap, desc) in zip(cols(4), KPIS):
        d1.kpi(k, cap, desc, (x, 104, w, 120))
    d1.sheet('Hours per month', (CX, 240, CW, 276))
    (xa, wa), (xb, wb) = cols(2, [656, 448])
    d1.sheet('Listening clock', (xa, 532, wa, 352))
    d1.sheet('Top artists', (xb, 532, wb, 352))

    d2 = Dash('Artists & tracks', 'Favourites, discoveries and how concentrated your taste is')
    d2.chrome()
    (xa, wa), (xb, wb) = cols(2, [672, 432])
    d2.sheet_with_legend('Artist trends', artist, (xa, 104, wa, 384), 150)
    d2.sheet('Top tracks', (xb, 104, wb, 384))
    (xa, wa), (xb, wb) = cols(2)
    d2.sheet('New artists per year', (xa, 504, wa, 380))
    d2.sheet('Concentration curve', (xb, 504, wb, 380))

    def kpi_row(d, items, y=104, h=120):
        for (x, w), (k, cap, desc) in zip(cols(len(items)), items):
            d.kpi(k, cap, desc, (x, y, w, h))

    d3 = Dash('Skipping', 'When, how fast and how often tracks get skipped')
    d3.chrome()
    kpi_row(d3, [('KPI Skip', 'SKIP RATE', 'Share of plays skipped forward'),
                 ('KPI Shuffle', 'SHUFFLE RATE', 'Share of plays with shuffle on'),
                 ('KPI End', 'PLAYED TO THE END', 'Share of plays that finished')])
    (xa, wa), (xb, wb) = cols(2)
    d3.sheet('Skip rate by hour', (xa, 240, wa, 314))
    d3.sheet('Skip and shuffle by year', (xb, 240, wb, 314))
    d3.sheet('Time before skipping', (xa, 570, wa, 314))
    d3.sheet('How tracks ended', (xb, 570, wb, 314))

    d4 = Dash('Sessions & devices', 'How long each session lasts, what you listened on, and where')
    d4.chrome()
    kpi_row(d4, [('KPI Sessions', 'LISTENING SESSIONS', 'A new session starts after a 30-minute gap'),
                 ('KPI SessAvg', 'AVERAGE SESSION', 'Minutes per session'),
                 ('KPI SessMax', 'LONGEST SESSION', 'Hours in a single sitting')])
    d4.sheet_with_legend('Devices by year', device, (CX, 240, CW, 314), 160)
    (xa, wa), (xb, wb) = cols(2)
    d4.sheet('Session lengths', (xa, 570, wa, 314))
    d4.sheet('Countries', (xb, 570, wb, 314))
    DASHES = [d1, d2, d3, d4]


def ws_window(name):
    return (f'<window class="worksheet" hidden="true" maximized="true" name={q(name)}><cards>'
            '<edge name="left"><strip size="160"><card type="pages" /><card type="filters" /><card type="marks" /></strip></edge>'
            '<edge name="top"><strip size="2147483647"><card type="columns" /></strip><strip size="2147483647"><card type="rows" /></strip>'
            '<strip size="31"><card type="title" /></strip></edge></cards>'
            f'<simple-id uuid="{uid()}" /></window>')

def workbook():
    return ('<?xml version="1.0" encoding="utf-8" ?>\n'
            '<workbook original-version="18.1" source-build="2023.1.0 (20231.23.0310.1045)" source-platform="mac" version="18.1" '
            'xmlns:user="http://www.tableausoftware.com/xml/user">'
            '<document-format-change-manifest><SheetIdentifierTracking /><WindowsPersistSimpleIdentifiers /></document-format-change-manifest>'
            '<preferences><preference name="ui.encoding.shelf.height" value="24" /><preference name="ui.shelf.height" value="26" /></preferences>'
            '<datasources>' + params_ds_xml() + ''.join(datasource_xml(k) for k in DS) + '</datasources>'
            '<actions><action caption="Filter page by artist" name="[Action1_ArtistFilter]">'
            '<activation auto-clear="true" type="on-select" />'
            '<source dashboard="Overview" type="sheet" worksheet="Top artists" />'
            '<command command="tsc:tsl-filter"><param name="special-fields" value="all" />'
            '<param name="target" value="Overview" /></command></action></actions>'
            '<worksheets>' + ''.join(worksheet_xml(w) for w in SHEETS) + '</worksheets>'
            '<dashboards>' + ''.join(d.xml() for d in DASHES) + '</dashboards>'
            '<windows source-height="30">' + ''.join(d.window() for d in DASHES)
            + ''.join(ws_window(w['name']) for w in SHEETS) + '</windows>'
            '</workbook>')

def _bg_runs(meta, note):
    items = meta.get('background', [])
    if not items:
        runs = r('Nothing in this history matched.', 9, TXT2)
    else:
        runs = r('In this history: ', 9, TXT2)
        shown = items[:3]
        for k, it in enumerate(shown):
            if k:
                runs += r(', ' if k < len(shown) - 1 else ' and ', 9, TXT2)
            runs += r(it['artist'], 9, TXT, FONT_SB)
            runs += r(f" ({it['plays']:,} plays, about {round(it['hours']):,} h)", 9, TXT2)
        if len(items) > 3:
            runs += r(f' and {len(items) - 3} more', 9, TXT2)
        runs += r('.', 9, TXT2)
    if note:
        runs += NL + NL + r(note, 9, TXT2)
    return runs


def build(meta, note=None, link=None, link_label='see the project on GitHub'):
    """Return the workbook XML for one listening history."""
    PARAMS[0]['values'] = ['All'] + [str(y) for y in meta['years']]
    CONTEXT.clear()
    CONTEXT.update(bg_runs=_bg_runs(meta, note), has_bg=bool(meta.get('background')), note=note,
                   link=link, link_label=link_label)
    define_sheets(meta)
    define_dashes()
    return workbook()
