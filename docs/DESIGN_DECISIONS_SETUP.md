# Design Decisions — Setup

Architectural choices about the tools and the environment they run in: which runtime, which
orchestrator, how Airflow itself is configured. The decisions behind a particular load pipeline live
in the companion files, one per pipeline era.

This file complements the technical setup guide, which covers how to install and run things; this
covers why they're built the way they are.

Each entry follows the same shape: options considered, decision, reasoning, revisit trigger.

---

## For models updating these documents

These rules govern all three files — this one, `DESIGN_DECISIONS_ORCHESTRATION.md` and `DESIGN_DECISIONS_DBT.md`. They live here only, so there is one copy to keep true.

The audience is a future reader applying these decisions to a different situation — often production, shared, or at scale. Write for them.

Before adding or editing an entry, check:

- **State the decision and when it applies.** Not how the mechanism works. "Enabled for individual dev, not for shared" is the decision. "Because hooks resolve connections through the Task SDK" is mechanics — leave it out.
- **Give the reason for the choice, not the reason it works.** Why this was picked over the alternatives, not why it functions.
- **Name what the other situation uses instead.** If the decision is local-dev-only, say what production does.
- **Every entry needs a revisit trigger and an action.** "Not really a revisit case" is filler — either find the real condition or cut the line.
- **Pick the file by scope, not by subject.** This file holds the tools and the environment — anything binding every pipeline, whichever era. An era file holds what is specific to that era's pipelines, including its Airflow decisions, so an orchestration decision sits beside the data decision it serves. Inside an era file, use the narrowest group that is true. An entry whose scope isn't obvious from its file and group reads as a contradiction of one elsewhere — that is the failure this structure exists to prevent.
- **An entry lives in one file only.** When a decision narrows or replaces one elsewhere, say so in both and name the file. Don't duplicate the entry, and don't delete the one it replaces if it still governs its own scope — the Postgres load still merges on a row hash.
- **A statement with no alternatives weighed is a principle, not a decision.** It belongs in the Guiding Principles table below, with one example decision that follows from it. Forcing it into the entry shape invents options nobody considered and produces the filler revisit line the rule above forbids.
- **Be concise.** Don't restate reasoning already given earlier in the same entry. If a paragraph explains rather than decides, cut it.

---

# Guiding Principles

Adopted rather than decided — no alternative was weighed, so these don't take the entry shape used
everywhere else in these files. A decision cites a principle instead of re-arguing it.

Each principle names one decision that follows from it. A principle with nothing following from it is
decoration and should be cut.

| Guiding principle | Example decision that follows from it |
|---|---|
| Raw is faithful to the source | dbt: 2. Who resolves types? |
| Loads are idempotent | dbt: 1.1.1 Should the insert and prune be atomic? |
| Fail loudly rather than degrade silently | dbt: 4.3 What happens when the source schema changes? |
| Every row carries its provenance | dbt: 2.1 How are the landing tables partitioned and clustered? |
| Infrastructure is declarative; data is imperative | Terraform owns the containers; pipelines own what's inside them |
| Credentials are declared, not scattered | Credentials are Connections; configuration is Variables |
| Build for the general case, not for this dataset | dbt: 4.1 Where do the column names come from? |

Decisions prefixed `dbt:` live in `DESIGN_DECISIONS_DBT.md`; a number means it is one of the
numbered decisions under the driver section there. The last two are in this file.

The last one is the odd one out: it is a learning goal rather than an engineering property, and it is here because without it a reader finds defensive machinery that this dataset demonstrably does not need — a header read on every file whose header never changes, and a drift check against months measured as schema-uniform — and concludes it was waste.

**No sources yet.** These were derived from decisions already made in this project, not taken from a
published set — see Future.

---

# General

Decisions about the base environment, not tied to any one tool built on top of it.

## Container runtime: Docker Engine, not Docker Desktop

**Options considered:** Docker Desktop (Windows app, GUI, integrates with WSL2 under the hood) vs Docker Engine installed directly inside Ubuntu/WSL2, managed entirely from the terminal.

**Decision:** Docker Engine, inside Ubuntu.

**Reasoning:** No licensing overhead — Docker Desktop requires a paid license for commercial use, Engine doesn't. It's closer to how a real Linux server runs Docker in production, since there's no Windows GUI layer in between. It also matches the broader approach taken throughout this setup: WSL2 and Ubuntu as the real working environment, Windows as GUI only. A GUI layer that hides what's happening was avoided consistently elsewhere too — this is the same call made again later for Airflow (official docker compose over the Astro CLI).

