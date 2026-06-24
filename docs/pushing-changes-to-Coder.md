## How Agent-UI gets into the Coder workspace

```
Your local agent-ui repo → GitHub → Docker image (GHCR) → VPS pull → Workspace rebuild
```

The Dockerfile.workspace **clones your `pedrogrande/agent-ui` fork from GitHub** at build time (line 22: `git clone https://github.com/pedrogrande/agent-ui.git`). So the Docker image is the delivery mechanism — there's no live sync.

## Steps to push your changes

**1. Commit and push your Agent-UI changes to GitHub:**

```bash
cd /Users/peteargent/edgeos/agent-ui
git add -A
git commit -m "Add file upload to knowledge view"
git push
```

**2. Rebuild the Docker image (from the agentic-starter repo):**

```bash
cd /Users/peteargent/edgeos/agentic-starter
docker buildx prune -af
docker buildx build --platform linux/amd64 --no-cache --output type=registry \
  -t ghcr.io/pedrogrande/course-workspace:latest \
  -f Dockerfile.workspace .
```

The `--no-cache` and `prune -af` are important — without them, buildx can silently reuse a cached layer that has the old `git clone` of agent-ui (this bit us before, see Issue 14 in the docs).

**3. Pull the new image on the VPS:**

```bash
ssh root@74.208.237.168 'docker pull ghcr.io/pedrogrande/course-workspace:latest'
```

**4. Recreate the workspace:**

```bash
ssh root@74.208.237.168 'echo yes | coder stop pedrog/starter; sleep 5; echo yes | coder start pedrog/starter'
```

The workspace container gets recreated with the new image on start. Students' data persists (it's on the Docker volume at `/app/data`).

## Pushing template changes (main.tf)

When you change `coder-template/main.tf` (resource limits, startup script, IDE options, etc.):

```bash
# 1. Copy the template to the VPS
scp coder-template/main.tf root@74.208.237.168:/tmp/main.tf

# 2. Push the template (API keys are read from TF_VAR_* env vars on the VPS)
ssh root@74.208.237.168 'cp /tmp/main.tf /tmp/coder-template/ && cd /tmp/coder-template && \
  echo yes | coder templates push agentos-course --directory .'

# 3. Recreate the workspace to pick up the changes
ssh root@74.208.237.168 'echo yes | coder stop pedrog/starter; sleep 5; echo yes | coder start pedrog/starter'
```

**API key setup (one-time on the VPS):** The API keys are stored as `TF_VAR_*` environment variables on the VPS, not in the template file (which is in a public repo). Terraform automatically picks up `TF_VAR_<name>` as the value for `variable "<name>"`.

```bash
# On the VPS, one-time setup — add to /etc/coder/coder.env:
ssh root@74.208.237.168 'cat >> /etc/coder/coder.env << EOF
TF_VAR_openai_api_key=sk-your-key-here
TF_VAR_ollama_api_key=ollama-your-key-here
EOF'
ssh root@74.208.237.168 'systemctl restart coder'
```

After this, every `coder templates push` and every workspace build will have the keys available — no `--var` flags needed. Students don't enter API keys; they're injected automatically.

## Hot-reload and restarting the API

The AgentOS API runs with `--reload`, which watches files in `agents/` and `app/`. Edits to existing files (tweaking instructions, changing tools, updating `config.yaml`) are picked up automatically — just refresh the browser.

A full restart is needed when adding a **new** agent file or registering a new agent/team in `app/main.py`. Students run:

```bash
./scripts/restart-api.sh
```

This stops the old uvicorn process, starts a fresh one with hot-reload, and waits for the API to be ready. Logs go to `/tmp/agentos.log`.

**TL;DR:** Push to GitHub → rebuild Docker image → pull on VPS → stop/start workspace. The Docker image is the bridge between your local Agent-UI and the Coder workspace.
