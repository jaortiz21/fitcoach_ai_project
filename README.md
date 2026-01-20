# FitCoach Homelab Stack

This project sets up a local AI "fitness coach" assistant with **memory** using Ollama, Qdrant, and FastAPI.

---

## Features
- **Ollama** runs your LLMs locally (e.g., DeepSeek, Llama3).
- **Qdrant** stores embeddings for long-term memory.
- **FastAPI** glues everything together into a simple chat API.
- **Docker Compose** handles orchestration.

---

## Prerequisites
- Docker + Docker Compose installed
- At least one Ollama model installed (e.g. `deepseek`)
- Optional: your custom Modelfile in `./models`

---

## Usage

### 1 Start the stack
```bash
docker compose up --build -d
```

### 2 (Optional) Build your model
If you have a Modelfile under `models/fitcoach/Modelfile`:
```bash
docker exec -it ollama ollama create fitcoach -f /models/fitcoach/Modelfile
```

### 3 Chat with your coach
```bash
curl http://localhost:8000/chat -H "Content-Type: application/json" -d "{\"conversation_id\":\"$CONVO_ID\", \"message\":\"Message\"}"
```

---

## How It Works
1. Your message is embedded via `nomic-embed-text` (Ollama).
2. The vector and message are stored in Qdrant.
3. On each new message, similar past context is retrieved.
4. The combined context is sent to the model (`deepseek` by default).
5. The reply is returned and also stored for future reference.

---

## Components
- `ollama`: LLM runtime
- `qdrant`: vector database for memory
- `api`: FastAPI service

---

## Stop the stack
```bash
docker compose down
```

---

## Notes
- Adjust model names in `app.py` if using something other than `deepseek`.
- To switch embedding models, change the model used in `embed_text()`.
- Data persists across runs via Docker volumes.
