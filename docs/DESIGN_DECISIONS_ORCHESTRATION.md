# Design Decisions — Orchestration only

The first era of pipelines: the Postgres load and the original GCP upload, orchestrated by Kestra and
Airflow with nothing downstream of the warehouse. The load itself does the deduplication, with a
seven-column row hash and a `MERGE`.

These DAGs still run as they are. The decisions here are deliberate for them, not debt — the later
pipelines diverge on purpose, and those decisions live in `DESIGN_DECISIONS_DBT.md`. Setup and
environment decisions that bind every DAG are in `DESIGN_DECISIONS_SETUP.md`, along with the
authoring rules for all three files.

Each entry follows the same shape: options considered, decision, reasoning, revisit trigger.

---

## Per-month staging tables in BigQuery: kept dated, for now

**Narrowed.** The staging table is gone — the load inserts into the final table straight from the external table. What remains dated and kept is the per-month *external* table, which costs nothing because it only references the GCS file. The revisit trigger below now applies to those.

**Context:** Kestra's BigQuery flow names both the external table and the staging table with year and month baked in, and nothing in the flow ever drops them — one pair accumulates per month, indefinitely. This differs from the Postgres pipeline, where staging is a single table, truncated and reused every run.

**Options considered:**

| Option | Effect |
|---|---|
| Dated, kept | One staging table per month, permanent. Matches Kestra. |
| Truncate and reuse | One staging table, overwritten every run. Matches the Postgres pipeline. |
| Dated, dropped after merge | One per month during the run, deleted once the merge succeeds. |

**Decision:** dated and kept, matching Kestra.

**Reasoning:** This is a genuine trade, not a strict improvement either way. Dated staging buys auditability of a specific run's output — if a past month's merge produced something unexpected, its staging table shows exactly what went in, which a reused table can't. It does not buy idempotency; the hash and the merge already provide that on their own. External tables cost nothing extra since they only reference the GCS file, but staging tables do hold real BigQuery storage and accumulate cost and clutter over time, though BigQuery halves the storage rate after 90 days untouched.

**Revisit:** trigger — the accumulated staging tables become a real cost or clutter problem. Action — see *Cleanup is its own DAG; GCS retention is declarative* in `DESIGN_DECISIONS_DBT.md`, which is where this went. Kestra's own design doesn't settle this either way, so there was no precedent to defer to.

---

## Duplicate fingerprints in a source file: fail, for now

**Still live for Postgres, replaced elsewhere.** BigQuery and DuckDB dropped the merge, so they have no fingerprint to collide — see *1.1 At what grain is the load idempotent?* in `DESIGN_DECISIONS_DBT.md`. Postgres still merges on the seven-column hash, so this is the behaviour there.

**Context:** Some monthly files contain rows that hash to the same `unique_row_id` — February 2021 does, January and March don't. The merge can't catch these: it compares staging against the final table, and both copies pass `WHEN NOT MATCHED` because neither is in final yet. The primary key catches the second insert and the run fails. Kestra's flow has the same flaw.

**Options considered:**

| Option | Effect |
|---|---|
| Quarantine | Extras go to a rejects table with filename and timestamp; the rest merges. Nothing lost, nothing assumed |
| Fail | A duplicate fingerprint means an assumption broke, so stop and make someone look |
| Widen the hash | Hash every column, so identical fingerprints mean identical rows by construction |

**Decision:** fail.

**Reasoning:** It's already the behaviour and costs nothing to keep. During development a pipeline that halts teaches you something each time, where one that quietly routes rows aside has to be remembered about.

Worth knowing what the current seven-column hash gives up: it omits `tip_amount`, `total_amount`, `payment_type` and others, so two genuinely different trips can collide. That means a duplicate fingerprint can't be distinguished from real data loss. Widening the hash is what makes that knowable; quarantining is what makes it recoverable. A one-off query can confirm whether this month's duplicates are identical rows, but an automated pipeline can't assume the next month behaves the same way.

**Revisit:** trigger — this moves beyond development, or the failures become frequent enough to be noise. Action — widen the hash first, so a collision unambiguously means a duplicate row, then decide between quarantine and fail. Which of those is right is a business rule, not a technical one.

---

## DAG authoring style: `with DAG(...)`, not the `@dag` decorator

**Options considered:** the context-manager form, `with DAG(...) as dag:`, with `PythonOperator` and `op_kwargs`; or the TaskFlow form, `@dag` and `@task`, where plain functions become tasks and return values pass between them as XComs.

**Decision:** context-manager form, for now.

**Reasoning:** The course material uses it throughout, and following along is easier without translating every example. It is not deprecated — `with DAG(...)` is fully supported in Airflow 3 — but it is the older of the two styles, and current documentation and community answers lead with the decorator.

Three things in this pipeline are artefacts of the older style rather than necessities: `PythonOperator` with `op_kwargs` instead of `@task` with plain arguments, the separate helper module holding a callable, and the `globals()` assignment in the DAG factory. The decorator needs none of these — calling the decorated function registers the DAG, so the factory loses its `globals()` line.

**Revisit:** trigger — the course material is finished, or a piece of work needs XComs passing between tasks, where TaskFlow is markedly less awkward. Action — convert one DAG and keep the other in the old style for comparison, rather than converting everything at once.

---

## Running the pipeline task: PythonOperator, for now

**Options considered:**

| Option | Isolation | Cost |
|---|---|---|
| `PythonOperator` | None — shares the Airflow worker's own Python environment | Zero setup |
| `PythonVirtualenvOperator` | Task-level — Airflow builds a throwaway venv per run | Rebuilds the venv on every run; startup penalty |
| `DockerOperator` | Full — runs any image, any language | Needs Airflow to have Docker engine access (`/var/run/docker.sock`, same pattern Kestra uses), and the container needs network access to `pgdatabase` |

