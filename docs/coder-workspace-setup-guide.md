# Coder Workspace Setup: Step-by-Step Guide

This guide walks through the complete process of setting up a Coder-based student workspace environment for agentic AI courses. It incorporates all lessons learned from the initial implementation (see `coder-implementation-issues.md` for the issues encountered and their root causes).

**Prerequisites:**

- A GitHub account with a repository containing the course material
- Docker Desktop (or Docker Engine) on your local machine
- A VPS provisioned with 16–32 GB RAM

---

## Step 1: Prepare the GitHub Repository

Ensure your course repository is pushed to GitHub with all the latest changes. The workspace will clone this repo at startup.

```bash
# From your local repo
git add -A
git commit -m "Your latest changes"
git push origin main
```

**Verify:** Open the repo on GitHub and confirm the key files are present:

- `db/session.py` contains `DB_BACKEND` switch
- `Dockerfile.workspace` exists
- `coder-template/main.tf` exists
- `requirements.txt` includes `chromadb`

---

## Step 2: Build and Push the Workspace Image

### 2.1 Authenticate Docker with GHCR

On your **local machine**:

```bash
# Create a PAT at GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)
# Scope: write:packages
echo "<YOUR_PAT>" | docker login ghcr.io -u <YOUR_GITHUB_USERNAME> --password-stdin
```

### 2.2 Build for the correct architecture

**Critical:** If you're on a Mac with Apple Silicon, you MUST specify `--platform linux/amd64` for the image to run on an x86_64 VPS.

**Critical:** Use `--output type=registry` instead of `--push`. The `--push` flag uses buildx's internal push cache which can silently fail to update the registry manifest. `--output type=registry` pushes directly to the registry, bypassing that cache. See `coder-implementation-issues.md` Issue 14 for details.

```bash
cd /path/to/your/repo

# Clear buildx cache to ensure a fresh build
docker buildx prune -af

# Build for AMD64 and push directly to registry
docker buildx build --platform linux/amd64 --no-cache --output type=registry \
  -t ghcr.io/<YOUR_GITHUB_USERNAME>/course-workspace:latest \
  -f Dockerfile.workspace .
```

**Verify the push worked** (CRITICAL — do not skip this step):

```bash
docker buildx imagetools inspect ghcr.io/<YOUR_GITHUB_USERNAME>/course-workspace:latest
```

Note the `Digest:` value. If it matches a previous build's digest, the push didn't work. Each successful push should produce a new digest.

```

### 2.3 Make the image public

1. Go to `https://github.com/<YOUR_USERNAME>?tab=packages`
2. Click `course-workspace`
3. **Package settings → Danger Zone → Change visibility → Public**

**Verify:** Pull the image from a different machine (or the VPS) without authentication:

```bash
docker pull ghcr.io/<YOUR_GITHUB_USERNAME>/course-workspace:latest
```

---

## Step 3: Set Up the VPS

### 3.1 Install Docker

#### Ubuntu 24.04

```bash
apt-get update
apt-get install -y ca-certificates curl
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  | tee /etc/apt/sources.list.d/docker.list > /dev/null

apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

#### AlmaLinux 9

```bash
dnf install -y dnf-plugins-core
dnf config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
dnf install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
systemctl enable docker
systemctl start docker
```

#### SELinux (AlmaLinux only)

```bash
getenforce  # Check current mode
sed -i 's/^SELINUX=enforcing/SELINUX=permissive/' /etc/selinux/config
setenforce 0
```

### 3.2 Configure firewall

#### Ubuntu

```bash
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw enable
```

#### AlmaLinux 9

```bash
firewall-cmd --permanent --add-port=22/tcp
firewall-cmd --permanent --add-port=80/tcp
firewall-cmd --permanent --add-port=443/tcp
firewall-cmd --reload
```

### 3.3 Verify Docker

```bash
docker --version
docker run hello-world
```

---

## Step 4: Install and Configure Coder

### 4.1 Install Coder

```bash
curl -L https://coder.com/install.sh | sh
```

### 4.2 Create a non-root user for Coder

The bundled PostgreSQL cannot run as root.

```bash
useradd -r -m -d /var/lib/coder -s /bin/bash coder
mkdir -p /var/lib/coder/.config/coderv2
chown -R coder:coder /var/lib/coder
```

### 4.3 Configure Coder

```bash
mkdir -p /etc/coder
cat > /etc/coder/coder.env << 'EOF'
CODER_HTTP_ADDRESS=0.0.0.0:80
CODER_ACCESS_URL=http://<VPS_IP>
EOF
chown coder:coder /etc/coder/coder.env
```

**Important notes:**

- Use `CODER_HTTP_ADDRESS` (not the deprecated `CODER_ADDRESS`)
- Use `http://` (not `https://`) unless you have TLS certificates configured
- Do NOT set `CODER_PG_CONNECTION_URL` — let Coder use its bundled PostgreSQL
- Set `CODER_ACCESS_URL` to the VPS's public IP, not `localhost`

