# Coder Implementation: Issues Report

This document records every issue encountered during the Coder workspace implementation, with root cause analysis and explanations. It serves as a reference for troubleshooting similar setups and as a record of lessons learned.

**Date:** 2026-06-22 (initial), 2026-06-23 (Agent-UI and buildx updates)
**VPS:** OVHcloud, AlmaLinux 9, x86_64
**Coder:** v2.34.3 (server), v2.33.5 (CLI)
**Image registry:** GitHub Container Registry (GHCR)

---

## Issue 1: TLS Configuration Mismatch

### Symptom

```
error: TLS is disabled. Enable with --tls-enable or specify a HTTP address
```

Coder service failed to start.

### Root Cause

The `CODER_ACCESS_URL` in `/etc/coder/coder.env` was set to `https://74.208.237.168` (HTTPS), but no TLS certificates were configured. Coder saw the `https://` scheme and expected TLS to be enabled, but it wasn't — hence the error.

### Fix

Changed `CODER_ACCESS_URL` from `https://` to `http://` since no domain or TLS certificate was set up:

```bash
sed -i 's|CODER_ACCESS_URL=https://74.208.237.168|CODER_ACCESS_URL=http://74.208.237.168|' /etc/coder/coder.env
```

### Explanation

Coder uses `CODER_ACCESS_URL` to determine whether to serve TLS. If the URL scheme is `https://`, Coder expects `CODER_TLS_CERT` and `CODER_TLS_KEY` to be set. Without a domain name and Let's Encrypt certificate, HTTP is the correct choice. The `https://` was copied from the setup guide which assumed a domain would be configured.

---

## Issue 2: Built-in PostgreSQL Cannot Run as Root

### Symptom

```
error: The built-in PostgreSQL cannot run as the root user. Create a non-root user and run again!
```

### Root Cause

Coder's bundled PostgreSQL (used for the control plane's own state) refuses to run as the root user for security reasons. The default systemd service runs as root.

### Fix

Created a `coder` user and configured the systemd service to run as that user:

```bash
useradd -r -m -d /var/lib/coder -s /bin/bash coder
mkdir -p /var/lib/coder/.config/coderv2
chown -R coder:coder /var/lib/coder

mkdir -p /etc/systemd/system/coder.service.d
cat > /etc/systemd/system/coder.service.d/override.conf << 'EOF'
[Service]
User=coder
Group=coder
EnvironmentFile=/etc/coder/coder.env
EOF

systemctl daemon-reload
systemctl restart coder
```

### Explanation

The bundled PostgreSQL is Coder's zero-dependency option for small deployments. It stores data under the running user's home directory (`~/.config/coderv2/postgres`). Running as root is blocked because PostgreSQL itself refuses root — it's a database security best practice that prevents privilege escalation through the database process.

---

## Issue 3: External PostgreSQL Connection URL Pointed to Non-Existent Server

### Symptom

```
error: connect to postgres: unable to connect after 11 tries; last error: dial tcp [::1]:5432: connect: connection refused
```

### Root Cause

The `CODER_PG_CONNECTION_URL` in `/etc/coder/coder.env` was set to `postgres://coder:coder@localhost:5432/coder?sslmode=disable`, pointing to an external PostgreSQL instance that was never installed on the VPS. The setup guide included this line assuming an external Postgres would be provisioned, but the bundled PostgreSQL was the intended approach.

### Fix

Removed the `CODER_PG_CONNECTION_URL` line entirely, letting Coder use its built-in PostgreSQL:

```bash
sed -i '/CODER_PG_CONNECTION_URL/d' /etc/coder/coder.env
```

### Explanation

Coder offers two database options: (1) the bundled PostgreSQL, which runs as a subprocess under the `coder` user, and (2) an external PostgreSQL connection via `CODER_PG_CONNECTION_URL`. The setup guide incorrectly included the external URL when no external Postgres was provisioned. The bundled PostgreSQL is the correct choice for a course deployment — it's zero-dependency and sufficient for Coder's control plane state (workspace metadata, user accounts, template versions).

---

## Issue 4: Deprecated Environment Variable

### Symptom

```
WARN: `CODER_ADDRESS` is deprecated, please use `CODER_HTTP_ADDRESS` and `CODER_TLS_ADDRESS` instead.
```

