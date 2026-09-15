# ETL vs ELT

---

## Q: Is this a standard ETL, but with transformation last?

**A: No — it's ELT. The labels are about where the compute happens, not the ordering.**

- **ETL** — a separate processing tier (pandas, Spark, an ETL tool) transforms data before the database sees it. The database only ever receives finished tables
- **ELT** — raw data lands in the warehouse first, then the warehouse's own SQL engine transforms it

Applied to this pipeline:

- The CSV lands in Postgres untouched, then SQL does the hashing and merging inside Postgres → **ELT**
- It would be ETL if pandas cleaned, cast and deduplicated before `to_sql`

Why it reads as odd: "transform last" sounds like an afterthought, when it's the point — warehouses got cheap and fast enough that pushing work into them beat maintaining a separate transformation tier.

---

## Q: Isn't staging always part of any pipeline? Isn't the real difference whether raw data is stored permanently — e.g. `API → data lake → database` vs `API → database`?

**A: Staging is universal and isn't the distinction. Permanence of raw storage isn't the dividing line either, though it correlates.**

- Staging tables appear in both ETL and ELT
- `API → data lake → database` vs `API → database` describes **architecture** — whether there's a durable raw layer
- You can do ETL *with* a data lake: land raw, transform in Spark, write results elsewhere
- You can do ELT *without* one: load straight to Postgres, transform with SQL

**Why they correlate anyway:**

- ETL existed because databases were expensive and slow — do the work outside, only pay to store the finished product
- Once warehouses got cheap and fast, dumping everything in and transforming in place became better
- Cheap storage is also what made keeping a raw layer viable
- Same economics drove both, so they arrived together

---

## Q: Aren't there two transformations? CSV → DB table, then DB table → final DB table.

**A: Two steps, but only one is a transformation in the ETL/ELT sense.**

- **CSV → staging table** is a **load**. Same columns, same values, same rows — only the container changes. Parsing a CSV into typed columns is deserialization, not transformation
- **Staging → final table** is the **transformation**. Computed `unique_row_id`, `filename` provenance column, deduplication deciding which rows survive

**The test — could you reconstruct the input exactly from the output?**

- After the CSV load: yes, the staging table is the file
- After the merge: no, rows have been added to and filtered

---

## Q: What about type casting — isn't that a transformation?

**A: Genuinely blurry. Judgement call, not a rule.**

- `CREATE TABLE` declaring `passenger_count integer`, `tpep_pickup_datetime timestamp` does coerce strings into types
- That's a real change — some would call it transformation
- Reasonable to call it load, because the intent is to represent the same values faithfully rather than derive new ones

**Why it matters practically:**

- If the CSV load starts *rejecting* rows that fail type coercion, it has silently become a transformation — one that drops data without telling you
- Know which tasks are allowed to change row counts. In this pipeline, only the merge should

---

## Related

Per `04_postgres_taxi_explained.md`, the Kestra flow was "mostly EL rather than full ELT" — the only transformations were the hash and filename columns. Adding the SQL steps is the T arriving.
