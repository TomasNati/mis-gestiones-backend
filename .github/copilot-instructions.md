Build, test, and lint commands

- Install deps: pip install -r requirements.txt
- Run dev server: uvicorn main:app --reload --port 5001
- Environment: set DATABASE_URL in a .env (python-dotenv is used)
- Tests: no tests detected. When tests are added, run a single test with:
  pytest tests/test_file.py::test_name
- Lint: no linter configured in repo (add flake8/ruff/black if desired)

High-level architecture

- main.py: FastAPI app and route definitions (endpoints under /api/*).
- db.py: Database layer using SQLAlchemy ORM sessions; implements query helpers, pagination, sorting and CRUD helpers.
- structure.py: SQLAlchemy models and DB schema (schema name: "misgestiones"). Also defines domain-specific deletion exceptions.
- models.py: Pydantic models / request-query schemas and response shapes used by FastAPI endpoints.
- public/: static assets (favicon and example HTML).
- Configuration via .env (DATABASE_URL expected). No migration tool found in repo.

Key conventions and patterns (repo-specific)

- UUID primary keys across models. Use UUID objects (python uuid.UUID) in API params.
- Soft-delete pattern: entities use an active boolean; delete functions set active=False instead of hard delete.
- Domain exceptions: CategoriaDeletionError and SubcategoriaDeletionError are raised from db logic and handled in main.py — preserve those when changing deletion flows.
- Pydantic models use Config.from_attributes = True to allow model validation from SQLAlchemy ORM instances.
- db functions accept flexible query params (pagination, page_size/page_number, sort_by supporting nested properties like "subcategoria.nombre") — keep query param names consistent when adding endpoints.
- Eager loading: selectinload + with_loader_criteria used to control related-object loading and filtering by active status.

AI assistant / other configs checked

- No CLAUDE.md, .cursorrules, AGENTS.md, .windsurfrules, CONVENTIONS.md, or other assistant rule files found.

Notes for Copilot sessions

- When updating DB schema in structure.py, update models.py Pydantic models where responses are returned (they rely on attribute names and from_attributes).
- Ensure DATABASE_URL set in environment for local testing. The SQLAlchemy engine is created directly from that URL (no migration layer detected).
- Preserve soft-delete semantics and exception types to avoid breaking client behavior.

If you want this file to include examples for tests, CI, or linting presets, tell me which tools to prefer (pytest/flake8/black/ruff) and they will be added.
