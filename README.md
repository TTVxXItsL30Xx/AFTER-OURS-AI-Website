# AFTER OURS

AFTER OURS is a self-hosted content discovery and production control room. It discovers public YouTube opportunities through the official Data API, keeps discovery separate from authorised media ingestion, and carries approved source media through transcription, moment review, FFmpeg rendering, scheduling, publication records, and stored analytics.

The V1 is designed for a single private Ubuntu deployment. Optional providers can be absent: the application still boots, exposes its setup checklist, accepts authorised media, and runs the clearly labelled local transcription and analysis fallbacks.

## Architecture

| Service | Responsibility |
| --- | --- |
| `frontend` | Next.js 16 App Router control-room UI on host port `3200` |
| `backend` | FastAPI REST API, validation, file ingestion, and system checks on localhost port `8100` |
| `worker` | Redis-backed Celery jobs for ingestion, transcription, analysis, rendering, discovery, publishing, and analytics |
| `scheduler` | Celery Beat dispatch for discovery rules, due publications, and analytics refresh |
| `postgres` | Durable application records; internal Docker network only |
| `redis` | Queue broker and task results; internal Docker network only |
| shared media volume | Authorised uploads and validated render outputs |

PostgreSQL and Redis do not publish host ports. The backend is bound to `127.0.0.1` by default. Put the frontend behind your HTTPS reverse proxy for internet access, and expose the backend only if your network design requires it.

## Product areas

- **Overview:** database-backed totals, recent discoveries and clips, job activity, publishing state, health, quick actions, and first-launch checklist.
- **Discover:** official YouTube Data API search, duplicate protection, filtering, scoring, save/ignore, creator follow, rules, and blacklists.
- **Creators:** monitoring state, frequency, tags, source permission, notes, detail history, and removal.
- **Sources:** permission confirmation, extension and size validation, filename sanitisation, SHA-256 duplicate detection, durable upload storage, and background inspection.
- **Studio:** source preview, transcript state, provider-labelled transcript, moment suggestions, editable clip ranges, hook/caption settings, FFmpeg render jobs, SRT generation, and validated outputs.
- **Queue / Published:** persistent editorial and scheduling statuses, platform connection guards, retry/error fields, cancellation, and publication history.
- **Analytics:** stored publication snapshots only. Empty state is shown when no real provider data exists.
- **Settings:** setup checklist, discovery guardrails, provider/runtime information, connection states, storage, processing, worker jobs, and service health.

## Prerequisites

- Ubuntu 22.04 or newer
- Docker Engine with the Compose v2 plugin
- 4 GB RAM minimum; 8 GB or more recommended for video work
- Enough disk capacity for source and output media
- A YouTube Data API key for discovery (optional at boot)
- HTTPS reverse proxy and DNS for a remote production deployment

FFmpeg is installed in the backend/worker image. It does not need to be installed on the Ubuntu host.

## Ubuntu deployment

```bash
git clone https://github.com/TTVxXItsL30Xx/AFTER-OURS-AI-Website.git
cd AFTER-OURS-AI-Website
git checkout codex/after-ours-v1
cp .env.example .env
nano .env
docker compose up -d --build
docker compose ps
docker compose logs -f backend worker scheduler
```

Open `http://SERVER_IP:3200`. Browser API requests use the same origin and are proxied by the frontend to the internal backend. The API documentation is also available locally at `http://127.0.0.1:8100/api/docs` on the server.

At minimum, replace `POSTGRES_PASSWORD`. The default relative `NEXT_PUBLIC_API_URL=/api/v1` works through the frontend proxy and keeps FastAPI private. If you deliberately expose the API on a separate HTTPS origin, change `NEXT_PUBLIC_API_URL` and add the frontend origin to `CORS_ORIGINS`, then rebuild the frontend:

```bash
docker compose up -d --build frontend backend
```

### Environment setup

The checked-in [.env.example](./.env.example) is the complete configuration reference.