**Revisit:** if a GUI for container management genuinely becomes useful day to day, Docker Desktop can still be added on top without removing Engine. Unlikely to be needed for this course.

---

## Python version and environment management: uv

**Options considered:**

| Option | What it does |
|---|---|
| `pyenv` + `venv` | pyenv manages Python versions, venv manages per-project isolation — two tools |
| Poetry | Manages packages, dependencies and Python packaging together |
| uv | Manages Python versions, virtual environments and package installs in one tool |

**Decision:** uv.

**Reasoning:** Replaces both pyenv and pip in a single fast tool — one thing to install and learn rather than two. Poetry is geared more toward building and publishing Python packages/libraries, which isn't the shape of this work — it's pipelines and scripts, not a library being distributed. uv is significantly faster (Rust-based) and is where the ecosystem was visibly heading. Confirmed against the official docs partway through the course after some early confusion mixing up `uv init` / `uv venv` / `uv python pin` — `uv init` alone creates both `pyproject.toml` and `.venv`; the other two aren't needed for the standard project workflow.

**Revisit:** not expected to change for this course. Poetry would be the tool to revisit if a project here ever needed to be packaged and published rather than just run.

---

## Repo structure: own repo, course repo as reference only

**Options considered:** fork the course's zoomcamp repo on GitHub and clone the fork locally as the working copy; versus create an entirely separate personal repo, and never clone the course repo at all.

**Decision:** a separate personal repo. The course repo is read on GitHub as reference material and never cloned locally.

**Reasoning:** This reversed direction once, and the reversal is the useful part to remember. The first instinct was the standard open-source contribution pattern — fork, clone the fork, work in it — on the reasoning that it keeps a personal copy backed up and versioned. That pattern makes sense when the intent is to eventually contribute back or track upstream changes. Neither applies here: this is coursework, not a contribution, and the course repo's structure (organised by module, with the original author's own solutions) isn't the structure this work should end up in anyway. Cloning it locally would just mean carrying around files never edited, with no real reason to keep them in sync with upstream. A plain new repo, organised by module for this work specifically, avoids that clutter and avoids any temptation to edit inside what's meant to stay reference material.

**Revisit:** trigger — a case comes up for actually contributing a fix or improvement back to the original course repo. Action — fork the course repo on GitHub for that purpose only, as a separate repo unrelated to this project's own work; do not merge it into or clone it alongside the personal repo described above.

---

# Infrastructure

Decisions about the GCP footprint and how it's provisioned.

## Terraform owns the containers; pipelines own what's inside them

**Context:** both Terraform and the load DAGs can create things in GCP. Without a line between them, the same object gets created twice or by whichever ran last.

**Options considered:**

| Option | Effect |
|---|---|
| Terraform owns everything, tables included | A schema change is a `terraform apply`; state drifts every month a table appears |
| Pipelines create everything, dataset included | No declarative record of the project's GCP footprint |
| Terraform owns the containers, pipelines the contents | Boundary at the thing that's long-lived |

**Decision:** Terraform owns the project, the dataset, the bucket and their settings — including the bucket's lifecycle rule. Pipelines create, replace and drop tables and objects inside them.

**Reasoning:** the split is between what exists and what flows through it. A dataset and a bucket are created once, live indefinitely, and their settings are policy — location, retention — which belongs in version-controlled declarative config where it applies whether or not a DAG ran. Tables and GCS objects are per-month artefacts of a load, created and replaced by the thing doing the loading; declaring those in Terraform would make every month's arrival a state drift and every schema change a `terraform apply`.

**Practical consequence:** cleanup removes tables, never the dataset. A DAG that dropped the dataset would put Terraform's state out of sync with reality, and the next apply would quietly recreate an empty one.

**Revisit:** trigger — the target tables' schemas become a published contract other people depend on. Action — declare the target tables in Terraform as well, and have the load fail rather than create, so a schema change becomes a reviewed commit. The per-month external tables stay with the pipeline either way.

---

## GCP auth: a service-account key file, not browser login

**Options considered:**

| Option | Effect |
|---|---|
| `gcloud auth login` | User credentials. Opens a browser |
| Application Default Credentials from a user login | Same browser flow, then cached |
| A service-account key file | Works identically from a shell, Terraform and a container |

**Decision:** one service-account key at `terraform/keys/creds.json`, gitignored. Terraform reads it directly, the CLI gets it via `gcloud auth activate-service-account --key-file=`, and Airflow reads it through a Connection.

**Reasoning:** the browser flows are awkward from WSL — `gcloud init` and `gcloud auth login` open a browser on the Windows side of the boundary, which is friction every time credentials expire. A key file behaves the same way everywhere, which matters most for the callers that have no browser at all: Terraform, and tasks running inside an Airflow container. One credential then covers every caller instead of each having its own path.

