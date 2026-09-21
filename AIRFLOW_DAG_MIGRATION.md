# Airflow DAG: Bringing 04_postgres_taxi's Steps Across from Kestra

Kestra's `04_postgres_taxi` flow has no equivalent counterpart on the Airflow side — this DAG (`04_postgres_taxi.py`) currently only covers extract + load into a single table. This file tracks bringing the remaining steps across, one at a time, tested as they're added. There's no other source for this work, so this is the record of what was done and why.

Each step below will be filled in with what was built, the sub-steps taken, and how it was tested, as the work happens.

---

## S0 — Migrate `ingest_task` to `PostgresHook`

**Purpose:** Replace the loose `os.getenv` credential reads with a proper Airflow Connection, before any new SQL steps are added on top. Gives every later step one consistent way to connect.

**Steps:**

- Confirmed `apache-airflow-providers-postgres` present (7.0.1):
  ```bash
  docker compose exec airflow-scheduler python -c "import airflow.providers.postgres; print('ok')"
  ```
- Added `AIRFLOW_CONN_PG_NY_TAXI` to `.env`
- Recreated the containers and confirmed Airflow had parsed it, before any code depended on it:
  ```bash
  docker compose up -d
  # check the returned values match .env
  docker compose exec airflow-scheduler airflow connections get pg_ny_taxi
  ```
- Declared `PG_CONN_ID = "pg_ny_taxi"` as a constant in the DAG, passed through `op_kwargs`
- Replaced `get_engine()` with a function taking `pg_conn_id` and returning `PostgresHook(postgres_conn_id=...).get_sqlalchemy_engine()`
- Removed the five credential params from `op_kwargs` and from `ingest_callable`'s signature

**Worth knowing:**

- `docker compose` commands must be run from the compose project directory, or they fail with `no configuration file provided: not found`.
- `pip list` doesn't work in these containers — the container user is `default` and pip resolves to `/root/bin/pip`, permission denied. Use `python -c "import ..."` to check a package instead.
- The conn_id is derived from the env var name — `AIRFLOW_CONN_PG_NY_TAXI` → `pg_ny_taxi`. It isn't defined anywhere else; it's just a string typed where needed.
- `AIRFLOW_CONN_*` is resolved by Airflow's own Connection machinery, not `os.getenv`. It does not need declaring in the compose `environment:` block.
- `.env` changes only reach containers on recreate. The first `docker compose up -d` didn't take; a second run made the connection visible.
- `airflow connections get` shows the parsed values, including the password, which is how a placeholder left in `.env` was eventually caught — it appeared percent-encoded in the `get_uri` column. That bug survived this step's test, because the load was still reading the old `PG_*` variables directly; it only surfaced once the hook was actually in use.

**Test:** triggered for a month already verified via the health check. Ran identically to before.

---

## S1 — Staging table

**Purpose:** Split "load" from "final" the way Kestra does, so later steps have a staging table to hash and merge from, rather than overwriting the real table directly.

**Steps:**

- Dropped the date from the table name — the name is now `tripdata_<colour>_staging`, built from a `TAXI_COLOUR` constant
- Renamed the tasks to `extract` and `load`
- Replaced hardcoded `yellow` with `TAXI_COLOUR` throughout
- New `dag_id` and a renamed helper module, to keep this pipeline separate from the old one

**Worth knowing:**

- A module name can't start with a digit, so a helper file named `04_something.py` can't be imported. Fine for a DAG file, since Airflow loads those by path.
- `dag_id` must be unique. Reusing the old one meant only one entry appeared in the UI, with no way to tell which file it came from.
- `op_args` (positional) exists alongside `op_kwargs` (keyword) but isn't worth using — reordering a function's parameters silently changes which value goes where, whereas a keyword mismatch throws immediately.

**Test:** ran two different months back to back. Staging row counts were 1,369,765 then 1,371,708 — two comparable figures rather than the second being the sum, confirming replacement rather than accumulation.

---

## S2 — Set up the SQL operator

