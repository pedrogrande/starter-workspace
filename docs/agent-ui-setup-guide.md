# Agent-UI Setup Guide: Adding Custom Views to Coder Workspaces

This guide walks through the complete process of integrating Agent-UI (with custom management views) into a Coder workspace. It incorporates all lessons learned from the initial implementation (see `agent-ui-implementation-issues.md` for issues and root causes).

**Prerequisites:**

- A working Coder workspace setup (see `coder-workspace-setup-guide.md`)
- A GitHub account for forking Agent-UI
- Docker Desktop with buildx support on your local machine
- A domain with wildcard DNS configured for Coder (see `infrastructure-setup.md`)

---

## Step 1: Fork Agent-UI

```bash
# Fork via GitHub API (or use the GitHub UI)
gh api repos/agno-agi/agent-ui/forks -X POST

# Clone your fork locally
git clone https://github.com/<YOUR_USERNAME>/agent-ui.git
cd agent-ui
```

---

## Step 2: Fix pnpm Build Scripts

The upstream repo has a `sharp` dependency that fails to build on Node 22+. Apply the fix from `sharp-build-fix.md`:

### 2.1 Add `onlyBuiltDependencies` to `package.json`

```json
{
  "pnpm": {
    "overrides": {
      "picomatch": ">=2.3.2"
    },
    "onlyBuiltDependencies": ["esbuild"]
  },
  "packageManager": "pnpm@10.33.0"
}
```

### 2.2 Commit and push

```bash
git add package.json
git commit -m "Fix sharp build: add onlyBuiltDependencies whitelist, pin pnpm version"
git push origin main
```

---

## Step 3: Add Custom View Types, Routes, and API Functions

### 3.1 Add TypeScript types to `src/types/os.ts`

Add interfaces for session details, user memories, knowledge content, and vector search results. Use `Record<string, unknown>` (not `any`) for flexible JSON fields to satisfy ESLint's `no-explicit-any` rule.

Key types to add:

- `AgentSessionDetail`, `TeamSessionDetail`, `WorkflowSessionDetail` — session detail responses
- `UserMemory`, `UserMemoryCreate`, `DeleteMemoriesRequest` — memory management
- `ContentResponse`, `ContentStatus`, `VectorSearchRequest`, `VectorSearchResult` — knowledge management
- `PaginatedResponse<T>` — generic paginated response wrapper
- Fix `SessionEntry.created_at` to `string | number` (API returns ISO datetime strings)
- Fix `Pagination` to include `search_time_ms`

### 3.2 Add API routes to `src/api/routes.ts`

Add route functions for all new endpoints. **No `/v1/` prefix** — all routes are at the root level:

```typescript
// Sessions
GetSessionDetail: (url, id) => `${url}/sessions/${id}`,
RenameSession: (url, id) => `${url}/sessions/${id}/rename`,
DeleteSessions: (url) => `${url}/sessions`,

// Memory
GetMemories: (url) => `${url}/memories`,
CreateMemory: (url) => `${url}/memories`,
// ... etc

// Knowledge
GetKnowledgeContent: (url) => `${url}/knowledge/content`,
UploadContent: (url) => `${url}/knowledge/content`,
SearchKnowledge: (url) => `${url}/knowledge/search`,
// ... etc
```

### 3.3 Add API functions to `src/api/os.ts`

Follow the existing `createHeaders()` pattern. **Critical:** for `uploadContentAPI()`, do NOT use `createHeaders()` — FormData needs the browser to set the Content-Type with multipart boundary:

```typescript
// For FormData uploads — no Content-Type header
const headers: HeadersInit = {}
if (authToken) headers['Authorization'] = `Bearer ${authToken}`
const response = await fetch(url, { method: 'POST', headers, body: formData })
```

### 3.4 Update `src/store.ts`

Add `viewMode` state and change the default endpoint:

```typescript
viewMode: 'chat' | 'sessions' | 'memory' | 'knowledge'
setViewMode: (viewMode) => set(() => ({ viewMode }))

// Change default from 7777 to 8000
selectedEndpoint: 'http://localhost:8000',
```

---

## Step 4: Add Navigation and View Components

### 4.1 Add ViewNav to Sidebar (`src/components/chat/Sidebar/Sidebar.tsx`)

Add a navigation section with 4 buttons (Chat, Sessions, Memory, Knowledge) using `lucide-react` icons. Only show chat-specific sections (mode selector, entity selector, sessions list) when `viewMode === 'chat'`.

