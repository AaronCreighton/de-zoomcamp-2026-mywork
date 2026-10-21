# Design Decisions — Airflow + dbt

The second era: the download producer and the per-target load consumers, built so dbt can run one
project against BigQuery and DuckDB. The load does no deduplication — it appends raw text stamped
with a load time and prunes by filename, leaving every transformation to dbt.

These pipelines diverge from the earlier ones on purpose. Those decisions are in
`DESIGN_DECISIONS_ORCHESTRATION.md` and are not debt. Setup and environment decisions that bind
every DAG are in `DESIGN_DECISIONS_SETUP.md`, along with the authoring rules for all three files.

Read it in order. **Premises** holds the two decisions everything else rests on. Each **driver**
section then states what forced a group of decisions, maps them, and answers the ones the group
turns on, numbered in the order they resolve; *What follows from tree A* holds the decisions that
fall out of those answers. **Future** is what isn't decided yet.

Every entry names what it follows from or what it leads to, and its scope where that isn't the whole
section. Most follow the same shape: options considered, decision, reasoning, revisit trigger.

---

## Premises

Two decisions sit above both driver sections. Neither is about the load, and both constrain it.

**P1** settles that there are two targets at all, which is what D1 and B-D1 then have to deal with.
**P2** settles that the load doesn't transform, and decision 2 is a special case of it.

Neither follows from the other, and they arrive by different routes: P2 descends from the principle
*Raw is faithful to the source* in `DESIGN_DECISIONS_SETUP.md`, while P1 comes out of how the course
itself is set up. There is no question above them in this file.

---

### P1 One dbt project, or two?

**Leads to:** D1 — both targets must hold the same rows — and B-D1, which exists because there is
more than one consumer for one download.

**Context:** The course runs dbt Cloud against BigQuery. Running dbt Core locally against DuckDB as well raises whether that's one dbt project with two targets, or two separate projects.

**Options considered:**

| Option | Shape |
|---|---|
| One project, two targets | One set of models, `profiles.yml` targets selecting DuckDB or BigQuery |
| Two projects | Separate model sets, independent of each other |

**Decision:** one project, two targets.

**Reasoning:** It follows what the course expects — its setup instructions assume continuity between the Cloud and local setups and break down if the two are treated as separate, which is what produced the two-branch mess. It also means the models are written once rather than every later module being done twice.

Beyond the course, the mechanism is worth knowing in its own right: switching output databases from one project, several pipelines writing to one warehouse and sharing a connection, or one pipeline writing to two destinations, are all the same `targets` feature.

**Worth being honest about the weakness:** dbt's target mechanism was designed for dev-versus-prod — stages of one deployed system, where one promotes to the other. A local DuckDB setup and a cloud BigQuery setup aren't that. Nothing promotes between them, neither is upstream of the other, and in practice they are two systems that happen to share model SQL. The decision uses a mechanism built for a relationship this setup doesn't have.

**Revisit:** trigger — the model SQL genuinely diverges between the two engines. DuckDB and BigQuery differ in real ways (hash return types, date functions, `MERGE` support, partitioning syntax), and the Postgres-to-BigQuery move already demonstrated this class of problem. Action — handle a handful of divergent models with macros and `{{ target.type }}` conditionals or `adapter.dispatch` first; split into two projects only if most models need engine-specific SQL, at which point they have genuinely become two projects.

---

### P2 Where does transformation happen?

**Leads to:** decision 2. Types are a special case of transformation, so once this is settled, who
resolves them is the next question rather than an open one.

**Context:** a pipeline loading into a warehouse can also reshape on the way in — renaming columns, changing types, collapsing duplicates. With dbt in the stack that reshaping has two possible homes.

**Options considered:**

| Option | Effect |
|---|---|
| Transform in the load | Renames and casts in the load. Every load path must produce identical output |
| Load raw, transform in dbt | Loads deliver source-shaped data; dbt reshapes it |

**Decision:** load raw, transform in dbt. Follows *Raw is faithful to the source*.

**Reasoning:** dbt is the transformation layer and its staging models exist for exactly this reshaping. Transforming at load time puts that logic outside dbt and makes each load path responsible for producing identical output — and with two targets loaded by different code, that is two implementations to keep in step, checked by nothing. Raw loads mean both targets hold the same shape and dbt reshapes them the same way.

Where the line falls:

- **Stays in the load:** `filename`, `ingestion_timestamp`, and the prune that makes a re-run idempotent. Load metadata and reliability — EL's job.
- **Moves to dbt:** column renames, type casts, deduplication to trip grain, business logic.

The earlier pipelines put deduplication in the load, via the row hash and the `MERGE` — see `DESIGN_DECISIONS_ORCHESTRATION.md`. That is the single biggest difference between the two eras, and it is why this entry exists rather than being assumed.

This also reverses the framing in `ETL_VS_ELT.md` and the migration doc's S2–S3, both of which describe the merge as the transformation step.

**Revisit:** trigger — a consumer that can't run dbt needs reshaped data. Action — build it a dbt table to read, rather than reshaping in the load and reopening this.

---

## Driver: dbt must read the same rows from BigQuery and DuckDB

Everything in this section follows from one requirement and one defect.

**D1 — requirement.** dbt runs one project against two targets, so both have to hold the same rows.

They didn't. The Airflow load merged on a row hash and declared column types; the DuckDB script appended and let the CSV sniffer choose. Decision 1 is which side changed.

**D2 — observed defect.** The previous chain converted types two to three times and did not preserve the file's text. Parsed to an inferred type, cast to a declared one, and cast back to `STRING` if raw was meant to hold text — `0.50` came back `0.5`, irreversibly, with nothing able to tell whether the file had said `0.50`, `0.5` or `.50`.

**Stated assumption:** dbt is the only consumer of the landing tables. Decisions 2, 3, 4 and 4.3 all rest on it, and it isn't a choice anyone made — nothing else has ever needed to read them. Revisit if something other than dbt does, which is also decision 2's own revisit trigger.

`csv vs parquet vs gzip` is not one three-way choice. It is two independent questions — who resolves types, and what format crosses the boundary — plus a third that breaks the tie between them. The map below is the order they resolve in, and the entries follow in the same order. It is not the order they were argued in — decision 3 was never settled at the time, which is why it had no entry until the map was drawn.

