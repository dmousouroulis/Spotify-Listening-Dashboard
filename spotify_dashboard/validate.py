"""Internal consistency checks for a generated workbook (every field, filter, sheet and action resolves)."""
import re

from lxml import etree


def check_workbook(xml_text):
    """Return a list of problems (empty when the workbook is consistent)."""
    r = etree.fromstring(xml_text.encode('utf-8'))
    errs = []

    ds_fields={}
    for ds in r.find('datasources'):
        nm=ds.get('name'); cols=set()
        for c in ds.iter('column'):
            n=c.get('name'); cols.add(n if n.startswith('[') else '['+n+']')
        ds_fields[nm]=cols
        for c in ds.findall('column'):
            calc=c.find('calculation')
            if calc is not None:
                for ref in re.findall(r'(\[[^\]]+\]\.)?(\[[^\]]+\])', calc.get('formula')):
                    dsn=ref[0][1:-2] if ref[0] else nm
                    if ref[1] not in ds_fields.get(dsn,set()) and dsn!='Parameters' and ref[1] not in cols:
                        errs.append(f'{nm}: formula ref {ref} missing')
                    if dsn=='Parameters' and ref[1] not in ds_fields['Parameters']: errs.append('param missing '+ref[1])
    sheets=set()
    for ws in r.find('worksheets'):
        name=ws.get('name'); sheets.add(name)
        insts={}
        for dep in ws.iter('datasource-dependencies'):
            dsn=dep.get('datasource')
            cols={c.get('name') for c in dep.findall('column')}
            for ci in dep.findall('column-instance'):
                insts[f'[{dsn}].{ci.get("name")}']=ci
                if ci.get('column') not in cols: errs.append(f'{name}: instance {ci.get("name")} column not declared')
        text=etree.tostring(ws).decode()
        for m in re.findall(r'\[(federated\.[^\]]+)\]\.(\[[a-z]+:[^\]]+\])', text):
            k=f'[{m[0]}].{m[1]}'
            if k not in insts: errs.append(f'{name}: uses {k} not declared')
        for gf in ws.iter('groupfilter'):
            lv=gf.get('level')
            if lv and not any(k.endswith(lv) for k in insts): errs.append(f'{name}: filter level {lv} missing')
    for db in r.find('dashboards'):
        for z in db.iter('zone'):
            if z.get('name') and z.get('name') not in sheets: errs.append(f'dash {db.get("name")}: unknown sheet {z.get("name")}')
            p=z.get('param')
            if p and z.get('type-v2')=='color':
                ws=[w for w in r.find('worksheets') if w.get('name')==z.get('name')][0]
                if p not in etree.tostring(ws).decode(): errs.append('legend field not on sheet '+p)
    wins={w.get('name') for w in r.find('windows')}
    dashes={d.get('name') for d in r.find('dashboards')}
    if wins!=sheets|dashes: errs.append('windows mismatch')
    for a in r.iter('source'):
        if a.get('worksheet') not in sheets: errs.append('action source missing')
    return errs