**Purpose:** Get `SQLExecuteQueryOperator` working end to end, using `create_final_table` as the thing that proves it. Everything in S3 goes into the same task, so this is the step that establishes the pattern rather than a step about the table itself.

**Steps:**

- Created `dags/sql/` and wrote `transform.sql`, initially containing only the `CREATE TABLE IF NOT EXISTS` for the final table
- Added a `SQLExecuteQueryOperator` task with `conn_id=PG_CONN_ID`, `sql="sql/transform.sql"`, `split_statements=True`, `autocommit=False`
- Passed table names through `params`, referenced in the file as `{{ params.final_table }}`

**Worth knowing:**

- Template paths are relative to the `dags/` folder. `template_searchpath` is only needed when the SQL lives outside it, which is Astro's layout, not this one.
- Staging and final are allowed to have different column types. Staging mirrors the source file; final is the contract. The cast happens in the merge, and that divergence is part of the transformation rather than a mistake to reconcile.

**Test:** ran it, checked the Rendered Templates tab to confirm `{{ params.final_table }}` had substituted rather than rendering empty, then confirmed the table and its columns in pgAdmin. Ran a second time to confirm `IF NOT EXISTS` no-ops.

---

## S3 — Add hash and merge

**Purpose:** Append the `UPDATE` that sets `unique_row_id` and `filename` on staging, then the `MERGE` that inserts unmatched rows into the final table. Same file and same task as S2 — the transformation step, per `ETL_VS_ELT.md`, and the thing that makes reruns idempotent.

**Steps:**

- `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` for `unique_row_id` (uuid) and `filename` (text) on staging — pandas builds staging from the DataFrame, so neither column exists
- Added the `UPDATE` setting `unique_row_id = md5(...)::uuid` and `filename` — ran and checked the values in the database before going further
- Added the `MERGE ... WHEN NOT MATCHED THEN INSERT`, then tested
- Renamed the columns to snake_case — its own piece of work, since it spans both the `CREATE TABLE` and the `MERGE`
- Final table declared with `unique_row_id uuid PRIMARY KEY`

**Worth knowing:**

- Four CSV headers are mixed-case (`VendorID`, `RatecodeID`, `PULocationID`, `DOLocationID`). Pandas created those columns quoted, so they only match when quoted: `S."VendorID"`.
- md5 returns 128 bits, too wide for bigint but exactly a uuid. `md5(...)::uuid` is 16 bytes instead of 33, fixed width, and compares as an integer rather than a string.
- Jinja renders once. A template string passed through `params` arrives unrendered, and its inner quotes then terminate the surrounding SQL string. Build the value in the `.sql` file instead, where `logical_date` is available directly: `'{{ params.taxi_colour }}_tripdata_{{ logical_date.strftime("%Y-%m") }}.csv.gz'`. Note double quotes inside.
- `autocommit=False` runs all the statements as one transaction, so a failing merge rolls back the `ALTER` and `UPDATE` too and staging can't be inspected afterwards. Set it to `True` while testing, so each statement commits on its own and the intermediate state survives a failure. Set it back when done.

**Note:** February 2021's file contains rows with duplicate fingerprints and will fail on the primary key. Use January and March when testing two months.

**Test:** January 2021 merged 1,369,765 rows. Rerunning the same month reported 0 rows affected — idempotency confirmed. February failed on the duplicate. March merged cleanly, and the final table then held two filenames with neither month's rows disturbed.

---

## S4 — Yellow/green split

**Purpose:** The pipeline was yellow-only — dtypes, the final table DDL, the hash and the merge all assumed yellow's schema. Green differs: `lpep_` rather than `tpep_` datetime prefixes, plus `ehail_fee` and `trip_type`.

**Steps:**