```
D1  (requirement)      dbt must read the same rows from BigQuery and DuckDB
D2  (observed defect)  the previous chain converted types two to three times
                       and did not preserve the file's text

1.  Which side changes so the targets match?                     [both targets]
      change DuckDB to match Airflow   → needs a hash and a MERGE; DuckDB has none
      leave them different             → dbt staging diverges per target
   ✔  change Airflow to match DuckDB   → drop the merge, append and prune
      parent: D1
      └─ 1.1  appending needs a replacement key, so: at what grain is the load idempotent?

2.  Who resolves types?                                          [both targets]
      the load declares real types     → a value that won't cast fails the load
      the engine infers them           → types differ month to month
   ✔  dbt, downstream                  → raw carries text only
      parents: 1 (DuckDB's contract defers types) and D2 (conversion loses the text)

3.  What is the external table for?                              [BigQuery only]
      a queryable raw layer            → read-side performance matters
   ✔  a one-shot transfer, then dropped → read-side performance is moot

4.  What format crosses into GCS?                                [BigQuery only]
   ⟲  plain CSV, gunzipped on download — INCUMBENT, orchestration era
        stated reason: gz isn't splittable, so external reads are single-threaded
        also matched Kestra
      parquet, all columns string      → answers 2 directly, splittable,
                                         costs a conversion, GCS holds a re-encoding
   ✔  the .csv.gz as downloaded        → answers 2 via a declared schema,
                                         GCS holds the published bytes
      parents: 2 (only arises once types are deferred), 3 (which settles it)

5.  Clean up
      parents: 3 (the external tables are disposable) and 4 (one per month)
      → 5

consequences of 2 + 4
   4.1  CSV maps positionally and the header is discarded:
          where do the column names come from?
   4.2  a declared schema over text columns, and a month may be missing one:
          how does the insert map its columns?
   4.3  the names are read, so they can be compared against the target:
          what happens when the source schema changes?
```

**Decision 2 is not the top of the chain.** Types are a special case of transformation, so it sits under P2 and the principle *Raw is faithful to the source*. The map starts below that entry, not above it.

**Decision 4 reverses a recorded decision.** The orchestration-era pipeline decompressed on download — `AIRFLOW_DAG_MIGRATION.md` states the reason: a gz can't be split, so an external table read over it is slower and single-threaded. That cost was accepted rather than rebutted, and decision 3 is why: the table is read once for a single month's file, selecting everything, then dropped — so single-threaded decompression costs one read of one month.

That holds at this volume and not necessarily beyond it. If a single file grew large enough that one single-threaded read dominated the load, the arithmetic changes and parquet's splittability starts to matter. It is the same revisit as decision 3 flipping, arriving from the other direction: there the table gets read repeatedly, here one read gets expensive on its own.

**What decision 4 actually cost.** Parquet answers 2 for free — self-describing, so no header read, no positional mapping, and nothing to diff. The gz route needs 4.1, 4.2 and 4.3 to reach the same place. One conversion step against three mechanisms, with raw fidelity as the tiebreak.

**Decision 5 is last by build order, not by dependency.** Its parents are 3 and 4, so nothing stops it being settled earlier; it sits last because the cleanup DAG is the final thing built, after both consumers exist. Nothing else in the tree depends on its answer, so the map lists it without expanding its options — those are in the entry.

**Everything that follows from 1 to 5 is in the next section**, *What follows from tree A* — the
consequences the map names, plus five more that fall out of them and are not in the map.

**If decision 3 flips**, 4 flips to parquet and 4.1 through 4.3 stop being necessary. That is the revisit worth watching, and a stronger trigger than any of these entries carried before they were put in order.

---

### 1. Which side changes so the targets match?

**Scope:** both targets.

**Context:** D1 and the state of the two loads are stated above. This decides which of them moved.

**Options considered:**

| Option | Effect |
|---|---|
| Change DuckDB to match Airflow | Add a hash and a merge to the script; DuckDB has no `MERGE` |
| Change Airflow to match DuckDB | Drop the merge; append and prune instead |
| Leave them different | dbt staging models diverge per target |

**Decision:** change the Airflow load. Both targets now append raw text and dedupe by filename.

**Reasoning:** the DuckDB script was better on the one axis that was blocking dbt, and worse on most others. It had no merge to break on duplicate fingerprints and `union_by_name=true` already tolerated a month whose columns moved — so matching it removed a failure mode instead of copying one across. It is not otherwise a model to follow: no schedule, no retries, no provenance, no per-month idempotency, a full 109M-row rebuild to add one month, and a staleness bug (see Future). Only its load contract was adopted.

**How parity is checked:** the same dbt model run against both targets returns the same row count. That is the test, and it is why the contract has to be a contract rather than a resemblance — a difference in types or in which rows survive the load shows up as a count mismatch with no way to tell which target is wrong.

The individual decisions that fell out of this are the entries below.

**Revisit:** trigger — a third target that can't append cheaply. Action — the shared contract is "all columns text, plus `filename` and `ingestion_timestamp`"; a target that can't meet it gets its own dbt source and staging model rather than bending the other two.

---

### 2. Who resolves types?

**Scope:** both targets.

**Context:** the landing tables are the raw layer, and something has to decide their types.

**Options considered:**

| Option | Effect |
|---|---|
| BigQuery autodetect | Types inferred from the first 500 rows. Differ between months |
| Declare real types at the landing layer | A value that won't cast fails the load |
| Declare everything `STRING` | Nothing can fail on a cast; dbt casts downstream |

**Decision:** every source column `STRING`, in both targets.

**Reasoning:** this is the existing *loads stay raw* decision applied to types, and it keeps the load's only job reliability. Both engines guess from a sample, so both drift. BigQuery autodetect infers from the first 500 rows: a column typed `INTEGER` in January and `FLOAT` in February makes two months of the same table disagree. DuckDB's CSV sniffer samples 20,480 rows, and on a `.gz` only from the beginning of the file, so a value that first appears late in the month is never seen. Declaring real types moves a transformation into the load and hands it a way to fail on data it should merely be storing. All-text also preserves what the file actually said: casting `0.50` through `NUMERIC` and back gives `0.5`, so the landing layer stops being a faithful record of the source.

The cost is real: every dbt staging model now carries a `CAST` per column, and the landing tables are larger than typed ones.

