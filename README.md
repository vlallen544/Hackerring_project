# VidyaPath

## Setup

Create and activate a virtual environment, then install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and set `AGNES_API_KEY` before running Agnes scripts. Never commit `.env`.

## Run the API

From the repository root:

```bash
uvicorn backend.main:app --reload
```

Health check: <http://localhost:8000/health>. Interactive API docs: <http://localhost:8000/docs>.

## Run the frontend

```bash
streamlit run frontend/app.py
```

## Check Agnes

```bash
python scripts/hello_agnes.py
python scripts/test_client.py
```

The reusable Agnes client is `backend/tools/agnes_client.py`; it provides per-process rate limiting, disk caching, transient-error retries, and Pydantic-validated JSON responses.