- Replaced the single dtype dict with `SCHEMAS`, keyed by colour, each holding its own `dtype` and `parse_dates`. The load looks up `SCHEMAS[taxi_colour]`
- Split the SQL into `transform_yellow.sql` and `transform_green.sql`
- Wrapped the whole DAG in a factory function taking `colour`, called once per colour in a loop
- Table names, URL and SQL filename all derive from the factory's `colour` parameter; `TAXI_COLOUR` as a module constant is gone

**Worth knowing:**

- Airflow finds DAGs by scanning the module's top-level namespace. A DAG built inside a function and returned isn't visible unless it's bound to a module-level name — hence `globals()[f"dag_{colour}"] = make_dag(colour)`. The `@dag` decorator doesn't need this.
- Two DAGs now, one per colour, so schedules, backfills and run history are independent. Green failing doesn't touch yellow's history.

**Test:** green January 2021 merged 76,518 rows against yellow's 1,369,765, and the final table has 22 columns to yellow's 20. Rerunning the same month reported 0 rows affected; a second month inserted cleanly on top.

---

## S5 — Cleanup

**Purpose:** Delete the downloaded CSV after a run, matching Kestra's `purge_files`.

**Steps:**

- Added a `BashOperator` running `rm -f` against the downloaded file, chained after transform
- Left `trigger_rule` at its default, with `all_done` present as a commented option

**Worth knowing:**

- Default `trigger_rule` skips cleanup when transform fails, which preserves the file for inspection. `all_done` runs it regardless. Default kept while still debugging — February's file is exactly the one worth looking at.

**Test:** confirmed the file present during the run and absent afterwards, via `docker compose exec airflow-worker find /opt/airflow -name "*.csv.gz"`. Note `docker compose` must be run from the compose project directory.

---

## Postgres pipeline: done

S0–S5 complete. The Airflow pipeline now matches Kestra's `04_postgres_taxi` — extract, load to staging, hash and merge into a final table, cleanup — with two DAGs generated per taxi colour.

---

# GCP pipeline — from Kestra's `08_gcp_taxi`

A different shape rather than the same pipeline pointed elsewhere. GCS holds the raw CSV; BigQuery reads it in place through an external table rather than ingesting it; a `CREATE OR REPLACE TABLE ... AS SELECT` builds the staging table. Pandas disappears entirely — no dtypes, no chunking, no `to_sql` — so the external table's DDL becomes the only schema definition.

Two storage layers doing different jobs: GCS is the landing zone and the external table is a view over a file that stays a file, while the temp and final tables are real BigQuery storage. Data only moves in at the `CREATE OR REPLACE TABLE AS SELECT`.

Two deliberate departures from the Postgres pipeline, both firing revisit triggers already logged in `DESIGN_DECISIONS.md`:

- **TaskFlow.** `@dag` and `@task` rather than `with DAG(...)` and `PythonOperator`. The decision's trigger was "the course material is finished, or a piece of work needs XComs passing between tasks" — the GCS path needs passing between tasks, so it applies.
- **Config-driven factory.** Per-dataset values held in a dict outside the factory rather than derived inside it. That decision's action said to consider it from the start on the next pipeline rather than converting this one.

Also worth noting the hash here is five columns, not seven — it drops `fare_amount` and `trip_distance` — and `unique_row_id` is `BYTES`, since BigQuery's `MD5()` returns bytes directly.

---

## G0 — GCP account and project

**Purpose:** New account, project, GCS bucket, BigQuery dataset, and a service account with a downloaded key. Everything below is blocked on this.

**Steps:**

Grant yourself two org-level roles. Being Owner on the project is not enough, and none of these appear in the project-level role list:

```bash
gcloud organizations list

gcloud organizations add-iam-policy-binding <ORG_ID> \
  --member="user:<your email>" --role="roles/orgpolicy.policyAdmin"
gcloud organizations add-iam-policy-binding <ORG_ID> \
  --member="user:<your email>" --role="roles/resourcemanager.tagAdmin"
gcloud organizations add-iam-policy-binding <ORG_ID> \
  --member="user:<your email>" --role="roles/resourcemanager.tagUser"
```

Create a tag key with two values:

```bash
gcloud resource-manager tags keys create disableServiceAccountKeyCreation \
  --parent=organizations/<ORG_ID>
gcloud resource-manager tags values create enforced \
  --parent=<ORG_ID>/disableServiceAccountKeyCreation
gcloud resource-manager tags values create not_enforced \
  --parent=<ORG_ID>/disableServiceAccountKeyCreation
```

Attach `enforced` to the organization, so everything inherits it, and `not_enforced` to the project holding the service account, which overrides the inherited value:

```bash
gcloud resource-manager tags bindings create \
  --tag-value=<ORG_ID>/disableServiceAccountKeyCreation/enforced \
  --parent=//cloudresourcemanager.googleapis.com/organizations/<ORG_ID>

gcloud resource-manager tags bindings create \
  --tag-value=<ORG_ID>/disableServiceAccountKeyCreation/not_enforced \
  --parent=//cloudresourcemanager.googleapis.com/projects/<PROJECT_ID>
```

Then replace the policy with a conditional one — enforced everywhere except the tagged resource:

```bash
cat > policy.yaml << 'EOF'
name: organizations/<ORG_ID>/policies/iam.disableServiceAccountKeyCreation
spec:
  rules:
  - enforce: false
    condition:
      expression: "resource.matchTag('<ORG_ID>/disableServiceAccountKeyCreation', 'not_enforced')"
  - enforce: true
EOF

gcloud org-policies set-policy policy.yaml
```

Wait a few minutes, then create the key on the service account.

Then create the bucket and dataset by rerunning Terraform against the new project — the sequence is in `HEALTH_CHECK.md` Step 5, Route B. Beyond that route: link billing, enable the BigQuery and Cloud Storage APIs, and grant the new service account Storage Admin and BigQuery Admin in the new project.

**Worth knowing:**

- New organizations also enforce `constraints/storage.uniformBucketLevelAccess`, which the course's bucket resource predates. Fix it in the resource rather than relaxing the policy — `uniform_bucket_level_access = true`. Nothing in the course uses object-level ACLs, so there's no downside, and it's one line rather than more tag bindings.

---

## G1 — Google provider and Airflow connection

**Purpose:** `apache-airflow-providers-google` in `requirements.txt` and an image rebuild, then a Google Cloud connection in Airflow alongside the existing Postgres one.

**Steps:**

Confirm the provider is actually installed. It had been sitting in `requirements.txt` since the start but never exercised, so the image may not have been rebuilt since:

```bash
docker compose exec airflow-scheduler python -c "import airflow.providers.google; print('ok')"
```

If that fails, `docker compose build` then `docker compose up -d`.

Mount a folder for the key, since the compose file only mounts `dags`, `logs`, `plugins` and `config`. In the `x-airflow-common` anchor's `volumes:` block:

```yaml
- ${AIRFLOW_PROJ_DIR:-.}/keys:/keys
```

Create `keys/` next to `dags/`, move the JSON in, and add `keys/` to `.gitignore`.

Enable the connection test button, which ships disabled. In the same anchor's `environment:` block, alongside `AIRFLOW__CORE__LOAD_EXAMPLES`:

```yaml
AIRFLOW__CORE__TEST_CONNECTION: 'Enabled'
```

Then `docker compose up -d`, create the connection in the UI — Admin → Connections, type **Google Cloud**, key path and project ID — and use the **Test** button.

**Worth knowing:**

- `AIRFLOW__CORE__TEST_CONNECTION` takes `Disabled`, `Enabled` or `Hidden`, not a boolean. It ships off because the button executes against real infrastructure from the web UI.
- Without it, a connection can't be tested from a shell — Airflow 3 hooks need a task context, so `GCSHook(...)` in a bare `python -c` fails even for a connection that exists. The alternative is a throwaway one-task DAG and `airflow dags test`.

**Test:** Test button in the UI, once enabled.

---

## G2 — New DAG shape

**Purpose:** Establish the `@dag`/`@task` structure and the config-driven factory before any GCP tasks depend on it, so the shape is proven separately from the new services.