**Revisit:** trigger — something other than dbt reads the landing tables and has to cast for itself, or load-time validation becomes worth having. Action — declare types, with two prerequisites: the TLC data dictionary to source them from, and a single schema file both loaders read, so the contract isn't duplicated per target and able to drift. Typed views over the text tables are the cheaper half-step if only one consumer needs them. Note that the column descriptions move to dbt's `sources.yml`, which covers most of the data-dictionary work — dbt lists Sources among the resource types `persist_docs` applies to, though with no example, so confirm that before relying on it.

---

### 3. What is the external table for?

**Scope:** BigQuery only.

**Context:** the external table sits over the GCS object and the insert selects from it. Whether it is something people query, or a wire the data passes through on its way into a native table, was never decided out loud — and it settles decision 4 single-handedly.

**Options considered:**

| Option | Effect |
|---|---|
| A queryable raw layer | Read performance matters: splittability, column pruning, typed reads |
| A one-shot transfer, dropped after the insert | Read performance is one read of one month |

**Decision:** a one-shot transfer. Created per month, selected from once, dropped by the cleanup DAG.

**Reasoning:** nothing queries it. The insert reads every column of every row exactly once, and dbt reads the native table afterwards. Treating it as a layer would mean optimising for reads that never happen — and those reads are the whole of parquet's advantage over gzipped CSV, which is why decision 4 could go the way it did.

Keeping it disposable also keeps the landing layer honest. Data lives in one place, the native table, rather than two that can disagree; the external table's only job is to make the GCS bytes addressable from SQL.

**Revisit:** trigger — anyone querying the external tables directly, or a single file growing large enough that one single-threaded read dominates the load. Action — convert to parquet on upload and declare the external table over that. Decisions 4.1, 4.2 and 4.3 all become unnecessary at that point.

---

### 4. What format crosses into GCS?

**Scope:** BigQuery only.

**Context:** the pipeline downloads `.csv.gz` and the BigQuery load reads it from GCS. Parquet is the conventional format for a cloud warehouse's external tables.

**Options considered:**

| Option | Effect |
|---|---|
| Convert to parquet before upload | Columnar, typed, prunes columns on scan. Adds a conversion step |
| Upload the `.csv.gz` unchanged | BigQuery reads gzip CSV directly with `compression = 'GZIP'` |

**Decision:** upload unchanged.

**Reasoning:** the raw layer holds what the source published, byte for byte — a converted file is already a derived artifact sitting where the original should be. Conversion also reintroduces the question this rework just removed: parquet is typed, so something has to decide those types, and that decision moves back out of dbt. Against that, parquet's advantages are real but don't bite at this size, and gzip CSV cost nothing to adopt because BigQuery already reads it.

Two figures worth keeping straight, because both were initially overstated in parquet's favour. Conversion runs in tens of seconds per month, not minutes, so compute was never the deciding argument. And parquet's size advantage is against *uncompressed* CSV; against gzipped CSV the gap is modest, since both are compressed. What parquet actually buys here is column pruning and typed reads, not bytes stored.

**Revisit:** trigger — external-table scan time or bytes billed becomes material, which happens when the landing layer is queried directly rather than read once by dbt. Action — the parquet route is kept as a documented alternative in `04-dbt-analytics-engineering/setup/airflow_load_rework.md`; convert on upload and keep the gz as the archive.

---

### 5. How is cleanup handled?

**Follows from:** decision 3 (the external tables are disposable) and 4 (there is one per month).

**Context:** each load leaves a per-month external table behind, and a GCS object that only matters if the month is re-loaded. Leaving both to accumulate is what the previous pipeline did, and the clutter is the trade recorded in *Per-month staging tables in BigQuery: kept dated, for now* in `DESIGN_DECISIONS_ORCHESTRATION.md`. These are two separate questions, so they get two answers.

**How GCS objects are removed:**

| Option | Effect |
|---|---|
| A task in the pipeline deletes them | Runs only when the DAG runs |
| A bucket lifecycle rule in Terraform | Applies whether or not a DAG ran |

**Where the BigQuery cleanup lives:**

| Option | Effect |
|---|---|
| A task at the end of each consumer | Runs when the load runs. A cleanup failure fails a load that succeeded |
| A separate cleanup DAG | Independent of the loads. One DAG serves every target |

**Decision:** GCS objects expire by a bucket lifecycle rule in Terraform. BigQuery objects are dropped by a separate cleanup DAG.

**Reasoning:** split by what each thing belongs to. An object's retention is a property of the bucket, so it belongs with the bucket's definition — a DAG task deleting objects is a retention policy that silently stops being enforced the moment the DAG is paused, and nothing reports that. For the BigQuery side, keeping the task out of the consumers means a cleanup failure can't fail a load that already succeeded, and one DAG can serve both targets once DuckDB exists rather than the same task being duplicated per consumer.

**Worth knowing the option this predates:** BigQuery tables can carry an expiration themselves, which would make the external tables declarative too and remove most of the cleanup DAG's reason to exist. That wasn't considered when the DAG was planned.

**Revisit:** trigger — either the expiration option above being confirmed, or cleanup drifting out of step with the loads and removing something a consumer still needs. Action — for the first, set an expiration on the external table at creation and keep the DAG only for whatever can't express one; for the second, schedule the cleanup DAG on the consumers' completion assets instead of on time.

---

## What follows from tree A

Decisions that fall out of answers 1 to 5 rather than deciding anything the tree turns on. Every one
names what it follows from, and its number gives its place in the hierarchy — `1.1.1` follows
`1.1`. Where a decision has two parents it is numbered under the primary one and names the other in
its `Follows from:` line. Not every numbered entry is a node in tree A's map; the map carries only
the ones the tree turns on.

### 1.1 At what grain is the load idempotent?

**Follows from:** decision 1 — appending needs a replacement key, so the grain has to be settled.

**Scope:** both targets.

**Context:** reloading a month must not duplicate rows. The original pipeline hashed seven columns into a `unique_row_id` and merged on it. Some files contain rows that hash identically — yellow 2019-01 has five such pairs.

**Options considered:**

| Option | Effect |
|---|---|
| Merge on a row hash | Per-row idempotency. Needs a key that is genuinely unique, at any hash width |
| Append and prune by `filename` | Insert the file stamped with a load time, then delete that filename's older rows |

**Decision:** append and prune by `filename`.