Important values:

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | SQLAlchemy connection from containers to PostgreSQL |
| `REDIS_URL` | Celery broker/result Redis URL |
| `NEXT_PUBLIC_API_URL` | Browser API base; `/api/v1` uses the built-in same-origin proxy |
| `INTERNAL_API_URL` | Backend origin used only by the frontend container proxy |
| `CORS_ORIGINS` | Comma-separated allowed browser origins |
| `MEDIA_ROOT` | Shared media root inside backend and worker containers |
| `UPLOAD_MAX_MB` | Server-enforced maximum upload size |
| `YOUTUBE_API_KEY` | Optional official YouTube Data API discovery key |
| `TRANSCRIPTION_PROVIDER` | `mock` in V1; provider interface is ready for an external adapter |
| `ANALYSIS_PROVIDER` | `mock` in V1; provider interface is ready for an external adapter |
| `DEMO_MODE` | Must be explicitly `true` before the demo seed command will run |

Do not commit `.env`. Secrets are read by the containers and connection values shown in the UI are masked.

## YouTube discovery setup

1. Create or select a Google Cloud project.
2. Enable **YouTube Data API v3**.
3. Create an API key and restrict it to that API. Apply IP restrictions appropriate for the Ubuntu server where possible.
4. Set `YOUTUBE_API_KEY` in `.env`.
5. Restart the backend, worker, and scheduler:

```bash
docker compose up -d --force-recreate backend worker scheduler
```

6. Open **Settings → Connections** and run the YouTube Discovery connection test.

Discovery uses only official API metadata. AFTER OURS does not download YouTube videos. A discovery can enter Studio only after it has a separate authorised/local source record.

## AI provider setup

V1 includes explicit `TranscriptionProvider` and `AnalysisProvider` contracts plus local mock implementations. Mock results say that the fallback produced them; they are not presented as speech-accurate AI output. The workflow can therefore be tested without a key.

The `.env.example` reserves `OPENAI_API_KEY`. To add OpenAI later, implement provider classes in `backend/app/services/providers.py`, return timed transcript segments / moment dictionaries through the existing result types, and select the adapter with `TRANSCRIPTION_PROVIDER` and `ANALYSIS_PROVIDER`. No route or database redesign is required.

## Database migrations

The backend runs `alembic upgrade head` whenever its container starts. Manual commands:

```bash
docker compose exec backend alembic current
docker compose exec backend alembic upgrade head
```

Create a migration after changing SQLAlchemy models:

```bash
docker compose exec backend alembic revision --autogenerate -m "describe change"
docker compose exec backend alembic upgrade head
```

## Optional development data

Seed data is never automatic and is refused unless demo mode is explicitly enabled. On a disposable development database:

```bash
sed -i 's/^DEMO_MODE=false/DEMO_MODE=true/' .env
docker compose up -d backend
docker compose exec backend python -m app.seed
```

The seed records are labelled demo data and perform no external upload. Set `DEMO_MODE=false` again before a production deployment.

## Local development

Frontend (Node.js 20.9+; Node 22 recommended):

```bash
cd frontend
corepack enable
pnpm install
pnpm dev
```

Backend (Python 3.13 recommended):

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8100
```

For local backend development, start PostgreSQL and Redis through Docker and adjust `DATABASE_URL` / `REDIS_URL` to use mapped development ports, or run the whole Compose stack.

## Quality checks

```bash
cd frontend
pnpm lint
pnpm typecheck
pnpm build

cd ../backend
ruff check .
pytest
python -m compileall -q app

