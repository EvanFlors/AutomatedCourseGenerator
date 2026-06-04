# Course Automation

Auto-generate structured courses from mixed content sources (YouTube, PDFs, URLs, free-form text) and store the resulting knowledge in a graph database for rich querying and visualization.

## Architecture

This project follows **Domain-Driven Design (DDD)** and **Clean Architecture** principles. See [`Arquitecture.md`](./Arquitecture.md) for the full layout.

**Bounded contexts**
- `course` — course/structure management (modules, topics, content blocks)
- `content` — source material ingestion, chunks, embeddings
- `generation` — auto-generation jobs and pipeline orchestration
- `knowledge_graph` — concept nodes and typed relations (Neo4j)
- `learning` — user progress (future)

**Layers**
```
src/
├── domain/           # Pure business logic (no external deps)
├── application/      # Use cases / orchestration
├── infrastructure/   # Adapters: Postgres, Neo4j, Gemini, ingestors
├── interfaces/       # Delivery mechanisms (FastAPI REST, WebSocket, CLI)
└── bootstrap/        # Wiring (DI, settings, app factory)
```

## Stack

| Concern | Technology |
|---|---|
| API | FastAPI + Pydantic v2 |
| Relational DB | PostgreSQL (SQLAlchemy 2.0 async + Alembic) |
| Graph DB | Neo4j (knowledge graph, Cypher) |
| LLM | Google Gemini (text + embeddings) |
| Frontend | Vite + React + TypeScript + react-flow (planned) |
| Tests | pytest + pytest-asyncio + testcontainers |

## Quick start

```bash
# 1. Install
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# 2. Configure
cp .env.example .env
# Edit .env with your credentials (Gemini, Postgres, Neo4j)

# 3. Run migrations
alembic upgrade head

# 4. Start the API
uvicorn src.main:app --reload
```

## Project status

**Sprint 0** — Foundations
- [x] Domain entities: `Course`, `Module`, `Topic`, `ContentBlock`
- [x] Course repository port
- [x] Domain exceptions
- [ ] Persistence (Postgres + Neo4j)
- [ ] Generation pipeline (Gemini)
- [ ] FastAPI endpoints
- [ ] React frontend
- [ ] docker-compose