**Reasoning:** inspecting the colliding pairs settled it — they are the same trip recorded twice with conflicting payment fields, which reads as amended meter records in the source. No hash makes that a clean key: widening it to every column makes the two rows distinct and loads both, which is a decision about the data disguised as a decision about hashing. File grain sidesteps the question. A file is the unit the source publishes and the unit the pipeline retries, so making it the unit of replacement means a rerun is a whole-file replacement and nothing has to be unique within it.

What this gives up: a correction that rewrites part of a month can't be loaded on its own. The whole file has to be reloaded.

**Revisit:** trigger — a source starts publishing partial-file corrections, or dbt needs row-level lineage into the landing tables. Action — add a row key in dbt's staging layer, where a late correction is a transformation problem rather than a load problem.

This replaces *Duplicate fingerprints in a source file: fail, for now* in `DESIGN_DECISIONS_ORCHESTRATION.md`, which still governs the Postgres load.

---

### 1.1.1 Should the insert and prune be atomic?

**Follows from:** decision 1.1.

**Context:** the load inserts a stamped copy of the file, then deletes that filename's older rows. Wrapping both in `BEGIN TRANSACTION` is the obvious way to make the pair atomic.

**Options considered:**

| Option | Effect |
|---|---|
| Both statements in a transaction | Atomic. Blocks all mutating DML on the table, and is cancelled rather than retried on conflict |
| Two auto-committing statements | Conflicts only per partition, retried three times. A failure between them leaves two copies of one file |

**Decision:** no transaction. Two statements in one BigQuery script, each auto-committing.

**Reasoning:** the transaction makes concurrency worse, not better. A BigQuery transaction that deletes rows blocks all mutating DML on the whole table for its duration, and a transaction that hits a conflict is cancelled with no automatic retry. Standalone DML conflicts only per partition and BigQuery retries it up to three times on its own. Since the backfill runs many months against one table, the serialising version is the one that fails.

Atomicity isn't lost, only deferred: the insert lands before the delete, so a failure between them leaves two copies of one file, and the next run's prune removes the older. The load time is generated inside the script so a retry gets a new stamp and prunes its own previous attempt.

**Revisit:** trigger — a consumer reads the landing tables between the two statements and can't tolerate the duplicate. Action — that consumer reads a view filtered to the latest `ingestion_timestamp` per filename, not a transaction.

---

### 2.1 How are the landing tables partitioned and clustered?

**Follows from:** decision 2 (no typed column exists to partition on) and 1.1 (the prune filters on `filename`).

**Options considered:**

| Option | Effect |
|---|---|
| Partition on the trip date | Prunes the way analysts query. Partition key comes from source data |
| Partition on `ingestion_timestamp` | Prunes the way the pipeline writes. Key is generated by the load |
| No partitioning | Every prune scans the table |

Clustering isn't in the table because it wasn't a choice: the prune's only selective predicate is `WHERE filename = …`, and clustering is the one mechanism that works on a `STRING` column.

**Decision:** `PARTITION BY DATE(ingestion_timestamp)`, `CLUSTER BY filename`.

**Reasoning:** partitioning on a source column would mean a landing table whose physical layout depends on a value in the file, so a malformed date becomes a load failure in a layer that is meant to accept anything. `ingestion_timestamp` is generated by the load, so it can't be bad. Clustering on `filename` is what makes the prune cheap, since that's the column it deletes by. Analyst-facing pruning belongs on dbt's models, where the dates have been cast and validated.

**Revisit:** trigger — dbt's incremental models scan the landing tables by trip date. Action — partition the dbt model on the trip date; leave the landing layer alone.

---

### 4.1 Where do the column names come from?

**Follows from:** decisions 2 and 4 — CSV maps positionally and `skip_leading_rows` discards the header, so declared names have to come from somewhere.

**Scope:** BigQuery only.

**Context:** with autodetect off, the column names and order have to come from somewhere. BigQuery maps CSV fields by position and `skip_leading_rows` discards the header rather than reading it, so a declared schema in the wrong order loads silently misaligned data.

**Options considered:**

| Option | Effect |
|---|---|
| Hardcode the column list per colour | Breaks silently when a month reorders or renames |
| Autodetect | Gets the names from the header too, so it answers this question — but it decides the types at the same time, and that is what rules it out |
| Read the header from the file at load time | Names and order always match the file in hand |

**Decision:** read the header, declare the external table from it.

**Reasoning:** it's the only option where the declared order cannot disagree with the file, which is the failure that produces plausible-looking wrong data rather than an error. It also gives the drift check something to compare against for free.

**Revisit:** trigger — a source with no header row. Action — a per-source column list in config, versioned, with the file's field count asserted on load.

---

### 4.1.1 Where does the generated SQL live?

**Follows from:** decision 4.1.

**Context:** narrows *SQL steps: SQLExecuteQueryOperator with .sql files*, which still holds for fixed statements.

**Options considered:**

| Option | Effect |
|---|---|
| `.sql` file with Jinja params | Matches the earlier decision. Can't express a per-file column list |
| SQL built inline in the DAG | No extra file. DAG becomes mostly string formatting |
| SQL built in a helper module | DAG stays about wiring |

**Decision:** `dags/utils/bigquery.py` holds the SQL templates and the functions that fill them.

**Reasoning:** the column list is per-file and arrives as an XCom, so there is nothing a static file or a Jinja param can hold — the SQL has to be built at task runtime from a mapped value. Given that, the choice is only where the builder lives, and keeping it out of the DAG file follows the same reasoning as the original decision to keep lengthy SQL out: the DAG should read as task wiring.

The earlier decision is unchanged where it applies. Fixed statements stay in `.sql` files under `dags/sql/`; only generated ones move.

**Revisit:** trigger — the generated SQL grows past the two statements it holds now. Action — the transformation belongs in dbt, which is the same action the earlier entry gives.

---

### 4.1.2 Which operator runs the BigQuery DDL?

**Follows from:** decision 4 (one external table per month) and 4.1 (its column list is per-file).

**Options considered:**

| Option | Effect |
|---|---|
| `BigQueryCreateTableOperator` | Takes a `table_resource` dict. No replace. Also what the purpose-built `BigQueryCreateExternalTableOperator` was deprecated in favour of, so that one isn't a separate route |
| `BigQueryInsertJobOperator` with generated DDL | Any statement BigQuery accepts |

**Decision:** `BigQueryInsertJobOperator`, running generated DDL.

