"""Write the three tables as Tableau Hyper extracts (Tableau Public requires extracts)."""
from pathlib import Path

from tableauhyperapi import (Connection, CreateMode, HyperProcess, Inserter, Nullability, SqlType,
                             TableDefinition, TableName, Telemetry)

from .workbook import DS

TYPES = {'integer': SqlType.big_int(), 'real': SqlType.double(), 'string': SqlType.text(),
         'date': SqlType.date(), 'datetime': SqlType.timestamp()}


def write_extracts(tables, out_dir):
    """tables: {'plays': DataFrame, 'artists': ..., 'sessions': ...}. Returns {key: path}."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {}
    with HyperProcess(Telemetry.DO_NOT_SEND_USAGE_DATA_TO_TABLEAU,
                      parameters={'default_database_version': '2', 'log_config': ''}) as hp:
        for key, spec in DS.items():
            df = tables[key]
            path = out_dir / f'{key}.hyper'
            cols = [c for c, _ in spec['cols']]
            with Connection(hp.endpoint, str(path), CreateMode.CREATE_AND_REPLACE) as conn:
                conn.catalog.create_schema('Extract')
                table = TableDefinition(TableName('Extract', 'Extract'),
                                        [TableDefinition.Column(c, TYPES[t], Nullability.NULLABLE)
                                         for c, t in spec['cols']])
                conn.catalog.create_table(table)
                # Stage through CSV text so dates/timestamps parse exactly as Tableau's text reader would.
                csv_path = out_dir / f'{key}.csv'
                df[cols].to_csv(csv_path, index=False)
                conn.execute_command(f"COPY {table.table_name} FROM '{csv_path.as_posix()}' "
                                     "WITH (format csv, header true, null '')")
                csv_path.unlink()
            paths[key] = path
    return paths