**When not to:** anything shared, and anything production. A key file is a long-lived credential sitting on disk and inside a volume mount. It doesn't expire, can't be rotated centrally, and is as strong as whatever roles the service account holds. Production uses workload identity federation, or service-account impersonation from a short-lived user credential.

**Revisit:** trigger — this stops being local and single-user, or the key would have to be shared with anyone. Action — impersonation locally (`gcloud config set auth/impersonate_service_account`) and workload identity federation in CI. The key is deleted rather than rotated; a key that exists is a key that leaks.

---

# Orchestration

Decisions that apply across orchestration tools generally, rather than to one specifically.

## Orchestration tool: Kestra and Airflow, both

Both Kestra and Airflow are set up as separate compose projects, so they can run side by side and be compared directly rather than picking one up front.

### Kestra

| | |
|---|---|
| **Pro** | Declarative YAML — no Python needed to define a flow |
| | Flows editable in the browser, with the UI validating as you type |
| | Single container plus its database; small footprint |
| | Fast to get started — one compose file and nothing else |
| **Con** | Open-core, not fully open source. The core is Apache 2.0; the Enterprise Edition is proprietary with closed source |
| | Free edition has basic auth only. RBAC, SSO, audit logs, multi-tenancy, secrets management and worker isolation are paid |
| | Three tiers: free OSS, Pro (~$25/month), Enterprise (custom) |
| | Smaller community, fewer answers when something breaks |
| | Flows live in the metadata database — losing the volume means re-importing them |

In fairness, core orchestration is not paywalled: unlimited executions, 1,200+ plugins and full API access are all in the free edition. The gate is governance and scale, not capability.

### Airflow

| | |
|---|---|
| **Pro** | Fully open source, Apache 2.0, Apache Software Foundation project — no proprietary tier |
| | Most widely adopted orchestrator; largest ecosystem and talent pool |
| | DAGs are Python — full language available, and they version in git like any other code |
| | Vendors (Astronomer, MWAA, Cloud Composer) sell hosting and support, not gated features |
| **Con** | Heaviest operational footprint — seven containers for a local install |
| | More setup steps, and more that can go wrong |
| | Steeper learning curve; DAG authoring is a real API to learn |
| | Airflow 3 changed enough that older tutorials and course material no longer apply cleanly |
| | Time-based and data-aware scheduling are separate models, and a DAG scheduled on an asset gives up backfill — see *Asset-scheduled consumers can't be backfilled* in `DESIGN_DECISIONS_DBT.md` |

**Observed, not read:** building the producer/consumer pair found the seam between those two scheduling models. Airflow is time-partitioned at its core — `logical_date`, data intervals, catchup, backfill all assume a run is a time window — and event-driven fan-out is grafted on top, so an asset's URI can't carry which month arrived, the payload rides in a free-form `extra`, events coalesce into one run uncontrollably, and backfill stops applying. Dagster inverts this, treating assets as the primary unit and schedules as secondary, so it is the tool to look at if data-aware orchestration becomes the main requirement rather than an experiment.

**Revisit:** if either tool is dropped from the course going forward — rather than both being actively compared — remove that tool's section here so this doesn't go stale describing a comparison no longer being made.

---

## Postgres per orchestration project, not one shared warehouse

**Options considered:**

| Option | Shape |
|---|---|
| A — duplicate `pgdatabase`/`pgadmin` into every orchestrator's compose file | Each project fully self-contained, own volume |
| B — one orchestrator's compose "owns" Postgres, others attach to its network externally | One shared database, dependent on whichever project owns it staying up |
| C — Postgres + pgAdmin pulled into their own dedicated compose project, all orchestrators attach externally | One shared database, independent of any single orchestrator |

**Decision:** A — each orchestration project gets its own `pgdatabase` and `pgadmin`, on its own ports, writing to its own volume.

**Reasoning:** This reversed direction once during the conversation, worth recording both sides. The initial instinct was C — a dedicated shared-infrastructure project, on the reasoning that a data warehouse is shared infrastructure and orchestrators are consumers of it, letting both tools compare results against one shared dataset. That's a reasonable design in general, but it doesn't match how this course is actually structured: each module (Docker/Terraform, Kestra, Airflow) is self-contained, and the course's own precedent — Kestra's compose file already contains its own `pgdatabase` and `pgadmin` alongside `kestra`'s metadata store — is the same pattern, one module earlier. A search of real-world example repos also found this to be the dominant pattern in practice; the shared-network-backbone approach exists but is thin outside Docker-specific writing, not data engineering courses/repos. Option B was rejected outright: it makes one orchestrator's uptime a dependency for another's database, which is backwards.

