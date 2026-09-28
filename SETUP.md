# Local Development Environment Setup
## Data Engineering Zoomcamp — Windows 11

This guide documents the local development environment setup for the Data Engineering Zoomcamp course, following best practices for data engineering on Windows.

---

## Philosophy

All data engineering work runs inside **Ubuntu via WSL2**. Windows is used only as the GUI layer. This approach matches real production server environments and avoids compatibility issues with Linux-native tools.

---

## Prerequisites

- Windows 11
- Admin rights on your machine
- A GitHub account

---

## Tools Overview

| Tool | Where | Why |
|------|-------|-----|
| **WSL2** | Windows feature | Runs a real Linux kernel inside Windows |
| **Ubuntu** | Inside WSL2 | Your primary working environment — all tools, code and files live here |
| **Docker Engine** | Inside Ubuntu | Runs containers (Postgres etc) without installing them directly. Engine only — no Docker Desktop (licensing + overhead) |
| **Git** | Inside Ubuntu | Version control. Ships pre-installed with Ubuntu |
| **VS Code** | Windows | Code editor. WSL extension connects it to Ubuntu seamlessly |
| **uv** | Inside Ubuntu | Manages Python versions and isolated environments per project. Replaces pyenv + pip in one fast tool |
| **Google Cloud CLI** | Inside Ubuntu | Authenticates and interacts with GCP services from the terminal |
| **Terraform** | Inside Ubuntu | Provisions GCP infrastructure as code |
| **Kestra** | Docker container | Workflow orchestrator. Declarative YAML flows, stored in its own metadata database |
| **Airflow** | Docker containers | Workflow orchestrator. DAGs written in Python, read from files on disk |
| **DuckDB** | Inside Ubuntu, via uv | Embedded analytical database — a file on disk, no server. Local target for dbt Core |
| **dbt Core** | Inside Ubuntu, via uv | Transforms data with SQL models run against a warehouse. Installed with the `dbt-duckdb` adapter |
| **dbt Cloud** | Browser | Hosted dbt, set up through its own wizard and connected to the git repo |

---

> Architectural choices — which orchestration tool(s), which operator type for tasks, and why — are recorded in `DESIGN_DECISIONS.md` rather than here. This file stays focused on installation and setup steps.

---

## Step 1: WSL2 + Ubuntu

WSL2 runs a real Linux kernel inside Windows. All tools, code, and files live here.

Open **PowerShell as Administrator** and run:

```powershell
# Fix execution policy if needed
Set-ExecutionPolicy RemoteSigned -Scope CurrentUser

# Install WSL2 + Ubuntu
wsl --install
```

Restart your machine when prompted. Ubuntu will be available as an app from the Start menu.

```powershell
# check install

wsl --list --verbose
```


Update Ubuntu on first launch:

```bash
sudo apt update && sudo apt upgrade -y
```

---

## Step 2: Docker Engine (inside Ubuntu)

Docker Engine is installed directly inside Ubuntu — not Docker Desktop. This avoids licensing overhead and more closely matches production environments.

```bash
# Install dependencies
sudo apt install ca-certificates curl gnupg -y

# Add Docker's GPG key
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

# Add Docker repository
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker Engine
sudo apt update
sudo apt install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin -y

# Allow running Docker without sudo
sudo usermod -aG docker $USER
```

Close and reopen your Ubuntu terminal, then verify:

```bash
docker run hello-world
docker compose version
```

---

## Step 3: VS Code (Windows) + WSL Extension

VS Code runs on Windows but connects seamlessly into Ubuntu via the WSL extension.