### Root Cause

`CODER_ADDRESS` was the original env var for specifying the listen address. In newer Coder versions, it was split into `CODER_HTTP_ADDRESS` and `CODER_TLS_ADDRESS` to support simultaneous HTTP and TLS listeners.

### Fix

```bash
sed -i 's/CODER_ADDRESS=0.0.0.0:80/CODER_HTTP_ADDRESS=0.0.0.0:80/' /etc/coder/coder.env
```

### Explanation

This was a warning, not an error — Coder still accepts `CODER_ADDRESS` for backward compatibility. However, updating to `CODER_HTTP_ADDRESS` is the correct approach for future-proofing. The split allows configurations where HTTP and TLS listen on different ports (e.g., HTTP on 80 for redirects, TLS on 443 for the actual UI).

---

## Issue 5: ARM64 Image on AMD64 VPS

### Symptom

```
exec /usr/local/bin/uvicorn: exec format error
```

Container repeatedly crashed and restarted.

### Root Cause

The workspace Docker image was built on a Mac with Apple Silicon (ARM64 architecture). The VPS is x86_64 (AMD64). The `uvicorn` binary inside the image was compiled for ARM64 and cannot execute on an AMD64 CPU. The Linux kernel reports this as `exec format error`.

### Fix

Rebuilt the image for `linux/amd64` using Docker buildx:

```bash
docker buildx build --platform linux/amd64 -t ghcr.io/pedrogrande/course-workspace:latest -f Dockerfile.workspace --push .
```

### Explanation

Docker images are architecture-specific. When you run `docker build` on an ARM64 machine, the resulting image contains ARM64 binaries. Running that image on an AMD64 host fails because the CPU can't execute the ARM64 instruction set. Docker buildx with `--platform linux/amd64` uses QEMU emulation to cross-compile for the target architecture. The `--push` flag pushes directly to the registry, avoiding the need to store a large AMD64 image locally on the ARM64 Mac.

**Key lesson:** Always specify `--platform linux/amd64` when building images on Apple Silicon for deployment on x86_64 VPS instances. For multi-arch support (testing from both Mac and VPS), use `--platform linux/amd64,linux/arm64`.

---

## Issue 6: Stale Cached Image on VPS

### Symptom

After pushing the corrected AMD64 image, the VPS still ran the old ARM64 image, producing the same `exec format error`.

### Root Cause

Docker caches images locally. The `docker pull` during workspace creation found the old image in the local cache (same tag: `latest`) and used it instead of pulling the new one from GHCR. The `lifecycle { ignore_changes = [image] }` in the Terraform template also prevented Coder from detecting image changes.

### Fix

Forced the VPS to discard the cached image and pull the new one:

```bash
docker rmi ghcr.io/pedrogrande/course-workspace:latest
docker pull ghcr.io/pedrogrande/course-workspace:latest
```

### Explanation

Docker's image cache is keyed by tag. When a tag is updated in the registry, local Docker daemons don't automatically know — they use the cached version unless explicitly told to pull. The `docker rmi` command removes the local cache entry, forcing the next `docker pull` (triggered by workspace creation) to fetch the new image from GHCR.

**Key lesson:** When updating a workspace image, always `docker rmi` the old image on the VPS before recreating workspaces. Alternatively, use unique tags (e.g., `course-workspace:2026-06-22`) instead of `latest` to avoid cache conflicts.

---

## Issue 7: Container Running Default CMD Before Agent Connects

### Symptom

```
ModuleNotFoundError: No module named 'app'
```

Uvicorn started immediately on container boot and failed because the repo hadn't been cloned yet.

### Root Cause

The workspace image's `Dockerfile.workspace` sets `CMD ["uvicorn", "app.main:app", ...]` as the default command. When Coder started the container, Docker ran this CMD immediately — before the Coder agent had a chance to connect and run the startup script that clones the repo. The `app` module didn't exist because `/app` only contained `requirements.txt` and `data/` (from the image), not the cloned repo.

### Fix

Set the container's `entrypoint` to the Coder agent's init script, which downloads and starts the agent first. The agent then runs the `startup_script` (which clones the repo and starts uvicorn) after connecting to the Coder server:

```hcl
entrypoint = ["sh", "-c", coder_agent.main.init_script]
```

