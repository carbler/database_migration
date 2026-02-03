# DB Migrator - AI Agent Guide

This document is specifically designed for AI agents (like Claude, GPT-4, etc.) to understand and use this project effectively.

## Project Purpose

This is a professional database migration tool that creates exact replicas of databases while preserving:
- All data with original IDs
- Foreign key relationships
- Indexes and constraints
- Sequences/auto-increment values
- PostgreSQL extensions (documented)

## Architecture Overview

```
Clean Architecture with SOLID principles:
├── Domain Layer (core/domain/) - Business entities
├── Application Layer (application/) - Use cases
├── Infrastructure Layer (infrastructure/) - DB connectors
└── Presentation Layer (presentation/) - CLI
```

## Key Components for AI Agents

### 1. Database Connectors
Location: `src/infrastructure/connectors/`

**Abstract Base Class**:
```python
class DatabaseConnector(ABC):
    @abstractmethod
    def connect(self) -> Connection
    @abstractmethod
    def get_tables(self) -> List[Table]
    @abstractmethod
    def get_foreign_keys(self, table: str) -> List[ForeignKey]
    @abstractmethod
    def migrate_table(self, table: Table, batch_size: int)
```

**Implementations**: `mysql_connector.py`, `postgresql_connector.py`

### 2. Migration Strategies
Location: `src/application/strategies/`

When data conflicts exist in target:
- `fail_strategy.py` - Abort migration (default)
- `overwrite_strategy.py` - Replace existing data
- `skip_strategy.py` - Skip conflicting records
- `merge_strategy.py` - Intelligent merge

### 3. Validation Service
Location: `src/application/services/validation_service.py`

Validates migration success:
- Row count comparison
- Checksum verification (sample-based)
- Foreign key integrity
- Sequence values

### 4. CLI Commands
Location: `src/presentation/cli.py`

```bash
db-migrator migrate [OPTIONS]
db-migrator validate [OPTIONS]
db-migrator export-schema [OPTIONS]
db-migrator info
```

## Common AI Agent Tasks

### Task 1: Add New Conflict Strategy
1. Create `src/application/strategies/your_strategy.py`
2. Inherit from `BaseStrategy`
3. Implement `resolve(existing, new) -> Action`
4. Register in `conflict_resolver.py`

### Task 2: Add New Database Type
1. Create `src/infrastructure/connectors/newdb_connector.py`
2. Inherit from `DatabaseConnector`
3. Implement all abstract methods
4. Add to `connector_factory.py`
5. Update tests

### Task 3: Enhance Validation
1. Edit `src/application/services/validation_service.py`
2. Add new validation method
3. Update `ValidationReport` class
4. Add corresponding tests

### Task 4: Optimize Performance
Areas to optimize:
- Batch size tuning (`BATCH_SIZE` in `.env`)
- Worker count (`MAX_WORKERS`)
- Query optimization in connectors
- Memory usage in `data_repository.py`

## Testing Guidelines for AI Agents

### Running Tests
```bash
# All tests
pytest

# Specific module
pytest tests/unit/test_connectors.py

# With coverage
pytest --cov=src

# Integration (requires Docker)
docker-compose up -d
pytest tests/integration/
```

### Creating New Tests
1. Unit tests: `tests/unit/test_<module>.py`
2. Integration tests: `tests/integration/test_<feature>.py`
3. Use fixtures from `tests/conftest.py`
4. Aim for 80%+ coverage

## Configuration for AI Agents

### Environment Variables
`.env` file controls all configuration. Key variables:

```env
SOURCE_DB_TYPE=mysql
SOURCE_DB_HOST=localhost
SOURCE_DB_PORT=3306
BATCH_SIZE=1000
MAX_WORKERS=4
LOG_LEVEL=INFO
```

### Secrets Management
- Never commit `.env`
- Use `python-decouple` for loading
- Support for AWS Secrets Manager (optional)

## Error Handling Patterns

```python
try:
    connector.migrate_table(table)
except ForeignKeyViolationError as e:
    logger.error("FK violation", table=table, error=str(e))
    # Handle gracefully
except ConnectionError as e:
    logger.critical("Connection lost", error=str(e))
    # Retry or abort
```

## Logging Best Practices

```python
import structlog

logger = structlog.get_logger()

# Good logging
logger.info("table_migrated",
    table=table.name,
    rows=count,
    duration_ms=elapsed)

# Include context
logger.error("migration_failed",
    table=table.name,
    error=str(e),
    exc_info=True)
```

## Code Quality Checklist

Before committing:
- [ ] `black src/ tests/` (formatting)
- [ ] `isort src/ tests/` (import sorting)
- [ ] `flake8 src/ tests/` (linting)
- [ ] `mypy src/` (type checking)
- [ ] `pytest --cov=src` (tests pass, >80% coverage)

## Performance Benchmarks

Target performance:
- Small DB (< 1GB): < 5 minutes
- Medium DB (1-10GB): < 30 minutes
- Large DB (10-100GB): < 4 hours

Optimize if not meeting targets.

## Common Pitfalls for AI Agents

❌ **Don't**:
- Modify `.env` directly (use `.env.example` as template)
- Skip foreign key ordering (breaks integrity)
- Ignore batch processing (memory issues)
- Mix database types (MySQL ↔ PostgreSQL)

✅ **Do**:
- Use generators for large datasets
- Implement retry logic for network errors
- Validate after migration
- Log all operations
- Follow SOLID principles

## Extension Points

Easy to extend:
1. **New strategies**: Add to `strategies/`
2. **New validators**: Add to `validators/`
3. **New DB types**: Add to `connectors/`
4. **New CLI commands**: Add to `cli.py`

## Resources for AI Agents

- Architecture diagram: `docs/architecture.md`
- API reference: `docs/api_reference.md`
- Examples: `docs/examples.md`
- Test fixtures: `tests/fixtures/`

## Quick Reference

| Need | Location |
|------|----------|
| Add DB connector | `infrastructure/connectors/` |
| Add strategy | `application/strategies/` |
| Add CLI command | `presentation/cli.py` |
| Add validator | `application/services/validation_service.py` |
| Add test | `tests/unit/` or `tests/integration/` |
| Check logs | `logs/migration.log` |

## Support

For AI agents encountering issues:
1. Check `README.md` for setup
2. Review test examples in `tests/`
3. Examine existing code patterns
4. Follow SOLID principles
5. Maintain 80%+ test coverage
