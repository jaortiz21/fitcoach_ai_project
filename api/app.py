from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List
import os
import requests
import json
import sqlite3
import time
from datetime import datetime

# ------------------ Utils ------------------

def ollama_post_with_retry(payload, max_retries=3, timeout=240):
    delay = 2

    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.post(
                OLLAMA_URL,
                json=payload,
                timeout=timeout,
            )
            resp.raise_for_status()
            return resp

        except requests.exceptions.ReadTimeout:
            print(f"[OLLAMA] Timeout attempt {attempt}/{max_retries}")
        except requests.exceptions.ConnectionError as e:
            print(f"[OLLAMA] Connection error: {e}")
        except Exception:
            raise

        if attempt < max_retries:
            time.sleep(delay)
            delay *= 2

    raise RuntimeError("Ollama request failed after retries")

def should_summarize(conversation_id: str) -> bool:
    db = get_db()
    row = db.execute("""
        SELECT updated_at FROM summaries WHERE conversation_id = ?
    """, (conversation_id,)).fetchone()
    db.close()

    if not row:
        return True

    last = datetime.fromisoformat(row[0])
    return (datetime.utcnow() - last).seconds > 300

# ------------------ Config ------------------
# All of these are overridable via environment variables so the same image
# works in docker-compose (see docker-compose.yml OLLAMA_HOST/OLLAMA_MODEL),
# ECS (Infrastructure/*.tf), or plain local dev without code changes.

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://ollama:11434")
OLLAMA_URL = f"{OLLAMA_HOST.rstrip('/')}/api/chat"
MODEL_NAME = os.environ.get("OLLAMA_MODEL", "fitcoach")

DB_PATH = os.environ.get("DB_PATH", "data/conversations.db")

SUMMARY_TRIGGER_TURNS = int(os.environ.get("SUMMARY_TRIGGER_TURNS", "5"))   # turns (user+assistant)
RECENT_TURNS = int(os.environ.get("RECENT_TURNS", "4"))                     # turns to keep verbatim

# Comma-separated list of allowed browser origins for the frontend, e.g.
# "http://localhost:8080,https://coach.example.com". Defaults to "*" for
# homelab/local use -- tighten this before exposing the API publicly.
CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "*")

# ------------------ App ------------------

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if CORS_ORIGINS == "*" else [o.strip() for o in CORS_ORIGINS.split(",")],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    """Basic liveness/readiness check for docker healthchecks and the frontend."""
    return {"status": "ok", "model": MODEL_NAME}

@app.on_event("startup")
def warm_model():
    try:
        requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL_NAME,
                "stream": False,
                "messages": [{"role": "user", "content": "ping"}],
            },
            timeout=30,
        )
        print("[OLLAMA] Model warmed")
    except Exception as e:
        print(f"[OLLAMA] Warmup failed: {e}")

# ------------------ Database ------------------