**Reasoning:** the external table has to be `CREATE OR REPLACE`, because a rerun re-declares it with that file's column list, and `BigQueryCreateTableOperator` cannot replace. Its `if_exists` takes `log`, `ignore`, `fail` or `skip` — and the default, `log`, marks the task **successful** without creating or replacing anything. A silent no-op reported as a pass is worse than an unsupported option. Using one operator for every BigQuery statement also means SQL is executed from one place rather than three.

**Revisit:** trigger — a provider release gives the table operators a replace behaviour. Action — worth switching only for the target table; the external table's per-file column list still needs generated DDL.

---

### 4.2 How does the insert map its columns?

**Follows from:** decisions 2 and 4 — a declared schema over text columns, and a month may be missing one of them.

**Scope:** BigQuery only.

**Context:** the target table holds two columns the source never has — `filename` and `ingestion_timestamp` — and a month may be missing one the target does have. The insert has to say which value goes where.

**Options considered:**

| Option | Effect |
|---|---|
| `INSERT INTO t SELECT *` | Positional, and the counts have to match — so a month missing a column cannot be inserted at all. **Exact behaviour unverified; probe pending** |
| `INSERT INTO t (cols…) SELECT *` | Named. BigQuery NULL-fills any target column not listed |

**Decision:** the insert names every column it supplies, taken from the file's header.

**Reasoning:** this is what stands in for the DuckDB script's `union_by_name=true`, and it is why subtractive drift needs no code change: a column absent from the header is absent from the insert's list, and BigQuery fills it with NULL. The alternative can't do that — the column list is the only way to tell BigQuery that a value is deliberately not being supplied.

It also removes order from the question entirely on the target side. A positional insert into a table whose column order has drifted doesn't fail, it writes plausible wrong data, which is the failure worth spending a column list to avoid.

`SELECT *` is still positional against the *external* table, which looks like it reintroduces the problem. It doesn't, because both the external table's declared columns and the insert's column list are generated from the same header read — they agree by construction, and neither is written by hand.

**Revisit:** trigger — a source *renames* a column rather than adding or dropping one. NULL-filling hides that, since the old name goes missing and the new one arrives. Action — none here; that's the case the drift check fails on, so the two belong together.

---

### 4.3 What happens when the source schema changes?

**Follows from:** decisions 2 and 4 — the names are read from each file, so they can be compared against the target.

**Scope:** BigQuery only.

**Options considered:**

| Option | Effect |
|---|---|
| Ignore drift | A renamed column loads as all-NULL and nobody notices |
| `ALTER TABLE` automatically | Loads keep running; schema changes without review |
| Fail on new, warn on missing | A new column stops the run; a missing one loads as NULL |

**Decision:** fail on a source column the target lacks, log a warning for a target column the source lacks.

**Reasoning:** the two directions aren't symmetric. A missing column is the recoverable case — the insert omits it, the warehouse NULL-fills, and older months stay queryable. *Invented example, not something that happened:* if green stopped emitting `ehail_fee` next month, the load would keep running and that column would simply be NULL from then on. A new column is a change in what the source is telling you, and loading it silently is how a rename becomes an all-NULL column with the real data discarded. Auto-`ALTER` was rejected for the same reason: a scheduled run shouldn't change the warehouse's schema at 9am with nobody watching.

Failing is cheap because drift is rare in this range: both colours are schema-uniform across 2019–2020 — 109,047,518 yellow rows and 7,778,101 green rows, no within-range drift. So the check costs almost nothing against the source, and what it earns its place on is catching our own schema mistakes — the hand-written `CREATE TABLE` for yellow omitted `trip_distance` and `total_amount`, and the check named both before the insert ran.

The check compares the file's header against the target table, so it fails before the insert rather than inside it, and names the column rather than returning a BigQuery error.

**Revisit:** trigger — drift becomes frequent enough that the failures are noise rather than signal. Action — auto-`ALTER` additive changes and alert, keep failing on anything else.

---

### 4.3.1 How much does the drift check need to do?

**Follows from:** decisions 4.3 and 2 — 2 is what shrank it.

**Options considered:**

| Option | Effect |
|---|---|
| Generate a per-column projection and compare names | What the original `columns.py` did. Large enough to need its own module |
| Compare names against the external table's schema | A second hook call, for a schema the pipeline wrote moments earlier |
| Compare names against the target table only | One hook call, and it can run before the upload |

**Decision:** compare `target["names"]` — the header read in 4.1 — against the target table's schema.

**Reasoning:** decision 2 is what made this small. While the external table was autodetected and arbitrarily typed, every column had to be cast back to text on the way in, so `columns.py` held a `build_projection` that generated a `CAST` per column. Declaring the external table all-`STRING` left nothing to cast: `SELECT *` plus a named column list needs no projection, and the generator had nothing to generate. The module wasn't rejected on merit — an upstream decision emptied it, and it was removed.

Comparing against the target rather than the external table drops the second hook call, and means the check can run before the upload instead of after it, so a drifted file fails before anything has been spent on it.

**Where it lives:** inline, as a `@task` in the DAG file. At fifteen lines, moving it buys an import and nothing else. `dags/utils/columns.py` is gone — recoverable from git history if it is ever wanted, though what it contained is obsolete rather than useful.

**Revisit:** trigger — a second DAG needs the same check, which the DuckDB load would, or it grows past roughly twenty lines. Action — move it to `dags/utils/columns.py`, taking `conn_id`, `dataset` and `table` as arguments rather than reading module-level constants, so it isn't bound to one DAG's config.

---

## Driver: downloading is one job with two consumers

This section shares a premise with the one above rather than descending from it. P1 created a second
consumer; D1 then required that both hold the same rows, and B-D1 asks who fetches the file they both
need. Nothing here follows from D1 — two targets could each download their own copy and still hold
identical rows.

Everything here binds every target, so the per-node scope tags used in section A would all read
the same and are left out.

**B-D1 — two goals**, pursued to improve on the previous pipeline rather than forced by anything. Neither is a requirement: the single-DAG version worked, and would have kept working with a second target bolted on. They are stated here because they are what the options below were judged against, and they eliminate different ones.

**(a) The loads are independent of each other.** A BigQuery schema failure shouldn't stop DuckDB from
loading that month.