### Explanation

The Coder agent's `init_script` is a shell script that:

1. Downloads the `coder` agent binary
2. Sets the `CODER_AGENT_TOKEN` and `CODER_AGENT_URL` environment variables
3. Starts the agent process

The agent then connects to the Coder server, receives the `startup_script`, and executes it. The `startup_script` is where the repo clone and uvicorn launch happen. By using `init_script` as the entrypoint, the container's lifecycle becomes: boot → download agent → connect to server → run startup script → clone repo → start uvicorn.

The image's `CMD` is overridden by the `entrypoint` in the Terraform template. The `CMD` in the Dockerfile is only a fallback for when the image is run outside Coder (e.g., local testing).

**Key lesson:** The workspace image's `CMD` should be a fallback, not the primary command. The Coder template's `entrypoint` must be set to `coder_agent.main.init_script` so the agent lifecycle is managed by Coder.

---

## Issue 8: Agent Not Connecting — Missing Init Script

### Symptom

The container was running `sleep infinity` (a previous fix attempt) and the Coder agent was never started. The dashboard showed "waiting for agents to connect" indefinitely.

### Root Cause

An earlier fix attempt set `command = ["sleep", "infinity"]` to prevent the default CMD from running. However, this also prevented the Coder agent from starting — the container just slept forever with no agent process inside it.

### Fix

Replaced `command = ["sleep", "infinity"]` with `entrypoint = ["sh", "-c", coder_agent.main.init_script]` (see Issue 7).

### Explanation

The `command` attribute in `docker_container` sets the CMD, but the `entrypoint` attribute sets the ENTRYPOINT. The Coder agent's init script must be the ENTRYPOINT because it's the first thing that runs when the container starts. Using `command` alone doesn't override the image's ENTRYPOINT — the image's ENTRYPOINT (`/app/scripts/entrypoint.sh`) would still run first and potentially interfere.

**Key lesson:** Use `entrypoint` (not `command`) to inject the Coder agent init script. The init script is the container's primary process — everything else (repo clone, uvicorn) is a child of the agent.

---

## Issue 9: Git Clone URL Corruption via Terraform Parameter Interpolation

### Symptom

```
fatal: repository 'export CODER_URL=http' is not supported
```

or

```
fatal: Too many arguments.
```

The `git clone` command in the startup script received corrupted URL text instead of the actual GitHub URL.

### Root Cause

The startup script used Terraform interpolation to inject the repo URL:

```hcl
startup_script = <<-EOT
  git clone ${data.coder_parameter.repo_url.value} /app-tmp
EOT
```

The `data.coder_parameter.repo_url.value` was being interpolated by Terraform at provision time, but the resulting string was being mangled when passed through the `sh -c` wrapper in the entrypoint. The Coder agent's init script concatenates the agent bootstrap code with the startup script, and the `replace()` function (which was being used to rewrite `localhost` to `host.docker.internal`) was corrupting the combined string.

Additionally, the `CODER_URL` environment variable from the local terminal session (used for the `coder create` CLI command) was leaking into the startup script context, causing `export CODER_URL=http://...` to appear as part of the `git clone` arguments.

### Fix

Hardcoded the repo URL directly in the startup script instead of using a Terraform parameter:

```hcl
startup_script = <<-EOT
  git clone https://github.com/pedrogrande/starter-workspace /app-tmp
EOT
```

Removed the `data "coder_parameter" "repo_url"` block entirely.

### Explanation

Terraform's `${...}` interpolation in heredoc strings works at provision time — the value is substituted before the script is sent to the agent. However, the Coder agent's `init_script` is a complex string that includes the agent bootstrap code, environment variable exports, and the startup script. When `replace()` was applied to the entire `init_script` (to rewrite `localhost` references), it could corrupt parts of the startup script that happened to contain matching patterns.

The safest approach is to hardcode values that don't need to be user-configurable. The repo URL is the same for all students, so a parameter adds complexity without value. API keys (which are per-student) are still passed via `coder_parameter` and injected through the `coder_agent` env block, which is the correct mechanism.

**Key lesson:** Only use `coder_parameter` for values that actually vary per student. For fixed values like repo URLs, hardcode them in the template. When using Terraform interpolation in `startup_script`, be aware that the entire `init_script` (including the startup script) may be processed by `replace()` or other functions.

