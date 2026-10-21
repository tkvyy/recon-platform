# Automated Attack Surface Reconnaissance Platform

A web platform that automates passive subdomain discovery (Subfinder) and live
HTTP probing (HTTPx). Scans run asynchronously through a Redis/Celery queue so
the web interface never blocks.

**Use only on domains you own or are explicitly authorized to test.**

## Architecture
Next.js UI -> FastAPI -> Redis queue -> Celery worker -> Subfinder -> HTTPx -> SQLite

## Requirements
Python 3.11+, Node.js 20+, Go, Redis, Subfinder, HTTPx

## Setup
```bash
# Recon tools
go install -v github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest
go install -v github.com/projectdiscovery/httpx/cmd/httpx@latest

# Backend
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Frontend
cd ../frontend && npm install
```

## Run (four processes)
```bash
sudo service redis-server start                     # 1. Redis
cd backend && celery -A app.celery_app worker --loglevel=info   # 2. Worker
cd backend && uvicorn app.main:app --reload         # 3. API (port 8000)
cd frontend && npm run dev                          # 4. UI (port 3000)
```
Open http://localhost:3000, enter a domain, and click Start scan.
API docs: http://localhost:8000/docs

## Tests
```bash
cd backend && python -m pytest -v
```

## Project structure
- `backend/app/` API, worker tasks, recon wrappers, models, validators
- `backend/tests/` unit tests
- `frontend/` Next.js interface
- `docs/` design document, dev log, bug log
