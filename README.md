## closedai-chatbot

Small FastAPI app with a streaming `POST /question` endpoint and a static `index.html` client.

## 1. Prerequisites

- Python 3.13+
- `uv` installed

Install `uv` (Windows PowerShell):

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Verify:

```bash
uv --version
python --version
```

## 2. Clone and install dependencies

After cloning this repository:

From your project folder:

```bash
uv sync
```

This creates/updates `.venv` and installs everything from `pyproject.toml` / `uv.lock`.

## 3. Environment variables

Create a `.env` in the project root:

```env
API_KEY=your_openrouter_or_provider_key
BASE_URL=https://openrouter.ai/api/v1 #(or any OpenAI capable API)
LLM_MODEL=your_chosen_model
```

Required:
- `DEFAULT_CONTEXT` (always injected as system context for every request)

## 4. Run the API

```bash
uv run uvicorn main:app --app-dir src --reload --port 8000
```

Server will be available at:
- `http://localhost:8000`
- Health check: `http://localhost:8000/health`

## 5. Use the static web client (`index.html`)

`index.html` is in the project root and calls:
- `http://localhost:8000/question`


## 6. API usage (manual test)

Endpoint:
- `POST /question`

Request body:

```json
{
  "question": "What is Langfuse?",
  "context": "Use only info from internal docs from 2026 Q1.",
  "history": [
    { "role": "user", "content": "What is observability?" },
    { "role": "assistant", "content": "Observability is..." }
  ],
  "history_window": 6
}
```

`context` is optional and is added as per-request system context.  
`history` is optional prior chat messages.  
`history_window` controls how many recent turns are included.

Response:
- Streaming `text/plain` chunks

Example with `curl`:

```bash
curl -N -X POST http://localhost:8000/question \
  -H "Content-Type: application/json" \
  -d "{\"question\":\"What is Langfuse?\",\"context\":\"Explain for a non-technical manager.\",\"history\":[{\"role\":\"user\",\"content\":\"What is observability?\"},{\"role\":\"assistant\",\"content\":\"Observability is...\"}],\"history_window\":6}"
```