# WMS AI Agent — Natural Language Query Interface

A Python microservice that lets you query your WMS database using natural language. Powered by Azure OpenAI.

## Architecture

```
User Question → Azure OpenAI (NL→SQL) → SQL Validator → MySQL (read-only) → Result Summarizer → Response
```

## Quick Start

### 1. Prerequisites
- Python 3.11+
- MySQL 8.0+ (your existing WMS database)
- Azure OpenAI resource with a deployed model (GPT-4o recommended)

### 2. Setup

```bash
# Clone / navigate to project
cd wms-ai-agent

# Create virtual environment
python -m venv .venv
source .venv/bin/activate   # Linux/Mac
# .venv\Scripts\activate    # Windows

# Install dependencies
pip install -r requirements.txt

# Create read-only MySQL user
mysql -u root -p < setup_readonly_user.sql

# Configure environment
cp .env.example .env
# Edit .env with your Azure OpenAI and MySQL credentials
```

### 3. Run

```bash
# Development
uvicorn app.main:app --reload --port 8000

# Or
python -m app.main
```

### 4. Test

```bash
# Health check
curl http://localhost:8000/health

# Ask a question
curl -X POST http://localhost:8000/api/ai/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the total inventory on hand?"}'

# Follow-up
curl -X POST http://localhost:8000/api/ai/follow-up \
  -H "Content-Type: application/json" \
  -d '{"question": "Break that down by client", "thread_id": "t-xxx", "parent_node_id": "n-xxx"}'

# List threads
curl http://localhost:8000/api/ai/threads
```

### 5. API Docs
Visit `http://localhost:8000/docs` for interactive Swagger UI.

## Project Structure

```
wms-ai-agent/
├── app/
│   ├── main.py                  # FastAPI entry point
│   ├── config.py                # Settings from .env
│   ├── routers/
│   │   ├── query.py             # POST /query, /follow-up
│   │   └── threads.py           # Thread CRUD
│   ├── services/
│   │   ├── sql_generator.py     # NL → SQL (Azure OpenAI)
│   │   ├── sql_validator.py     # Safety checks
│   │   ├── query_executor.py    # MySQL execution
│   │   ├── result_formatter.py  # Summarization
│   │   └── thread_manager.py    # SQLite thread storage
│   ├── prompts/
│   │   └── system_prompt.py     # Schema + glossary + few-shot
│   └── models/
│       └── schemas.py           # Pydantic models
├── setup_readonly_user.sql      # MySQL user setup
├── requirements.txt
├── Dockerfile
└── .env.example
```

## Security

- **Read-only MySQL user** — the agent cannot modify data
- **SQL validation layer** — blocks INSERT/UPDATE/DELETE/DROP
- **Table whitelist** — blocks access to users/roles/permissions
- **Query timeout** — 10 second max execution
- **Row limit** — 500 rows max per query
- **No sensitive tables** — auth tables explicitly blocked

## Azure Setup

1. Create an Azure OpenAI resource in Azure Portal
2. Deploy a model (GPT-4o recommended)
3. Copy endpoint + API key to your `.env` file