---

## Issue 10: `replace()` Function Corrupting Init Script

### Symptom

The `git clone` command received garbled text, including fragments of the `CODER_URL` environment variable and previous terminal commands.

### Root Cause

The official Coder Docker template uses:

```hcl
entrypoint = ["sh", "-c", replace(coder_agent.main.init_script, "/localhost|127\\.0\\.0\\.1/", "host.docker.internal")]
```

This `replace()` function rewrites `localhost` and `127.0.0.1` to `host.docker.internal` so the agent inside the container can reach the Coder server on the host. However, in our case:

1. The `CODER_ACCESS_URL` was already set to the VPS's external IP (`http://74.208.237.168`), not `localhost`. So the `replace()` was unnecessary.
2. The `replace()` was operating on the entire `init_script`, which includes both the agent bootstrap AND the startup script. If any part of the startup script contained `localhost` (e.g., `AGENTOS_URL=http://localhost:8000`), it would be rewritten, potentially breaking the script structure.
3. The regex pattern `/localhost|127\.0\.0\.1/` could match substrings within other text, causing unexpected replacements.

### Fix

Removed the `replace()` function entirely since `CODER_ACCESS_URL` was already set to the external IP:

```hcl
entrypoint = ["sh", "-c", coder_agent.main.init_script]
```

### Explanation

The `replace()` function is only needed when `CODER_ACCESS_URL` contains `localhost` or `127.0.0.1` — typically when Coder runs on the same machine as the workspaces and the access URL is `http://localhost:3000`. In our setup, the access URL is the VPS's public IP, which the container can reach directly via the default Docker bridge network. No rewriting is needed.

**Key lesson:** Only use `replace()` when `CODER_ACCESS_URL` contains `localhost` or `127.0.0.1`. If the access URL is a public IP or domain, the container can reach the server directly and `replace()` is unnecessary — and potentially harmful.

---

## Issue 11: GitHub Repo Not Updated with SQLite Changes

### Symptom

```
ERROR Error checking if table exists: (psycopg.OperationalError) connection failed: connection to server at "127.0.0.1", port 5432 failed: Connection refused
```

Uvicorn started but tried to connect to Postgres on localhost:5432, despite `DB_BACKEND=sqlite` being set in the environment.

### Root Cause

The workspace cloned the repo from `https://github.com/pedrogrande/starter-workspace`, but the repo on GitHub still had the original Postgres-only `db/session.py`. The SQLite + ChromaDB changes were made locally but never committed and pushed to GitHub. The `DB_BACKEND` env var was set, but the code didn't reference it because the old `db/session.py` had no `DB_BACKEND` switch — it always used `PostgresDb`.

### Fix

Committed all local changes and pushed to GitHub:

```bash
git add -A
git commit -m "Add SQLite + ChromaDB backend with DB_BACKEND switch"
git push origin main
```

Then deleted and recreated the workspace so it cloned the updated repo.

### Explanation

The Coder workspace's startup script clones the repo from GitHub at workspace start time. If the GitHub repo doesn't have the latest changes, the workspace will run old code regardless of what environment variables are set. The `DB_BACKEND=sqlite` env var only works if `db/session.py` reads it — and the old version of `db/session.py` didn't.

**Key lesson:** Always push repo changes to GitHub before creating workspaces. The workspace's code is determined by what's on GitHub at clone time, not what's on your local machine. Consider adding a pre-flight check to the startup script that verifies the repo has the expected files (e.g., `grep DB_BACKEND /app/db/session.py || echo "WARNING: repo may be outdated"`).

---

## Issue 12: Isolated Docker Network Blocking Agent Connectivity

### Symptom

The Coder agent inside the container couldn't connect to the Coder server on the host. The dashboard showed "waiting for agents to connect" indefinitely.

### Root Cause

The initial template created an isolated Docker network (`docker_network.coder`) and attached the workspace container to it. An isolated Docker network doesn't provide a route to the host's external IP — the container could only reach other containers on the same network, not the VPS host itself.

### Fix

Removed the isolated `docker_network` resource and let the container use the default Docker bridge network, which provides a route to the host:

