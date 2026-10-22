# Airflow Pipeline for dbt — build steps

The steps that built the download producer and the BigQuery load consumer, in the order they were
done. Commands, code and the checks that catch a step going wrong.

**Why any of it is shaped this way is not here.** That is in `DESIGN_DECISIONS_DBT.md`, as numbered
decisions under two driver sections, with `DESIGN_DECISIONS_SETUP.md` for the environment. This file
assumes those were already decided and just builds the thing.

---

# Producer

One DAG per colour from a factory. Downloads the `.csv.gz` to the mounted volume and publishes it as
an asset. Nothing else — no conversion, no target-specific anything.

### 1. Mount the download volume

```bash
mkdir -p ./taxi_download
echo 'taxi_download/' >> .gitignore
```

One line in `docker-compose.yaml`, under `x-airflow-common` → `volumes`:

```yaml
    - ${AIRFLOW_PROJ_DIR:-.}/taxi_download:/opt/airflow/taxi_download
```

That's the anchor every service inherits, so it covers the scheduler, dag-processor, triggerer,
worker and apiserver at once — it isn't repeated per service.

```bash
docker compose down
docker compose up -d
```

It isn't mounted today. That worked only because download and load ran in the same container in the
same DAG run. The split needs the file to outlive the producer's run, be readable by another DAG's
tasks, and survive a container restart part-way through a 48-month backfill.

### 2. Create the producer DAG

Start from a copy of the old GCP DAG and remove everything after the extract task.

**Remove**

- Everything after extract: upload, external table, staging, merge, cleanup.
- The GCP Variables and `GCP_CONN_ID` — the producer is target-agnostic, nothing in it touches
  Google.
- `TABLE_NAME`, `GCS_FILE_PREFIX`, and anything else only the load used.

**Change**

- `dag_id` → a new one. Must not collide with the old DAG's, which still exists as the consumer.
- `start_date` → `pendulum.datetime(2019, 1, 1, tz="UTC")`. Timezone-aware, or `logical_date`
  renders as today again.
- `catchup=False` — the 24 months get triggered explicitly with backfill, not by catching up on
  unpause.

**Keep**

- The `DATASETS` config dict outside the DAG, with the per-colour monthly crons.
- The factory and the `globals()` registration loop.

The producer is the DAG with a cron, so it owns the date range and it's the one you backfill; the
consumers have no schedule of their own.

### 3. Assets module

`dags/utils/assets.py`, imported by both producer and consumer. The consumer can't import an asset
defined inside the producer's factory, and redefining it means the identity string exists twice.

```python
from airflow.sdk import Asset

TAXI_GZ = {
    colour: Asset(name=f"{colour}_tripdata_gz", uri=f"taxi://{colour}_tripdata_gz")
    for colour in ("yellow", "green")
}
```

Needs `dags/utils/__init__.py` beside it.

The URI is the asset's identity — what the consumer subscribes to — not a file location. Airflow
never opens it. It's fixed at parse time, so it identifies the stream of yellow downloads, and which
file arrived on a given run travels in the event's `extra`. It must be unique per colour, or both
consumers fire on both colours. `name` is the label shown in the UI.

Check it imports. Run from the DAGs folder — an ad-hoc shell doesn't have it on `sys.path`:

```bash
docker compose exec -w /opt/airflow/dags airflow-scheduler python -c "
from utils.assets import TAXI_GZ
print(TAXI_GZ)
"
```

### 4. Extract and publish

The `BashOperator` becomes a Python task that downloads the file and publishes the asset:

```python
import requests
from airflow.sdk import dag, task
from utils.assets import TAXI_GZ

DOWNLOAD_DIR = "/opt/airflow/taxi_download"
```

```python
            asset = TAXI_GZ[colour]

            @task(outlets=[asset])
            def extract(url, dest, *, outlet_events):
                with requests.get(url, stream=True, timeout=60) as r:
                    r.raise_for_status()
                    with open(dest, "wb") as f:
                        for chunk in r.iter_content(chunk_size=1 << 20):
                            f.write(chunk)
                outlet_events[asset].extra = {"path": dest}

            extract(URL_TEMPLATE, OUTPUT_FILE_TEMPLATE)
```