### 4.4 Configure systemd to run Coder as the non-root user

```bash
mkdir -p /etc/systemd/system/coder.service.d
cat > /etc/systemd/system/coder.service.d/override.conf << 'EOF'
[Service]
User=coder
Group=coder
EnvironmentFile=/etc/coder/coder.env
EOF

systemctl daemon-reload
systemctl enable coder
systemctl start coder
```

### 4.5 Verify Coder is running

```bash
systemctl status coder
```

You should see `Active: active (running)`.

### 4.6 Create admin account

```bash
coder login http://<VPS_IP>
```

Follow the prompts to set a username and password.

### 4.7 Verify the dashboard

Open `http://<VPS_IP>` in your browser and log in.

---

## Step 5: Prepare the Coder Template

### 5.1 Update the template with your details

Edit `coder-template/main.tf` in your local repo:

1. **Image name:** Replace `ghcr.io/pedrogrande/course-workspace:latest` with your GHCR image URL
2. **Repo URL:** Replace `https://github.com/pedrogrande/starter-workspace` in the `startup_script` with your repo URL
3. **Resource limits:** Adjust `memory` and `cpu_quota` if needed

### 5.2 Key template design decisions (don't change these unless you know why)

- **`entrypoint = ["sh", "-c", coder_agent.main.init_script]`** — This is critical. The init script downloads and starts the Coder agent, which then runs the startup script. Do NOT use `command = ["sleep", "infinity"]` or the image's default CMD.
- **No `replace()` function** — Only use `replace(coder_agent.main.init_script, "/localhost|127\\.0\\.0\\.1/", "host.docker.internal")` if `CODER_ACCESS_URL` contains `localhost` or `127.0.0.1`. If it's a public IP or domain, don't use `replace()`.
- **No isolated Docker network** — The container needs to reach the Coder server on the host. Use the default bridge network.
- **Only `CODER_AGENT_TOKEN` in container env** — All other env vars go in the `coder_agent` env block.
- **Hardcoded repo URL in startup_script** — Don't use `coder_parameter` for the repo URL. Terraform interpolation in `startup_script` can be corrupted by the `replace()` function or shell quoting issues.
- **`docker_volume` without `count`** — The data volume must persist across workspace stop/start. Declaring it without `count = data.coder_workspace.me.start_count` ensures it's not destroyed when the workspace stops.
- **Volume at `/app/data`** — Mount the data volume at a subdirectory, not at `/app` itself. Mounting at `/app` would shadow the git-cloned repo.
- **`subdomain = true` on all `coder_app` resources** — Required for Next.js and other SPAs. Path-based proxying (`subdomain = false`) breaks absolute asset paths. Requires wildcard DNS (see Step 5.4).

### 5.3 Commit and push template changes

```bash
git add coder-template/main.tf
git commit -m "Update Coder template with correct image and repo URL"
git push origin main
```

### 5.4 Set up wildcard DNS (required for `subdomain = true`)

`subdomain = true` on `coder_app` resources requires a domain with wildcard DNS. Without this, Next.js apps won't load CSS/JS assets correctly (see `coder-implementation-issues.md` Issue 16).

1. **Create two A records** in your DNS provider (e.g., Cloudflare):
   - `coder.yourdomain.com` → VPS IP (A record, DNS only / grey cloud)
   - `*.coder.yourdomain.com` → VPS IP (A record, DNS only / grey cloud)