**Decision:** `PythonOperator`.

**Reasoning:** This is what the course material actually teaches, and the current goal is working through the videos' core steps before comparing alternatives. `DockerOperator` would stack a second unfamiliar concept — Docker socket access from inside Airflow, container networking for the spawned task — on top of the one already being learned (DAG structure, logical dates, task dependency wiring). Debugging both at once is exactly the kind of tangle that piling GCP onto the Kestra setup created earlier.

Airflow's own best-practices docs describe `PythonOperator` → `PythonVirtualenvOperator` as the normal *development* progression, with Docker/Kubernetes explicitly flagged as "far more involved" — a strategy for when isolation needs matter more than they do for a first working DAG.

**Revisit:** once a working `PythonOperator` version of the ingestion DAG exists and is confirmed correct, `DockerOperator` is worth a deliberate second pass. The case for it is stronger than usual here: `taxi_ingest:v001`/`v002` already exists, tested and working, from the Module 1 Docker/Terraform exercise. Swapping to `DockerOperator` at that point means reusing a proven artifact rather than solving pipeline dependency isolation from scratch. A working PythonOperator version also gives something to diff results against if the Docker version misbehaves.

References for that pass — both predate Airflow 3, so treat as a starting point for the concept rather than copy-ready syntax, the same caution that applied to the 2022 course material generally. The older one in particular predates the `@dag`/`@task` decorator API adopted in this project and should be expected to need translation, not just adaptation:
- [Utilizing DockerOperator in Airflow to run containerized applications in data engineering projects](https://medium.com/apache-airflow/utilizing-dockeroperator-in-airflow-to-run-containerized-applications-in-data-engineer-projects-f596df26ea83) (2024)
- [Setting up Apache Airflow with Docker Compose in 5 minutes](https://towardsdatascience.com/setting-up-apache-airflow-with-docker-compose-in-5-minutes-56a1110f4122/) (2022)

---

## SQL steps: SQLExecuteQueryOperator with .sql files

**Options considered:** reuse the existing `get_engine()`/SQLAlchemy pattern inside a `PythonOperator`; or use `SQLExecuteQueryOperator` from the Common SQL provider.

**Decision:** `SQLExecuteQueryOperator`, with SQL kept in `.sql` files under `dags/sql/`.

**Reasoning:** Astronomer's guidance is to use hooks and operators rather than hand-rolled connections, and to keep lengthy SQL out of the DAG file. The SQLAlchemy route works but is the fallback, not the recommendation. Costs a provider in `requirements.txt` and an image rebuild.

Astronomer's examples set `template_searchpath`, but that's because Astro projects keep SQL in an `include/` folder outside `dags/`. Template paths are relative to `dags/` by default, so with the files at `dags/sql/` no searchpath is needed — `sql="sql/transform.sql"` resolves on its own. The official compose file only mounts `dags`, `logs`, `plugins` and `config`, so an `include/` sibling wouldn't exist inside the containers anyway without adding a mount.

**Revisit:** trigger — SQL becomes complex enough to need real testing, lineage or modularity. Action — move transformations to dbt rather than growing the `.sql` file set, which is what the course does in a later module anyway.

---

## Per-dataset values: derived inside the factory, not passed in

**Options considered:** compute each dataset's values (table names, URL, schedule) inside the factory from its `colour` parameter; or hold them in a config structure outside it and pass them in.

**Decision:** derived inside, for now.

**Reasoning:** With two colours and a consistent naming rule, every value is a formula — `colour` plus a fixed pattern. Pulling those out would duplicate a formula as data and let the two drift. Everything else derived from `colour` already lives inside the factory, so splitting the schedule out would be inconsistent for no gain.

This is a preference at this scale, not a decision that goes either way on merit.

**Revisit:** trigger — the values stop being derivable. If one dataset's table were `green_taxi_trips` while another's was `tripdata_yellow`, with no shared rule, a config structure is the only honest way to express it, because there is nothing to derive. Same if the list grows to a dozen datasets, or the values come from a file someone non-technical edits. Action — move to a dict of dicts keyed by dataset, passed into the factory. Worth considering from the start on the next pipeline rather than converting this one.

**What happened:** the next pipeline took the last sentence. The dbt-era DAGs keep per-colour values in `dags/utils/config.py` as a dict keyed by colour, because the download and load DAGs both need the same list and a formula duplicated across two files is the drift this entry warns about. These DAGs are unchanged.

---

---

## Postgres credentials: `PostgresHook`, not five env vars

**Options considered:** keep reading `PG_USER`/`PG_PASSWORD`/`PG_HOST`/`PG_PORT`/`PG_DATABASE` as plain env vars via `os.getenv`, as `ingest_task` did; or define one Airflow Connection and read it via `PostgresHook`.

**Decision:** one Connection, read through `PostgresHook.get_sqlalchemy_engine()`.

**Reasoning:** applying *Credentials are Connections; configuration is Variables* (see `DESIGN_DECISIONS_SETUP.md`) to the pipeline that prompted it. Five loose env vars become one `AIRFLOW_CONN_{CONN_ID}` URI, so this isn't a new place to manage secrets — it's the correct shape for one that already existed.

The migration costs nothing: `PostgresHook.get_sqlalchemy_engine()` returns the same kind of engine the hand-written `get_engine()` built, so `pandas.to_sql` needs no change.

`TARGET_TABLE` and `CHUNKSIZE` are not credentials and stay as env vars — configuration, not authentication.

**Revisit:** trigger — this DAG is retired, or a secrets backend arrives. Action — in the second case the Connection moves to the backend and the hook call is unchanged.
