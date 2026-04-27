## closedai-chatbot

FastAPI backend for a DNN CMS embedded webshop chatbot.

The production chatbot UI is embedded in the DNN CMS. The root `index.html`
file is only a small local test client for manual API testing during
development.

## 1. Prerequisites

- Python 3.14+
- `uv` installed
- SQL Server access through an installed ODBC driver
- An OpenAI-compatible LLM API endpoint
- Langfuse credentials, if tracing/observability is enabled

Install `uv` on Windows PowerShell:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Verify:

```bash
uv --version
python --version
```

## 2. Install dependencies

From the project root:

```bash
uv sync
```

This creates or updates `.venv` and installs the dependencies from
`pyproject.toml` / `uv.lock`.

## 3. Configuration

Create a local `.env` file from `.env.sample`:

```powershell
Copy-Item .env.sample .env
```

Then fill in the real secret values.

Required variables:

- `API_KEY`: API key for the OpenAI-compatible LLM provider.
- `BASE_URL`: Base URL of the OpenAI-compatible API.
- `LLM_MODEL`: Model identifier used for router and formatter calls.
- `DB_CONNECTION_STRING`: ODBC-style SQL Server connection string.

Langfuse variables used by the Langfuse OpenAI wrapper:

- `LANGFUSE_SECRET_KEY`
- `LANGFUSE_PUBLIC_KEY`
- `LANGFUSE_BASE_URL`

The router and formatter system prompts are defined in
`src/prompts/system.py`; they are not configured through `.env`.

## 4. Run the API locally

```bash
uv run uvicorn main:app --app-dir src --reload --port 8080
```

Server URLs:

- API root and local test client: `http://localhost:8080`
- Health check: `http://localhost:8080/health`
- Chat endpoint: `POST http://localhost:8080/question`

## 5. API usage

Endpoint:

- `POST /question`

Request body:

```json
{
  "question": "Melyek a legnepszerubb termekek?",
  "history": [
    { "role": "user", "content": "Segits modella autot valasztani." },
    { "role": "assistant", "content": "Milyen kategoriaban keresel?" }
  ],
  "history_window": 4
}
```

`history` is optional. `history_window` controls how many recent messages are
included in the model context.

Response:

```json
{
  "answer": "...",
  "tool_used": "get_hot_products",
  "data": {
    "products": []
  }
}
```

`tool_used` and `data` can be `null` when the model answers directly without a
database-backed tool.

Example with `curl`:

```bash
curl -N -X POST http://localhost:8080/question \
  -H "Content-Type: application/json" \
  -d "{\"question\":\"Melyek a legnepszerubb termekek?\",\"history\":[],\"history_window\":4}"
```

## 6. Local test client

`index.html` is a small development-only client. It calls:

- `http://localhost:8080/question`
