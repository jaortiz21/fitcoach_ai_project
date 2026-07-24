# FitCoach API – Memory‑Aware Chat Backend

This repository contains a **memory‑aware chat API** designed to support long‑running conversations with automatic summarization, profile extraction, and safe message pruning. The system is intentionally built in **incremental layers**, starting with SQLite and Docker Compose, while being structured for a clean migration to Postgres and multi‑service deployment later.

A static web frontend (`frontend/`) now ships alongside the API so the assistant can be used like any other chat product, not just via `curl`.

For a deeper look at where the architecture has rough edges and what's worth fixing next, see [`ARCHITECTURE.md`](./ARCHITECTURE.md).

---

## What We’ve Built So Far

### 1. Chat API (FastAPI + Uvicorn)

* Supports **streaming** and **non‑streaming** chat endpoints
* Messages are persisted per `conversation_id`
* Compatible with local LLMs via **Ollama**
* `/health` endpoint for liveness checks (used by the Docker healthcheck and the frontend's connection indicator)
* CORS enabled so a browser-based frontend can call the API directly

### 2. Conversation Summarization

* Automatically triggers after **N turns** (e.g. 24 messages)
* Uses an LLM to generate **compressed summaries** of older messages
* Summaries are stored in a dedicated `summaries` table
* Original messages are **pruned safely** after summarization

This prevents unbounded context growth while preserving semantic history.

---

### 3. Profile Extraction & Memory

The system now includes **long‑term user memory** extracted from conversations.

#### Profile Signals Tracked

* **Goals** (e.g. consistency, strength, fat loss)
* **Constraints** (e.g. 60‑minute workouts)
* **Preferences** (e.g. HIIT cardio, machine‑based exercises)

#### How It Works

1. Recent messages are summarized
2. A dedicated extraction prompt produces **flat JSON**
3. Output is normalized into canonical values
4. A diff is computed against existing profile memory
5. Only **new or improved** data is persisted (guarded upsert)
6. The stored profile is injected back into the system prompt on every chat turn, so the coach actually remembers goals/constraints/preferences across the conversation

This prevents regressions and noisy overwrites.

> Note: memory here is entirely SQLite-backed (raw messages + LLM summaries + structured profile fields). A Qdrant vector database is also provisioned in `docker-compose.yml`, but nothing in `app.py` calls it yet — see the "Qdrant" item in ARCHITECTURE.md.

---

### 4. Guarded Memory Writes (Important)

* Profile writes are **diff‑based**
* `NULL` or empty values never overwrite valid data
* Writes are skipped if nothing changed

This makes memory:

* Stable
* Auditable
* Migration‑safe

---

### 5. Resilience Improvements

* Ollama calls include **retry + backoff**
* Model warming avoids cold‑start timeouts
* Summarization failures do not block chat responses
* SQLite runs in **WAL mode** with an explicit busy timeout, so concurrent requests from multiple conversations don't trip over each other with `database is locked` errors

---

### 6. Frontend

* Single-file HTML/CSS/JS chat UI in `frontend/`, no build step or dependencies
* Streams responses from `/chat`, shows a live online/offline indicator against `/health`
* Keeps a sidebar of past conversations — **stored client-side in the browser's `localStorage`**, not fetched from the server, since the API doesn't currently expose an endpoint to list or retrieve past conversations (see TODO below)
* Served via its own nginx container in `docker-compose.yml`

---

## Current Data Model (SQLite)

### Tables

#### `messages`

| column          | description         |
| --------------- | ------------------- |
| id              | message id          |
| conversation_id | logical chat thread |
| role            | user / assistant    |
| content         | message text        |
| created_at      | timestamp           |

#### `summaries`

| column          | description        |
| --------------- | ------------------ |
| conversation_id | chat thread        |
| content         | compressed summary |
| created_at      | timestamp          |

#### `profile`

| column          | description            |
| --------------- | ---------------------- |
| conversation_id | chat thread            |
| goals           | normalized goals       |
| constraints     | normalized constraints |
| preferences     | normalized preferences |
| updated_at      | last write             |

---

## 🐳 Deployment with Docker Compose

### Prerequisites

* Docker
* Docker Compose v2

### Directory Layout

```
.
├── api/
│   ├── app.py
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── index.html
│   ├── nginx.conf
│   └── Dockerfile
├── models/
│   ├── Modelfile
│   ├── init-models.sh
│   └── Dockerfile        # used for the ECS/model image, not docker-compose
├── Infrastructure/        # Terraform for an AWS ECS deployment target
├── docker-compose.yml
└── data/
    └── conversations.db   # created on first run, gitignored
```

### Services & Ports

| Service    | Port                | Purpose                                   |
| ---------- | -------------------- | ------------------------------------------ |
| `frontend` | `8080` → 80          | Chat UI                                    |
| `api`      | `8000` → 8000         | FastAPI backend                            |
| `ollama`   | `11434` → 11434       | LLM runtime                                |
| `qdrant`   | `6333`/`6334`         | Vector DB (provisioned, currently unused)  |

### Environment Variables (`api` service)

All of these are read at startup with sensible defaults, so the API also runs standalone outside Docker:

| Variable                | Default                     | Purpose                                                       |
| ------------------------ | ---------------------------- | -------------------------------------------------------------- |
| `OLLAMA_HOST`            | `http://ollama:11434`        | Base URL of the Ollama server                                  |
| `OLLAMA_MODEL`           | `fitcoach`                   | Model name to chat against                                     |
| `DB_PATH`                | `data/conversations.db`      | SQLite file location                                            |
| `CORS_ORIGINS`           | `*`                          | Comma-separated allowed origins for the frontend (compose sets this to `http://localhost:8080`) |
| `SUMMARY_TRIGGER_TURNS`  | `5`                          | Turns before summarization kicks in                             |
| `RECENT_TURNS`           | `4`                          | Verbatim turns kept after summarization                         |

### 1. Start the Stack

```bash
docker compose up --build
```

This brings up Ollama (pulling the base + embedding models and building the `fitcoach` model on first run — can take a few minutes), Qdrant, the API, and the frontend.

### 2. Use it

* **Chat UI:** open `http://localhost:8080`
* **Direct API:**

```bash
curl http://localhost:8000/chat -H "Content-Type: application/json" -d "{\"conversation_id\":\"$CONVO_ID\", \"message\":\"Message\"}"
```

* **Health check:**

```bash
curl http://localhost:8000/health
```

### Stop the Stack

```bash
docker compose down
```

---

## Validation & Debugging

### Exec into API Container

```bash
docker compose exec api bash
```

### Inspect SQLite

```bash
sqlite3 data/conversations.db
.tables
SELECT * FROM profile;
```

### Useful Logs

* `[PROFILE EXTRACT RAW]`
* `[PROFILE CANDIDATES NORMALIZED]`
* `[PROFILE UPSERT]`
* `[SUMMARY]` (search for this prefix — logging is currently `print()`-based, see TODO)

---

## Known Intentional Limitations

* SQLite is single‑writer (mitigated with WAL mode, but still a ceiling at real scale)
* Profile memory is scoped per `conversation_id`, not per authenticated user
* No auth / multi‑user separation yet — anyone who knows a `conversation_id` can read/write it

A full breakdown of these and other architectural tradeoffs is in [`ARCHITECTURE.md`](./ARCHITECTURE.md).

---

## Design Philosophy

This system is built as:

* A **real LLM memory architecture**, not a demo
* Incremental, debuggable, migration‑friendly
* Suitable for both Python *and* future Go backends

If you understand this codebase, you understand how modern AI systems actually work.

---

## TODO

Tracked here the same way we track work-in-progress in chat — status, then what it is. Update this list as items land instead of letting it go stale (the "Next Planned Steps" section this replaced hadn't been touched in 6 months, and by the time we looked at it, item #1 on it had quietly already been done).

### Done (last 3 commits, dev branch)

- [x] Fix `summarize()` crash — undefined variable + wrong types passed to `diff_profile()`, threw `NameError` on every summarization
- [x] Fix streaming responses never being saved — persistence ran before the client had consumed any tokens
- [x] Read `OLLAMA_HOST` / `OLLAMA_MODEL` / `DB_PATH` / `CORS_ORIGINS` from env instead of hardcoding
- [x] Add `/health` endpoint, CORS middleware, pinned `requirements.txt`, Docker `HEALTHCHECK`
- [x] Fix stale `docker-compose.yml` mount path that broke `docker compose up`
- [x] Build static frontend (`frontend/`) and wire it into `docker-compose.yml`
- [x] Write `ARCHITECTURE.md` architecture review
- [x] Enable SQLite WAL mode + busy timeout for concurrent multi-user access

### Not yet verified

- [ ] **Load-test multi-user concurrency against a live stack.** The WAL/busy-timeout fix above was applied based on code inspection, not a live test — no docker/network access was available in the environment it was written in. Plan: run `docker compose up`, then a script that fires concurrent requests from several distinct `conversation_id`s and checks for cross-talk, lock errors, and broken streaming.
- [ ] End-to-end smoke test of `/chat` (streaming + non-streaming) against a real Ollama model, not just a syntax check

### Next up (from ARCHITECTURE.md, roughly priority order)

- [ ] Decide on Qdrant: either wire up real embedding-based retrieval, or drop the container + `qdrant-client` dependency and correct the README/compose to describe SQLite-only memory
- [ ] Add auth so `conversation_id` isn't a bare guessable secret — needed before this is exposed beyond your own network, per the "serve any consumer" goal
- [ ] Add `GET`/`DELETE` endpoints for conversations, so the frontend's `localStorage` sidebar can become a real reflection of server state instead of a client-side-only mirror
- [ ] Fix Terraform/ECS drift: no Qdrant task definition, API's EFS mount path (`/app/storage`) doesn't match where the app actually writes (`/app/data`), and `container_port_api`/`container_port_model` defaults look swapped
- [ ] Add a minimal test suite + CI (even a smoke test would have caught the two bugs fixed in this round six months earlier)
- [ ] Replace `print()` logging with Python's `logging` module
- [ ] Move blocking `requests` calls to async `httpx` if concurrent load ever becomes a real bottleneck
