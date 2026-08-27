# Tools Health Check & Memory Refresh
## Data Engineering Zoomcamp — Windows 11 / WSL2

Use this document each time you return to the project after a break. Work through each step in order — each one builds on the previous.

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

## Step 3 — Activate Python Environment & Verify Packages

Navigate to the pipeline directory and activate the virtual environment:
```bash
cd 01-docker-terraform/pipeline
source .venv/bin/activate
```

Confirm the virtual environment is active:
```bash
which python
```

Expected output:
```
/home/aaron/projects/de-zoomcamp-2026-mywork/01-docker-terraform/pipeline/.venv/bin/python
```

Verify key packages are available:
```bash
uv run python -c "import pandas; import sqlalchemy; import pyarrow; print('all packages ok')"
```

Expected output:
```
all packages ok
```

| Result | Meaning |
|--------|---------|
| ✅ `(pipeline)` in terminal prompt | Virtual environment is active |
| ✅ `which python` points to `.venv` | Correct Python is being used, not system Python |
| ✅ `all packages ok` printed | All required packages are installed |
| ❌ `(pipeline)` not in prompt | Run `source .venv/bin/activate` |
| ❌ `which python` points to `/usr/bin/python` | Virtual environment not active — run activate command |
| ❌ `ModuleNotFoundError` | Package missing — run `uv add <package-name>` |

---

## Step 4 — Verify Core Tools

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

## Step 5 — Check Git Status

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

## Step 6 — Start Docker Services

> **Note:** Only start the `02-kestra-workflow-orchestration` compose file — it includes all services. Never run both compose files at the same time as they share port 5432.

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

## Step 7 — Re-import Kestra Flows (if fresh volume) (if fresh volume)

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
4. Verify data in Postgres via Step 7

| Result | Meaning |
|--------|---------|
| ✅ All flows listed in Kestra UI | Flows imported successfully |
| ✅ Row count returns 7667792 | Data ingested successfully |
| ❌ curl returns 401 | Check username and password in the curl command |
| ❌ Workflow fails | Check Kestra logs in the UI for error details |

---

---

## Step 8 — Verify Postgres Data

Connect to the database via pgcli:
```bash
cd ~/projects/de-zoomcamp-2026-mywork/01-docker-terraform/pipeline
uv run pgcli -h localhost -p 5432 -u root -d ny_taxi
```

When prompted enter password: `root`

Then inside pgcli run:
```sql
-- run each line seperately.

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
| ❌ No tables listed | Volume was recreated fresh — re-import flows via Step 7 and re-ingest data |
| ❌ Connection refused | Postgres container not running — go back to Step 6 |

---

---

## Step 9 — Verify UIs in Browser

### pgAdmin
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
| ❌ No tables in ny_taxi | Data not ingested — go back to Step 8 |

---

### Kestra
Open **localhost:8080** and login:
- Email: `admin@kestra.io`
- Password: `Admin1234!`

Then verify:
1. Go to **Flows** — confirm workflows are listed
2. Go to **Executions** — confirm last run of `04_postgre_taxi` shows as success
3. Trigger a test run — select yellow / 2019 / 01 and confirm it completes successfully

> **Note:** If flows are missing, run the curl import loop from Step 7.

| Result | Meaning |
|--------|---------|
| ✅ Flows listed and last execution successful | Kestra is working correctly |
| ❌ No flows listed | Re-import flows via Step 7 |
| ❌ Execution failed | Check Kestra logs in the UI for error details |

---

## Step 10 — GCP & Terraform

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

## Summary

| Step | Check | Status |
|------|-------|--------|
| 1 | WSL2 environment | ✅ |
| 2 | Project directory and contents | ✅ |
| 3 | Python environment and packages | ✅ |
| 4 | Core tools installed and versioned | ✅ |
| 5 | Git status and history | ✅ |
| 6 | Docker images, volumes and services | ✅ |
| 7 | Kestra flows imported | ✅ |
| 8 | Postgres data verified via pgcli | ✅ |
| 9 | pgAdmin and Kestra UIs working | ✅ |
| 10 | GCP & Terraform | ⚠️ Needs new GCP account |