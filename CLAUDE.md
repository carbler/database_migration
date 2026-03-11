# db-clone

Database cloning tool: PostgreSQL→PostgreSQL, MySQL→MySQL.

## Dev setup
```bash
pip install -e ".[dev]"
```

## Run tests
```bash
pytest tests/unit/ -v          # unit tests (no DB needed)
pytest tests/integration/ -v   # integration (needs Docker)
```

## Architecture
- `src/db_clone/` - main package
- `connectors/` - DB-specific connectors (PostgreSQL, MySQL)
- `engine/` - orchestrator, discovery, data transfer, validation
- `strategies/` - conflict resolution strategies
- Uses server-side cursors + batched inserts for large DBs
- Checkpoint/resume system for interrupted migrations
