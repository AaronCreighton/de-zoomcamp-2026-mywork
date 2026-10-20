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
    
    