def get_db():
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def init_db():
    db = get_db()

    db.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT,
            role TEXT,
            content TEXT,
            created_at TEXT
        )
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS summaries (
            conversation_id TEXT PRIMARY KEY,
            content TEXT,
            updated_at TEXT
        )
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS profile (
            conversation_id TEXT PRIMARY KEY,
            goals TEXT,
            constraints TEXT,
            preferences TEXT,
            updated_at TEXT
        )
    """)

    db.commit()
    db.close()


init_db()

# ------------------ Profiles ------------------

def load_profile(conversation_id: str) -> Optional[str]:
    db = get_db()
    row = db.execute("""
        SELECT goals, constraints, preferences
        FROM profile
        WHERE conversation_id = ?
    """, (conversation_id,)).fetchone()
    db.close()

    if not row:
        return None

    goals, constraints, preferences = row

    parts = []
    if goals:
        parts.append(f"Goals: {goals}")
    if constraints:
        parts.append(f"Constraints: {constraints}")
    if preferences:
        parts.append(f"Preferences: {preferences}")

    return "\n".join(parts) if parts else None


def load_profile_dict(conversation_id: str) -> Optional[dict]:
    """Like load_profile(), but returns the raw {goals, constraints, preferences}
    dict instead of a formatted string. Used by diff_profile() when computing
    what changed, since load_profile()'s string output can't be diffed."""
    db = get_db()
    row = db.execute("""
        SELECT goals, constraints, preferences
        FROM profile
        WHERE conversation_id = ?
    """, (conversation_id,)).fetchone()
    db.close()

    if not row:
        return None

    goals, constraints, preferences = row
    return {"goals": goals, "constraints": constraints, "preferences": preferences}


def upsert_profile(conversation_id: str, updates: dict):
    db = get_db()
    if not updates:
        print("[PROFILE UPSERT] No changes detected")
        return

    columns = ", ".join(updates.keys())
    placeholders = ", ".join(["?"] * len(updates))
    update_clause = ", ".join([f"{k}=excluded.{k}" for k in updates.keys()])

    values = list(updates.values())

    db.execute(
        f"""
        INSERT INTO profile (conversation_id, {columns})
        VALUES (?, {placeholders})
        ON CONFLICT(conversation_id)
        DO UPDATE SET
            {update_clause},
            updated_at=CURRENT_TIMESTAMP
        """,
        [conversation_id] + values,
    )

    db.commit()

    print(f"[PROFILE UPSERT] Updated fields: {list(updates.keys())}")


def extract_profile_candidates(conversation_id: str) -> dict:
    history = load_history(conversation_id)

    if not history:
        return {}

    convo_text = "\n".join(
        f"{m['role']}: {m['content']}" for m in history
    )

    prompt = f"""
Analyze the following conversation.
Extract ONLY stable, factual user attributes.

Return valid JSON with these keys:
- goals
- constraints
- preferences

Rules:
- Do NOT invent facts
- Do NOT infer medical conditions
- Only include information explicitly stated
- Use null if no new information exists
- Keep values concise (1–2 sentences max)