**(b) The download is defined once, and the targets fan out from it.** One source feeding several
consumers, with the shared part written once, is a standard shape in pipeline tooling — and doing it
in Airflow rather than copying the download per target was part of why the split was worth trying at
all. The URL template, the streaming write, the retry and the overwrite-never-skip rule then change
in one place instead of two that drift with nothing checking they agree. Less bandwidth and one copy
on the mount instead of two follow from this; they are effects, not reasons.

**B-D2 — observed defect.** The course's DuckDB script skips a file already on disk —
`if parquet_filepath.exists(): continue` — so a revised month is never re-downloaded, `CREATE OR
REPLACE` rebuilds from the stale local copy, and the run reports success. Nothing in that script can
detect it.

Unlike the section above, this is a shallow tree rather than a chain. Splitting the DAG opened four
independent questions at once, and one of those opened two more.

```
B-D1  (goals, not        (a) the two loads are independent of each other
       requirements)     (b) the download is defined once, not once per target
                         both sought as improvements on the previous pipeline;
                         (b) is the one-source-many-consumers shape, tried deliberately
B-D2  (observed defect)  the course script skips a file that already exists, so a revised
                         month is never re-downloaded and reports success

      ⟲ reverses the orchestration-era pipeline   ◦ prior state, not reversed

B1  Who downloads?
 ⟲   download and load in one DAG — viable with one target only
     one DAG per target, each downloading    → the same file fetched once per target
     one DAG doing download and all loads    → one target's load failure fails the month
  ✔  a producer publishing an asset, consumers scheduled on it
                                             → one download, loads independent
     parent: B-D1
     → B1

  B2  How does a consumer learn what arrived?
       infer it from its own logical_date     → couples it to the producer's cron, and a
                                                coalesced run can't say which months
       list the download directory            → races the next download
    ✔  the asset event's extra carries the path
       parent: B1
       → B2

    B3  Where do the month and the replacement key come from?
     ⟲   derived from logical_date           → the logical date is when the event fired,
                                                not the month of the data
         a manifest written by the producer   → a second thing to keep in step
      ✔  the filename, which carries the month and is the key; every path
         derived from it is deterministic and overwritten
         parents: B2 (the name travels in the extra) and B-D2
         → B3

    B4  A run can carry several files — how?
         loop inside one task                 → one pass/fail for the whole batch
         one DAG run per file                 → needs the producer to fan out runs
      ✔  dynamic task mapping
         parent: B2 (the event list is what makes a run multi-file)
         → B4

  B5  Where does the file live between the DAGs?
   ⟲   inside the container, no mount — worked only while download and load
       were one DAG in one container
       under AIRFLOW_HOME                     → mixes raw data with Airflow's own files
       stream to GCS, no local file           → consumers can't read the bytes locally
    ✔  a dedicated bind mount
       parent: B1
       → B5

  B6  How is history loaded?
   ◦   no catchup line — Airflow 3 already defaults catchup to False, so this
       is the prior state rather than something overturned
       catchup=True                           → 24 months fire on unpause
    ✔  catchup=False stated explicitly, history loaded by explicit backfill
       parent: B1 (the producer owns the cron, so it is the one you backfill)
       → B6

  B7  One DAG per dataset, or one DAG for all?
    ✔  a DAG per dataset, generated from a factory over one config dict
       parent: B1 (the split left three modules needing the same colour list)
       → *Per-dataset values: derived inside the factory, not passed in* in
         DESIGN_DECISIONS_ORCHESTRATION.md, under "What happened"

what follows from B2
     one task both writes the file and publishes it, so a single success means
       "file landed" and "event fired" rather than two things that can disagree
     asset identity lives in a shared module, and the URI must be unique per
       colour or both consumers fire on both colours
     the first task returns a list — Airflow coalesces asset events during a backfill

what follows from B3
     the download overwrites the same path and never skips          (B-D2)
     the GCS object is derived from year and month, so a re-run replaces
     the prune key is basename(path)                          → used by A's 1.1
     every mapped BigQuery object carries the month           → governs A's 4
```

**B1 is the root and the rest fans out from it.** Splitting download from load created the handover
question, the storage question, the backfill question and the config question simultaneously; only
B3 and B4 descend from another decision rather than from B1 directly.

**Three of the seven reverse the orchestration-era pipeline** — B1, B3 and B5. B6's `◦` marks a prior state that was restated rather than overturned. B3's reversal is the one that matters:
`AIRFLOW_DAG_MIGRATION.md` derives the GCS path from `logical_date` in three places, which stops
being correct the moment an asset fires the run, because the logical date then records when the
event fired rather than which month arrived.

