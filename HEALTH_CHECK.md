# Tools Health Check & Memory Refresh
## Data Engineering Zoomcamp — Windows 11 / WSL2

Use this document each time you return to the project after a break. Work through each step in order — each one builds on the previous.

## Which sections to run

Always run the base checks first. Then run only the sub-project section(s) for what you're resuming — no need to touch the others.

| Section | Steps | Covers |
|---|---|---|
| Base health check | 1–4 | WSL2, project directory, core tools, git |
| 01-docker-terraform | Step 5 (Terraform) only | No dedicated bring-up section yet for this module's own Docker Postgres/pgAdmin — only Terraform is currently covered |
| K — Kestra | K1–K4 | Docker services, flow import, Postgres data, UIs |
| A — Airflow | A1–A7 | Docker services, env vars, DAG parsing, DAG run, Postgres data |

---

## Step 1 — Confirm WSL2 Environment

Before anything else, confirm you are working inside WSL2/Ubuntu and not a Windows terminal.

Run:
```bash
uname -a
```

Expected output:
```
Linux Cookie 6.6.87.2-microsoft-standard-WSL2 #1 SMP PREEMPT_DYNAMIC Thu Jun 5 18:30:46 UTC 2025 x86_64 x86_64 x86_64 GNU/Linux
```

What to look for:
- `Linux` at the start
- `WSL2` in the kernel name
- `x86_64` architecture

| Result | Meaning |
|--------|---------|
| ✅ Output contains `WSL2` | You are in the correct Ubuntu environment |
| ❌ Command not found or no `WSL2` | You are in a Windows terminal — open Ubuntu instead |

---

## Step 2 — Navigate to Project & Confirm Contents

First check where you are:
```bash
pwd
```

Expected output:
```
/home/aaron/projects/de-zoomcamp-2026-mywork
```

If not already there, navigate to the project:
```bash
cd ~/projects/de-zoomcamp-2026-mywork
pwd
```

Expected output:
```
/home/aaron/projects/de-zoomcamp-2026-mywork
```

Confirm the project contents are intact:
```bash
ls
```

Expected output:
```
01-docker-terraform  02-workflow-orchestration  README.md  SETUP.md
```

| Result | Meaning |
|--------|---------|
| ✅ Both module folders visible | Project is intact and you are in the right place |
| ❌ Wrong directory from `pwd` | Navigate using `cd ~/projects/de-zoomcamp-2026-mywork` |
| ❌ Module folders missing from `ls` | Project files may have been deleted — check `git status` |

---

## Step 3 — Verify Core Tools

Run each command and confirm the tool is available:
```bash
docker --version
terraform --version
uv --version
git --version
```

Expected output (versions recorded at time of setup):
```
Docker version 29.2.1, build a5c7197
Terraform v1.14.8
uv 0.10.8
git version 2.43.0
```

| Result | Meaning |
|--------|---------|
| ✅ All four return version numbers | All core tools installed and available |
| ⚠️ Terraform reports a newer version available | Not critical — update when convenient via hashicorp.com |
| ❌ `command not found` for any tool | Tool not installed or not on PATH — refer to SETUP.md |

> **Note:** Version numbers will increase over time as tools are updated. What matters is that each command returns a version number, not that it matches exactly.

---

## Step 4 — Check Git Status

From the project root:
```bash
cd ~/projects/de-zoomcamp-2026-mywork
git status
git log --oneline -10
```

Expected `git status` output:
```
On branch main
Your branch is up to date with 'origin/main'.
nothing to commit, working tree clean
```

Expected `git log` output — a list of your recent commits, most recent at the top:
```
ff9803a (HEAD -> main, origin/main, origin/HEAD) add tool name to folder & readme
c240c23 add remaining files to workflow
...
```

| Result | Meaning |
|--------|---------|
| ✅ `up to date with 'origin/main'` | Local code matches GitHub |
| ✅ `nothing to commit` | No uncommitted changes |
| ⚠️ `Changes not staged for commit` | You have uncommitted local changes — commit, discard or note before continuing |
| ⚠️ `Your branch is behind` | GitHub has newer changes — run `git pull` |
| ❌ `not a git repository` | You are in the wrong directory |