cd ..
docker compose config
docker compose build
```

## Video pipeline

1. The API accepts only configured extensions and enforces the streaming upload limit.
2. An ingest worker runs `ffprobe` and marks the source ready only when real media inspection succeeds.
3. The selected transcription provider produces text and timed segments.
4. The selected analysis provider stores scored moments.
5. An editor creates a clip project with validated start/end times.
6. FFmpeg trims, centre-fills a vertical `1080×1920` canvas, preserves audio, optionally burns an SRT, writes metadata, and creates a fast-start MP4.
7. `ffprobe` validates duration, dimensions, and a non-empty finished file before the render is marked ready.

Failures and their real stderr summaries are persisted in processing/render records. A failed render is never returned as successful.

## Publishing integrations

Publishing provider contracts and setup states exist for YouTube, TikTok, and Instagram. V1 deliberately does **not** fake OAuth or platform uploads. Until an official adapter and account token flow are installed, Settings shows **Not configured** and Publish Now returns a clear setup/adapter message without transmitting anything.

External credentials reserved in `.env.example`:

- YouTube publishing client ID and secret
- TikTok client key and secret
- Instagram app ID and secret
- OpenAI API key

Use the official APIs and current platform review requirements when implementing these adapters.

## Troubleshooting

**The UI says the API is unavailable**

```bash
docker compose ps
curl http://127.0.0.1:8100/health/live
docker compose logs --tail=200 backend
```

Check that `NEXT_PUBLIC_API_URL` is reachable from the browser, not merely from inside Docker. Rebuild the frontend after changing it.

**The worker or scheduler is unhealthy**

```bash
docker compose logs --tail=200 worker scheduler redis
docker compose restart worker scheduler
```

**Upload accepted but inspection failed**

Inspect the source error in Sources or the worker log. Confirm that the file contains a supported video stream and is not truncated.

**FFmpeg render failed**

Look at the render/processing error in Studio and:

```bash
docker compose exec worker ffmpeg -version
docker compose logs --tail=300 worker
```

Subtitle burn-in requires a valid transcript and FFmpeg's subtitles filter, both included in the image.

**YouTube search fails**

Use the Settings connection test. Check API enablement, key restrictions, quota, and server egress. No results are silently invented when the API is unavailable.

**Reset a disposable installation**

This deletes PostgreSQL, Redis, and media volumes and is irreversible:

```bash
docker compose down
docker volume ls | grep after-ours
# Only after verifying the project and accepting data loss:
docker compose down -v
```

## Project structure

```text
.
├── backend/
│   ├── alembic/                 # schema migrations
│   ├── app/
│   │   ├── routers/             # API surfaces by product area
│   │   ├── services/            # scoring, providers, and FFmpeg helpers
│   │   ├── models.py            # indexed SQLAlchemy domain model
│   │   ├── worker.py            # Celery jobs and schedules
│   │   └── seed.py              # guarded development seed
│   └── tests/
├── frontend/
│   ├── app/                     # every sidebar area is a real App Router route
│   ├── components/              # navigation, feedback, and reusable UI
│   └── lib/                     # API client and TypeScript domain types
├── media/                       # local non-Docker development directories
├── docker-compose.yml
└── .env.example
```

## V1 boundaries

- YouTube is the only discovery provider implemented; Twitch, RSS, podcast, and other providers fit the discovery/source contracts but have no adapter yet.
- Local upload is the implemented source adapter. Watched folders, Twitch imports, direct licensed-media imports, and podcast/RSS ingestion need adapters.
- The local mock providers exercise transcription/analysis state and output shapes. A production speech/LLM provider still needs to be connected.
- Official YouTube, TikTok, and Instagram OAuth/upload/analytics adapters are not implemented. The UI and backend report this honestly.
- The V1 is a private single-admin deployment; multi-user authentication and tenant isolation are not included.
- FFmpeg V1 uses centre crop/scale. Face tracking and keyframed reframing are later Studio enhancements.

## Security notes

- Keep the backend on localhost or a private network unless it is protected by your reverse proxy and access controls.
- Add authentication before exposing the application to untrusted users; V1 assumes a private admin network.
- Keep `.env` permissions restricted, rotate platform credentials, patch Docker images, and back up PostgreSQL/media volumes.
- Apply upload limits at both the reverse proxy and application layers.
- Imported filenames are sanitised, media endpoints use resolved-path containment, and database/Redis ports remain internal by default.