**Steps:**

- Copied the working Postgres DAG to a new file with a new `dag_id`, leaving the original untouched as a reference
- Added a `DATASETS` dict outside the factory, holding only `schedule` for now — it gains bucket, dataset and project ID when the GCP tasks arrive
- Replaced `with DAG(...)` with a nested `@dag`-decorated function
- Replaced the `PythonOperator` with a `@task`-decorated wrapper taking plain arguments instead of `op_kwargs`

**Worth knowing:**

- `return local_workflow()` with the parentheses. Returning the undecorated function registers nothing.
- The `globals()` line is still needed. Calling the decorated function registers the DAG at module level, but not from inside a factory.
- `@task def load(...)` defines a template; `load(...)` in the chain creates the task. Putting the bare name into `>>` gives `AttributeError: '_TaskDecorator' object has no attribute 'update_relative'`.

**Test:** green January 2021 merged 76,518 rows — identical to what the original DAG produced at S4. Same input, same output, different code.

---

## G3 — Extract and upload to GCS

**Purpose:** Download the CSV as before, then upload it to the bucket. The first task whose output another task consumes by value rather than through the filesystem — the GCS path — which is what TaskFlow is actually for.

**Steps:**

- Changed extract to decompress during download rather than uploading a `.gz` — piping through `gunzip` rather than writing the compressed file to disk, matching Kestra. Compressed files can't be split, so external table reads on a `.gz` would be slower and single-threaded.
- Added `upload_to_gcs` as a plain `LocalFilesystemToGCSOperator`, not wrapped in `@task` — it's already an operator, so there's nothing to convert
- Bucket, dataset and project ID set as Airflow Variables via `.env`, using the `AIRFLOW_VAR_*` prefix — `AIRFLOW_VAR_GCP_BUCKET` becomes `{{ var.value.gcp_bucket }}`
- `GCP_CONN_ID` stays a plain module constant, not a Variable — `gcp_conn_id` isn't a templated field on most operators, so `{{ var.value.* }}` would pass through as literal template text rather than resolving, and fail with a connection-not-found error naming that text
- Removed the old Postgres load and transform tasks from this DAG for now, so each test run only exercises what's actually been built

**Worth knowing:**

- Variables live in the metadata database and are lost on `down --volumes`, same as Connections. Setting them via `AIRFLOW_VAR_*` in `.env` instead survives that, at the cost of not being visible or editable from the UI's Variables page — only the CLI sees environment-set Variables.

**Test:** file appeared in the bucket after a run; confirmed via the Rendered Templates tab that `{{ var.value.gcp_bucket }}` resolved to the real bucket name rather than rendering empty.

---

## G4 — External table

**Purpose:** `CREATE OR REPLACE EXTERNAL TABLE` over the uploaded file. No equivalent in the Postgres pipeline — Postgres can't query a file where it sits. This is also where the schema is declared, now that pandas isn't inferring one.

**Steps:**

- Copied Kestra's external table DDL into two `.sql` files, one per colour
- `BigQueryInsertJobOperator` executes the rendered SQL — `useLegacySql: False` set explicitly in the job config

**Worth knowing:**

- `useLegacySql` is left unset by default, which now triggers a deprecation warning — a future release flips the default from legacy SQL to standard SQL. Set it explicitly rather than relying on the current default, especially with BigQuery legacy SQL availability restricted after June 1, 2026.
- `{% include %}` was working — the switch to rendering in Python wasn't forced by an include failure. It was tried as an alternative and kept once it worked.
- Rendering the SQL in Python and passing it as an XCom is the genuine case for TaskFlow's XCom passing that hadn't materialised yet in this pipeline — one task builds the string, the next consumes it.
- `logical_date` comes from the task's own execution context (`**context`) inside the render task, rather than from a `{{ }}` tag Airflow would otherwise resolve.
- Autocomplete suggested `from uri_template import Variable` for an Airflow Variable import — an unrelated package. The correct import is `from airflow.sdk import Variable`.