**If you have uncommitted changes:**
```bash
# Commit and push
git add .
git commit -m "your message"
git push

# Or discard changes
git restore <filename>
```

---

## Step 5 — GCP & Terraform (01-docker-terraform)

GCP free trials expire after 90 days. First check which route applies:

**Route A — Existing account still active:**

Log in to [console.cloud.google.com](https://console.cloud.google.com) and confirm billing is active. Then run:

```bash
cd ~/projects/de-zoomcamp-2026-mywork/01-docker-terraform/terraform
terraform apply
```

Expected output if resources already exist:
```
No changes. Your infrastructure matches the configuration.
Apply complete! Resources: 0 added, 0 changed, 0 destroyed.
```

Expected output if resources need to be created:
```
Apply complete! Resources: 2 added, 0 changed, 0 destroyed.
```

The 2 resources are:
- GCS bucket: `de-zoomcamp-terraform-493201-demo-bucket`
- BigQuery dataset: `demo_dataset`

---

**Route B — Account expired, new account needed:**

1. Create a new GCP account and project at [console.cloud.google.com](https://console.cloud.google.com)
2. Create a service account with BigQuery and GCS permissions and download the credentials JSON key
3. Update `variables.tf` with the new project ID and credentials path
4. Clear the old Terraform state files — they reference resources from the old account:
```bash
cd ~/projects/de-zoomcamp-2026-mywork/01-docker-terraform/terraform
rm terraform.tfstate
rm terraform.tfstate.backup
```
5. Then run:
```bash
terraform init
terraform apply
```

Expected output:
```
Apply complete! Resources: 2 added, 0 changed, 0 destroyed.
```

---

| Result | Meaning |
|--------|---------|
| ✅ `No changes` | Terraform state matches GCP infrastructure |
| ✅ `2 added` | Resources created successfully |
| ❌ Billing disabled | Free trial expired — follow Route B |
| ❌ Authentication error | Credentials not set up correctly — check variables.tf |

---

# K — Kestra (02-kestra-workflow-orchestration)

## K1 — Start Docker Services

> **Note:** Only start the `02-kestra-workflow-orchestration` compose file — it includes all Kestra-related services. Never run this and the Airflow compose file's `pgdatabase` at the same time on the same ports — see the port table in the A section.

First check that Docker images are cached locally — if any are missing, the compose up will need to pull them which can take 20-30 minutes:
```bash
docker images
```

Expected images:
```
REPOSITORY          TAG
kestra/kestra       v1.1
postgres            18
dpage/pgadmin4      latest
```

| Result | Meaning |
|--------|---------|
| ✅ All three images listed | Compose up will be fast |
| ❌ `kestra/kestra` missing | Will need to pull — allow 20-30 minutes |
| ❌ `postgres` or `pgadmin4` missing | Will need to pull — allow a few minutes |

Then check what volumes already exist before starting services:
```bash
docker volume ls
```

What to look for:

| Volume name contains | Meaning |
|---------------------|---------|
| `02-kestra-workflow-orchestration_ny_taxi_postgres_data` | Current ny_taxi data volume — data should be intact |
| `02-kestra-workflow-orchestration_kestra_*` | Current kestra volumes |
| `pipeline_ny_taxi_postgres_data` | Old volume from module 1 pipeline — data may be here if current is empty |
Then start the services and verify all containers are running:
```bash
cd ~/projects/de-zoomcamp-2026-mywork/02-kestra-workflow-orchestration
docker compose up -d
docker ps
```

Expected `docker ps` output — all 4 containers running:

| Container | Image | Port |
|-----------|-------|------|
| pgdatabase | postgres:18 | 5432 |
| pgadmin | dpage/pgadmin4 | 8085 |
| kestra | kestra/kestra:v1.1 | 8080-8081 |
| kestra_postgres | postgres:18 | internal only |

| Result | Meaning |
|--------|---------|
| ✅ All 4 containers show `Up` in STATUS | All services started correctly |
| ⚠️ `kestra_postgres` shows `health: starting` | Normal on first start — wait 30 seconds and run `docker ps` again |
| ❌ Port already allocated error | Another compose stack is running — run `docker compose down` from the other directory first |
| ❌ Container shows `Exited` | Container failed to start — run `docker logs <container_name>` to investigate |

---

## K2 — Re-import Kestra Flows (if fresh volume)

> Only needed if Kestra has no workflows — i.e. after a fresh volume was created.

Import all flows in one command from the terminal:
```bash
for flow in ~/projects/de-zoomcamp-2026-mywork/02-kestra-workflow-orchestration/flows/*.yaml; do
  curl -X POST http://localhost:8080/api/v1/flows/import     -H "Content-Type: multipart/form-data"     -u admin@kestra.io:Admin1234!     -F "fileUpload=@$flow"
done
```

Then verify flows imported correctly:
1. Open **localhost:8080** in your browser
2. Login with `admin@kestra.io` / `Admin1234!`
3. Go to **Flows** in the left sidebar
4. Confirm all flows are listed

Then trigger the ingestion workflow to repopulate data:
1. Select `04_postgre_taxi` workflow
2. Trigger a run — select yellow / 2019 / 01
3. Wait for it to complete successfully
4. Verify data in Postgres via K3

| Result | Meaning |
|--------|---------|
| ✅ All flows listed in Kestra UI | Flows imported successfully |
| ✅ Row count returns 7667792 | Data ingested successfully |
| ❌ curl returns 401 | Check username and password in the curl command |
| ❌ Workflow fails | Check Kestra logs in the UI for error details |

---

## K3 — Verify Postgres Data

pgcli is installed as a dev dependency of the `01-docker-terraform/pipeline` project, so `uv run` must be invoked from inside that directory — it isn't available globally.

```bash
cd ~/projects/de-zoomcamp-2026-mywork/01-docker-terraform/pipeline
uv run pgcli -h localhost -p 5432 -u root -d ny_taxi
```

When prompted enter password: `root`

Then inside pgcli run:
```sql
\dt
SELECT COUNT(*) FROM yellow_tripdata;
\q
```

Expected output:
```
+--------+-------------------------+-------+-------+
| Schema | Name                    | Type  | Owner |
|--------+-------------------------+-------+-------|
| public | yellow_tripdata         | table | root  |
| public | yellow_tripdata_staging | table | root  |
+--------+-------------------------+-------+-------+

+---------+
| count   |
|---------|
| 7667792 |
+---------+
```

| Result | Meaning |
|--------|---------|
| ✅ Tables listed and row count returned | Data is intact and Postgres is working |
| ❌ No tables listed | Volume was recreated fresh — re-import flows via K2 and re-ingest data |
| ❌ Connection refused | Postgres container not running — go back to K1 |

---

## K4 — Verify UIs in Browser

#### pgAdmin
Open **localhost:8085** and login:
- Email: `admin@admin.com`
- Password: `root`

Add a server connection if not already saved:

| Field | Value |
|-------|-------|
| Name | ny_taxi |
| Host | pgdatabase |
| Port | 5432 |
| Database | ny_taxi |
| Username | root |
| Password | root |

Then verify:
1. Navigate to the `ny_taxi` database
2. Confirm `yellow_tripdata` and `yellow_tripdata_staging` tables are present
3. Run a quick count query to confirm data is intact:
```sql
SELECT COUNT(*) FROM yellow_tripdata;
```

| Result | Meaning |
|--------|---------|
| ✅ Tables visible and row count returns | pgAdmin connected and data intact |
| ✅ `postgres` database is empty | Expected — this is the default system database |
| ❌ Cannot connect to server | Check pgdatabase container is running via `docker ps` |
| ❌ No tables in ny_taxi | Data not ingested — go back to K3 |

---

#### Kestra
Open **localhost:8080** and login:
- Email: `admin@kestra.io`
- Password: `Admin1234!`

Then verify:
1. Go to **Flows** — confirm workflows are listed
2. Go to **Executions** — confirm last run of `04_postgre_taxi` shows as success
3. Trigger a test run — select yellow / 2019 / 01 and confirm it completes successfully

> **Note:** If flows are missing, run the curl import loop from K2.

| Result | Meaning |
|--------|---------|
| ✅ Flows listed and last execution successful | Kestra is working correctly |
| ❌ No flows listed | Re-import flows via K2 |
| ❌ Execution failed | Check Kestra logs in the UI for error details |

---

# A — Airflow (02-airflow-workflow-orchestration)

Steps 1–5 (base checks) must pass first. This section brings the Airflow stack back up and verifies it end to end — written for the case where everything was cleanly shut down, not torn down.

For the reasoning behind choices referenced below (why `pgdatabase` depends on the apiserver, why Airflow gets its own separate Postgres), see `DESIGN_DECISIONS.md`.

## A1 — Check images and volumes are still present

```bash
docker images
docker volume ls
```

Expected images — note two different Postgres versions coexist here: `postgres:16` is Airflow's own metadata database, entirely separate from this project's own `pgdatabase` (running `postgres:18`, same version as Kestra's):

```
apache/airflow:3.3.1                                                  ← base image the Dockerfile builds from
02-airflow-workflow-orchestration-airflow-apiserver:latest            ← built
02-airflow-workflow-orchestration-airflow-scheduler:latest            ← built
02-airflow-workflow-orchestration-airflow-dag-processor:latest        ← built
02-airflow-workflow-orchestration-airflow-worker:latest                ← built
02-airflow-workflow-orchestration-airflow-triggerer:latest             ← built
02-airflow-workflow-orchestration-airflow-init:latest                  ← built, one-shot, only runs during setup
postgres:16                                                           ← Airflow's own metadata DB
postgres:18                                                           ← this project's ny_taxi pgdatabase
redis:7.2-bookworm                                                    ← required by the default CeleryExecutor
dpage/pgadmin4:latest                                                 ← this project's own pgAdmin
```

The six `02-airflow-workflow-orchestration-*` images are built, not pulled — one per service, because `build: .` with `image:` commented out gives each service its own implicit image rather than sharing one. They each report a large total size, but the true per-image cost on top of the shared base layers is only around 660MB — not six times the base image's size.

`postgres:18` and `dpage/pgadmin4` are the same image names Kestra's project also uses — if both projects have been pulled, `docker images` shows only one copy of each, shared between them; this doesn't distinguish which project it belongs to.

Expected volumes (names will be prefixed with the compose project name):
```
02-airflow-workflow-orchestration_postgres-db-volume
02-airflow-workflow-orchestration_ny_taxi_postgres_data
02-airflow-workflow-orchestration_pgadmin_data
```

| Result | Meaning |
|--------|---------|
| ✅ All images and volumes listed | Nothing was deleted; a plain `up -d` should restore full state |
| ❌ Volumes missing | Something was torn down with `--volumes` since last session — `airflow-init` and DAG data will both need re-doing, see A5 and A7 |
| ❌ None of the six `02-airflow-workflow-orchestration-*` images present, only base `apache/airflow` | Built images were removed — check `docker-compose.yaml` still has `build: .` uncommented, not `image:` |
| ❌ Some but not all six built images present | One service's build failed or was skipped previously — `docker compose build` should recreate the missing one(s) |
| ❌ `redis` missing | Required by the default CeleryExecutor; `docker compose up -d` should pull it automatically |

---

## A2 — Start the stack

```bash
cd ~/projects/de-zoomcamp-2026-mywork/02-airflow-workflow-orchestration
docker compose up -d
docker ps
```

Expect 9 containers: `airflow-apiserver`, `airflow-scheduler`, `airflow-dag-processor`, `airflow-worker`, `airflow-triggerer`, the Airflow metadata `postgres`, `redis`, plus this project's own `pgdatabase` and `pgadmin`.

| Result | Meaning |
|--------|---------|
| ✅ All 9 show `Up`/`healthy` | Stack started correctly |
| ⚠️ `pgdatabase` takes noticeably longer to start than the rest | Expected — it has `depends_on: airflow-apiserver, condition: service_healthy`, a deliberate choice logged in `DESIGN_DECISIONS.md`. It waits for the apiserver to report healthy first |
| ❌ Port already allocated (8090, 5433, or 8086) | Another process or stack already holds that port — check nothing from a previous session is still up with `docker ps -a` across other projects |
| ❌ `airflow-apiserver` never reaches healthy, `pgdatabase` never starts | Apiserver problem — check its logs; `pgdatabase` is blocked behind it by design, see the `depends_on` entry in `DESIGN_DECISIONS.md` |

---

## A3 — Confirm environment variables actually reached the containers

This is the specific failure that cost the most time tonight: the compose file having the right `environment:` block doesn't mean a running container has it, if that container was started before the block was added. Since this is a fresh `up -d` on an unchanged compose file, this should pass — but it's the single most valuable 10-second check available if anything downstream misbehaves.

```bash
docker compose exec airflow-scheduler env | grep PG_
```

| Result | Meaning |
|--------|---------|
| ✅ `PG_USER`, `PG_HOST`, `PG_PORT`, `PG_DATABASE` etc. all show real values | Environment reached the container correctly |
| ❌ Empty or missing | Recreate the containers: `docker compose up -d` (compose detects config changed and recreates); if that doesn't fix it, check `.env` still has the right values and `env_file:`/`environment:` in the compose file still reference them |

---

## A4 — Confirm the DAG parses with no import errors

```bash
docker compose exec airflow-scheduler ls -la /opt/airflow/dags
```

Then check the Airflow UI (**localhost:8090**) → DAGs list. The ingestion DAG should appear with no red "Broken DAG" banner.

| Result | Meaning |
|--------|---------|
| ✅ DAG listed, no import errors | dag-processor parsed it cleanly |
| ❌ `ModuleNotFoundError` | Check sibling file exists and — case-sensitively — matches the import statement exactly (`ingest_task.py` vs `Ingest_task.py` caused this once already) |
| ❌ `SyntaxError` | Check the file for a plain typo — a capitalized `From`/`Import` caused this once already |
| ❌ DAG missing entirely from the list | dag-processor may not have picked it up yet — wait ~30 seconds, it polls rather than watching instantly |

---

## A5 — Log in and confirm the DAG is unpaused

Open **localhost:8090**, login `airflow` / `airflow`. Find the ingestion DAG and toggle it on if it's paused (new/recreated DAGs default to paused).

---

## A6 — Test one run manually before trusting the schedule

Trigger the DAG with a specific logical date typed directly into the field (not the calendar picker — defaults to now and is awkward to move back). Must be on or after the DAG's `start_date` — `2021-01-01`, or a couple of months after, both work.

| Result | Meaning |
|--------|---------|
| ✅ Run succeeds, logical date matches the month requested | DAG logic confirmed working |
| ❌ `Connection refused` on port 5433 | `PG_PORT` is set to the host-side port (5433) instead of the container-side port (5432) — container-to-container traffic never uses the published mapping |
| ❌ Values print as the string `'None'` | A value is being read via `os.getenv()` at module level / inside `op_kwargs` rather than inside the task callable — captured once at parse time rather than read at run time |

---

## A7 — Verify Postgres data

Open **localhost:8086**, add a server connection if not already saved. Use `.env` values to connect.

Find the table name in the UI — expand the connection's tree: Databases → the database from `.env` → Schemas → public → Tables.

The source files contain more than one month's data. To compare file names to table names, if the table already exists, drop and run again.

| Result | Meaning |
|--------|---------|
| ✅ Table exists, month matches A6's logical date | Data intact and correct |
| ❌ No tables | Either a genuinely fresh volume (see A1) or A6 hasn't been run yet this session |
| ❌ Table exists but month doesn't match | Recheck the logical date used in A6, or the DAG's date-handling logic |

---


## Summary

| Section | Step | Check |
|---|---|---|
| Base | 1 | WSL2 environment |
| Base | 2 | Project directory and contents |
| Base | 3 | Core tools installed and versioned |
| Base | 4 | Git status and history |
| 01-docker-terraform | 5 | GCP & Terraform — ⚠️ needs new GCP account, see Route B |
| K — Kestra | K1 | Docker images, volumes and services |
| K — Kestra | K2 | Flows imported |
| K — Kestra | K3 | Postgres data verified via pgcli |
| K — Kestra | K4 | pgAdmin and Kestra UIs working |
| A — Airflow | A1 | Docker images and volumes present |
| A — Airflow | A2 | Stack started, 9 containers healthy |
| A — Airflow | A3 | Environment variables reached containers |
| A — Airflow | A4 | DAG parses with no import errors |
| A — Airflow | A5 | DAG unpaused |
| A — Airflow | A6 | Manual run succeeds with correct logical date |
| A — Airflow | A7 | Postgres data verified via pgcli |
| A — Airflow | A8 | Airflow and pgAdmin UIs working |