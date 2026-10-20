import os


EXT_BQT_SQL = """\
CREATE OR REPLACE EXTERNAL TABLE `{project}.{dataset}.{table}`
(
{columns}
)
OPTIONS (
  format = 'CSV',
  uris = ['{uri}'],
  compression = 'GZIP',
  skip_leading_rows = 1
)
"""

def build_bqt_ext_sql(target, project, dataset, bucket, table_base, prefix):
    columns = ",\n".join(f"  `{n}` STRING" for n in target["names"])
    return EXT_BQT_SQL.format(
        project=project,
        dataset=dataset,
        table=f"{table_base}_{target['year']}_{target['month']}_ext",
        columns=columns,
        uri= f"gs://{bucket}/{prefix}/{target['year']}/{target['month']}.csv.gz",
    )
    
    
INSERT_DELETE_SQL = """\
DECLARE load_ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP();

INSERT INTO `{project}.{dataset}.{table}`
(
{columns},
  `filename`,
  `ingestion_timestamp`
)
SELECT *, '{filename}', load_ts
FROM `{project}.{dataset}.{ext_table}`;

DELETE FROM `{project}.{dataset}.{table}`
WHERE filename = '{filename}'
  AND ingestion_timestamp < load_ts;
"""


def build_insert_delete_sql(target, project, dataset, table_base):
    columns = ",\n".join(f"  `{n}`" for n in target["names"])
    return INSERT_DELETE_SQL.format(
        project=project,
        dataset=dataset,
        table=table_base,
        ext_table=f"{table_base}_{target['year']}_{target['month']}_ext",
        columns=columns,
        filename=os.path.basename(target["path"]),
    )