Python because only a Python task can set an `extra` on the asset event. One task rather than a
bash download plus a publish task, because `outlets` declares *this task produced this asset* —
the task that writes the file should be the one that announces it, and one success then means both
"file landed" and "event fired".

The `extra` carries the full `path`. Where files land is the producer's decision; handing over the
path means the consumer doesn't need to know the mount location, and it takes the basename for the
`filename` idempotency key. The event payload is the interface between the DAGs — the consumer is
told what arrived rather than inferring it from the producer's schedule.

`OUTPUT_FILE_TEMPLATE` is built from `DOWNLOAD_DIR` and ends `.csv.gz` — DuckDB infers compression
from the extension. Not `os.environ.get("AIRFLOW_HOME", ...)`: `AIRFLOW_HOME` is set to
`/opt/airflow` in the container, so the default never applies and files land outside the mount.

`iter_content` streams the download to disk in 1 MB pieces rather than holding the whole file in
memory. The bytes are written verbatim — nothing is decompressed. `raise_for_status()` fails the
task on an HTTP error.

Overwrite the same path each run, and do **not** add a skip-if-the-output-exists check — that's the
bug in the course script, where a revised source file would never be re-downloaded.

`dag` and `task` both come from `airflow.sdk`; dropping `dag` from the import gives
`NameError: name 'dag' is not defined` at the `@dag(` line.

### 5. Test the producer

Trigger one month. The file is intact gzip:

```bash
gunzip -t taxi_download/yellow_tripdata_2019-01.csv.gz && zcat taxi_download/yellow_tripdata_2019-01.csv.gz | head -2
```

No output from `-t`, then a header line and a row.

The handover: in the UI, **Assets** → `yellow_tripdata_gz` → latest event shows `path` in its extra.

---

# BigQuery consumer

The existing GCP DAG, restructured: no download, scheduled on the parquet asset, loading with
append-and-prune.

### 6. Strip down the old DAG

**Remove**

- The extract task — the download DAG does that now.
- The strings it used: the source URL and the download path templates.
- The local-file cleanup task.
- The `DATASETS` dict. This DAG needs the colours, not the crons — those only serve the download
  DAG now. Replaced in step 7.

**Keep**

- The factory and the `globals()` registration loop.
- `GCP_CONN_ID` and the GCP Variables.
- The target-table create task.

### 7. Shared config module

The colour list is now needed by both DAGs and by `assets.py`, so it lives in one place:

```python
# dags/utils/config.py
DATASETS = {
    "yellow": {"schedule": "0 10 1 * *"},
    "green":  {"schedule": "0 9 1 * *"},
}
COLOURS = tuple(DATASETS)
```

```python
# download DAG
from utils.config import DATASETS

for colour, config in DATASETS.items():
    globals()[f"dag_{colour}"] = make_dag(colour, config)
```

```python
# load DAG
from utils.config import COLOURS

for colour in COLOURS:
    globals()[f"dag_{colour}"] = make_dag(colour)
```

`assets.py` imports `COLOURS` too, instead of its own `("yellow", "green")` literal.

`COLOURS` derives from `DATASETS` rather than the reverse — the crons can't be generated from a
colour list, so the dict is the authority and adding a colour is one edit.

The download DAG loops over `DATASETS` because it needs a per-colour cron; the load DAG loops over
`COLOURS` because it doesn't.

### 8. Schedule on the asset

```python
from utils.assets import TAXI_GZ

    @dag(
        dag_id=...,
        schedule=[TAXI_GZ[colour]],
        catchup=False,
    )
```

First task reads what arrived:

```python
        @task
        def file_downloaded(*, triggering_asset_events):
            return [
                e.extra["path"]
                for events in triggering_asset_events.values()
                for e in events
            ]
```

It returns a **list**. A run can be triggered by several events — during a backfill they arrive
faster than the load drains and Airflow coalesces them into one run. The steps below `.expand()`
over this, or months get silently skipped.

