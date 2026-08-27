# The Data Pipeline Pattern
## Explained through `04_postgres_taxi.yaml`

This document explains the pattern behind the NYC taxi ingestion pipeline — why each step exists, with the relevant code alongside it.

> **Note on ordering:** This document is organised conceptually, working through the ideas in the order that makes them easiest to understand. The YAML file is organised sequentially, in execution order. They will not line up line-for-line. Code shown here is trimmed to the part that makes the point — the full task definitions live in the YAML.

---

## Why This Pattern Exists

The core problem this pipeline solves is: **how do you repeatedly load data safely without creating duplicates or corrupting your data?**

---

## Why Parameterise the Inputs?

A pipeline is not a one-off script. The same logic needs to run against January 2019, then February, then a different taxi type — without editing the code each time.

Inputs turn the pipeline into a template. The values get chosen at run time, either by a person in the UI or by a schedule:

```yaml
inputs:
  - id: taxi
    type: SELECT
    values: [yellow, green]
    defaults: yellow

  - id: year
    type: SELECT
    values: ["2019", "2020"]
    defaults: "2019"

  - id: month
    type: SELECT
    values: ["01", "02", ... "12"]
    defaults: "01"
```

Those inputs then compose the filename and table names, so one definition covers every combination:

```yaml
variables:
  file: "{{inputs.taxi}}_tripdata_{{inputs.year}}-{{inputs.month}}.csv"
  table: "public.{{inputs.taxi}}_tripdata"
```

This is what makes the pipeline schedulable. A monthly trigger can supply the year and month automatically and the same code runs unchanged.

---

## Why Extract First?

The data lives elsewhere — in this case compressed on GitHub. Before anything can be loaded it has to be pulled down and decompressed locally:

```bash
wget -qO- .../{{render(vars.file)}}.gz | gunzip > {{render(vars.file)}}
```

Download and decompress happen in one piped step, so the compressed file is never written to disk. The pipeline shape is **fetch → load → merge**, and this is the fetch.

---

## Why a Staging Table?

You never load raw data directly into your production table. Instead you load into a staging table first because:

- If something goes wrong mid-load your production data is untouched
- You can transform and validate data before it hits production
- You can truncate and reload staging as many times as needed without risk

Think of staging as a **loading dock** — goods arrive there first before going into the warehouse.

The staging table mirrors the final table's structure, plus the two columns the pipeline adds itself:

```sql
CREATE TABLE IF NOT EXISTS public.yellow_tripdata_staging (
    unique_row_id          text,
    filename               text,
    VendorID               text,
    tpep_pickup_datetime   timestamp,
    ...
);
```

`IF NOT EXISTS` means this is safe to run on every execution — it creates the table the first time and does nothing thereafter.

---

## Why Truncate Staging Each Run?

Because you want a clean slate every time. If you loaded January data last run and now you're loading February, you don't want January data still sitting in staging causing confusion or duplicate merge attempts.

```sql
TRUNCATE TABLE public.yellow_tripdata_staging;
```

---

## Why Bulk Copy Instead of Inserts?

The staging load uses Postgres's native `COPY` rather than row-by-row inserts. For a file of several million rows the difference is minutes versus hours:

```yaml
type: io.kestra.plugin.jdbc.postgresql.CopyIn
format: CSV
header: true
columns: [VendorID, tpep_pickup_datetime, tpep_dropoff_datetime, ...]
```

The explicit column list matters — it maps CSV columns to table columns by position, so the two added columns (`unique_row_id`, `filename`) are simply left out and stay null until the next step fills them.

---

## Why Generate a Unique ID?

The source CSV data has no guaranteed unique identifier per row. Without one you can't tell if a row already exists in your database.

By hashing key fields together you create a fingerprint for each trip:

```sql
UPDATE public.yellow_tripdata_staging
SET
  unique_row_id = md5(
    COALESCE(CAST(VendorID AS text), '') ||
    COALESCE(CAST(tpep_pickup_datetime AS text), '') ||
    COALESCE(CAST(tpep_dropoff_datetime AS text), '') ||
    COALESCE(PULocationID, '') ||
    COALESCE(DOLocationID, '') ||
    COALESCE(CAST(fare_amount AS text), '') ||
    COALESCE(CAST(trip_distance AS text), '')
  ),
  filename = 'yellow_tripdata_2019-01.csv';
```

