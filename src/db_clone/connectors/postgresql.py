"""PostgreSQL connector using psycopg2."""

from __future__ import annotations

import uuid
from typing import Any, Iterator
from urllib.parse import urlparse

import psycopg2
import psycopg2.extensions
import psycopg2.extras
from psycopg2.extras import Json

from db_clone.connectors.base import BaseConnector
from db_clone.logging_config import get_logger
from db_clone.models import DbObject, DbType, ObjectType, TableInfo

log = get_logger(__name__)


class PostgreSQLConnector(BaseConnector):
    db_type = DbType.POSTGRESQL

    def connect(self) -> None:
        # Register JSON/dict adapter so jsonb columns work transparently
        psycopg2.extensions.register_adapter(dict, Json)
        psycopg2.extensions.register_adapter(list, Json)
        self._connection = psycopg2.connect(self.url)
        self._connection.autocommit = True

    def disconnect(self) -> None:
        if self._connection and not self._connection.closed:
            self._connection.close()

    def test_connection(self) -> bool:
        try:
            with self._connection.cursor() as cur:
                cur.execute("SELECT 1")
            return True
        except Exception:
            return False

    def _ensure_transaction(self) -> None:
        """Ensure we have a clean transaction state."""
        if self._connection.closed:
            self.connect()
        try:
            self._connection.rollback()
        except Exception:
            pass

    def _query(self, sql: str, params: tuple | None = None) -> list[tuple]:
        """Execute a query and return all rows."""
        if not self._connection.autocommit:
            try:
                self._connection.rollback()
            except Exception:
                pass
            self._connection.autocommit = True
        with self._connection.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()

    # --- Discovery ---

    def discover_schemas(self) -> list[DbObject]:
        rows = self._query("""
            SELECT schema_name
            FROM information_schema.schemata
            WHERE schema_name NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
              AND schema_name NOT LIKE 'pg_temp_%'
              AND schema_name NOT LIKE 'pg_toast_temp_%'
            ORDER BY schema_name
        """)
        result = []
        for (name,) in rows:
            if name == "public":
                continue  # public exists by default
            result.append(DbObject(
                name=name,
                schema="",
                object_type=ObjectType.SCHEMA,
                definition=f"CREATE SCHEMA IF NOT EXISTS {_qi(name)};",
            ))
        return result

    def discover_extensions(self) -> list[DbObject]:
        rows = self._query("""
            SELECT extname, extversion
            FROM pg_extension
            WHERE extname != 'plpgsql'
            ORDER BY extname
        """)
        return [
            DbObject(
                name=name,
                schema="",
                object_type=ObjectType.EXTENSION,
                definition=f"CREATE EXTENSION IF NOT EXISTS \"{name}\";",
            )
            for name, _ in rows
        ]

    def discover_custom_types(self) -> list[DbObject]:
        # Enum types
        rows = self._query("""
            SELECT n.nspname, t.typname,
                   array_agg(e.enumlabel ORDER BY e.enumsortorder) AS labels
            FROM pg_type t
            JOIN pg_enum e ON e.enumtypid = t.oid
            JOIN pg_namespace n ON n.oid = t.typnamespace
            WHERE n.nspname NOT IN ('pg_catalog', 'information_schema')
            GROUP BY n.nspname, t.typname
            ORDER BY n.nspname, t.typname
        """)
        result = []
        for schema, name, labels in rows:
            labels_sql = ", ".join(f"'{label}'" for label in labels)
            result.append(DbObject(
                name=name,
                schema=schema,
                object_type=ObjectType.CUSTOM_TYPE,
                definition=f"CREATE TYPE {_qi(schema)}.{_qi(name)} AS ENUM ({labels_sql});",
            ))

        # Composite types
        rows = self._query("""
            SELECT n.nspname, t.typname,
                   array_agg(a.attname || ' ' || pg_catalog.format_type(a.atttypid, a.atttypmod)
                             ORDER BY a.attnum) AS attrs
            FROM pg_type t
            JOIN pg_namespace n ON n.oid = t.typnamespace
            JOIN pg_class c ON c.oid = t.typrelid
            JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum > 0 AND NOT a.attisdropped
            WHERE t.typtype = 'c'
              AND c.relkind = 'c'
              AND n.nspname NOT IN ('pg_catalog', 'information_schema')
            GROUP BY n.nspname, t.typname
            ORDER BY n.nspname, t.typname
        """)
        for schema, name, attrs in rows:
            attrs_sql = ", ".join(attrs)
            result.append(DbObject(
                name=name,
                schema=schema,
                object_type=ObjectType.CUSTOM_TYPE,
                definition=f"CREATE TYPE {_qi(schema)}.{_qi(name)} AS ({attrs_sql});",
            ))
        return result

    def discover_sequences(self) -> list[DbObject]:
        rows = self._query("""
            SELECT schemaname, sequencename, sequenceowner,
                   start_value, min_value, max_value, increment_by, cycle, cache_size
            FROM pg_sequences
            WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
            ORDER BY schemaname, sequencename
        """)
        result = []
        for schema, name, _, start, minv, maxv, inc, cycle, cache in rows:
            parts = [f"CREATE SEQUENCE {_qi(schema)}.{_qi(name)}"]
            if inc and inc != 1:
                parts.append(f"INCREMENT BY {inc}")
            if minv is not None:
                parts.append(f"MINVALUE {minv}")
            if maxv is not None:
                parts.append(f"MAXVALUE {maxv}")
            if start is not None:
                parts.append(f"START WITH {start}")
            if cache and cache != 1:
                parts.append(f"CACHE {cache}")
            if cycle:
                parts.append("CYCLE")
            result.append(DbObject(
                name=name,
                schema=schema,
                object_type=ObjectType.SEQUENCE,
                definition=" ".join(parts) + ";",
            ))
        return result

    def discover_tables(self) -> list[DbObject]:
        rows = self._query("""
            SELECT schemaname, tablename
            FROM pg_tables
            WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
            ORDER BY schemaname, tablename
        """)
        result = []
        for schema, table in rows:
            ddl = self._get_table_ddl(schema, table)
            result.append(DbObject(
                name=table,
                schema=schema,
                object_type=ObjectType.TABLE,
                definition=ddl,
            ))
        return result

    def _get_table_ddl(self, schema: str, table: str) -> str:
        """Build CREATE TABLE DDL from pg_catalog (without FKs)."""
        cols = self._query("""
            SELECT a.attname,
                   pg_catalog.format_type(a.atttypid, a.atttypmod) AS data_type,
                   a.attnotnull,
                   pg_get_expr(d.adbin, d.adrelid) AS default_val
            FROM pg_attribute a
            JOIN pg_class c ON c.oid = a.attrelid
            JOIN pg_namespace n ON n.oid = c.relnamespace
            LEFT JOIN pg_attrdef d ON d.adrelid = a.attrelid AND d.adnum = a.attnum
            WHERE n.nspname = %s AND c.relname = %s
              AND a.attnum > 0 AND NOT a.attisdropped
            ORDER BY a.attnum
        """, (schema, table))

        col_defs = []
        for name, dtype, notnull, default in cols:
            parts = [f"    {_qi(name)} {dtype}"]
            if default:
                parts.append(f"DEFAULT {default}")
            if notnull:
                parts.append("NOT NULL")
            col_defs.append(" ".join(parts))

        # Primary key
        pk_rows = self._query("""
            SELECT a.attname
            FROM pg_index i
            JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
            JOIN pg_class c ON c.oid = i.indrelid
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = %s AND c.relname = %s AND i.indisprimary
            ORDER BY array_position(i.indkey, a.attnum)
        """, (schema, table))
        if pk_rows:
            pk_cols = ", ".join(_qi(r[0]) for r in pk_rows)
            col_defs.append(f"    PRIMARY KEY ({pk_cols})")

        # Unique constraints (not FKs)
        uc_rows = self._query("""
            SELECT con.conname,
                   array_agg(a.attname ORDER BY array_position(con.conkey, a.attnum))
            FROM pg_constraint con
            JOIN pg_attribute a ON a.attrelid = con.conrelid AND a.attnum = ANY(con.conkey)
            JOIN pg_class c ON c.oid = con.conrelid
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = %s AND c.relname = %s AND con.contype = 'u'
            GROUP BY con.conname
        """, (schema, table))
        for conname, ucols in uc_rows:
            ucol_list = ", ".join(_qi(c) for c in ucols)
            col_defs.append(f"    CONSTRAINT {_qi(conname)} UNIQUE ({ucol_list})")

        # Check constraints
        ck_rows = self._query("""
            SELECT conname, pg_get_constraintdef(oid)
            FROM pg_constraint
            WHERE conrelid = (
                SELECT c.oid FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = %s AND c.relname = %s
            ) AND contype = 'c'
        """, (schema, table))
        for conname, condef in ck_rows:
            col_defs.append(f"    CONSTRAINT {_qi(conname)} {condef}")

        body = ",\n".join(col_defs)
        return f"CREATE TABLE {_qi(schema)}.{_qi(table)} (\n{body}\n);"

    def discover_indexes(self) -> list[DbObject]:
        rows = self._query("""
            SELECT schemaname, tablename, indexname, indexdef
            FROM pg_indexes
            WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
              AND indexname NOT IN (
                  SELECT conname FROM pg_constraint
                  WHERE contype IN ('p', 'u')
              )
            ORDER BY schemaname, tablename, indexname
        """)
        return [
            DbObject(
                name=idxname,
                schema=schema,
                object_type=ObjectType.INDEX,
                definition=indexdef + ";",
                dependencies=[f"{schema}.{table}"],
            )
            for schema, table, idxname, indexdef in rows
        ]

    def discover_foreign_keys(self) -> list[DbObject]:
        rows = self._query("""
            SELECT
                n.nspname AS schema,
                c.relname AS table_name,
                con.conname AS fk_name,
                pg_get_constraintdef(con.oid) AS fk_def
            FROM pg_constraint con
            JOIN pg_class c ON c.oid = con.conrelid
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE con.contype = 'f'
              AND n.nspname NOT IN ('pg_catalog', 'information_schema')
            ORDER BY n.nspname, c.relname, con.conname
        """)
        return [
            DbObject(
                name=fk_name,
                schema=schema,
                object_type=ObjectType.FOREIGN_KEY,
                definition=(
                    f"ALTER TABLE {_qi(schema)}.{_qi(table)} "
                    f"ADD CONSTRAINT {_qi(fk_name)} {fk_def};"
                ),
                dependencies=[f"{schema}.{table}"],
            )
            for schema, table, fk_name, fk_def in rows
        ]

    def discover_views(self) -> list[DbObject]:
        rows = self._query("""
            SELECT schemaname, viewname, definition
            FROM pg_views
            WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
            ORDER BY schemaname, viewname
        """)
        return [
            DbObject(
                name=name,
                schema=schema,
                object_type=ObjectType.VIEW,
                definition=f"CREATE OR REPLACE VIEW {_qi(schema)}.{_qi(name)} AS {defn}",
            )
            for schema, name, defn in rows
        ]

    def discover_functions(self) -> list[DbObject]:
        # Get function OIDs first (exclude aggregates 'a' and window 'w')
        oid_rows = self._query("""
            SELECT p.oid, n.nspname, p.proname
            FROM pg_proc p
            JOIN pg_namespace n ON n.oid = p.pronamespace
            WHERE n.nspname NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
              AND p.proname NOT LIKE 'pg_%'
              AND p.prokind IN ('f', 'p')
            ORDER BY n.nspname, p.proname
        """)
        result = []
        for oid, schema, name in oid_rows:
            try:
                rows = self._query("SELECT pg_get_functiondef(%s)", (oid,))
                funcdef = rows[0][0] if rows else None
                if funcdef:
                    result.append(DbObject(
                        name=name,
                        schema=schema,
                        object_type=ObjectType.FUNCTION,
                        definition=funcdef + ";",
                    ))
            except Exception as e:
                log.warning("skip_function", name=f"{schema}.{name}", error=str(e))
        return result

    def discover_triggers(self) -> list[DbObject]:
        rows = self._query("""
            SELECT
                n.nspname AS schema,
                c.relname AS table_name,
                t.tgname AS trigger_name,
                pg_get_triggerdef(t.oid) AS trigger_def
            FROM pg_trigger t
            JOIN pg_class c ON c.oid = t.tgrelid
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE NOT t.tgisinternal
              AND n.nspname NOT IN ('pg_catalog', 'information_schema')
            ORDER BY n.nspname, c.relname, t.tgname
        """)
        return [
            DbObject(
                name=tname,
                schema=schema,
                object_type=ObjectType.TRIGGER,
                definition=tdef + ";",
                dependencies=[f"{schema}.{table}"],
            )
            for schema, table, tname, tdef in rows
        ]

    # --- Table info ---

    def get_table_info(self, schema: str, table: str) -> TableInfo:
        pk_rows = self._query("""
            SELECT a.attname
            FROM pg_index i
            JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
            JOIN pg_class c ON c.oid = i.indrelid
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = %s AND c.relname = %s AND i.indisprimary
            ORDER BY array_position(i.indkey, a.attnum)
        """, (schema, table))
        row_count = self.get_row_count(schema, table)
        return TableInfo(
            name=table,
            schema=schema,
            row_count=row_count,
            primary_key=[r[0] for r in pk_rows],
        )

    def get_row_count(self, schema: str, table: str) -> int:
        rows = self._query("""
            SELECT reltuples::bigint
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = %s AND c.relname = %s
        """, (schema, table))
        count = rows[0][0] if rows else 0
        return max(count, 0)

    # --- Data reading ---

    def read_rows(
        self, schema: str, table: str, batch_size: int, offset: int = 0
    ) -> Iterator[list[tuple]]:
        # Get columns BEFORE entering the transaction for the named cursor
        cols = self.get_columns(schema, table)
        if not cols:
            return

        col_list = ", ".join(_qi(c) for c in cols)
        query = f"SELECT {col_list} FROM {_qi(schema)}.{_qi(table)}"
        if offset > 0:
            query += f" OFFSET {offset}"

        cursor_name = f"db_clone_{uuid.uuid4().hex[:8]}"
        self._connection.autocommit = False
        try:
            with self._connection.cursor(name=cursor_name) as cur:
                cur.itersize = batch_size
                cur.execute(query)

                while True:
                    rows = cur.fetchmany(batch_size)
                    if not rows:
                        break
                    yield [tuple(r) for r in rows]
            self._connection.commit()
        except Exception:
            self._connection.rollback()
            raise
        finally:
            self._connection.autocommit = True

    def get_columns(self, schema: str, table: str) -> list[str]:
        rows = self._query("""
            SELECT a.attname
            FROM pg_attribute a
            JOIN pg_class c ON c.oid = a.attrelid
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = %s AND c.relname = %s
              AND a.attnum > 0 AND NOT a.attisdropped
            ORDER BY a.attnum
        """, (schema, table))
        return [r[0] for r in rows]

    # --- Writing ---

    def execute_ddl(self, sql: str) -> None:
        if not self._connection.autocommit:
            try:
                self._connection.rollback()
            except Exception:
                pass
            self._connection.autocommit = True
        with self._connection.cursor() as cur:
            cur.execute(sql)

    def insert_rows(
        self, schema: str, table: str, columns: list[str], rows: list[tuple]
    ) -> int:
        if not rows:
            return 0
        col_list = ", ".join(_qi(c) for c in columns)
        tpl = f"({', '.join(['%s'] * len(columns))})"
        sql = f"INSERT INTO {_qi(schema)}.{_qi(table)} ({col_list}) VALUES %s"
        self._connection.autocommit = False
        try:
            with self._connection.cursor() as cur:
                psycopg2.extras.execute_values(cur, sql, rows, template=tpl)
            self._connection.commit()
            return len(rows)
        except Exception:
            self._connection.rollback()
            raise
        finally:
            self._connection.autocommit = True

    def disable_fk_checks(self) -> None:
        self.execute_ddl("SET session_replication_role = 'replica';")

    def enable_fk_checks(self) -> None:
        self.execute_ddl("SET session_replication_role = 'origin';")

    def update_sequences(self, schema: str, table: str) -> None:
        """Update sequences owned by columns in this table."""
        rows = self._query("""
            SELECT a.attname, pg_get_serial_sequence(%s, a.attname) AS seq
            FROM pg_attribute a
            JOIN pg_class c ON c.oid = a.attrelid
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = %s AND c.relname = %s
              AND a.attnum > 0 AND NOT a.attisdropped
        """, (f"{schema}.{table}", schema, table))

        for col, seq in rows:
            if seq:
                self.execute_ddl(
                    f"SELECT setval('{seq}', COALESCE("
                    f"(SELECT MAX({_qi(col)}) FROM {_qi(schema)}.{_qi(table)}), 1));"
                )

    def drop_object(self, obj: DbObject) -> None:
        drop_map = {
            ObjectType.SCHEMA: f"DROP SCHEMA IF EXISTS {_qi(obj.name)} CASCADE;",
            ObjectType.EXTENSION: f'DROP EXTENSION IF EXISTS "{obj.name}" CASCADE;',
            ObjectType.CUSTOM_TYPE: f"DROP TYPE IF EXISTS {_qi(obj.schema)}.{_qi(obj.name)} CASCADE;",
            ObjectType.SEQUENCE: f"DROP SEQUENCE IF EXISTS {_qi(obj.schema)}.{_qi(obj.name)} CASCADE;",
            ObjectType.TABLE: f"DROP TABLE IF EXISTS {_qi(obj.schema)}.{_qi(obj.name)} CASCADE;",
            ObjectType.INDEX: f"DROP INDEX IF EXISTS {_qi(obj.schema)}.{_qi(obj.name)};",
            ObjectType.VIEW: f"DROP VIEW IF EXISTS {_qi(obj.schema)}.{_qi(obj.name)} CASCADE;",
            ObjectType.FUNCTION: f"DROP FUNCTION IF EXISTS {_qi(obj.schema)}.{_qi(obj.name)} CASCADE;",
            ObjectType.TRIGGER: "",  # handled via table
        }
        if obj.object_type == ObjectType.FOREIGN_KEY and obj.dependencies:
            table_ref = obj.dependencies[0]
            s, t = table_ref.split(".", 1)
            sql = f"ALTER TABLE {_qi(s)}.{_qi(t)} DROP CONSTRAINT IF EXISTS {_qi(obj.name)};"
        else:
            sql = drop_map.get(obj.object_type, "")
        if sql:
            self.execute_ddl(sql)

    def object_exists(self, obj: DbObject) -> bool:
        checks = {
            ObjectType.SCHEMA: (
                "SELECT 1 FROM pg_namespace WHERE nspname = %s",
                (obj.name,),
            ),
            ObjectType.TABLE: (
                "SELECT 1 FROM pg_tables WHERE schemaname = %s AND tablename = %s",
                (obj.schema, obj.name),
            ),
            ObjectType.VIEW: (
                "SELECT 1 FROM pg_views WHERE schemaname = %s AND viewname = %s",
                (obj.schema, obj.name),
            ),
            ObjectType.SEQUENCE: (
                "SELECT 1 FROM pg_sequences WHERE schemaname = %s AND sequencename = %s",
                (obj.schema, obj.name),
            ),
        }
        check = checks.get(obj.object_type)
        if check:
            rows = self._query(*check)
            return len(rows) > 0
        return False

    def get_database_info(self) -> dict[str, Any]:
        version = self._query("SELECT version()")[0][0]
        parsed = urlparse(self.url)
        db_name = parsed.path.lstrip("/")

        size_rows = self._query(
            "SELECT pg_database_size(%s)", (db_name,)
        )
        size = size_rows[0][0] if size_rows else 0

        table_count = self._query("""
            SELECT count(*) FROM pg_tables
            WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
        """)[0][0]

        return {
            "type": "PostgreSQL",
            "version": version,
            "database": db_name,
            "size_bytes": size,
            "table_count": table_count,
        }


def _qi(identifier: str) -> str:
    """Quote a SQL identifier."""
    return f'"{identifier}"'
