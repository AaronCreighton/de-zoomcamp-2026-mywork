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

## Install PostGreSQL

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



---


## Connect to PostSQL

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



## install jupyter

``` 
uv add --dev jupyter

ub run jupyter notebook
```

## Connect to PostgreSQL in Python/Jupyter

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

## Convert Jupyter to script

```bash
uv run jupyter nbconvert --to=script Notebook.ipynb
mv Notebook.py ingest_data.py

```

## Add to docker

add ingrest_data to dockerfile & then build it. 

```bash
docker build -t taxi_ingrest:v001 .
```


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
