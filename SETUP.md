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
echo 'PS1=">"' > ~/.bashrc
```


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

ub run jupyter notebook
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


## 8. Add to docker

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

## 9. pgAdmin 

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

## 10. create docker-compose.yaml

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

## 11 Cleanup


Stop All Running Containers

```bash
docker-compose down
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

# 4 creating main.tf

create file in terraform folder. 

web search for terraform provder e.g. "terraform google provider"

they used https://registry.terraform.io/providers/hashicorp/google/latest/docs

selected "use provider" and copied code to main.tf

4.1 add resources to the main.tf


# 5 create .gitignore 

good search terraform .gitignore & copy

add *.json

test with github private account to make sure all credentials and sensitive files are ignored.

## Still To Install

| Tool | Status |
|------|--------|
| WSL2 + Ubuntu | ✅ Done |
| VS Code + WSL Extension | ✅ Done |
| Docker Engine | ✅ Done |
| Git | ✅ Done |
| SSH Key for GitHub | ✅ Done |
| uv | ✅ Done |
| Python 3.11 (via uv) | ⬜ In progress |
| GCP Account + Project | ⬜ Todo |
| Google Cloud CLI | ⬜ Todo |
| Terraform | ⬜ Todo |

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