**B6 changed nothing at runtime.** Airflow 3 already defaults `catchup_by_default` to `False`
([upgrading to Airflow 3](https://airflow.apache.org/docs/apache-airflow/3.0.1/installation/upgrading_to_airflow3.html):
*"The `catchup_by_default` dag parameter is now `False` by default."*). The line states a default
rather than overriding one, and the decision with consequences is loading history by explicit
backfill — which is what makes the producer the DAG you backfill, and the consumers, being
asset-scheduled, the DAGs you can't. That is the Future item *Asset-scheduled consumers can't be
backfilled*, which until now had no parent.

**B7 is answered in another file.** The dbt-era config module is recorded as the outcome of the
orchestration-era factory decision, under its *What happened* paragraph. Writing it again here would
duplicate it, so the node points there instead.

**One placement is arguable.** *Every mapped BigQuery object carries the month* has both parents in
this tree — the filename carries the month, and mapping creates the collision risk — but its subject
is A's external tables. It sits here with a pointer into A; the reverse would also be defensible.

**Numbering.** This tree uses a `B` prefix while section A's decisions are bare numbers. Worth
resolving when A's remaining leaves are moved, since that change already touches A's numbering and
the cross-references into it.

---

### B1 Who downloads?

**Options considered**, against B-D1's two goals. Each rejected option fails exactly one of them:

| Option | (a) Loads independent | (b) Download defined once |
|---|---|---|
| One DAG per target, each downloading | yes | **no** — two copies to keep in step |
| One DAG doing download and all loads | **no** — either load fails the month for both | yes |
| Producer publishes an Asset, consumers schedule on it | yes | yes |

**Decision:** a producer DAG that downloads and publishes an Asset, with a consumer DAG per target scheduled on it.

**Reasoning:** goal (a) rules out the single DAG — a BigQuery schema failure would fail the month for DuckDB too, and the two targets are deliberately allowed to use different operators. Goal (b) rules out a DAG per target, because the download would then be written twice and the second copy is the one that silently falls behind. Only the split satisfies both, and Assets are Airflow 3's mechanism for a data dependency between DAGs — replacing the sensor and `TriggerDagRunOperator` patterns — so this is the shape they exist for.

What it costs, in order of how much it hurts:

- **The consumers can't be backfilled.** See B6, which this cost belongs to.
- **No single place shows a month's end-to-end status.** A failed load shows on the consumer, not on the download that succeeded.
- **An extra DAG run per month.**

**What replaces run-list status:** the target table, queried by `filename`, is the record of what is loaded — not the DAG run list. A producer run succeeding means a `.csv.gz` exists, nothing more. This is where dbt's tests were going to put the question anyway, so the split brought it forward rather than creating it.

**Revisit:** trigger — a target needs a different source file from the others. Action — a second asset, rather than branching inside the producer. The recovery problem has its own trigger under B6.

---

### B2 How does a consumer learn what arrived?

**Context:** the producer's run and the consumer's run are now separate. Something has to tell the consumer which file it is loading.

**Options considered:**

| Option | Effect |
|---|---|
| Infer it from the consumer's own `logical_date` | Couples the consumer to the producer's cron, and a run triggered by several coalesced events can't say which months it covers |
| List the download directory at load time | Races the next download, and a re-run sees whatever is there now rather than what triggered it |
| The asset event's `extra` carries the path | The consumer is told what arrived |

**Decision:** the producer sets `outlet_events[asset].extra = {"path": dest}`, and the consumer's first task reads `triggering_asset_events`.

**Reasoning:** the event payload is the interface between the two DAGs, so the consumer is told what arrived rather than inferring it. Inference is what breaks: asset URIs are static and resolved at parse time, so the URI identifies the *stream* of yellow downloads and can't carry a month, and a consumer run can be triggered by several events at once — Airflow coalesces them during a backfill — which no single `logical_date` describes.

The extra carries the full path rather than a month or a filename. Where files land is the producer's decision, so handing over the path means the consumer never needs to know the mount location, and it takes what it needs off the end of it.

**Three things this forces:**

- **One task writes the file and publishes it.** `outlets` declares *this task produced this asset*, so the task that writes the bytes is the one that announces them. A single success then means both "file landed" and "event fired", rather than two things that can disagree.
- **Only a Python task can set an `extra`.** That is why the download is a `@task` rather than the `BashOperator` it started as — the handover, not the download, decided the task type.
- **Asset identity lives in a shared module.** `dags/utils/assets.py`, imported by producer and consumers alike, because a consumer can't import an asset defined inside the producer's factory and redefining it means the identity string exists in two places. The URI must be unique per colour or both consumers fire on both colours.

**Revisit:** trigger — a consumer needs something the producer doesn't currently publish, such as a checksum or a row count. Action — add it to the `extra`, which is a dict, rather than having the consumer derive it from the file.

---

### B3 Where do the month and the replacement key come from?

**Context:** four things need to know which month a file holds: the GCS object path, the external table name, the prune's `WHERE filename =`, and the log line a human reads. They can all derive from one source or each from its own.

**Options considered:**

| Option | Effect |
|---|---|
| The run's `logical_date` | Wrong once an asset fires the run — the logical date records when the event fired, not which month arrived |
| A manifest written by the producer | Authoritative, and a second artefact to keep in step with the files |
| The filename, which already contains the month | One source, and it is the file's own name |

**Decision:** the filename. `get_file_info` pulls `(\d{4})-(\d{2})` out of the basename, and every path and key downstream is built from those parts.

**Reasoning:** the filename is the only candidate that cannot disagree with the file it describes. A manifest can drift from what is on disk; `logical_date` was correct while the download and the load were the same run and stopped being correct the moment an asset fired the consumer. Deriving everything from one source also means a month's identity is decided once rather than in four places that can diverge.

**What follows from it:**

- **The download overwrites the same path and never skips.** Explicitly no skip-if-the-output-exists check — that is B-D2, the course script's bug stated as a rule. A revised source file must replace the old one.
- **The GCS object is derived from year and month**, so a re-run replaces rather than accumulates.
- **The prune key is `basename(path)`** — used by A's decision 1.1, which is what makes a reload idempotent at file grain.
- **Every mapped BigQuery object carries the month.** Without it, mapped instances all `CREATE OR REPLACE` the same `<colour>_tripdata_ext` and race, and the load reads whichever month won. This governs the per-month naming in A's decision 4.

**The cost:** the filename is now load-bearing, and nothing validates it. A source that renamed its files — or dropped the `YYYY-MM` from them — breaks four things, and three of them break silently.

**Revisit:** trigger — a source whose filenames don't carry a parseable month, or two sources whose names collide. Action — the producer derives the month and puts it in the asset event's `extra` alongside the path, so the parse happens once, at the only point that knows where the file came from.

---

### B4 A run can carry several files — how?

**Context:** a producer run can publish more than one file — a backfill of 24 months does — and each has to be uploaded, declared and inserted.

**Options considered:**

| Option | Effect |
|---|---|
| Loop inside one task | One task per step. One pass/fail for the whole batch |
| One DAG run per file | Per-file status from the scheduler. Needs the producer to fan out runs |
| Dynamic task mapping | One task instance per file within one run |

**Decision:** dynamic task mapping — `.expand()`, or `.expand_kwargs()` fed by `.map()`.

**Reasoning:** each file gets its own task instance, so one bad month fails on its own, is visible as its own square in the grid, and can be cleared and retried without touching the others. A loop inside one task collapses that to a single outcome and makes a partial failure mean re-running everything. Mapping is also the only one of the three that needs nothing from the producer.

**The trap, which cost a debugging cycle:** `.expand(src=a, dst=b)` takes the **cross product** of the two lists — N files produce N² task instances. Pairing values from the same file requires `.expand_kwargs()`, fed by `.map()` building one kwargs dict per file. Arguments that are the same for every instance go on `.partial()`.

**Revisit:** trigger — the mapped count grows enough that per-instance scheduling overhead matters, or a single file needs splitting across instances. Action — chunk inside the mapped task rather than abandoning mapping; one DAG run per file only if per-month scheduler visibility becomes the requirement.

---

### B5 Where does the file live between the DAGs?

**Context:** the producer writes the `.gz` and the consumers read it. Both run in containers, so the directory has to be a mount shared between them.

**Options considered:**

| Option | Effect |
|---|---|
| Write under `AIRFLOW_HOME` | No new mount. Mixes raw data with Airflow's own files |
| A dedicated bind mount | One obvious place, inspectable and clearable from the host |
| No local file — stream to GCS | No shared directory at all. Consumers can't read the bytes locally |

**Decision:** `./taxi_download` on the host, bind-mounted at `/opt/airflow/taxi_download`, as a module constant.

**Reasoning:** raw downloads aren't Airflow's state and shouldn't live among its logs and dags, where clearing them means picking through files that matter. A named directory can be listed, measured and emptied from the host without care.

The `AIRFLOW_HOME` version also hid a bug worth not repeating: `os.environ.get("AIRFLOW_HOME", "/opt/airflow/")` reads as having a safe fallback, but the official compose file always sets `AIRFLOW_HOME`, so the default never applies and the path silently depends on the environment rather than on the code. A constant says what it is.

**Revisit:** trigger — more than one worker, or workers on separate hosts. Action — a local file stops being a shared channel at that point; the producer uploads to GCS and publishes the object path in the asset event instead of a filesystem path, and the consumers read from GCS.

---

### B6 How is history loaded?

**Context:** 24 months per colour had to be loaded once, and new months arrive monthly thereafter.

**Options considered:**

| Option | Effect |
|---|---|
| `catchup=True` | All 24 months fire the moment the DAG is unpaused |
| `catchup=False` with explicit backfill | History is loaded when someone asks for it, in a range they choose |

**Decision:** `catchup=False`, stated explicitly, and history loaded with `airflow backfill create` against the producer.

**Reasoning:** the line changes nothing at runtime — Airflow 3 already defaults `catchup_by_default` to `False` — so it is there to say the choice was made rather than inherited. The choice itself is that a backfill is an operation someone runs deliberately, with a range and a reprocess behaviour, rather than something that happens because a DAG was unpaused at the wrong moment.

**The producer is the DAG you backfill.** It owns the cron; the consumers are asset-scheduled and have no schedule of their own. That has three consequences worth knowing before trying it:

- **The window is compared against the run time, not the date.** With a `0 9 1 * *` schedule, `--to-date 2020-12-01` excludes that month's run at 09:00 and yields 23 months rather than 24. The from-date looks inclusive and the to-date exclusive; both are inclusive of a run time you have set to 09:00.
- **`--reprocess-behavior` defaults to missing runs only.** Months that already have a run are skipped whatever their state, so a second attempt over the same range reports nothing to do. `failed` or `completed` re-runs them.
- **A manual trigger of a consumer loads nothing.** It has no triggering asset event, so the first task returns an empty list. Re-loading one month means re-running the producer for it, or a params override.

**Revisit:** trigger — re-running failed loads by hand becomes routine rather than occasional. Action — give the consumers their own time-based schedule alongside the asset so a backfill can drive them, and make the load skip a month already loaded. Merging the DAGs back together is the wrong fix; it trades a recovery problem for a coupling one. Tracked in Future as *Asset-scheduled consumers can't be backfilled*.

---

---

# Future

Known problems and ideas not yet acted on.

## dbt's staging layer owes a trip-grain dedup rule

**Problem:** the colliding row pairs — five in yellow 2019-01 — are loaded into raw deliberately, because the load does no deduplication. Nothing downstream resolves them, so the duplicates are sitting in both targets waiting for a model that hasn't been written.

**Idea:** a staging model that deduplicates to trip grain with an explicit, documented rule for which record wins. The pairs are amended meter records — same trip, conflicting payment fields — so "latest wins" needs a definition of latest that the source doesn't provide. A deliberate rule written next to the model, not a `DISTINCT`.

**How it gets checked:** the same model over both targets returns the same row count, which is the parity test named in decision 1.

**One constraint on the implementation, if it uses a surrogate key.** Hash cast values, not raw text. Hashing raw text works only while both engines spell every value identically, and they parse the same CSV independently — BigQuery's external table and DuckDB's reader can differ on empty string versus `NULL`, and on quoting or leading whitespace. Same bytes in, different strings out, different hash. Worth a probe before relying on either behaviour. A key is only one way to deduplicate, though — `row_number()` over the natural columns needs no hash at all, and this constraint then doesn't apply.

## Asset-scheduled consumers can't be backfilled

**Problem:** the load DAGs are scheduled on an asset, which means they have no time-based schedule and `airflow backfill create` doesn't apply to them. There is no `--reprocess-behavior failed` equivalent — recovering a range of failed loads means clearing each run by hand, or re-running the producer for those months and re-downloading files already on disk. See *Producer and consumer DAGs, linked by an Asset*.

**Idea:** give the consumers a time-based schedule as well as the asset. `AssetOrTimeSchedule` looks like the mechanism — verify it exists in 3.3.1 and behaves as documented before planning around it.

**The real question, if it does:** a cron-driven run has no triggering asset event, so `file_downloaded` has nothing to read. The month would have to come from the run's logical date instead, and the task needs both paths — asset event when triggered by the producer, derived path when triggered by time. That also raises whether a time-driven run should download a missing file itself or fail, which decides whether the consumer stays a pure consumer.

**Also worth checking:** whether `--reprocess-behavior` then works against the consumer, or only against its time-based runs.

---

## DuckDB ingestion differs from the Airflow-loaded targets

**Problem:** DuckDB is loaded by the course's standalone script, while BigQuery and Postgres are loaded by Airflow. The script now lands the same all-text shape, so the targets match on content — but it has no schedule, no retries, no provenance, no per-month idempotency, and it rebuilds all 109M rows to add a month.

**The bug worth fixing first:** `if parquet_filepath.exists(): continue` means a revised source file is never re-downloaded, and `CREATE OR REPLACE` then rebuilds from the stale local copy and reports success. A corrected month is silently ignored. Nothing in the script can detect this; the BigQuery side can't either, except that its `ingestion_timestamp` would show the month was never re-loaded.

**Idea:** load DuckDB with an Airflow DAG, as the second consumer of the download asset. That is also what makes the producer/consumer split pay for itself.

**Constraints if done:** DuckDB allows only one process to write the file at a time, so it needs a mount shared by Airflow and dbt, and their runs can't overlap. `duckdb` also needs adding to Airflow's `requirements.txt`, alongside the dbt venv.

---