The same trip hashed twice produces the same fingerprint, which is what the next step relies on. `COALESCE` is doing quiet but essential work here — in SQL, concatenating anything with `NULL` produces `NULL`, so without it any row with a missing field would get a null fingerprint and break the deduplication.

The `filename` column is stamped at the same time, recording which source file each row came from.

---

## Why Merge Instead of Insert?

A plain `INSERT` would add every row every time you run — run it twice and you have duplicate data.

`MERGE` checks first:

```sql
MERGE INTO public.yellow_tripdata AS T
USING public.yellow_tripdata_staging AS S
ON T.unique_row_id = S.unique_row_id
WHEN NOT MATCHED THEN
  INSERT (unique_row_id, filename, VendorID, ...)
  VALUES (S.unique_row_id, S.filename, S.VendorID, ...);
```

**If this row already exists, skip it. If it's new, insert it.** This makes the pipeline **idempotent** — running it 10 times produces the same result as running it once.

Idempotency is what makes a pipeline safe to retry. A failure halfway through is no longer a problem: rerun it, and the rows that made it through the first time are recognised and skipped.

---

## Why Separate Yellow and Green?

The two datasets have different schemas. Most obviously, the pickup and dropoff columns are named differently:

| Yellow | Green |
|--------|-------|
| `tpep_pickup_datetime` | `lpep_pickup_datetime` |
| `tpep_dropoff_datetime` | `lpep_dropoff_datetime` |

Green also carries columns yellow doesn't have at all (`ehail_fee`, `trip_type`), and orders its columns differently.

That means the `CREATE TABLE`, `COPY`, `md5(...)` and `MERGE` statements all have to differ. There is no single SQL statement that covers both.

**This is handled in the structure of the YAML, not in the SQL.** The workflow branches before reaching any SQL, using a conditional task:

```yaml
- id: if_yellow_taxi
  type: io.kestra.plugin.core.flow.If
  condition: "{{inputs.taxi == 'yellow'}}"
  then:
    - id: yellow_create_table
      ...
    - id: yellow_merge_data
      ...

- id: if_green_taxi
  type: io.kestra.plugin.core.flow.If
  condition: "{{inputs.taxi == 'green'}}"
  then:
    - id: green_create_table
      ...
```

Each branch contains the same five-step sequence — create, stage, truncate, copy, hash, merge — written against its own schema. Only one branch runs on any given execution, decided by the `taxi` input.

This is a general point worth holding onto: **schema differences get resolved by the orchestrator, before the SQL layer.** The alternative — one set of SQL statements riddled with conditionals — would be far harder to read and change.

---

## The Full Flow in Plain English

```
1. User picks taxi type, year, month
2. Download that month's CSV from GitHub
3. Branch on taxi type
4. Load raw data into staging (fast bulk load)
5. Generate a unique fingerprint for each row
6. Merge into final table — only new rows get added
7. Clean up temporary files
```

This is the standard pattern used in production data pipelines — safe, repeatable, and efficient.

---

## What Transformations Are Actually Done?

Looking at the pipeline honestly — **very few**. This is mostly an **EL** pipeline (Extract, Load) rather than a full **ELT**.

The only two things that could be called transformations are:

**1. Adding `unique_row_id`**

```sql
unique_row_id = md5(COALESCE(CAST(VendorID AS text), '') || ...)
```

A derived column — doesn't exist in the source data, created from existing fields. Technically a transformation but it's more of a housekeeping step for deduplication than a business transformation.

**2. Adding `filename`**

```sql
filename = '{{render(vars.file)}}'
```

Stamps which file the row came from. Again more of a metadata/audit column than a true transformation.

**What's notably absent:**

- No data type casting or cleaning
- No filtering of bad rows (e.g. zero passengers, zero distance)
- No renaming of columns
- No business logic (e.g. calculating trip duration)
- No joining to other tables (e.g. zone lookups)

The course intentionally keeps this simple for Module 2 — the actual transformations come later in **Module 4 with dbt**, which is specifically designed for the transform step. This pipeline's job is just to get the raw data reliably into Postgres.