### 4.2 Update `src/app/page.tsx` for conditional rendering

```tsx
{viewMode === 'chat' && <ChatArea />}
{viewMode === 'sessions' && <SessionsView />}
{viewMode === 'memory' && <MemoryView />}
{viewMode === 'knowledge' && <KnowledgeView />}
```

### 4.3 Create view components in `src/components/views/`

- `SessionsView.tsx` — paginated session list + detail panel with chat history
- `MemoryView.tsx` — memory list + create/edit form + optimize with preview
- `KnowledgeView.tsx` — content list + text/URL upload + hybrid search

**Important:** Check the actual export name of UI components before importing. The textarea component is exported as `TextArea` (capital A), not `Textarea`:

```typescript
// Correct
import { TextArea } from '@/components/ui/textarea'
// Wrong
import { Textarea } from '@/components/ui/textarea'  // Type error!
```

---

## Step 5: Commit and Push All Changes

```bash
git add -A
git commit -m "Add Sessions, Memory, and Knowledge management views"
git push origin main
```

---

## Step 6: Update the Workspace Dockerfile

### 6.1 Add multi-stage build for Agent-UI

The Dockerfile needs a builder stage that clones the fork, installs dependencies, and builds the Next.js production bundle. The final image copies the pre-built Agent-UI alongside the Python dependencies.

Key points:

- Use `node:22-slim` as the builder base
- Install `git` and `ca-certificates` in the builder (slim images don't include them)
- Pin pnpm version: `corepack prepare pnpm@10.33.0 --activate`
- Use `pnpm install --no-frozen-lockfile` (the fork's package.json may differ from the lockfile)
- Set `NEXT_PUBLIC_OS_API_URL=http://localhost:8000` as a build-time env var
- Copy the built Agent-UI to the final image: `COPY --from=agent-ui-builder /agent-ui /agent-ui`
- Install Node.js runtime in the final image for `next start`

### 6.2 Example Dockerfile.workspace

```dockerfile
# Stage 1: Build Agent-UI
FROM node:22-slim AS agent-ui-builder
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates && rm -rf /var/lib/apt/lists/*
RUN corepack enable && corepack prepare pnpm@10.33.0 --activate
WORKDIR /agent-ui
RUN git clone https://github.com/<YOUR_USERNAME>/agent-ui.git . && \
    pnpm install --no-frozen-lockfile
ENV NEXT_PUBLIC_OS_API_URL=http://localhost:8000
RUN pnpm build

# Stage 2: Final image
FROM agnohq/python:3.12
RUN apt-get update && apt-get install -y --no-install-recommends curl git postgresql-client && rm -rf /var/lib/apt/lists/*
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && rm -rf /var/lib/apt/lists/*
WORKDIR /app
ENV PYTHONPATH=/app
COPY requirements.txt ./
RUN uv pip sync requirements.txt --system
COPY --from=agent-ui-builder /agent-ui /agent-ui
ENV DB_BACKEND=sqlite RUNTIME_ENV=dev AGNO_DEBUG=True DATA_DIR=/app/data NEXT_PUBLIC_OS_API_URL=http://localhost:8000
RUN mkdir -p /app/data
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## Step 7: Update the Coder Template

### 7.1 Add `subdomain = true` to both `coder_app` resources

**Critical for Next.js:** Path-based proxying breaks absolute asset paths. Subdomain proxying gives the app its own origin.

```hcl
resource "coder_app" "agent_ui" {
  # ...
  subdomain = true  # Required for Next.js apps
}

resource "coder_app" "agentos" {
  # ...
  subdomain = true
}
```

### 7.2 Update the startup script to run both processes

```bash
# Start AgentOS API in the background
uvicorn app.main:app --host 0.0.0.0 --port 8000 &

# Wait for AgentOS to be ready
until curl -s http://localhost:8000/ > /dev/null 2>&1; do sleep 1; done

# Start Agent-UI in the foreground (clean kill on workspace stop)
cd /agent-ui && exec npx next start -p 3000
```

### 7.3 Bump memory limit

```hcl
memory = 1610612736  # 1.5 GB (uvicorn + Next.js + ChromaDB)
```

---

## Step 8: Configure Wildcard DNS

**Required for `subdomain = true` to work.**

1. Create two A records in your DNS provider:
   - `coder.yourdomain.com` → VPS IP
   - `*.coder.yourdomain.com` → VPS IP (wildcard)

2. Update Coder config on the VPS:

```bash
cat > /etc/coder/coder.env << 'EOF'
CODER_HTTP_ADDRESS=0.0.0.0:80
CODER_ACCESS_URL=http://coder.yourdomain.com
CODER_WILDCARD_ACCESS_URL=*.coder.yourdomain.com
EOF

systemctl restart coder
```

---

## Step 9: Build, Push, and Deploy

### 9.1 Build the image

```bash
cd /path/to/your/repo
docker buildx build --platform linux/amd64 \
  -t ghcr.io/<USERNAME>/course-workspace:latest \
  -f Dockerfile.workspace --push .
```

**If the build fails with stale code after pushing changes to the fork:**

```bash
# Clear the buildx cache completely
docker buildx prune -f

# Rebuild
docker buildx build --platform linux/amd64 \
  -t ghcr.io/<USERNAME>/course-workspace:latest \
  -f Dockerfile.workspace --push .
```

### 9.2 Clear old image on VPS

```bash
ssh root@<VPS_IP> "docker rm -f student-<username>-<workspace> 2>/dev/null; docker rmi ghcr.io/<USERNAME>/course-workspace:latest"
```

### 9.3 Push template and recreate workspace

```bash
export CODER_URL=http://coder.yourdomain.com
export CODER_SESSION_TOKEN=<your-token>

coder templates push agentos-course -d coder-template --yes
coder delete <username>/<workspace> --yes
coder create <workspace> --template agentos-course \
  --parameter openai_api_key=<key> \
  --parameter ollama_api_key=<key> \
  --yes
```

---

## Step 10: Verify

1. Open `http://coder.yourdomain.com` → dashboard
2. Click workspace → **Agent UI** app link
3. Verify:
   - Endpoint shows `http://localhost:8000` (not 7777)
   - Server shows connected with available agents
   - **Views** section in sidebar with 4 buttons: Chat, Sessions, Memory, Knowledge
   - CSS loads correctly (no MIME type errors in browser console)
4. Test each view:
   - **Chat:** Send a message, verify response
   - **Sessions:** Verify chat session appears in list, click to view history
   - **Memory:** Add a memory, verify it appears, edit and delete it
   - **Knowledge:** Upload text content, wait for processing, search it

---

## Troubleshooting Quick Reference

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| `server certificate verification failed` | Missing CA certs in slim image | Add `ca-certificates` to apt-get install |
| `ERR_PNPM_LOCKFILE_CONFIG_MISMATCH` | Lockfile doesn't match package.json | Use `--no-frozen-lockfile` |
| `ERR_PNPM_IGNORED_BUILDS: sharp` | pnpm 10+ build script approval | Add `pnpm.onlyBuiltDependencies` to package.json |
| `no-explicit-any` ESLint error | Using `any` type | Replace with `unknown` |
| `has no exported member named 'Textarea'` | Wrong export name | Use `TextArea` (capital A) |
| Stale code in Docker build | buildx cache | `docker buildx prune -f` |
| CSS MIME type error | Path-based proxy | Set `subdomain = true` + wildcard DNS |
| Default endpoint shows 7777 | Store default not updated | Change `selectedEndpoint` to `localhost:8000` |
| Agent-UI shows old version | VPS has cached image | `docker rmi` on VPS, recreate workspace |

---

## File Reference

| File | Location | Purpose |
|------|----------|---------|
| `Dockerfile.workspace` | Main repo | Multi-stage build: Agent-UI + Python deps |
| `coder-template/main.tf` | Main repo | Coder template with `subdomain = true` and dual-process startup |
| `src/types/os.ts` | Agent-UI fork | TypeScript interfaces for API responses |
| `src/api/routes.ts` | Agent-UI fork | API route URL builders |
| `src/api/os.ts` | Agent-UI fork | Fetch functions for all API endpoints |
| `src/store.ts` | Agent-UI fork | Zustand store with `viewMode` state |
| `src/app/page.tsx` | Agent-UI fork | Conditional rendering based on `viewMode` |
| `src/components/chat/Sidebar/Sidebar.tsx` | Agent-UI fork | ViewNav navigation component |
| `src/components/views/SessionsView.tsx` | Agent-UI fork | Sessions management view |
| `src/components/views/MemoryView.tsx` | Agent-UI fork | Memory management view |
| `src/components/views/KnowledgeView.tsx` | Agent-UI fork | Knowledge management view |