2. **Update Coder config** on the VPS:

```bash
cat > /etc/coder/coder.env << 'EOF'
CODER_HTTP_ADDRESS=0.0.0.0:80
CODER_ACCESS_URL=http://coder.yourdomain.com
CODER_WILDCARD_ACCESS_URL=*.coder.yourdomain.com
EOF

systemctl restart coder
```

1. **Update Coder CLI config** locally:

```bash
echo "http://coder.yourdomain.com" > ~/.config/coderv2/url
```

---

## Step 6: Push the Template to Coder

### 6.1 Set up Coder CLI authentication

On your **local machine**:

```bash
# Get your API token from the Coder dashboard:
# Profile → Account Settings → API Token

# Write credentials to config files (avoids interactive prompts)
mkdir -p ~/.config/coderv2
echo "http://<VPS_IP>" > ~/.config/coderv2/url
echo "<YOUR_API_TOKEN>" > ~/.config/coderv2/session
```

### 6.2 Push the template

```bash
cd /path/to/your/repo
coder templates push agentos-course -d coder-template --yes
```

**Verify:** The output should show `Updated version at <timestamp>!` with a template preview listing `docker_container.workspace` and `docker_volume.workspace_data`.

---

## Step 7: Create a Test Workspace

### 7.1 Create the workspace via CLI

```bash
coder create starter-one \
  --template agentos-course \
  --parameter openai_api_key=<YOUR_OPENAI_KEY> \
  --parameter ollama_api_key=<YOUR_OLLAMA_KEY> \
  --yes
```

### 7.2 Wait for the agent to connect

```bash
# Check workspace status
coder list

# Wait until HEALTHY shows "true"
# This typically takes 30-60 seconds
```

### 7.3 Verify the workspace is working

**Check processes on the VPS:**

```bash
ssh root@<VPS_IP>
docker exec student-<username>-<workspace-name> ps aux
```

You should see:

- `./coder agent` (the Coder agent)
- `uvicorn app.main:app --host 0.0.0.0 --port 8000` (the AgentOS API)

**Check the API responds:**

```bash
docker exec student-<username>-<workspace-name> curl -s http://localhost:8000/
```

Should return: `{"name":"AgentOS API","version":"1.0.0"}`

**Check the startup script log:**

```bash
docker exec student-<username>-<workspace-name> cat /tmp/coder-startup-script.log
```

Should show:

```
Cloning into '/app-tmp'...
Cloning repository...
Starting AgentOS on port 8000...
```

Followed by agent registration debug messages.

---

## Step 8: Access the Workspace

### 8.1 Via the Coder dashboard

1. Open `http://<VPS_IP>` in your browser
2. Click the workspace name
3. Click the **AgentOS** app link — this opens the AgentOS UI proxied through Coder

### 8.2 Via SSH

```bash
coder ssh <workspace-name>
```

### 8.3 Via VS Code Remote-SSH

1. Install the Remote-SSH extension in VS Code
2. Use `coder ssh <workspace-name> --stdio` as the SSH command
3. Or configure `~/.ssh/config` with the Coder SSH proxy

---

## Step 9: Create Student Accounts

### 9.1 Create users

In the Coder dashboard:

1. Go to **Users → New User**
2. Enter the student's email and username
3. They'll receive a password setup link

### 9.2 Students create their own workspaces

Students log in to `http://<VPS_IP>`, click **Create Workspace**, select the `agentos-course` template, and enter their own OpenAI and Ollama API keys.

---

## Step 10: Ongoing Maintenance

### Updating the workspace image

When `requirements.txt` or Agent-UI changes:

```bash
# On your local machine — clear cache and rebuild
docker buildx prune -af
docker buildx build --platform linux/amd64 --no-cache --output type=registry \
  -t ghcr.io/<USERNAME>/course-workspace:latest \
  -f Dockerfile.workspace .

# CRITICAL: Verify the push worked
docker buildx imagetools inspect ghcr.io/<USERNAME>/course-workspace:latest
# Check that the Digest changed from the previous build

# On the VPS — clear the old cached image and pull the new one
ssh root@<VPS_IP> "docker rm -f student-<username>-<workspace> 2>/dev/null; docker rmi ghcr.io/<USERNAME>/course-workspace:latest 2>/dev/null; docker pull ghcr.io/<USERNAME>/course-workspace:latest"
```