Practical consequence: each project's `ny_taxi` starts empty and needs its own ingestion run. For comparing Kestra's output against Airflow's this is arguably a feature, not a cost — neither can contaminate the other's data.

Note: pointing an orchestrator at the database from module 1 instead is also architecturally fine — the 2022 course did exactly that with Airflow. Neither approach is more correct in general; weigh the pros and cons against the situation.

**Revisit:** trigger — if the goal ever shifts from "compare orchestrators" to "run one production pipeline with an interchangeable orchestrator." Action — switch to option C: pull `pgdatabase`/`pgadmin` into their own dedicated compose project, and point whichever orchestrator is in use at it as an external network.

---

# Airflow

How Airflow itself is set up. Binds every DAG in the project, whichever pipeline it belongs to.

## Local setup method: official docker-compose, not the Astro CLI

**Options considered:**

| Option | What it is |
|---|---|
| Official docker-compose | Full service set exposed directly — scheduler, api-server, dag-processor, worker, triggerer, redis, postgres all as separate services in one file |
| Astro CLI, container mode | Astronomer's tool, Docker or Podman underneath, runs everything through the `astro` command rather than compose directly |
| Astro CLI, standalone mode | Runs Airflow directly on the machine in a `uv`-managed virtualenv, no Docker at all — newer, not confirmed to work on Windows |

**Decision:** official docker-compose.

**Reasoning:** Astronomer's own documentation recommends Docker Compose for open-source local development and reserves Astro for managed operations and faster CI/CD — the vendor pointing at the vendor-neutral option for this use case is a strong signal. It also matches the reasoning already used for Docker Engine over Docker Desktop: avoiding a layer that hides what's actually running. Seeing scheduler, api-server, dag-processor, worker and triggerer as distinct services in one file is itself part of the point of this exercise — the same lesson the Kestra compose file gave about Kestra's own architecture.

**Revisit:** if the compose file becomes a fight rather than a lesson — repeated setup friction with no learning value left in it — switching to Astro CLI is cheap and legitimate at that point.

---

## Airflow's own image: pip inside the container, uv everywhere else

**Options considered:** use uv consistently everywhere, including inside the custom Airflow image that adds `apache-airflow-providers-google`; or use pip specifically inside that image.

**Decision:** pip inside the Airflow image; uv stays the tool for everything else (the project's own Python environment, `taxi_ingest`, etc).

**Reasoning:** Not a preference — uv has real, documented friction inside the official Airflow image specifically. Airflow installs itself into `~/.local` and sets `VIRTUAL_ENV` to point at it, so that directory gets treated as a virtual environment while also being system-level — a shape uv's own environment handling doesn't get along with. The Airflow image does ship a uv binary, but its own Dockerfile documentation describes uv support there as experimental. Confirmed via GitHub issues of others hitting the same conflict before deciding.

```dockerfile
FROM apache/airflow:3.3.1
COPY requirements.txt .
RUN pip install apache-airflow==${AIRFLOW_VERSION} -r requirements.txt
```

Pinning `apache-airflow` to the base image's own version stops pip from quietly upgrading or downgrading Airflow itself while resolving the new provider's dependencies.

**Revisit:** trigger — uv's support for this pattern moves out of experimental (check the Airflow image's own Dockerfile docs). Action — if it has, test switching the two `RUN` lines above to `uv pip install` in a throwaway build before committing to it in the real Dockerfile, since the underlying `~/.local` / `VIRTUAL_ENV` conflict this entry describes needs to actually be resolved, not just have uv's support label change.

---

## `pgdatabase` waits on Airflow's api-server via `depends_on`