`filename` is `basename(path)`, not built from `logical_date` — the run's logical date is when the
event fired, not the data month.

The external table name has to include the month, or mapped instances of step 12 all
`CREATE OR REPLACE` the same `<colour>_tripdata_ext` and race, leaving the load reading whichever
month won. They're metadata only, so the extra tables cost nothing.

A manual trigger has no triggering events, so `file_downloaded` comes back empty and nothing loads. A params
override for colour and month is the way to re-load one month without re-running the download DAG.

`start_date` isn't used for asset triggering. A past one is harmless.

Test: trigger the download DAG for one month. A load run should start on its own, with `file_downloaded`'s
XCom a one-item list holding that path.

### 9. Read the header

The external table over a CSV needs a declared column list. Types are fixed — all `STRING` — so the
only unknown is the names, and they come from the file itself.

```python
import csv, gzip, os, re

            @task
            def get_file_info(src):
                with gzip.open(src, "rt", newline="") as f:
                    names = next(csv.reader(f), None)
                if not names:
                    raise ValueError(f"no header row in {src}")
                m = re.search(r"(\d{4})-(\d{2})", os.path.basename(src))
                return {
                    "path": src,
                    "year": m[1],
                    "month": m[2],
                    "names": [n.strip() for n in names],
                }
```

```python
            file_info = get_file_info.expand(src=file_downloaded())
```

gzip streams, so this decompresses the first block rather than the file. `csv.reader` instead of
`readline().split(",")` handles a quoted field containing a comma, and `newline=""` is the
documented open mode so a quoted field containing a newline parses. Names are stripped because a
stray space makes an invalid BigQuery identifier and the DDL error won't point at the cause.

It returns a **dict rather than just the names** because the steps below map over it. Expanding over
several separate lists and keeping them aligned needs zipping; one mapped value carrying everything
each task needs avoids that, and the derived parts get computed once instead of in three places.

`year` and `month` are returned as parts rather than one formatted string, because the two consumers
want different shapes — `2019/01` for the GCS object path, `2019_01` for the external table name.
One regex, no pre-baked format that only fits one caller.

No `filename`: it's `os.path.basename(path)`, derived in one call where step 14 needs it.

No `>>` between `file_downloaded` and `get_file_info`. Passing the output creates the dependency,
and the same holds down the chain. `>>` is only for tasks with nothing to pass each other — the
target-table create before the insert.

### 10. Target table — done

Existing tables dropped (base, `_ext`, `_staging`), target renamed to `<colour>_tripdata`, and the
staging-table task and its SQL deleted from the DAG.