1. Download and install VS Code from [code.visualstudio.com](https://code.visualstudio.com/)
2. Open VS Code → Extensions (`Ctrl+Shift+X`) → search **WSL** → install the Microsoft WSL extension

To open any project in VS Code from Ubuntu:

```bash
code .
```

Confirm **"WSL: Ubuntu"** appears in the bottom left corner of VS Code.


### hide the directory in vs code

```bash
echo 'PS1=">"' >> ~/.bashrc
```

**Use `>>`, not `>`.** Both appear to work — the prompt changes either way — but `>` truncates `~/.bashrc` to zero and replaces the whole file with that one line. That silently removes:

* Ubuntu's stock settings — `ll`/`la` aliases, `ls` and `grep` colour, history tuning
* bash-completion, so tab-completing `git`, `docker` and `apt` stops working
* anything appended by a later step, most importantly uv's PATH line from Step 6

The failure is delayed and looks unrelated: re-running this command on an already-configured machine produces `Command 'uv' not found` the next time you open a terminal.

If it has already been run with `>`, restore the stock file and re-append:

```bash
cat /etc/skel/.bashrc > ~/.bashrc
echo 'PS1=">"' >> ~/.bashrc
echo 'source $HOME/.local/bin/env' >> ~/.bashrc
source ~/.bashrc
```

Order matters — stock file first, your lines after, so the last `PS1` assignment wins.

---

## Step 4: Git (already included with Ubuntu)

Git ships with Ubuntu. Configure your identity — this is attached to every commit:

```bash
git config --global user.name "Your Name"
git config --global user.email "your@email.com"
```

Verify:

```bash
git config --list
```

---

## Step 5: SSH Key for GitHub

SSH authentication means you never need to type your GitHub password.

```bash
# Generate SSH key
ssh-keygen -t ed25519 -C "your@email.com" -f ~/.ssh/id_ed25519

# Copy your public key
cat ~/.ssh/id_ed25519.pub
```

Add the key to GitHub:
1. GitHub → Profile → **Settings** → **SSH and GPG keys** → **New SSH key**
2. Title: `Ubuntu WSL2`
3. Paste the key output
4. Click **Add SSH key**

Test the connection:

```bash
ssh -T git@github.com
# Expected: Hi username! You've successfully authenticated...
```

---

## Step 6: uv (Python Version + Environment Manager)

`uv` replaces pyenv + pip in a single fast tool. It manages Python versions and isolated project environments.

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Add to PATH permanently
echo 'source $HOME/.local/bin/env' >> ~/.bashrc
source ~/.bashrc

# Verify
uv --version
```

---

## Step 7: Project Setup

Create a standard folder structure for all code projects:

```bash
mkdir ~/projects
cd ~/projects
```

Clone your work repository:

```bash
git clone git@github.com:yourusername/de-zoomcamp-2026.git
cd de-zoomcamp-2026
```

Set up Python environment with uv:

```bash
# Initialise project (creates pyproject.toml)
uv init

# it is currently unclear which of these two steps is needed. 
uv venv --python 3.12
uv python pin 3.12

# Activate environment
source .venv/bin/activate

# Install packages (records in pyproject.toml automatically)
uv add pandas pyarrow
```
---

# CSV to PostgreSQL Pipeline Setup

## 1. Install PostGreSQL

see for info on two methods: https://github.com/DataTalksClub/data-engineering-zoomcamp/blob/main/01-docker-terraform/docker-sql/04-postgres-docker.md

```bash
docker run -it --rm \
  -e POSTGRES_USER="root" \
  -e POSTGRES_PASSWORD="root" \
  -e POSTGRES_DB="ny_taxi" \
  -v ny_taxi_postgres_data:/var/lib/postgresql \
  -p 5432:5432 \
  postgres:18
```

## 2. Connect to PostSQL

in order to use pgcli, to acess the db. I needed to install libpq. This needs sudo password from password manager, under ubuntu. 

```bash
uv add --dev pgcli

sudo apt install libpq-dev -y

uv run pgcli -h localhost -p 5432 -u root -d ny_taxi

#validate by running some sql comands. 

```

* `uv run` executes a command in the context of the virtual environment
* `-h` is the host. Since we're running locally we can use `localhost`.
* `-p` is the port.
* `-u` is the username.
* `-d` is the database name.
* The password is not provided; it will be requested after running the command.

When prompted, enter the password: `root`



## 3. install jupyter

``` 
uv add --dev jupyter

uv run jupyter notebook
```

## 4. Connect to PostgreSQL in Python/Jupyter

inside directory in bash:
``` 
uv add sqlalchemy "psycopg[binary,pool]"
``` 

or inside Jupyter

``` 
!uv add sqlalchemy "psycopg[binary,pool]"
``` 


inside jupyter
```jupyter
from sqlalchemy import create_engine
engine = create_engine('postgresql+psycopg://root:root@localhost:5432/ny_taxi')
``` 

## 5. Convert Jupyter to script

```bash
uv run jupyter nbconvert --to=script Notebook.ipynb
mv Notebook.py ingest_data.py

```

## 6. create docker network


```bash
docker network create pg-network

# add network to postgreSQL db & docker for ingest data
# add name to postgreSQL db & host on ingest data

docker run -it --rm \
  -e POSTGRES_USER="root" \
  -e POSTGRES_PASSWORD="root" \
  -e POSTGRES_DB="ny_taxi" \
  -v ny_taxi_postgres_data:/var/lib/postgresql \
  -p 5432:5432 \
  --network=pg-network \
  --name pgdatabase \
  postgres:18
```


## 7. Add to docker

add ingrest_data to dockerfile & then build it. 

```bash

docker build -t taxi_ingest:v001 .

docker run -it --rm \
  --network=pg-network \
  taxi_ingest:v001 \
  --pg-user=root \
  --pg-pass=root \
  --pg-host=pgdatabase \
  --pg-port=5432 \
  --pg-db=ny_taxi \
  --target-table=yellow_taxi_trips
```

## 8. pgAdmin 

pgAdmin is UI instead of pgcli.

```bash
docker run -it \
  -e PGADMIN_DEFAULT_EMAIL="admin@admin.com" \
  -e PGADMIN_DEFAULT_PASSWORD="root" \
  -v pgadmin_data:/var/lib/pgadmin \
  -p 8085:80 \
  --network=pg-network \
  --name pgadmin \
  dpage/pgadmin4

```
note the addition of network and name parameters.

## 9. create docker-compose.yaml

see the file for details

note on first run, the postgre database will not have any data in the tables, as it is a new instance. Thus re-run the ingrestion script. The ingestion script will need to new network.

```bash
docker network ls
```

Then run the ingestion with new netork. 

The network should be called something like "(file name)_default"

e.g. pipeline_default

to execute the compose file

``` bash
docker compose up
```

## 10. Cleanup


Stop All Running Containers

```bash
docker compose down
```

Remove Specific Containers

```bash
# List all containers
docker ps -a

# Remove specific container
docker rm <container_id>

# Remove all stopped containers
docker container prune
```

Remove Docker Images

```bash
# List all images
docker images

# Remove specific image
docker rmi taxi_ingest:v001

# Remove all unused images
docker image prune -a
```

Remove Docker Volumes

```bash
# List volumes
docker volume ls

# Remove specific volumes
docker volume rm ny_taxi_postgres_data
docker volume rm pgadmin_data

# Remove all unused volumes
docker volume prune
```

Remove Docker Networks

```bash
# List networks
docker network ls

# Remove specific network
docker network rm pg-network

# Remove all unused networks
docker network prune
```

Complete Cleanup

Removes ALL Docker resources - use with caution!

```bash
# ⚠️ Warning: This removes ALL Docker resources!
docker system prune -a --volumes
```

Clean Up Local Files

```bash
# Remove parquet files
rm *.parquet

# Remove Python cache
rm -rf __pycache__ .pytest_cache

# Remove virtual environment (if using venv)
rm -rf .venv
```

---

# Terraform 

## 1 install terraform

https://developer.hashicorp.com/terraform/install

can be run from vs code terminal. root password is asked for after first line.

```bash
#2026 instructions for Ubuntu:
wget -O - https://apt.releases.hashicorp.com/gpg | sudo gpg --dearmor -o /usr/share/keyrings/hashicorp-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $(grep -oP '(?<=UBUNTU_CODENAME=).*' /etc/os-release || lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/hashicorp.list
sudo apt update && sudo apt install terraform

```

## 2. get keys for service account

2.1 add serivce account to project on gcp. 

2.2 give service account permission with Role access to: 

Cloud storage Admin, limited to bucket creat & destroy
BigQuery Admin, limit to create data set & destroy data set. 
Compute Engine Admin, limit to create and destroy engine.

2.3 add key to service account

2.4 get jey as json & store it in terraform folder.

e.g. terraform/keys/creds.json

see here for other ways to authenicate (plus the terraform video):
https://github.com/DataTalksClub/data-engineering-zoomcamp/blob/main/01-docker-terraform/terraform/windows.md 

## 3 Add terraform extention to vscode

HashiCorp is the one they recomend.

## 4 creating main.tf

create file in terraform folder. 

web search for terraform provder e.g. "terraform google provider"

they used https://registry.terraform.io/providers/hashicorp/google/latest/docs

selected "use provider" and copied code to main.tf

4.1 add resources to the main.tf


## 5 create .gitignore 

good search terraform .gitignore & copy

add *.json

test with github private account to make sure all credentials and sensitive files are ignored.

## 6 terraform AWS

they also have an example of AWS terraform

https://github.com/DataTalksClub/data-engineering-zoomcamp/tree/main/01-docker-terraform/terraform/terraform/terraform_with_variable_AWS


# Kestra

## install with docker-compose

update the docker-compose file (see folder)

```
docker compose up -d
```
-d stands for detached mode — runs the containers in the background so your terminal is free to use.
Without -d the container logs stream directly to your terminal and you can't use it for anything else until you stop the containers with Ctrl+C.

---

# Airflow

Airflow is set up as its own compose project in a separate folder, so it can run alongside Kestra rather than replacing it.

Unlike Kestra, which stores flows in its metadata database, Airflow reads DAGs as Python files bind-mounted from the host. That is why the directories below must exist before the containers start.

## 1. create the project directories

```bash
mkdir -p ~/projects/de-zoomcamp-2026-mywork/03-airflow-workflow-orchestration
cd ~/projects/de-zoomcamp-2026-mywork/03-airflow-workflow-orchestration

mkdir -p ./dags ./logs ./plugins ./config
echo -e "AIRFLOW_UID=$(id -u)" > .env
```

Without AIRFLOW_UID, files that the containers write into dags, logs, config and plugins are owned by root and cannot be edited from VS Code without sudo.

The `.env` here is read by Docker Compose, not by the shell. VS Code's Python extension may offer to inject it into terminals — decline, it is not needed.

## 2. add a .gitignore

Airflow writes continuously into `logs/`, which should never be committed. The Airflow project publishes its own at https://github.com/apache/airflow/blob/main/.gitignore — that file is aimed at developing Airflow itself, so most of it is irrelevant here, but it is a reasonable starting point.

The entries that actually matter for this project:

```gitignore
logs/
plugins/
.env
airflow.cfg
airflow.db
__pycache__/
```

`.env` holds only `AIRFLOW_UID` so far, but it is the file that would hold credentials later.

## 3. fetch the official docker-compose file

```bash
curl -LfO 'https://airflow.apache.org/docs/apache-airflow/3.3.1/docker-compose.yaml'
```

Pin the version in the URL rather than using `stable`, so a future major release does not silently change what is downloaded.

The official file is used rather than the Astro CLI. Astronomer themselves recommend Docker Compose for open-source local development, and the compose file makes the architecture visible — scheduler, api-server, dag-processor, worker, triggerer, redis and its own postgres are all separate services.

## 4. change the published port to 8090

Kestra already uses 8080. Edit the single ports line for the apiserver:

```yaml
      - "8090:8080"
```

Do NOT find-and-replace 8080 across the file. Only the host side of the published mapping changes. Every other 8080 is container-side, where the app really does listen on 8080:

* `AIRFLOW__CORE__EXECUTION_API_SERVER_URL` — how scheduler and workers reach the api-server over the internal docker network
* the healthcheck `curl` — runs inside the container

Rewriting those points them at a port nothing is listening on, and containers never report healthy.

Verify only the mapping changed:

```bash
grep -n "8080\|8090" docker-compose.yaml
```

## 5. initialise

Before initialising, turn off the bundled example DAGs — set this in `docker-compose.yaml`:

```yaml
AIRFLOW__CORE__LOAD_EXAMPLES: 'false'
```

Then:

```bash
docker compose up airflow-init
```

Runs the database migrations and creates the admin user. It is a one-shot service, so it exits rather than staying up. Look for `airflow-init-1 exited with code 0`.

Default login is `airflow` / `airflow`.

Airflow 3 does this natively. The 2022 course used a custom `entrypoint.sh` for it, which is no longer needed.

If the examples were already loaded, flipping the flag alone may leave them as stale records. To clear them out completely:

```bash
docker compose down --volumes
# set AIRFLOW__CORE__LOAD_EXAMPLES to 'false'
docker compose up airflow-init
docker compose up -d
```

`--volumes` wipes the metadata database, so only do this before there is any DAG history worth keeping.

## 6. run

```bash
docker compose up -d
docker ps
```

UI at http://localhost:8090

## 7. add pgdatabase and pgadmin

The Airflow compose file only brings up Airflow. Copy the `pgdatabase` and `pgadmin` services over from the Kestra compose file so this project has its own `ny_taxi` database, the same way the Kestra project does.

Two changes when copying:

* **Host ports must move.** Kestra's project already binds 5432 and 8085. Change the left-hand number only — the container side stays as it is.
* **Repoint `depends_on`.** The Kestra version waits on `kestra`, which does not exist here. Point it at `airflow-apiserver` with `condition: service_healthy`.

```yaml
  pgdatabase:
    image: postgres:18
    environment:
      POSTGRES_USER: root
      POSTGRES_PASSWORD: root
      POSTGRES_DB: ny_taxi
    ports:
      - "5433:5432"
    volumes:
      - ny_taxi_postgres_data:/var/lib/postgresql
    depends_on:
      airflow-apiserver:
        condition: service_healthy

  pgadmin:
    image: dpage/pgadmin4
    environment:
      - PGADMIN_DEFAULT_EMAIL=admin@admin.com
      - PGADMIN_DEFAULT_PASSWORD=root
    ports:
      - "8086:80"
    volumes:
      - pgadmin_data:/var/lib/pgadmin
```

Add to the `volumes:` block at the bottom of the file, alongside `postgres-db-volume`:

```yaml
  ny_taxi_postgres_data:
  pgadmin_data:
```

> Why `pgdatabase` depends on the Airflow api-server's health, and the trade-offs of that choice, are recorded in `DESIGN_DECISIONS.md` under Airflow.

To start the database without waiting on the rest of the Airflow stack:

```bash
docker compose up -d --no-deps pgdatabase
```

Each compose project gets its own prefixed volume, so this `ny_taxi` is a separate, empty database from Kestra's. It needs its own ingestion run. For comparing the two orchestrators that is an advantage — neither can contaminate the other's results.

## port allocation

Host ports are machine-wide, so they collide across compose projects even though each file only mentions its own. These values let both stacks run at the same time.

| Host port | Service | Project |
|------|---------|---------|
| 5432 | pgdatabase (ny_taxi) | Kestra |
| 5433 | pgdatabase (ny_taxi) | Airflow |
| 8080, 8081 | Kestra | Kestra |
| 8085 | pgAdmin | Kestra |
| 8086 | pgAdmin | Airflow |
| 8090 | Airflow api-server | Airflow |

Both metadata databases — Kestra's and Airflow's — are unpublished, so they never collide.

**Container ports never change.** A mapping is `host:container`, and only the left side can clash. Inside its own container every Postgres still listens on 5432 and pgAdmin on 80. This is why:

* A DAG connects to host `pgdatabase` on port **5432**, not 5433. Container-to-container traffic does not use the published port.
* pgcli from Ubuntu connects on **5433**, because that connection starts on the host.

## testing DAGs

To manually run one interval of a DAG and confirm it works before relying on the schedule or a full backfill:

1. Open the DAG in the UI and use **Trigger DAG**
2. Type the logical date directly into the date field rather than using the calendar picker — the picker defaults to now and is fiddly to move back to an arbitrary past month
3. Trigger, and check the run's logical date matches what was typed
4. Repeat with a different logical date to test another month

`start_date` and `logical_date` must be timezone-aware (`pendulum.datetime(..., tz="UTC")`, not plain `datetime(...)`) or the scheduler can silently anchor runs to the current date instead of the DAG's intended range — this was the cause the first time a run showed today's date instead of the expected historical one.

A manual trigger with no logical date specified always defaults to now. This is expected behaviour, not a bug — it is not the same thing as catchup or backfill, neither of which happen automatically. Once individual months have been confirmed this way, backfill is the tool for populating the full historical range in one action rather than triggering each month by hand.

## 8. Google provider and GCP connection

Add `apache-airflow-providers-google` to `requirements.txt`, then switch the compose file to the custom image — uncomment `build: .`, comment out `image:`. Use `pip` in the Dockerfile, not `uv`.

Mount a `keys/` folder into the containers and put the service account JSON there. Add `keys/` to `.gitignore`.

Set `AIRFLOW__CORE__TEST_CONNECTION: 'Enabled'` so the Test button works.

Create a Google Cloud connection with the key path and project ID, then test it.

Put bucket, dataset and project in `.env` as `AIRFLOW_VAR_*`.

Gotchas are recorded in `AIRFLOW_DAG_MIGRATION.md` under G1.

---

# DuckDB

```bash
uv add duckdb
```

---

# dbt

## dbt Cloud

Course instructions live at `04-dbt-analytics-engineering/setup/cloud_setup.md`. This section holds only what differs from or is missing there.

- Create the project directory `04-dbt-analytics-engineering` and a subfolder for the actual dbt project, with a `README.md` in each
- The course video is old and doesn't show a project setup wizard at all, so the actual wizard steps — including connecting to the git repo and setting the project subdirectory — aren't covered there
- **Observation, not a fixed step:** the subdirectory field wasn't obviously labelled — it was tucked under whatever field is titled "Project Name" rather than something clearly called "Subdirectory" or "Project path". Flagging this as something to look for rather than a numbered instruction, since the dbt Cloud free tier only allows one project, so this can't be reproduced or re-verified, and the wizard's layout can change without notice.

## dbt Core

Course instructions at `04-dbt-analytics-engineering/setup/local_setup.md`. The steps below cover what the course video shows but doesn't document — mainly the project layout, which the video mentions changing but never actually does.

Target layout — one level, with the Python environment and the dbt project files side by side, matching what dbt Cloud reads from its configured subdirectory:

```
04-dbt-analytics-engineering/
└── <project>/
    ├── .venv/
    ├── pyproject.toml
    ├── dbt_project.yml
    ├── models/
    └── ...
```

**1. Create the project folder.** This is the dbt project root, and where dbt Cloud's subdirectory setting should point.

```bash
mkdir -p ~/projects/de-zoomcamp-2026-mywork/04-dbt-analytics-engineering/<project>
cd ~/projects/de-zoomcamp-2026-mywork/04-dbt-analytics-engineering/<project>
```

**2. Create the Python environment inside it.** `--bare` creates only `pyproject.toml`, avoiding a `README.md` that would collide with dbt's in step 5.

```bash
uv init --bare
uv python pin 3.13
uv add dbt-duckdb
```

**3. Create `profiles.yml`.** dbt looks in `~/.dbt/profiles.yml` by default, not the project folder.

```bash
mkdir -p ~/.dbt
code ~/.dbt/profiles.yml
```

Paste in the profile and save. `code` creates the file on save but won't create the folder, hence `mkdir -p` first. `nano ~/.dbt/profiles.yml` works too (`Ctrl+O`, `Enter`, `Ctrl+X` to save and exit). The course video uses `open`, which is macOS-only and errors on a missing file.

**4. Run `dbt init` inside the project folder**, using the profile name as the project name so the two match. `--skip-profile-setup` stops it prompting for or overwriting the profile from step 3.

```bash
uv run dbt init <profile-name> --skip-profile-setup
```

**5. Move the files up.** `dbt init` creates a subfolder; move its contents into the project folder so everything sits at one level, then delete the empty subfolder. Either move them manually in VS Code's explorer, or from the terminal:

```bash
shopt -s dotglob
mv <profile-name>/* .
rmdir <profile-name>
shopt -u dotglob
```

`dotglob` makes `*` include dotfiles — `dbt init` creates a `.gitignore`, and without it `rmdir` fails on a folder that looks empty.

**6. Check the profile names match** — `profile:` in `dbt_project.yml` against the top-level key in `profiles.yml`.

```bash
grep profile dbt_project.yml
cat ~/.dbt/profiles.yml
```

**7. Confirm dbt can connect.**

```bash
uv run dbt debug
```

To keep the profile inside the project instead — reasonable for DuckDB since there's no credential to protect from git, unlike a warehouse password — use `--profiles-dir <path>` on every dbt command, or set `DBT_PROFILES_DIR` so it's automatic.

**dbt Power User (AltimateAI):** the extension needs pointing at an environment where `dbt` is importable, and prompts to install dbt Core if it can't find one. Detecting from the terminal picks up the project venv, but the setting it writes is:

```json
// .vscode/settings.json
{
    "dbt.dbtPythonPathOverride": "/home/aaron/projects/.../local_duckdb_taxi/.venv/bin/python3"
}
```

An absolute path with no variable in it, so it breaks silently if the venv moves. Worth re-checking after any project restructure.

`.vscode/settings.json` is workspace-scoped — it has to sit at whatever folder is opened as the workspace root. And the path is machine-specific, so it isn't meaningfully shareable if `.vscode/` is committed.

---

## Still To Install



| Tool | Status |
|------|--------|
| WSL2 + Ubuntu | ✅ Done |
| VS Code + WSL Extension | ✅ Done |
| Docker Engine | ✅ Done |
| Git | ✅ Done |
| SSH Key for GitHub | ✅ Done |
| uv | ✅ Done |
| Python 3.11 (via uv) | ✅ Done |
| GCP Account + Project | ✅ Done |
| Terraform | ✅ Done |
| Postgres (via Docker) | ✅ Done |
| pgAdmin (via Docker) | ✅ Done |
| Kestra (via Docker) | ✅ Done |
| Airflow (via Docker) | ✅ Done |
| dbt Cloud | ✅ Done |
| DuckDB | ⬜ Todo |
| dbt Core | ⬜ Todo |
| pgcli | ✅ Done |
| JupyterLab | ✅ Done |
| Google Cloud CLI | ⬜ Todo |

---

## Quick Reference

| Check | Command |
|-------|---------|
| WSL version | `wsl --list --verbose` |
| Docker running | `docker run hello-world` |
| Git identity | `git config --list` |
| SSH to GitHub | `ssh -T git@github.com` |
| uv version | `uv --version` |
| Python version | `python3 --version` |
| Active environment | `which python` |