```hcl
# Removed:
# resource "docker_network" "coder" {
#   name = "coder-network"
# }
# 
# networks_advanced {
#   name = docker_network.coder.name
# }
```

### Explanation

The default Docker bridge network (`docker0`) allows containers to reach the host's network interfaces, including the external IP. An isolated network is useful for security (preventing containers from reaching the host), but in this case it prevented the Coder agent from connecting to the Coder server. The official Coder Docker template doesn't use an isolated network for the same reason.

**Key lesson:** The Coder agent needs to reach the Coder server. If the server runs on the host (not in a container), the workspace container must be on a network that can route to the host. The default bridge network works. If you need isolation, use `host.docker.internal` with the `host` block and `replace()` — but only if `CODER_ACCESS_URL` contains `localhost`.

---

## Issue 13: GHCR Image Private by Default

### Symptom

```
Error: Unable to create container with image ghcr.io/pedrogrande/course-workspace:latest: unable to pull image: error from registry: unauthorized
```

### Root Cause

GitHub Container Registry images are private by default. The VPS's Docker daemon couldn't pull the image without authentication.

### Fix

Made the image public on GitHub:

1. Go to `https://github.com/pedrogrande?tab=packages`
2. Click `course-workspace`
3. Package settings → Danger Zone → Change visibility → Public

### Explanation

GHCR inherits the visibility settings from the GitHub package, not the repository. Even if the repository is public, the package is private by default. For a course where the image only contains Python dependencies (no secrets), public visibility is appropriate. If the image contained sensitive data, the VPS would need to authenticate with a PAT that has `read:packages` scope via `docker login ghcr.io`.

**Key lesson:** After pushing an image to GHCR, always check the package visibility. The default is private, which will block any Docker daemon that hasn't authenticated.

---

## Issue 14: Docker Buildx Push Cache — Silent Stale Image (CRITICAL)

### Symptom

Multiple "successful" Docker builds (`docker buildx build --platform linux/amd64 --push`) appeared to complete correctly — logs showed `DONE` and `naming to ghcr.io/...:latest done` — but the GHCR manifest was never updated. The VPS kept pulling the same old image for 15+ hours across 5+ rebuild attempts. The user saw no changes despite hours of work.

### Root Cause

Docker buildx maintains its own cache separate from the regular Docker daemon. When using `--push`, buildx pushes to the registry using its cache. If the buildx cache contains a previous push result for the same tag, it may reuse that cached manifest instead of pushing the new one — even with `--no-cache` (which only skips layer builds, not push manifest caching).

The `docker buildx prune -f` command was run but didn't fully clear the push manifest cache. The `-f` flag forces the prune without confirmation but doesn't clear all cache types.

### What I Was Seeing vs Reality

| What I saw | What was actually happening |
|---|---|
| "DONE 348.6s" in build logs | Build succeeded locally but push used cached manifest |
| `coder list` showing "HEALTHY: true" | Workspace was healthy but running the OLD image |
| `docker exec ... ls /agent-ui/src/components/views/` showing view files | Source files were copied into the image, but `.next/` build output was from the OLD commit |
| "LAST BUILT 1m" in coder list | Workspace was recently started, but from the old image |

### Verification Commands That Should Have Been Run Earlier

1. `docker buildx imagetools inspect ghcr.io/.../course-workspace:latest` — check the actual GHCR digest
2. Compare GHCR digest with `docker inspect <container> --format '{{.Image}}'` on the VPS
3. `docker exec <container> cat /agent-ui/.next/BUILD_ID` — check the Next.js build ID
4. Check the template's "LAST UPDATED" timestamp in the Coder dashboard

### Fix

```bash
# Clear ALL buildx cache (not just -f)
docker buildx prune -af

# Build and push directly to registry, bypassing buildx push cache
docker buildx build --platform linux/amd64 --no-cache --output type=registry \
  -t ghcr.io/pedrogrande/course-workspace:latest \
  -f Dockerfile.workspace .
```

Key differences from the failing approach:

- `prune -af` (not just `-f`) — clears all cache including push manifests
- `--output type=registry` — pushes directly to registry, bypassing buildx push cache
- `--no-cache` — forces fresh build of all layers

### Explanation

The `--push` flag uses buildx's internal push mechanism which caches the registry manifest. `--output type=registry` pushes directly to the registry without that cache layer. This is the critical difference.