Dropping an external table removes only BigQuery metadata; the GCS objects are untouched. Native
tables are really deleted — recovery is
[time travel](https://docs.cloud.google.com/bigquery/docs/access-historical-data) only, seven days
by default. Remove tables, not the dataset: Terraform owns the dataset.

**The target table is the contract**, and everything downstream conforms to it. Every source column
`STRING`, no exceptions — including the pickup and dropoff timestamps. Plus `filename` (`STRING`)
and `ingestion_timestamp` (`TIMESTAMP`). No `unique_row_id`.

```sql
PARTITION BY DATE(ingestion_timestamp)
CLUSTER BY filename
```

Column descriptions are not in the DDL — they move to `sources.yml`, so the contract isn't
duplicated.

### 11. Upload to GCS

The `.csv.gz` itself — nothing was converted, so nothing is created locally and nothing needs
deleting afterwards.

```python
            upload_task = LocalFilesystemToGCSOperator.partial(
                task_id="upload_to_gcs",
                gcp_conn_id=GCP_CONN_ID,
                bucket=Variable.get("GCP_BUCKET"),
            ).expand_kwargs(
                file_info.map(lambda t: {
                    "src": t["path"],
                    "dst": f"{GCS_FILE_PREFIX}/{t['year']}/{t['month']}.csv.gz",
                })
            )
```

Changes from the old task: `.csv.gz` rather than `.csv`, and `src`/`dst` come from the mapped dict
rather than `logical_date` — `OUTPUT_FILE_TEMPLATE` was removed from this DAG in step 6.

`src` and `dst` both derive from one upstream dict, and `.expand(src=…, dst=…)` would take the cross
product of two lists rather than pairing them. `expand_kwargs` takes a list of kwarg dicts instead,
and `XComArg.map()` reshapes each element without a visible task.

Deterministic object per month, overwritten on re-run, so a re-run replaces rather than accumulates.

Verify the object rather than trusting a green task, and list the prefix rather than assuming the
path — the old layout had a colour segment:

```bash
gcloud storage ls -r gs://<bucket>/taxi/
```

### 12. External table over the gz

The `{% include %}` template goes. The column list is per-file now — it comes from step 9's header
read — and a static SQL file can't hold it, so the DDL is generated.

`dags/utils/bigquery.py`:

```python
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
        uri=f"gs://{bucket}/{prefix}/{target['year']}/{target['month']}.csv.gz",
    )
```

```python
            ext = BigQueryInsertJobOperator.partial(
                task_id="bq_create_external_table",
                gcp_conn_id=GCP_CONN_ID,
            ).expand_kwargs(
                file_info.map(lambda t: {
                    "configuration": {
                        "query": {
                            "query": build_bqt_ext_sql(
                                t, PROJECT, DATASET, BUCKET, TABLE_NAME, GCS_FILE_PREFIX
                            ),
                            "useLegacySql": False,
                        }
                    }
                })
            )

            upload_task >> ext
```

`params` goes with the template — nothing is Jinja any more, the values are substituted in Python.

`bucket` and `prefix` are passed separately and joined into the absolute `gs://…` form inside the
builder, because `uris` needs it — step 11's `dst` is bucket-relative, since the operator takes
`bucket` on its own. So `/{year}/{month}.csv.gz` appears in both places. One f-string fragment of
duplication, same as the original had.

The `>>` is needed because no data flows between them: the operator returns nothing, so `ext` maps
over `file_info` rather than over the upload. Between two mapped tasks that waits for every upload
before any external table — irrelevant at one month per run, a serialisation point during the
backfill.

Four things in the OPTIONS:

**`compression = 'GZIP'`** — required; BigQuery does not infer it from the extension.

**`skip_leading_rows = 1`** — the header is in the file and the schema is declared separately, so it
has to be discarded.

**The column list, all `STRING`, in the file's own order.** That's what step 9 is for.

**The month in the table name** — `_2019_01_ext` — so mapped instances don't overwrite each other.
`_` not `-`: hyphens are invalid in BigQuery identifiers.

Check it's live:

```bash
bq show --schema --format=prettyjson demo_dataset.<colour>_tripdata_<YYYY_MM>_ext

bq query --use_legacy_sql=false \
'SELECT COUNT(*) FROM demo_dataset.<colour>_tripdata_<YYYY_MM>_ext'

bq query --use_legacy_sql=false --format=prettyjson \
'SELECT * FROM demo_dataset.<colour>_tripdata_<YYYY_MM>_ext LIMIT 1'
```

The count proves BigQuery decompressed and parsed it — 1,369,765 for yellow 2019-01. The single row
is the positional-mapping check: a timestamp under `tpep_pickup_datetime`, not under `VendorID`. A
count alone won't catch misalignment.

### 13. Match columns

Compare the file's header against the target table. Tolerate additive drift, fail on breaking
drift — silent NULL-filling is how a renamed upstream column becomes an all-NULL column nobody
notices.

```python
METADATA = ["filename", "ingestion_timestamp"]
log = logging.getLogger(__name__)
```

```python
        @task
        def match_columns(target):
            hook = BigQueryHook(gcp_conn_id=GCP_CONN_ID)
            contract = [
                f["name"] for f in hook.get_schema(
                    dataset_id=Variable.get("GCP_DATASET"), table_id=TABLE_NAME
                )["fields"]
            ]

            unexpected = [n for n in target["names"] if n not in contract]
            if unexpected:
                raise AirflowException(f"not in {TABLE_NAME}: {unexpected}")

            missing = [c for c in contract if c not in target["names"] + METADATA]
            if missing:
                log.warning("absent from source, will be NULL: %s", missing)

            return target
```

```python
            column_checked = match_columns.expand(target=file_info)
```

**It compares against `target["names"]`, not the external table's schema.** Step 9 already read the
header, and the external table's columns *are* those names — reading them back with `get_schema`
asks BigQuery for something you just put there. One hook call instead of two, and no
`bq_external_table >> column_checked` ordering, because the external table doesn't need to exist.

**Which means it doesn't sit in the upload path.** It depends on step 9 and on the target table,
nothing else, so it runs alongside the upload and the external table and gates only the insert.
Gating the upload as well was considered and dropped: it buys nothing but an unuploaded object,
which the lifecycle rule in step 19 clears anyway.

**`get_schema` returns the schema dict**, so `["fields"]` is required — iterating it directly gives
you the key `"fields"`.

**The contract side stays a list, not a set**, because the insert needs the column order.

`METADATA` must be a list, since `target["names"] + METADATA` concatenates, and its names must match
the target DDL exactly or those columns are reported missing on every run.

No projection is generated. Both sides are all-`STRING` in the same order, so step 14's insert names
the columns and `SELECT *` supplies them — BigQuery fills any target column not named with NULL on
its own. An earlier version of this step built a per-column `CAST` list, which was needed when the
external table was autodetected and arbitrarily typed. It isn't now.

### 14. Insert and prune — done

One task, one BigQuery script. Same generated-SQL shape as step 12.

`dags/utils/bigquery.py` — needs `import os` at the top of the module, for the `basename` call:

```python
INSERT_SQL = """\
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

def build_insert_sql(target, project, dataset, table_base):
    columns = ",\n".join(f"  `{n}`" for n in target["names"])
    return INSERT_SQL.format(
        project=project,
        dataset=dataset,
        table=table_base,
        ext_table=f"{table_base}_{target['year']}_{target['month']}_ext",
        columns=columns,
        filename=os.path.basename(target["path"]),
    )
```

```python
            insert_delete_task = BigQueryInsertJobOperator.partial(
                task_id="bq_insert_and_prune",
                gcp_conn_id=GCP_CONN_ID,
            ).expand_kwargs(
                column_checked.map(lambda t: {
                    "configuration": {
                        "query": {
                            "query": build_insert_sql(t, PROJECT, DATASET, TABLE_NAME),
                            "useLegacySql": False,
                        }
                    }
                })
            )
```

Both statements in one task. Each auto-commits, so the delete sees the insert's rows.

The stamp is generated **inside the script** so a task retry gets a new one and prunes the previous
attempt. A stamp from `logical_date` or `run_id` would be reused on retry, leaving two copies the
prune can't tell apart.

`filename` is the idempotency key now, not just provenance. It appears in both statements and must
be byte-identical, which is why the builder formats it from one value rather than taking it twice.
If they diverge the delete matches nothing and the insert leaves a second copy.

`SELECT *` is positional against the `INSERT INTO (...)` column list. Both come from
`target["names"]` — the step 9 header, in file order — so they agree by construction. Changing the
external table's column order without changing `target["names"]` would misalign them silently.

Only `column_checked` is mapped over, not `file_info` — that's what makes step 13 a gate rather
than a parallel branch that the insert ignores.

Deferred: a `<target>_loaded` asset as an outlet, month in the extra, for the cleanup DAG.

### 15. Task ordering

**A. A task has to be declared before it's called, and called before anything uses it.**
`file_info = get_file_info.expand(src=file_downloaded())` goes below the `def` for both
`file_downloaded` and `get_file_info`, and above every operator or edge that reads `file_info`. The
DAG body is an ordinary function run top to bottom at parse time, so either one out of order is an
`UnboundLocalError`.

**B. What gets piped is the return variable, not the task.** `file_info` is the handle on
`get_file_info`'s output; it's what `>>` and `.map()` take. Referencing it is already an edge, so
the `>>` lines are only needed where nothing is passed between two tasks.

Naming the handle is only necessary when it is used more than once. A call used once can sit inline
on the right of a `>>`. Only A above is a hard constraint.

**C. Two paths, not one chain.** Everything could be strung into a single line ending at the
insert, and it would run — but every `>>` is a real wait, so a single chain makes
`bq_target_table` wait on the external table and stops the column check running alongside the
upload. Neither dependency exists. Split into two paths, the branches run concurrently and both
name `insert_delete_task`, which waits on both.

```python
            file_info >> upload_task >> bq_external_table >> insert_delete_task
            bq_target_table >> column_checked >> insert_delete_task
```

### 16. Test the consumer

One month twice. Count doesn't move.

```sql
SELECT filename, COUNT(*) AS n, COUNT(DISTINCT ingestion_timestamp) AS stamps
FROM `<project>.<dataset>.<colour>_tripdata`
GROUP BY filename ORDER BY filename
```

`stamps > 1` for a filename means a prune didn't run — two copies present.

---

### 17. Publish the completion asset

Deferred until now because it has no consumer before step 18, and because the ordering in step 15
has to be working first — an outlet on a task whose place in the graph is still moving publishes at
the wrong moment.

A second asset, declared alongside the download one:

```python
# dags/utils/assets.py
BQ_LOADED = {
    colour: Asset(name=f"{colour}_loaded_bq", uri=f"taxi://{colour}_loaded_bq")
    for colour in COLOURS
}
```

A task downstream of the insert carries it as an outlet, with the path in the extra so cleanup knows
which file is now safe to delete:

```python
            asset = BQ_LOADED[colour]

            @task(outlets=[asset])
            def file_loaded(target, *, outlet_events):
                outlet_events[asset].extra = {"path": target["path"]}
```

```python
            mark_load = file_loaded.expand(target=column_checked)

            insert_delete_task >> mark_load
```

The `>>` is needed because the insert operator returns nothing for `file_loaded` to consume. The
separate `mark_load` name is not — it is used once, so
`insert_delete_task >> file_loaded.expand(target=column_checked)` works the same. Naming it is worth
it when a handle is referenced more than once, as `file_info` is in steps 11 and 12.

A separate task rather than an outlet on the insert itself, because `BigQueryInsertJobOperator` is not
a Python task and only a Python task can set an `extra`. Same constraint as step 4.

Mapped, so one asset event per file rather than one per run — cleanup needs a path per month, and a
single event covering several would tell it nothing about which.

Test: load one month, then **Assets** → `<colour>_loaded_bq` → latest event shows the path in its
extra.

# Cleanup

Built now, running on `bq_loaded` alone, written as though a second consumer were coming — the same
approach the load itself took. Adding `duck_loaded` to the schedule later is a config change, and the
task doesn't move.

The cost of running it with one consumer: if DuckDB is added, the 48 historical gz files are gone and
its first load re-downloads them. That is one producer backfill, which is cheap and already a thing
you do. Parity checking isn't affected — that compares row counts in the two tables, not files.

### 18. Cleanup DAG

Deletes the local `.csv.gz` from the mount. Not the external tables — see decision 5 in
`DESIGN_DECISIONS_DBT.md`.

One DAG per colour from a factory, like the others, so yellow's cleanup never waits on green.

The schedule derives itself, in `dags/utils/assets.py` beside the assets it lists:

```python
# dags/utils/assets.py
BQ_LOADED = {
    colour: Asset(name=f"{colour}_loaded_bq", uri=f"taxi://{colour}_loaded_bq")
    for colour in COLOURS
}

LOADED = (BQ_LOADED,)      # add DUCK_LOADED here when it exists

def loaded_assets(colour):
    """Every consumer's completion asset for one colour."""
    return [consumer[colour] for consumer in LOADED]
```

```python
    @dag(
        dag_id=f"dbt_taxi_cleanup_{colour}_dag",
        schedule=loaded_assets(colour),
        start_date=pendulum.datetime(2019, 1, 1, tz="UTC"),
        catchup=False,
    )
```

A list of assets means all of them must have updated since the last run, so adding `DUCK_LOADED` to
`LOADED` turns "after BigQuery" into "after both" with nothing else changing.

Two tasks: one resolves which files are safe, one deletes them.

```python
        @task
        def files_loaded(*, triggering_asset_events):
            per_asset = []
            for asset, events in triggering_asset_events.items():
                paths = {p for e in events if e.extra for p in e.extra.get("paths", ())}
                logging.info(
                    "%s: %d event(s), %d path(s)", asset.name, len(events), len(paths)
                )
                if events and not paths:
                    raise AirflowException(
                        f"{asset.name}: {len(events)} event(s), none carrying paths"
                    )
                per_asset.append(paths)

            if len(per_asset) != len(LOADED):
                raise AirflowException(
                    f"expected {len(LOADED)} consumers, got {len(per_asset)}"
                )

            return sorted(set.intersection(*per_asset))
```

```python
        @task
        def remove_files(candidates):
            if not candidates:
                logging.info("no month loaded by every consumer yet")

            removed = []
            for path in candidates:
                try:
                    os.remove(path)
                    removed.append(path)
                except FileNotFoundError:
                    logging.info("already gone %s", path)
            return removed
```

```python
        remove_files(files_loaded())
```

**The intersection is the point.** Each asset contributes the set of paths its consumer has loaded;
only months every consumer has are deleted. Deleting on the union would pull a file a slower consumer
hasn't read yet. With one consumer the intersection is that consumer's set, so the logic is already
final — it just has nothing to intersect against.

**Both raises exist because a quiet no-op is indistinguishable from working.** Events arriving with no
paths means the publishing side is broken; an asset in the schedule contributing nothing at all means
a consumer didn't run. Either way the run must fail rather than return an empty list, which is what
the counts and the two XComs are for: `files_loaded` shows what it decided, `remove_files` shows what
it did.

**`already gone` is logged, not passed over.** An empty return then distinguishes "nothing was
eligible" from "the files had already been removed", which is the difference between a working
pipeline and a broken one.

**The failure mode when a consumer is added is silent and destructive, not safe.** Add a consumer and
forget to add its asset, and cleanup keeps firing on the assets it does know — deleting the gz before
the new consumer has read it. `loaded_assets` is the first guard, since adding the asset and adding it
to the schedule become one edit in one file; the `len(LOADED)` check is the second.

**It only sees months loaded after it exists.** Cleanup is scheduled on asset events, so a file
already on the mount from a backfill run before this step existed is invisible to it and stays there.
Step 20 comes after this one precisely so the backfill drives cleanup as it goes — but if the
backfill was run earlier, delete those files once, after confirming every month is in the target
table:

```bash
bq query --use_legacy_sql=false '
SELECT filename, COUNT(*) AS n FROM `demo_dataset.<colour>_tripdata`
GROUP BY filename ORDER BY filename'

rm -f ./taxi_download/*.csv.gz
```

Test: trigger the download DAG for a month not on the mount. The file appears, the load runs, and
`remove_files` returns that one path with the mount empty afterwards.

### 19. GCS lifecycle rule

Expire the GCS prefix by age, in Terraform alongside the bucket. Once the insert has run the native
table holds the data and the GCS object only matters for re-loads. Declarative retention, not a
DAG's job.

Independent of the pause above — DuckDB reads the local gz, not GCS, so expiring the GCS copy costs
nothing but a re-upload on a re-load.

---

# Backfill

### 20. Load 2019–2020

Backfill the **producer**; consumers fire as events land. Verify early that backfill runs do emit
asset events — if they don't, the whole load needs a different trigger.

24 months × 2 colours. DuckDB holds 109,047,518 yellow and 7,778,101 green rows for that range —
the parity target. Check with the `filename` query above: 24 rows per colour.

Raise `max_active_runs` on the producer if you want it faster; the constraint is worker disk and
bandwidth, not BigQuery. The insert doesn't conflict with other DML, only the delete does, and on a
first load the prune deletes nothing.

---

## Alternative route — parquet

Convert the `.csv.gz` to parquet in the worker and upload that instead of the gz. Only steps 9, 11
and 12 differ; everything else is identical.

**Take it if** the gz probe fails — `compression = "GZIP"` rejected in the external table DDL — or
if the external table ever stops being a one-shot read path and becomes something queried
repeatedly. Parquet's advantages are all read-side: splittable so BigQuery can parallelise, and
column pruning so a query touching 3 of 20 columns scans 3. Neither lands when the table is read
once, selecting everything, then dropped.

**9. Convert to parquet** instead of reading the header. All columns forced to string, streaming so
memory is bounded by the batch rather than the file. Returns the local parquet path.

**11. Upload the parquet** instead of the gz, and delete the local copy after — it has one consumer,
in the same run, so no coordination is needed.

**12. External table with no schema.** Parquet is self-describing, so there's no column list, no
`skip_leading_rows`, no `compression`, and no names to carry from a header task into the DDL. This
is what the conversion buys: the names never leave the process that read them.

Indicative numbers, from a 763 MB / 9M-row CSV under a 1 GB container limit — close to a yellow
month in shape:

| Tool | Time | Memory |
|---|---|---|
| Polars | 19.3 s | ~235 MiB |
| Pandas (chunked) | 29.6 s | ~293–855 MiB |
| DuckDB | 42.5 s | ~124–287 MiB |

Tens of seconds, not minutes. Chunked pandas has the worst memory profile of the three, which
matters under a parallel backfill; DuckDB the best. Unchunked pandas is not an option — `dtype=str`
on 7.7M rows × 18 columns is gigabytes of Python string objects, and it dies on yellow while passing
on green.

The pandas version, since it needs no new dependency:

```python
            @task
            def convert(src):
                dest = src.removesuffix(".csv.gz") + ".parquet"
                schema, writer = None, None
                try:
                    for chunk in pd.read_csv(src, dtype=str, chunksize=500_000):
                        if writer is None:
                            schema = pa.schema([(c, pa.string()) for c in chunk.columns])
                            writer = pq.ParquetWriter(dest, schema, compression="snappy")
                        writer.write_table(
                            pa.Table.from_pandas(chunk, schema=schema, preserve_index=False)
                        )
                finally:
                    if writer is not None:
                        writer.close()
                return dest
```

The explicit `schema` is load-bearing: with `dtype=str`, a column that's entirely empty in one chunk
arrives as all-NaN object dtype and Arrow infers `null` rather than `string`, mismatching the writer
mid-file. `congestion_surcharge` is null for stretches of 2019. The `try/finally` matters because an
unclosed `ParquetWriter` leaves a footerless file that reads as valid until something opens it.

## Docs to update

- `AIRFLOW_DAG_MIGRATION.md` S2, S3, G6 — describe the merge as the transformation step
- `ETL_VS_ELT.md` — same problem in its third answer
- `DESIGN_DECISIONS.md` — **done.** Split into `DESIGN_DECISIONS_SETUP.md`,
  `DESIGN_DECISIONS_ORCHESTRATION.md` and `DESIGN_DECISIONS_DBT.md`. The idempotency grain change,
  the all-text landing layer and the producer/consumer split with its observability trade are all
  recorded in the dbt file, the first two as numbered decisions under its driver section.

## References

- [Assets](https://airflow.apache.org/docs/apache-airflow/stable/authoring-and-scheduling/assets.html)
- [Asset scheduling](https://airflow.apache.org/docs/apache-airflow/stable/authoring-and-scheduling/asset-scheduling.html)
- [Create Cloud Storage external tables](https://docs.cloud.google.com/bigquery/docs/external-data-cloud-storage)
- [Using data manipulation language](https://docs.cloud.google.com/bigquery/docs/data-manipulation-language)
- [Multi-statement transactions](https://docs.cloud.google.com/bigquery/docs/transactions)
- [DuckDB CSV auto detection](https://duckdb.org/docs/current/data/csv/auto_detection.html)
- [persist_docs](https://docs.getdbt.com/reference/resource-configs/persist_docs)