**Test:** table confirmed to exist in BigQuery via the console, backed by the uploaded CSV.

---

## G5 — Staging table with hash and filename

**Purpose:** `CREATE OR REPLACE TABLE ... AS SELECT` adding `unique_row_id` and `filename`. Same job as the Postgres `UPDATE`, but a rewrite rather than an in-place update, because BigQuery is columnar. Called "staging" rather than "temp" — same role as the Postgres staging table, and unlike `_ext` it's real BigQuery storage rather than a view over a file.

**Steps:**

- Copied Kestra's temp-table DDL into two `.sql` files, one per colour — five-column hash (drops `fare_amount` and `trip_distance`, unlike the Postgres seven-column hash), `unique_row_id` as `BYTES` rather than `uuid` since `MD5()` returns bytes natively in BigQuery, no cast needed
- Named with year and month baked in, matching Kestra's own `vars.table` pattern and G4's external table — one staging table per month, not truncated and reused
- Same render-then-execute shape as G4: `{% include %}` inside `BigQueryInsertJobOperator`'s `configuration`

**Worth knowing:**

- Kestra's `vars.table` already includes year and month, and nothing in its flow ever drops the resulting tables — one `_ext` and one staging table accumulate per month, indefinitely. `_ext` costs nothing since it only references the GCS file; staging does hold real storage and accumulates cost, though BigQuery halves the rate after 90 days untouched.
- `logical_date` needs to be in the SQL file, since it's only resolved at run time.
- `%Y-%m` produces a hyphen, which BigQuery table names can't contain. `%Y_%m` is required, not just conventional.

**Test:** staging table created and populated successfully after the naming and quoting fixes.

---

## G6 — Create final table and merge

**Purpose:** `MERGE ... WHEN NOT MATCHED`, same pattern as Postgres. Needed a `CREATE TABLE IF NOT EXISTS` first — `MERGE` doesn't create its own target. The final table is partitioned by pickup date, which the Postgres version has no equivalent of.

**Steps:**

- `CREATE TABLE IF NOT EXISTS` for the permanent table, snake_case columns matching the Postgres final table's convention, `unique_row_id BYTES` (native `MD5()` return type, no cast needed, unlike Postgres's `::uuid`), `PRIMARY KEY (unique_row_id) NOT ENFORCED`, `PARTITION BY DATE(tpep_pickup_datetime)`
- `MERGE INTO ... WHEN NOT MATCHED THEN INSERT`, same column-rename pattern as the Postgres merge

**Worth knowing:**

- BigQuery doesn't enforce primary keys — `NOT ENFORCED` is required syntax, and it's informational only, used by the query optimizer, never checked against actual data. A duplicate `unique_row_id` inserts without error. Unlike Postgres, nothing here fails on its own.
- Since nothing fails automatically, the fail-loudly behaviour has to be built: an `IF` checking for duplicate fingerprints in staging, raising before the merge runs, in the same file.
- The five-column hash from G5 produced false collisions that seven columns didn't — same source file, different result, purely from which columns feed the hash. January failed under five columns and passed under seven. This is a live demonstration of the trade already logged for the Postgres duplicate-fingerprint decision, not a new bug.

**Test:** January merged 1,369,765 rows — identical to the Postgres pipeline's count for the same month. Rerun reported nothing new to insert. February, previously failing under the five-column hash, needs re-verifying under seven.

---

## G7 — Cleanup

**Purpose:** Remove the local CSV, and decide whether the GCS object stays. Kestra's `purge_files` only clears its own storage — the bucket object persists, which may be the point given it's meant to be a durable raw layer.

**Steps:**

- Same as S5 — `rm -f` against the local file, default `trigger_rule`, `all_done` left as a commented option.

**Worth knowing:**

- Doesn't touch GCS or the BigQuery staging/external tables. Those accumulating per month is the trade already logged in `DESIGN_DECISIONS.md`, not something this step addresses.