Conversation:
{convo_text}
"""

    resp = ollama_post_with_retry(
        {
            "model": MODEL_NAME,
            "stream": False,
            "messages": [
                {
                    "role": "system",
                    "content": "You extract structured user profile data."
                },
                {
                    "role": "user",
                    "content": prompt
                },
            ],
        },
        timeout=240,
    )

    try:
        data = resp.json()
        import re

        raw = data["message"]["content"].strip()

        # Attempt direct parse
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass

        # Fallback: extract first JSON object
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except Exception:
                pass

        print("[PROFILE EXTRACT FAILED]")
        print(raw)
        return {}

    except Exception as e:
        print(f"[PROFILE EXTRACT ERROR] {e}")
        print(f"[PROFILE EXTRACT RAW] {resp.text}")
        return {}

def normalize_profile_candidates(candidates: dict) -> dict:
    normalized = {}

    for key in ["goals", "constraints", "preferences"]:
        value = candidates.get(key)

        if value is None:
            normalized[key] = None
            continue

        # If already a string, keep it
        if isinstance(value, str):
            normalized[key] = value.strip()
            continue

        # If dict, flatten into a readable string
        if isinstance(value, dict):
            parts = []
            for k, v in value.items():
                if v:
                    parts.append(f"{k}: {v}")
            normalized[key] = "; ".join(parts) if parts else None
            continue

        # Fallback: stringify safely
        normalized[key] = str(value)

    return normalized

def diff_profile(existing: dict | None, incoming: dict) -> dict:
    if existing is None:
        # New profile → insert everything non-null
        return {k: v for k, v in incoming.items() if v}

    updates = {}

    for key, new_value in incoming.items():
        if not new_value:
            continue  # never overwrite with null

        old_value = existing.get(key)

        if old_value != new_value:
            updates[key] = new_value

    return updates

# ------------------ Models ------------------

class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    stream: Optional[bool] = False


# ------------------ Memory ------------------

def save_message(conversation_id: Optional[str], role: str, content: str):
    if not conversation_id:
        return

    db = get_db()
    db.execute("""
        INSERT INTO messages (conversation_id, role, content, created_at)
        VALUES (?, ?, ?, ?)
    """, (conversation_id, role, content, datetime.utcnow().isoformat()))
    db.commit()
    db.close()


def message_count(conversation_id: str) -> int:
    db = get_db()
    count = db.execute(
        "SELECT COUNT(*) FROM messages WHERE conversation_id = ?",
        (conversation_id,)
    ).fetchone()[0]
    db.close()
    return count


def get_summary(conversation_id: str) -> Optional[str]:
    db = get_db()
    row = db.execute(
        "SELECT content FROM summaries WHERE conversation_id = ?",
        (conversation_id,)
    ).fetchone()
    db.close()
    return row[0] if row else None


def save_summary(conversation_id: str, content: str):
    db = get_db()
    db.execute("""
        INSERT INTO summaries (conversation_id, content, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(conversation_id)
        DO UPDATE SET content=excluded.content, updated_at=excluded.updated_at
    """, (conversation_id, content, datetime.utcnow().isoformat()))
    db.commit()
    db.close()


def load_history(conversation_id: Optional[str]) -> List[dict]:
    if not conversation_id:
        return []

    history = []

    summary = get_summary(conversation_id)
    if summary:
        history.append({
            "role": "system",
            "content": f"Conversation summary:\n{summary}"
        })

    db = get_db()
    rows = db.execute("""
        SELECT role, content
        FROM messages
        WHERE conversation_id = ?
        ORDER BY id DESC
        LIMIT ?
    """, (conversation_id, RECENT_TURNS * 2)).fetchall()
    db.close()

    history.extend(
        {"role": r[0], "content": r[1]}
        for r in reversed(rows)
    )

    return history


# ------------------ Summarization ------------------

def summarize(conversation_id: str):
    try:
        print(f"[SUMMARY] Running summarization for {conversation_id}")

        db = get_db()
        rows = db.execute("""
            SELECT role, content
            FROM messages
            WHERE conversation_id = ?
            ORDER BY id ASC
        """, (conversation_id,)).fetchall()
        db.close()

        convo = "\n".join([f"{r}: {c}" for r, c in rows])

        prompt = f"""
Extract stable, factual user attributes from the conversation below.

Return ONLY a valid JSON object.
Do NOT include markdown, code blocks, or explanations.

The JSON MUST have exactly these keys:
- goals
- constraints
- preferences

Each value MUST be:
- a single concise string, or
- null

Do NOT use nested objects.
Do NOT use arrays.
Do NOT infer or invent information.

Conversation:
{convo}
"""

        resp = ollama_post_with_retry({
            "model": MODEL_NAME,
            "stream": False,
            "messages": [
                {"role": "system", "content": "You summarize conversations."},
                {"role": "user", "content": prompt},
            ],
        })


        resp.raise_for_status()
        summary = resp.json()["message"]["content"]

        save_summary(conversation_id, summary)
        print(f"[SUMMARY] Saved summary")

        db = get_db()
        db.execute("""
            DELETE FROM messages
            WHERE conversation_id = ?
            AND id NOT IN (
                SELECT id FROM messages
                WHERE conversation_id = ?
                ORDER BY id DESC
                LIMIT ?
            )
        """, (conversation_id, conversation_id, RECENT_TURNS * 2))
        db.commit()
        db.close()

        print(f"[SUMMARY] Pruned old messages")

    except Exception as e:
        print(f"[SUMMARY ERROR] {e}")

    candidates = extract_profile_candidates(conversation_id)
    if not candidates:
        print("[PROFILE EXTRACT ERROR] Invalid JSON")
        return
    print(f"[PROFILE CANDIDATES] {candidates}")

    normalized = normalize_profile_candidates(candidates)
    if not normalized:
        print("[PROFILE NORMALIZE] Nothing usable")
        return
    print(f"[PROFILE CANDIDATES NORMALIZED] {normalized}")

    existing = load_profile_dict(conversation_id)
    print(f"[PROFILE EXISTING] {existing}")

    updates = diff_profile(existing, normalized)
    print(f"[PROFILE UPDATES] {updates}")

    upsert_profile(conversation_id, updates)

def load_summary(conversation_id: str) -> Optional[str]:
    db = get_db()
    row = db.execute("""
        SELECT content
        FROM summaries
        WHERE conversation_id = ?
        ORDER BY updated_at DESC
        LIMIT 1
    """, (conversation_id,)).fetchone()
    db.close()

    return row[0] if row else None

# ------------------ Chat Handlers ------------------

def chat_non_streaming(message: str, conversation_id: Optional[str]) -> str:
    summary = load_summary(conversation_id)

    messages = [
        {
            "role": "system",
            "content": (
                "You are a fitness coach who is firm but fair. "
                "You provide structured guidance, accountability, "
                "and practical advice without being harsh."
            )
        }
    ]

    profile = load_profile(conversation_id)
    if profile:
        messages.append({
            "role": "system",
            "content": f"User profile:\n{profile}"
        })

    if summary:
        messages.append({
            "role": "system",
            "content": f"Summary of previous conversations:\n{summary}"
        })

    messages.extend(load_history(conversation_id))
    messages.append({"role": "user", "content": message})

    resp = requests.post(
        OLLAMA_URL,
        json={
            "model": MODEL_NAME,
            "stream": False,
            "messages": messages,
        },
        timeout=240,
    )

    resp.raise_for_status()
    reply = resp.json()["message"]["content"]

    save_message(conversation_id, "user", message)
    save_message(conversation_id, "assistant", reply)

    count = message_count(conversation_id)
    print(f"[DEBUG] messages={count}")

    if count >= SUMMARY_TRIGGER_TURNS * 2 and should_summarize(conversation_id):
        summarize(conversation_id)

    return reply


def chat_streaming(message: str, conversation_id: Optional[str]):
    summary = load_summary(conversation_id)

    messages = [
        {
            "role": "system",
            "content": (
                "You are a fitness coach who is firm but fair. "
                "You provide structured guidance, accountability, "
                "and practical advice without being harsh."
            )
        }
    ]

    profile = load_profile(conversation_id)
    if profile:
        messages.append({
            "role": "system",
            "content": f"User profile:\n{profile}"
        })

    if summary:
        messages.append({
            "role": "system",
            "content": f"Summary of previous conversations:\n{summary}"
        })

    messages.extend(load_history(conversation_id))
    messages.append({"role": "user", "content": message})

    resp = requests.post(
        OLLAMA_URL,
        json={
            "model": MODEL_NAME,
            "stream": True,
            "messages": messages,
        },
        stream=True,
        timeout=240,
    )

    resp.raise_for_status()
    assistant_tokens = []

    def token_generator():
        # NOTE: this generator body only runs as the client consumes the
        # StreamingResponse, so persistence and the summarization check must
        # happen *after* the loop below (inside this generator), not right
        # after StreamingResponse(...) is constructed -- at that point no
        # tokens have been produced yet and assistant_tokens would be empty.
        try:
            for line in resp.iter_lines():
                if not line:
                    continue
                payload = json.loads(line)
                if "message" in payload:
                    token = payload["message"]["content"]
                    assistant_tokens.append(token)
                    yield token
        finally:
            save_message(conversation_id, "user", message)
            save_message(conversation_id, "assistant", "".join(assistant_tokens))

            count = message_count(conversation_id)
            print(f"[DEBUG] messages={count}")

            if count >= SUMMARY_TRIGGER_TURNS * 2 and should_summarize(conversation_id):
                summarize(conversation_id)

    return StreamingResponse(token_generator(), media_type="text/plain")


# ------------------ API ------------------

@app.post("/chat")
def chat(req: ChatRequest):
    if req.stream:
        return chat_streaming(req.message, req.conversation_id)

    reply = chat_non_streaming(req.message, req.conversation_id)
    return {"response": reply}
