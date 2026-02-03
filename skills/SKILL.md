# DB Migrator Skill

## Skill Name
database-migration

## Description
Professional database migration tool for creating exact replicas of MySQL and PostgreSQL databases with referential integrity preservation.

## When to Use This Skill
Use this skill when:
- User needs to migrate/replicate MySQL or PostgreSQL databases
- User asks about database migration tools
- User needs to preserve foreign keys and constraints
- User wants to migrate large databases efficiently
- User needs post-migration validation

## Capabilities
- ✅ MySQL to MySQL migration
- ✅ PostgreSQL to PostgreSQL migration
- ✅ Batch processing for large databases
- ✅ Foreign key preservation
- ✅ Multi-threaded migration
- ✅ Post-migration validation
- ✅ PostgreSQL extension documentation
- ✅ Multiple conflict resolution strategies

## Limitations
- ❌ No cross-database migration (MySQL ↔ PostgreSQL)
- ❌ Offline migration only (no live replication)
- ❌ Requires direct database access

## Required Inputs
1. **Source database credentials** (via .env):
   - DB type (mysql/postgresql)
   - Host, port, database name
   - Username, password

2. **Target database credentials** (via .env):
   - DB type (must match source)
   - Host, port, database name
   - Username, password

3. **Migration settings** (optional):
   - Batch size (default: 1000)
   - Max workers (default: 4)
   - Conflict strategy (fail/overwrite/skip/merge)
   - Validation enabled (true/false)

## Expected Outputs
1. **Migrated database** with:
   - Exact copy of all tables
   - Same IDs and data
   - Preserved foreign keys
   - Preserved indexes and constraints

2. **Migration report** showing:
   - Tables migrated
   - Total rows transferred
   - Duration
   - Any errors or warnings

3. **Validation report** (if enabled):
   - Row count comparison
   - Checksum verification
   - Foreign key integrity status

4. **PostgreSQL extensions document** (if PostgreSQL):
   - List of installed extensions
   - Versions
   - Installation commands for target

## Usage Examples

### Example 1: Basic MySQL Migration
```bash
# 1. Configure .env
SOURCE_DB_TYPE=mysql
SOURCE_DB_HOST=prod-server.com
SOURCE_DB_NAME=myapp
TARGET_DB_TYPE=mysql
TARGET_DB_HOST=localhost
TARGET_DB_NAME=myapp_replica

# 2. Run migration
db-migrator migrate
```

### Example 2: PostgreSQL Migration with Validation
```bash
# Configure .env
SOURCE_DB_TYPE=postgresql
TARGET_DB_TYPE=postgresql

# Run with validation
db-migrator migrate --validate
```

### Example 3: Large Database with Custom Settings
```bash
# Configure .env with optimizations
BATCH_SIZE=5000
MAX_WORKERS=8
CONFLICT_STRATEGY=overwrite

# Run migration
db-migrator migrate
```

### Example 4: Dry Run (Test First)
```bash
# See what would happen without executing
db-migrator migrate --dry-run
```

## Common Use Cases

### Use Case 1: Production to Staging Copy
**Scenario**: Copy production database to staging environment

**Steps**:
1. Configure source as production DB
2. Configure target as staging DB
3. Run: `db-migrator migrate --validate`
4. Review validation report
5. Test application on staging

### Use Case 2: Database Backup/Archive
**Scenario**: Create exact backup of database

**Steps**:
1. Configure source as live DB
2. Configure target as backup DB
3. Set `CONFLICT_STRATEGY=overwrite`
4. Run: `db-migrator migrate`
5. Verify with: `db-migrator validate`

### Use Case 3: Database Refactoring Test
**Scenario**: Test schema changes on copy

**Steps**:
1. Migrate to test environment
2. Apply schema changes to copy
3. Test thoroughly
4. Apply to production if successful

## Error Handling

### Error: Cross-Database Migration Attempted
**Message**: "Cross-database migrations not supported"
**Cause**: SOURCE_DB_TYPE ≠ TARGET_DB_TYPE
**Solution**: Ensure both are mysql or both are postgresql

### Error: Foreign Key Violation
**Message**: "Foreign key constraint violation"
**Cause**: Target DB has conflicting data
**Solution**:
- Use `--strategy overwrite` to replace data
- Or clear target database first

### Error: Connection Failed
**Message**: "Could not connect to database"
**Cause**: Invalid credentials or network issue
**Solution**:
- Verify .env credentials
- Check database is running
- Check firewall/network access

### Error: Out of Memory
**Message**: "Memory allocation failed"
**Cause**: Table too large for batch size
**Solution**:
- Reduce `BATCH_SIZE` in .env
- Increase system memory
- Use fewer `MAX_WORKERS`

## Performance Tuning

### For Small Databases (< 1GB)
```env
BATCH_SIZE=1000
MAX_WORKERS=4
```

### For Medium Databases (1-10GB)
```env
BATCH_SIZE=5000
MAX_WORKERS=8
```

### For Large Databases (> 10GB)
```env
BATCH_SIZE=10000
MAX_WORKERS=12
# Disable validation for speed
ENABLE_VALIDATION=false
```

## Integration with Other Tools

### With Docker
```bash
# Start test databases
docker-compose up -d

# Run migration
db-migrator migrate

# Cleanup
docker-compose down
```

### With CI/CD
```yaml
# .github/workflows/migrate.yml
- name: Migrate Database
  run: |
    cp .env.production .env
    python -m src.main migrate --validate
```

### With Monitoring
```python
# Custom monitoring hook
from src.core.domain.interfaces import MigrationObserver

class DatadogObserver(MigrationObserver):
    def on_table_complete(self, table, duration):
        statsd.timing('migration.table', duration, tags=[f'table:{table}'])
```

## Best Practices

1. **Always validate** after migration (use `--validate`)
2. **Dry run first** on important migrations (`--dry-run`)
3. **Test on copy** before production migration
4. **Monitor disk space** on target database
5. **Backup before** running with overwrite strategy
6. **Check logs** in `logs/migration.log` after completion
7. **Use version control** for .env.example (not .env)
8. **Document extensions** for PostgreSQL migrations

## Troubleshooting

### Migration is slow
- Check `BATCH_SIZE` (increase for speed)
- Check `MAX_WORKERS` (increase if CPU allows)
- Verify network speed between databases
- Check source database load

### Validation fails
- Check for active writes to target during migration
- Verify no manual changes to target
- Review validation report for specific failures
- Re-run migration with same settings

### Memory usage high
- Reduce `BATCH_SIZE`
- Reduce `MAX_WORKERS`
- Check for memory leaks (report issue)

## Related Skills
- `postgresql-admin` - PostgreSQL administration
- `mysql-admin` - MySQL administration
- `database-design` - Schema design
- `sql-optimization` - Query optimization

## Version History
- v1.0.0 - Initial release
  - MySQL and PostgreSQL support
  - Batch processing
  - Foreign key preservation
  - Validation service