**Key lesson:** Always verify the GHCR digest changed after a push:

```bash
docker buildx imagetools inspect ghcr.io/.../image:latest
```

Compare the digest before and after the push. If it didn't change, the push didn't work. Use `--output type=registry` instead of `--push` for buildx cross-compilation pushes.

---

## Issue 15: CORS Errors — Agent-UI Cannot Reach AgentOS API

### Symptom

```
Access to fetch at 'http://agentos--starter-one--pedrog.coder.viberiders.club/health'
from origin 'http://agent-ui--starter-one--pedrog.coder.viberiders.club'
has been blocked by CORS policy: Response to preflight request doesn't pass
access control check: Redirect is not allowed for a preflight request.
```

The Agent-UI showed "not connected" and the custom Views navigation was hidden (it only renders when the endpoint is active).

### Root Cause

When accessed via Coder subdomain proxying, Agent-UI and AgentOS are on **different subdomains** (different origins). The browser sends a CORS preflight (OPTIONS) request to the AgentOS subdomain. The Coder proxy intercepts the OPTIONS request and redirects (for auth) — but browsers don't allow redirects for preflight requests.

This also explained why the custom views weren't showing: the `ViewNav` component only renders when `isEndpointActive` is true. Since the endpoint couldn't connect (CORS error), `isEndpointActive` was false, so the Views nav was hidden. The UI looked like the "default" Agent-UI because the custom navigation never appeared.

### Fix

Added a Next.js API route (`/api/proxy/[...path]/route.ts`) that proxies requests server-side. The browser calls `/api/proxy/*` on the Agent-UI's own origin (same subdomain, no CORS). The Next.js server forwards the request to the AgentOS API server-side, where CORS doesn't apply.

Updated `detectDefaultEndpoint()` in `src/store.ts` to return `${window.location.origin}/api/proxy` when on a Coder subdomain, instead of the cross-origin AgentOS URL.

### Explanation

Server-to-server requests don't have CORS restrictions — CORS is a browser-only security mechanism. By proxying through the Next.js server, the browser only talks to the Agent-UI's own origin. The Next.js server then makes the request to the AgentOS API (either `localhost:8000` for SSH tunnel access, or the `agentos--` subdomain for Coder proxy access).

**Key lesson:** When deploying a frontend and API on different Coder subdomains, use a server-side proxy to avoid CORS. The browser should never make cross-origin requests to Coder-proxied endpoints.

---

## Issue 16: Path-Based Proxy Breaking Next.js Static Assets

### Symptom

```
Refused to apply style from 'http://74.208.237.168/_next/static/css/31d31879efc140bd.css'
because its MIME type ('text/html') is not a supported stylesheet MIME type,
and strict MIME checking is enabled.
```

### Root Cause

With `subdomain = false` (the default for `coder_app`), Coder proxies the app via a path-based URL like `http://74.208.237.168/@pedrog/starter-one/apps/agent-ui/`. Next.js generates absolute asset paths like `/_next/static/css/...` in its HTML. The browser resolves these to `http://74.208.237.168/_next/static/css/...` — missing the Coder proxy subpath. The Coder server returns HTML (the dashboard) for unknown paths, causing the MIME type mismatch.

### Fix

1. Set up a domain with wildcard DNS: `*.coder.viberiders.club` → `74.208.237.168`
2. Configured `CODER_WILDCARD_ACCESS_URL=*.coder.viberiders.club` on the VPS
3. Set `subdomain = true` on both `coder_app` resources in the template

With subdomain proxying, the app is accessed at `agent-ui--starter-one--pedrog.coder.viberiders.club` — its own origin, so absolute asset paths work correctly.

### Explanation

The Coder docs state: "`CODER_WILDCARD_ACCESS_URL` is necessary for port forwarding via the dashboard or running `coder_apps` on an absolute path." Path-based proxying (`subdomain = false`) doesn't work with SPAs like Next.js that generate absolute asset paths. Subdomain proxying (`subdomain = true`) gives each app its own origin, avoiding the path mismatch.

**Key lesson:** Always use `subdomain = true` for Next.js (or any SPA) apps in Coder. This requires a domain with wildcard DNS — plan for this during infrastructure setup.

---