**Options considered:** no `depends_on` on `pgdatabase` at all (nothing in this compose file genuinely depends on the database's startup order relative to Airflow); versus adding `depends_on: airflow-apiserver, condition: service_healthy`.

**Decision:** the dependency was added, against the initial recommendation to leave it out.

**Reasoning:** There's no functional need for it — `pgdatabase` doesn't read from or write to any Airflow service, so nothing about it genuinely depends on Airflow being healthy first. The decision to add it anyway was made deliberately rather than by accident, so the trade-off is worth being explicit about rather than treating this as a mistake to fix later:

* `depends_on` is evaluated once, at `docker compose up`. It is not a permanent link — once `pgdatabase` has started, an Airflow crash an hour later does not affect it.
* Cost: `pgdatabase` waits for the api-server to report healthy before it starts, adding delay on every cold start.
* Risk: if the api-server never reaches healthy, `pgdatabase` never starts either — an Airflow startup problem takes the `ny_taxi` database down with it, even though `ny_taxi` has nothing to do with Airflow.
* `condition: service_healthy` (used here) waits for the healthcheck to pass. `condition: service_started` (used on the equivalent line in the Kestra compose file) only waits for the container to start, which for a database is not the same as being ready to accept connections — worth knowing the two files aren't consistent with each other on this point.

If the startup delay or the coupling becomes annoying, the database can still be started on its own regardless of this setting:

```bash
docker compose up -d --no-deps pgdatabase
```

**Revisit:** if the Airflow project is ever a place where `pgdatabase` needs to be reliably available independent of Airflow's own health — for example, running the DAG from a different Postgres while debugging the apiserver — this should be removed.

---

## Credentials are Connections; configuration is Variables

**Options considered:** read everything a DAG needs from plain env vars via `os.getenv`; or split by what the value is — Connections for anything that authenticates to a service, Variables for anything that configures behaviour.

**Decision:** split by kind. Anything authenticating to a service is an Airflow Connection. Anything configuring behaviour is a Variable or a module constant.

**Reasoning:** it's Airflow's own rule of thumb, and it's the only split that survives a change of backend — a Connection can be defined by `.env` today (one `AIRFLOW_CONN_{CONN_ID}` URI) and by a secrets manager later without any DAG changing. Credentials read as loose env vars sit outside that model, so there is no single place to rotate them and no way to move them.

It also removes a bug class rather than a style complaint: a value read with `os.getenv` at module level is captured once at DAG *parse* time, not at execution. A credential that changes, or an environment that differs between the parser and the worker, then silently uses the stale one.

**What this doesn't settle:** whether a non-credential belongs in a Variable or in a module constant. Both are legitimate and the project is inconsistent — the dbt-era load DAG reads `Variable.get("GCP_DATASET")` in one place and a module-level `DATASET` in another. Rule of thumb: a Variable if it changes per environment, a constant if it changes only when the code does.

**Revisit:** trigger — a secrets backend (Vault, Secret Manager) is introduced. Action — the Connections move there; the split itself doesn't change.

---

## Connection testing: enabled for local dev only

**Decision:** enable the UI's **Test** button. It ships disabled.

```yaml
AIRFLOW__CORE__TEST_CONNECTION: 'Enabled'
```

Takes `Disabled`, `Enabled` or `Hidden` — a string, not a boolean.

**When to use it:** individual development on a local machine, with credentials for a throwaway project.

**When not to:** anything shared. The button opens a connection to real infrastructure from the web UI, using whatever credentials the connection holds, available to anyone who can reach the UI. On a shared instance, test connections with a throwaway one-task DAG and `airflow dags test` instead — which also works locally, just with more ceremony.

**Revisit:** trigger — this setup stops being local and single-user. Action — set back to `Disabled`.

---

---

# Future

Known problems and ideas not yet acted on.

## Nothing records how a failure reaches a person

**Problem:** *Fail loudly rather than degrade silently* is a guiding principle, and four decisions implement it — the drift check raises, no auto-`ALTER`, no skip-if-exists, cleanup kept out of the load path. Every one of them assumes somebody notices a red task. Nothing anywhere records how. For a DAG running `0 9 1 * *`, that makes the principle hollow.

**Idea:** decide where a failure goes and write it down — `on_failure_callback`, an SMTP connection, or a Slack webhook. The decision is not which tool; it is that unattended runs need a route out, and the drift check is deliberately the thing most likely to use it.

## Terraform's outputs reach Airflow by hand

**Problem:** Terraform creates the bucket and the dataset; the DAGs read `Variable.get("GCP_BUCKET")` and `Variable.get("GCP_DATASET")`. The same names are therefore declared in two systems and kept in step by someone remembering to. Nobody chose this — it is what happened, and it sits exactly on the seam the Infrastructure section draws.

**Idea:** either Terraform writes the Airflow Variables as part of its apply, or the DAGs read Terraform's outputs. The first keeps one source of truth and couples the apply to a running Airflow; the second keeps them decoupled and needs the state file reachable. Neither has been looked at.

## The guiding principles have no sources

**Problem:** the principles above were reverse-engineered from decisions this project already made.
That makes them descriptive of what was done, not a check against anything — a wrong principle
consistently applied looks exactly like a right one.

**Idea:** find a reputable published set to check them against. Airflow's own best-practices
documentation covers idempotency, and dbt's documentation covers ELT and the role of staging models,
so those two are the obvious starting points. Cite what each source actually says rather than
attaching it as decoration, and expect at least one principle here to be wrong, incomplete, or
missing from the list entirely.
