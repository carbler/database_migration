# db-clone

Professional database cloning tool for PostgreSQL and MySQL.

Clone entire databases including schemas, tables, data, indexes, foreign keys, views, functions, triggers, and more — with streaming transfer for large databases, checkpoint/resume support, and Rich progress UI.

## Installation

```bash
pip install db-clone
```

## Quick Start

```bash
# Clone a PostgreSQL database
db-clone clone \
    --source "postgresql://user:pass@source-host:5432/mydb" \
    --target "postgresql://user:pass@target-host:5432/mydb_clone"

# Clone with options
db-clone clone \
    --source "postgresql://user:pass@host/db" \
    --target "postgresql://user:pass@host/db_clone" \
    --strategy overwrite \
    --batch-size 10000 \
    --exclude-tables "temp_*,log_*"

# Resume an interrupted migration
db-clone clone --source "..." --target "..." --resume

# Schema only (no data)
db-clone clone --source "..." --target "..." --schema-only

# Data only (tables must exist)
db-clone clone --source "..." --target "..." --data-only
```

## Commands

```bash
db-clone clone       # Clone a database
db-clone info        # Show database information
db-clone validate    # Validate source matches target
db-clone checkpoint show   # Show checkpoint state
db-clone checkpoint clear  # Clear checkpoint
```

## Features

- **PostgreSQL → PostgreSQL** and **MySQL → MySQL** cloning
- **11-phase ordered copy**: schemas, extensions, types, sequences, tables, data, indexes, foreign keys, views, functions, triggers
- **Streaming transfer**: server-side cursors + batched inserts (no memory issues on large DBs)
- **Checkpoint/resume**: interrupt anytime with Ctrl+C, resume with `--resume`
- **Conflict strategies**: `overwrite` (default), `skip`, `fail`
- **Table filtering**: `--include-tables` and `--exclude-tables` with glob patterns
- **Rich progress UI**: live progress bars, summary tables
- **Structured logging**: file-based logs via structlog

## Environment Variables

Instead of CLI options, you can use environment variables:

```bash
export DB_CLONE_SOURCE_URL="postgresql://user:pass@host:5432/db"
export DB_CLONE_TARGET_URL="postgresql://user:pass@host:5432/db_clone"
export DB_CLONE_BATCH_SIZE=5000
export DB_CLONE_LOG_LEVEL=INFO
```

## Development

```bash
pip install -e ".[dev]"
pytest tests/unit/ -v
pytest tests/integration/ -v --run-integration  # requires Docker
```

## License

MIT