Students' workspaces pick up the new image on their next stop/start.

### Updating the course repo

```bash
git push origin main
```

Students' workspaces pull the latest repo on their next stop/start (the startup script runs `git pull` if the repo already exists).

### Updating the Coder template

```bash
coder templates push agentos-course -d coder-template --yes
```

Existing workspaces show as "Outdated" in the dashboard. Students click **Update** to apply the new template.

---

## Troubleshooting Quick Reference

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| `exec format error` | ARM64 image on AMD64 VPS | Rebuild with `--platform linux/amd64` |
| `unauthorized` pulling image | GHCR image is private | Make image public on GitHub |
| Agent not connecting | Wrong entrypoint or isolated network | Use `coder_agent.main.init_script` as entrypoint, remove isolated network |
| `ModuleNotFoundError: No module named 'app'` | Repo not cloned yet | Ensure entrypoint is init_script, not the image's default CMD |
| Postgres connection refused | Repo doesn't have SQLite changes | Push changes to GitHub, recreate workspace |
| `TLS is disabled` error | `CODER_ACCESS_URL` has `https://` but no certs | Change to `http://` |
| `cannot run as root` | Coder running as root user | Create `coder` user, configure systemd override |
| Git clone URL corrupted | Terraform interpolation issue | Hardcode repo URL in startup_script |
| Stale image after update | Docker cache on VPS | `docker rmi <image>` on VPS, then recreate workspace |
| `CODER_ADDRESS deprecated` | Old env var name | Use `CODER_HTTP_ADDRESS` instead |
| Image not updating despite "successful" build | Buildx push cache | Use `--output type=registry` instead of `--push`, verify with `imagetools inspect` |
| CORS errors in browser console | Agent-UI and AgentOS on different subdomains | Use Next.js API proxy route (`/api/proxy/*`) |
| CSS MIME type error | Path-based proxy with SPA | Set `subdomain = true` on `coder_app`, configure wildcard DNS |
| Agent-UI shows default interface, no Views | Endpoint not connected (CORS or wrong URL) | Fix CORS with proxy route, verify auto-detect endpoint |
| Endpoint shows port 7777 | Old default in store or stale localStorage | Update store default, bump persist version with migration |

---

## File Reference

| File | Purpose |
|------|---------|
| `Dockerfile.workspace` | Workspace image definition (multi-stage: Python deps + Agent-UI build) |
| `coder-template/main.tf` | Coder Terraform template (provisions container + volume + agent + apps) |
| `db/session.py` | Database backend switch (SQLite/ChromaDB or Postgres/PgVector) |
| `docs/infrastructure-setup.md` | VPS + Coder + GHCR setup guide |
| `docs/coder-implementation-issues.md` | Detailed report of all 17 issues encountered |
| `docs/coder-workspace-setup-guide.md` | This file — step-by-step guide |
| `docs/agent-ui-implementation-issues.md` | Agent-UI integration issues report |
| `docs/agent-ui-setup-guide.md` | Agent-UI custom views setup guide |
| `docs/phase-5-verification-guide.md` | Phase 5 verification guide |

## Critical Build Commands Reference

```bash
# Build and push workspace image (use --output type=registry, NOT --push)
docker buildx prune -af
docker buildx build --platform linux/amd64 --no-cache --output type=registry \
  -t ghcr.io/<USERNAME>/course-workspace:latest \
  -f Dockerfile.workspace .

# Verify the push worked (digest should change each build)
docker buildx imagetools inspect ghcr.io/<USERNAME>/course-workspace:latest

# Push Coder template
coder templates push agentos-course -d coder-template --yes

# Delete and recreate workspace
coder delete <username>/<workspace> --yes
coder create <workspace> --template agentos-course \
  --parameter openai_api_key=<key> \
  --parameter ollama_api_key=<key> \
  --yes

# Verify workspace health
coder list

# Verify the running container has the new image
ssh root@<VPS_IP> "docker inspect student-<user>-<workspace> --format '{{.Image}}'"
```
