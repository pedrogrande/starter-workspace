# Infrastructure Setup Guide

This guide covers everything you need to do **before** Phase 2 (building the workspace image) and Phase 3 (creating the Coder template):

1. Set up a GitHub Container Registry (GHCR) repository to store the workspace image
2. Procure and configure a VPS
3. Install Coder on the VPS

Once all three are done, you can proceed to build the workspace image and write the Coder Terraform template.

---

## Part 1 — GitHub Container Registry (GHCR)

The workspace Docker image needs to live somewhere the VPS can pull it from. GitHub Container Registry is free for public images and integrates with your existing GitHub account.

### 1.1 Create a Personal Access Token (PAT)

You need a PAT with `write:packages` scope to push images to GHCR.

1. Go to **GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)**.
2. Click **Generate new token (classic)**.
3. Give it a name like `ghcr-push`.
4. Set an expiration (recommend 90 days — you can renew).
5. Select the **`write:packages`** scope. This also auto-selects `repo` and `read:packages`.
6. Click **Generate token**. **Copy the token** — you won't see it again.

### 1.2 Authenticate Docker with GHCR

On your **local machine** (where you'll build the image):

```bash
echo "<YOUR_PAT>" | docker login ghcr.io -u <YOUR_GITHUB_USERNAME> --password-stdin
```

Verify it worked:

```bash
cat ~/.docker/config.json | grep ghcr.io
```

You should see `ghcr.io` in the auths section.

### 1.3 Tag and push the image

When you build the workspace image (Phase 2), you'll tag it like this:

```bash
docker build -t ghcr.io/<YOUR_GITHUB_USERNAME>/course-workspace:latest -f Dockerfile.workspace .
docker push ghcr.io/<YOUR_GITHUB_USERNAME>/course-workspace:latest
```

### 1.4 Make the image public (recommended for a course)

By default, GHCR images are private. For a course, make it public so the VPS can pull it without authentication:

1. Go to **GitHub → Your profile → Packages** (or `https://github.com/<USERNAME>?tab=packages`).
2. Click the `course-workspace` package.
3. **Package settings → Danger Zone → Change visibility → Public**.

If you prefer to keep it private, the VPS will need to authenticate with a PAT that has `read:packages` scope. You'll pass this to Docker on the VPS (see Part 2.4).

### 1.5 Image rebuild workflow

When `requirements.txt` changes (you add a dependency), rebuild and push:

```bash
docker build -t ghcr.io/<YOUR_GITHUB_USERNAME>/course-workspace:latest -f Dockerfile.workspace .
docker push ghcr.io/<YOUR_GITHUB_USERNAME>/course-workspace:latest
```

Existing student workspaces pick up the new image on their next stop/start. Running workspaces need a stop/start to get the new image.

---

## Part 2 — VPS Procurement and Setup

### 2.1 Choose a VPS provider

For 1–10 students with the SQLite + ChromaDB architecture (no Postgres container), each workspace needs ~512MB RAM. The VPS also runs Coder itself (~2GB) and the host OS (~1GB).

| Students | Min RAM | Recommended RAM | vCPU | Est. monthly cost |
|----------|--------|-----------------|------|-------------------|
| 1–5      | 8 GB   | 16 GB           | 4    | $10–20/mo         |
| 5–10     | 16 GB  | 32 GB           | 8    | $20–50/mo         |

**Recommended providers** (price-to-RAM ratio, as of 2026):

- **Hetzner Cloud** — CPX31 (8 vCPU / 16 GB ~ $13/mo) or CPX41 (8 vCPU / 32 GB ~ $25/mo). Best value.
- **DigitalOcean** — Premium Intel / 16 GB / 8 vCPU ~ $96/mo. More expensive but simpler UI.
- **OVHcloud** — Rise-2 (16 GB / 4 vCPU ~ $8/mo). Dedicated server, best raw value if you're comfortable with bare metal.

**Recommendation**: Hetzner CPX41 (32 GB / 8 vCPU) for 10 students with code-server. The extra headroom matters when students run evals (`python -m evals`) which are CPU-bound.

### 2.2 Provision the VPS

Create a server with **Ubuntu 24.04 LTS** or **AlmaLinux 9** (RHEL-compatible). Choose a region close to your students to minimize latency for the in-browser VS Code and AgentOS UI.

Save the **root password** or set up **SSH key authentication** immediately:

```bash
# On your local machine
ssh-copy-id root@<VPS_IP>
```

Disable password login (security best practice):

```bash
# On the VPS (same on both Ubuntu and AlmaLinux)
sed -i 's/^#PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
systemctl restart sshd
```

#### SELinux (AlmaLinux only)

AlmaLinux has SELinux enabled in **enforcing** mode by default. Docker volume mounts can be blocked by SELinux policies. Set it to **permissive** for simplicity:

```bash
# Check current mode
getenforce

# Set to permissive (survives reboot)
sed -i 's/^SELINUX=enforcing/SELINUX=permissive/' /etc/selinux/config
setenforce 0

# Verify
getenforce
```

> If you prefer to keep SELinux enforcing, add `:z` or `:Z` suffixes to Docker volume mounts in the Coder template (e.g. `container_path = "/app/data:z"`). Permissive is simpler for a course.

> Ubuntu does not have SELinux — skip this step entirely.

### 2.3 Install Docker on the VPS

Coder's Docker provider needs Docker running on the VPS host. This is the only place Docker runs — student workspaces don't have Docker inside them.

#### Ubuntu 24.04 / 22.04

```bash
# On the VPS
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

#### AlmaLinux 9 (RHEL-compatible)

```bash
# On the VPS
dnf install -y dnf-plugins-core

dnf config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo

dnf install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

systemctl enable docker
systemctl start docker
```

#### Verify (both distros)

```bash
docker --version
docker run hello-world
```

### 2.4 Authenticate Docker on the VPS (if image is private)

If you kept the GHCR image private (Part 1.4), the VPS needs to authenticate to pull it:

```bash
# On the VPS
echo "<READ_ONLY_PAT>" | docker login ghcr.io -u <YOUR_GITHUB_USERNAME> --password-stdin
```

Use a PAT with only `read:packages` scope (not your push PAT). If the image is public, skip this step.

### 2.5 Configure firewall

Open only the ports you need. Do **not** open port 8000 — student AgentOS instances are proxied through Coder, not exposed directly.

#### Ubuntu (`ufw`)

```bash
ufw allow 22/tcp       # SSH
ufw allow 80/tcp       # Coder HTTP (redirects to HTTPS)
ufw allow 443/tcp      # Coder HTTPS
ufw enable
```

#### AlmaLinux 9 (`firewalld`)

Install `firewalld`: <https://wiki.almalinux.org/documentation/after-installation-guide.html#configure-firewall-settings>

```bash
firewall-cmd --permanent --add-port=22/tcp       # SSH
firewall-cmd --permanent --add-port=80/tcp       # Coder HTTP (redirects to HTTPS)
firewall-cmd --permanent --add-port=443/tcp      # Coder HTTPS
firewall-cmd --reload

# Verify
firewall-cmd --list-all
```

---

## Part 3 — Install Coder on the VPS

### 3.1 Install Coder

```bash
# On the VPS
curl -L https://coder.com/install.sh | sh
```

This installs the `coder` binary and sets up a systemd service.

### 3.2 Configure Coder

Coder needs a database for its own state (separate from student workspaces — this is Coder's control plane, not the student SQLite databases). The bundled PostgreSQL is fine for a course.

Create a configuration file:

```bash
mkdir -p /etc/coder
cat > /etc/coder/coder.env << 'EOF'
CODER_ADDRESS=0.0.0.0:80
CODER_ACCESS_URL=https://<VPS_IP>
CODER_PG_CONNECTION_URL=postgres://coder:coder@localhost:5432/coder?sslmode=disable
EOF
```

> **Note**: The install script sets up a bundled PostgreSQL automatically. If you prefer an external Postgres, set `CODER_PG_CONNECTION_URL` to point at it. For a course, the bundled one is sufficient.

### 3.3 Start Coder

```bash
systemctl enable coder
systemctl start coder
```

Check it's running:

```bash
systemctl status coder
```

### 3.4 Set up TLS (recommended)

For a course, you can use Coder's built-in TLS with a self-signed cert, or set up a domain + Let's Encrypt. If you have a domain:

```bash
# Point a DNS A record at your VPS IP first, then:

# Ubuntu
apt-get install -y certbot

# AlmaLinux 9
dnf install -y certbot

# Both distros — obtain the certificate
certbot certonly --standalone -d coder.yourdomain.com

# Update /etc/coder/coder.env:
# CODER_ACCESS_URL=https://coder.yourdomain.com
# CODER_TLS_CERT=/etc/letsencrypt/live/coder.yourdomain.com/fullchain.pem
# CODER_TLS_KEY=/etc/letsencrypt/live/coder.yourdomain.com/privkey.pem

systemctl restart coder
```

If you don't have a domain, Coder works over HTTP with `CODER_ACCESS_URL=http://<VPS_IP>`. Students will see a browser warning about the non-HTTPS connection, which is fine for a course.

### 3.5 Create your admin account

```bash
coder login https://<VPS_IP>
```

This creates the first user (becomes admin). Follow the prompts to set a username and password.

### 3.6 Verify the Coder dashboard

Open `https://<VPS_IP>` (or `http://`) in your browser. Log in with the admin account. You should see the Coder dashboard with no workspaces yet.

---

## Checklist

Before proceeding to Phase 2, confirm:

- [ ] **GHCR**: PAT created, Docker authenticated locally, ready to push `course-workspace:latest`
- [ ] **VPS**: Provisioned with 16–32 GB RAM, Ubuntu 24.04 or AlmaLinux 9, SSH key auth, firewall configured, SELinux permissive (AlmaLinux only)
- [ ] **Docker**: Installed on VPS, `docker run hello-world` works
- [ ] **Coder**: Installed, running, admin account created, dashboard accessible at `https://<VPS_IP>`
- [ ] **VPS Docker auth** (if image is private): `docker login ghcr.io` done on VPS

Once all boxes are checked, you're ready for Phase 2 (build the workspace image) and Phase 3 (write the Coder Terraform template).

---

## Quick Reference

| What | Where | Value |
|------|-------|-------|
| GHCR image URL | — | `ghcr.io/<USERNAME>/course-workspace:latest` |
| Coder dashboard | VPS | `https://<VPS_IP>` |
| Coder config | VPS | `/etc/coder/coder.env` |
| Coder service | VPS | `systemctl status coder` |
| Docker daemon | VPS | `systemctl status docker` |
| Student AgentOS | Coder proxy | `https://<VPS_IP>/@<username>/<workspace>/apps/agentos` |
| Student data | VPS Docker volume | `student-<username>-data` (mounted at `/app/data`) |

## Troubleshooting

**Coder won't start**: Check `journalctl -u coder -f` for errors. Most common issue is the Postgres connection URL.

**VPS can't pull image**: If private, verify `docker login ghcr.io` succeeded on the VPS. If public, verify the image visibility setting in GitHub.

**Students can't access workspace**: Check firewall — `ufw status` (Ubuntu) or `firewall-cmd --list-all` (AlmaLinux) — ports 80/443 must be open. Check Coder logs: `journalctl -u coder -f`.

**Docker volume mount permission denied (AlmaLinux)**: SELinux is likely still enforcing. Run `getenforce` — if it says `Enforcing`, set it to permissive (see Part 2.2) or add `:z` suffixes to volume mounts in the Coder template.

**Docker not found on VPS**: The Coder Docker provider needs Docker on the host. Verify `docker ps` works on the VPS (not inside a container).

## OS Command Reference

| Task | Ubuntu (`apt-get`) | AlmaLinux 9 (`dnf`) |
|------|-------------------|---------------------|
| Install packages | `apt-get install -y` | `dnf install -y` |
| Docker repo | `download.docker.com/linux/ubuntu` | `download.docker.com/linux/centos/docker-ce.repo` |
| Firewall | `ufw allow 80/tcp` + `ufw enable` | `firewall-cmd --permanent --add-port=80/tcp` + `firewall-cmd --reload` |
| SELinux | N/A | Set to permissive (see Part 2.2) |
| SSH service | `systemctl restart sshd` | `systemctl restart sshd` (same) |
| Coder install | `curl -L https://coder.com/install.sh \| sh` | Same |
| Certbot install | `apt-get install -y certbot` | `dnf install -y certbot` |