## Issue 17: Agent-UI Default Endpoint Showing Port 7777

### Symptom

The Agent-UI sidebar showed `http://localhost:7777` as the default endpoint, but AgentOS runs on port 8000.

### Root Cause

The upstream Agent-UI repo defaults to `http://localhost:7777` (Agno's default dev port). The store change to `http://localhost:8000` was committed to the fork but the Docker image on the VPS was the old one (see Issue 14 — buildx push cache).

Additionally, the Zustand `persist` middleware stores the endpoint in `localStorage`. If a user previously visited with the old default, the persisted value takes precedence over the new default.

### Fix

1. Changed the default in `src/store.ts` to use `detectDefaultEndpoint()` (auto-detects the correct URL)
2. Added a `version: 2` migration to the persist config to clear stale `localStorage` values
3. Fixed the buildx push issue (Issue 14) so the new image actually reached the VPS

### Explanation

The default endpoint is persisted in `localStorage` via Zustand's `persist` middleware. If a student previously connected to a different endpoint, the persisted value takes precedence over the default. The `version: 2` migration clears old values so the new auto-detect default is used.

**Key lesson:** When changing default values in a Zustand store with `persist`, always bump the version and add a migration to clear stale values.

---

## Summary

| # | Issue | Category | Severity | Time to Resolve |
|---|-------|----------|----------|-----------------|
| 1 | TLS config mismatch | Configuration | High | 5 min |
| 2 | PostgreSQL can't run as root | Configuration | High | 10 min |
| 3 | External Postgres URL pointing to nothing | Configuration | High | 5 min |
| 4 | Deprecated env var | Configuration | Low | 2 min |
| 5 | ARM64 image on AMD64 VPS | Architecture | High | 15 min |
| 6 | Stale cached image | Docker caching | Medium | 5 min |
| 7 | Default CMD running before agent | Template design | High | 20 min |
| 8 | Agent not starting (sleep infinity) | Template design | High | 15 min |
| 9 | Git clone URL corruption | Terraform interpolation | High | 30 min |
| 10 | replace() corrupting init script | Terraform functions | High | 20 min |
| 11 | GitHub repo not updated | Git workflow | High | 5 min |
| 12 | Isolated network blocking agent | Networking | Medium | 10 min |
| 13 | GHCR image private | Registry config | Low | 5 min |
| 14 | Buildx push cache — silent stale image | Docker buildx | Critical | 3+ hours |
| 15 | CORS errors — Agent-UI can't reach API | CORS / proxy | High | 1 hour |
| 16 | Path-based proxy breaking Next.js assets | Coder proxy | High | 20 min |
| 17 | Default endpoint showing port 7777 | Configuration | Low | 10 min |

**Total troubleshooting time:** ~8 hours (initial setup ~2.5h, Agent-UI integration ~5.5h)

**Key themes:**

1. **Configuration accuracy** — the setup guide had several assumptions that didn't match the actual VPS setup (TLS, external Postgres, root user). Always verify config against the actual environment.
2. **Architecture mismatch** — building on Apple Silicon for AMD64 deployment requires explicit cross-compilation. This is a common pitfall for Mac-based developers.
3. **Coder agent lifecycle** — understanding the init_script → agent → startup_script flow is critical. The agent must start first, then it runs the startup script. The container's entrypoint must be the init script, not the app.
4. **Terraform interpolation caution** — `replace()` and `${...}` interpolation can have unintended effects on complex strings like the init script. Hardcode values that don't need to be dynamic.
5. **Git workflow** — always push changes to GitHub before testing workspace creation. The workspace clones from GitHub, not from your local machine.
6. **Docker buildx push cache** (CRITICAL) — `docker buildx build --push` can silently fail to update the registry manifest. Always verify the digest changed with `docker buildx imagetools inspect`. Use `--output type=registry` instead of `--push` for cross-compilation pushes.
7. **CORS with Coder subdomains** — when frontend and API are on different Coder subdomains, use a server-side proxy to avoid CORS. The browser should never make cross-origin requests to Coder-proxied endpoints.
8. **Coder subdomain proxying** — SPAs with absolute asset paths (like Next.js) require `subdomain = true` on `coder_app` resources, which requires wildcard DNS. Plan for this during infrastructure setup.
