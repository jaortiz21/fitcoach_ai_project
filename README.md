# FitCoach API – Memory‑Aware Chat Backend

This repository contains a **memory‑aware chat API** designed to support long‑running conversations with automatic summarization, profile extraction, and safe message pruning. The system is intentionally built in **incremental layers**, starting with SQLite and Docker Compose, while being structured for a clean migration to Postgres and multi‑service deployment later.

---

## What We’ve Built So Far

### 1. Chat API (FastAPI + Uvicorn)

* Supports **streaming** and **non‑streaming** chat endpoints
* Messages are persisted per `conversation_id`
* Compatible with local LLMs via **Ollama**

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

This prevents regressions and noisy overwrites.

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
* Ollama installed **or** running as a container

---

### 1. Directory Layout

```
.
├── api/
│   ├── app.py
│   ├── requirements.txt
│   └── Dockerfile
├── docker-compose.yml
└── data/
    └── fitcoach.db
```

---

### 2. Dockerfile (API)

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

### 3. docker-compose.yml

```yaml
version: "3.9"

services:
  api:
    build: ./api
    ports:
      - "8000:8000"
    volumes:
      - ./data:/data
    environment:
      - DB_PATH=/data/fitcoach.db
      - OLLAMA_BASE_URL=http://host.docker.internal:11434
    restart: unless-stopped
```

> I `host.docker.internal` allows the container to reach a locally running Ollama instance.

---

### 4. Start the Stack

```bash
docker compose up --build
```

API will be available at:

```
http://localhost:8000
```

---

## Validation & Debugging

### Exec into API Container

```bash
docker compose exec api bash
```

### Inspect SQLite

```bash
sqlite3 /data/fitcoach.db
.tables
SELECT * FROM profile;
```

### Useful Logs

* `[PROFILE EXTRACT RAW]`
* `[PROFILE CANDIDATES NORMALIZED]`
* `[PROFILE UPSERT]`
* `[SUMMARY CREATED]`

---

## Known Intentional Limitations

* SQLite is single‑writer
* Profile memory is scoped per `conversation_id`
* No auth / multi‑user separation yet

These are **deliberate**, to keep iteration speed high.

---

## Next Planned Steps

1. **Inject profile memory into chat prompts**
2. Add confidence / reinforcement gating
3. Migrate SQLite → Postgres
4. Cross‑conversation memory
5. Multi‑user support

---

## Design Philosophy

This system is built as:

* A **real LLM memory architecture**, not a demo
* Incremental, debuggable, migration‑friendly
* Suitable for both Python *and* future Go backends

If you understand this codebase, you understand how modern AI systems actually work.
