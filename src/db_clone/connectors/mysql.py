"""MySQL connector using PyMySQL."""

from __future__ import annotations

import re
from typing import Any, Iterator
from urllib.parse import urlparse

import pymysql
import pymysql.cursors

from db_clone.connectors.base import BaseConnector
from db_clone.logging_config import get_logger
from db_clone.models import DbObject, DbType, ObjectType, TableInfo

log = get_logger(__name__)


class MySQLConnector(BaseConnector):
    db_type = DbType.MYSQL

    def __init__(self, url: str) -> None:
        super().__init__(url)
        parsed = urlparse(url)
        self._host = parsed.hostname or "localhost"
        self._port = parsed.port or 3306
        self._user = parsed.username or "root"
        self._password = parsed.password or ""
        self._database = parsed.path.lstrip("/")

    def connect(self) -> None:
        self._connection = pymysql.connect(
            host=self._host,
            port=self._port,
            user=self._user,
            password=self._password,
            database=self._database,
            charset="utf8mb4",
            autocommit=True,
        )

    def disconnect(self) -> None:
        if self._connection and self._connection.open:
            self._connection.close()

    def test_connection(self) -> bool:
        try:
            self._connection.ping(reconnect=False)
            return True
        except Exception:
            return False

    def _query(self, sql: str, params: tuple | None = None) -> list[tuple]:
        with self._connection.cursor() as cur:
            cur.execute(sql, params)
            return list(cur.fetchall())

    def _query_one(self, sql: str, params: tuple | None = None) -> str:
        with self._connection.cursor() as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
            return row[1] if row and len(row) > 1 else ""

    # --- Discovery ---

    def discover_schemas(self) -> list[DbObject]:
        # MySQL: database = schema, no additional schemas to create
        return []

    def discover_extensions(self) -> list[DbObject]:
        # MySQL has no extension concept
        return []

    def discover_custom_types(self) -> list[DbObject]:
        # MySQL has no standalone enum/custom type objects
        return []

    def discover_sequences(self) -> list[DbObject]:
        # MySQL uses AUTO_INCREMENT, no standalone sequences
        return []

    def discover_tables(self) -> list[DbObject]:
        rows = self._query("""
            SELECT TABLE_NAME
            FROM information_schema.TABLES
            WHERE TABLE_SCHEMA = %s AND TABLE_TYPE = 'BASE TABLE'
            ORDER BY TABLE_NAME
        """, (self._database,))
        result = []
        for (table,) in rows:
            ddl = self._get_table_ddl(table)
            result.append(DbObject(
                name=table,
                schema=self._database,
                object_type=ObjectType.TABLE,
                definition=ddl,
            ))
        return result

    def _get_table_ddl(self, table: str) -> str:
        """Get CREATE TABLE via SHOW CREATE TABLE, strip FKs and AUTO_INCREMENT value."""
        raw = self._query_one(f"SHOW CREATE TABLE {_qi(table)}")
        # Remove FK constraints
        lines = raw.split("\n")
        filtered = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("CONSTRAINT") and "FOREIGN KEY" in stripped:
                continue
            filtered.append(line)
        ddl = "\n".join(filtered)
        # Remove trailing comma before closing paren
        ddl = re.sub(r",\s*\n\s*\)", "\n)", ddl)
        # Remove AUTO_INCREMENT=N from table options
        ddl = re.sub(r"\s*AUTO_INCREMENT=\d+", "", ddl)
        if not ddl.rstrip().endswith(";"):
            ddl = ddl.rstrip() + ";"
        return ddl

    def discover_indexes(self) -> list[DbObject]:
        rows = self._query("""
            SELECT DISTINCT INDEX_NAME, TABLE_NAME, NON_UNIQUE,
                   GROUP_CONCAT(COLUMN_NAME ORDER BY SEQ_IN_INDEX) AS cols
            FROM information_schema.STATISTICS
            WHERE TABLE_SCHEMA = %s
              AND INDEX_NAME != 'PRIMARY'
              AND INDEX_NAME NOT IN (
                  SELECT CONSTRAINT_NAME
                  FROM information_schema.TABLE_CONSTRAINTS
                  WHERE TABLE_SCHEMA = %s AND CONSTRAINT_TYPE = 'FOREIGN KEY'
              )
            GROUP BY INDEX_NAME, TABLE_NAME, NON_UNIQUE
            ORDER BY TABLE_NAME, INDEX_NAME
        """, (self._database, self._database))
        result = []
        for idx_name, table, non_unique, cols in rows:
            col_list = ", ".join(_qi(c.strip()) for c in cols.split(","))
            unique = "" if non_unique else "UNIQUE "
            ddl = (
                f"CREATE {unique}INDEX {_qi(idx_name)} "
                f"ON {_qi(table)} ({col_list});"
            )
            result.append(DbObject(
                name=idx_name,
                schema=self._database,
                object_type=ObjectType.INDEX,
                definition=ddl,
                dependencies=[f"{self._database}.{table}"],
            ))
        return result

    def discover_foreign_keys(self) -> list[DbObject]:
        rows = self._query("""
            SELECT
                tc.CONSTRAINT_NAME,
                tc.TABLE_NAME,
                GROUP_CONCAT(kcu.COLUMN_NAME ORDER BY kcu.ORDINAL_POSITION) AS cols,
                kcu.REFERENCED_TABLE_NAME,
                GROUP_CONCAT(kcu.REFERENCED_COLUMN_NAME ORDER BY kcu.ORDINAL_POSITION) AS ref_cols,
                rc.UPDATE_RULE,
                rc.DELETE_RULE
            FROM information_schema.TABLE_CONSTRAINTS tc
            JOIN information_schema.KEY_COLUMN_USAGE kcu
                ON tc.CONSTRAINT_NAME = kcu.CONSTRAINT_NAME
                AND tc.TABLE_SCHEMA = kcu.TABLE_SCHEMA
            JOIN information_schema.REFERENTIAL_CONSTRAINTS rc
                ON tc.CONSTRAINT_NAME = rc.CONSTRAINT_NAME
                AND tc.TABLE_SCHEMA = rc.CONSTRAINT_SCHEMA
            WHERE tc.TABLE_SCHEMA = %s AND tc.CONSTRAINT_TYPE = 'FOREIGN KEY'
            GROUP BY tc.CONSTRAINT_NAME, tc.TABLE_NAME,
                     kcu.REFERENCED_TABLE_NAME, rc.UPDATE_RULE, rc.DELETE_RULE
            ORDER BY tc.TABLE_NAME, tc.CONSTRAINT_NAME
        """, (self._database,))
        result = []
        for fk_name, table, cols, ref_table, ref_cols, on_update, on_delete in rows:
            col_list = ", ".join(_qi(c.strip()) for c in cols.split(","))
            ref_col_list = ", ".join(_qi(c.strip()) for c in ref_cols.split(","))
            parts = [
                f"ALTER TABLE {_qi(table)}",
                f"ADD CONSTRAINT {_qi(fk_name)}",
                f"FOREIGN KEY ({col_list})",
                f"REFERENCES {_qi(ref_table)} ({ref_col_list})",
            ]
            if on_delete and on_delete != "RESTRICT":
                parts.append(f"ON DELETE {on_delete}")
            if on_update and on_update != "RESTRICT":
                parts.append(f"ON UPDATE {on_update}")
            result.append(DbObject(
                name=fk_name,
                schema=self._database,
                object_type=ObjectType.FOREIGN_KEY,
                definition=" ".join(parts) + ";",
                dependencies=[f"{self._database}.{table}"],
            ))
        return result

    def discover_views(self) -> list[DbObject]:
        rows = self._query("""
            SELECT TABLE_NAME, VIEW_DEFINITION
            FROM information_schema.VIEWS
            WHERE TABLE_SCHEMA = %s
            ORDER BY TABLE_NAME
        """, (self._database,))
        return [
            DbObject(
                name=name,
                schema=self._database,
                object_type=ObjectType.VIEW,
                definition=f"CREATE OR REPLACE VIEW {_qi(name)} AS {defn};",
            )
            for name, defn in rows
        ]

    def discover_functions(self) -> list[DbObject]:
        rows = self._query("""
            SELECT ROUTINE_NAME, ROUTINE_TYPE
            FROM information_schema.ROUTINES
            WHERE ROUTINE_SCHEMA = %s
            ORDER BY ROUTINE_NAME
        """, (self._database,))
        result = []
        for name, rtype in rows:
            show_cmd = f"SHOW CREATE {'FUNCTION' if rtype == 'FUNCTION' else 'PROCEDURE'} {_qi(name)}"
            with self._connection.cursor() as cur:
                cur.execute(show_cmd)
                row = cur.fetchone()
                # Index 2 has the CREATE statement
                defn = row[2] if row and len(row) > 2 else ""
            if defn:
                result.append(DbObject(
                    name=name,
                    schema=self._database,
                    object_type=ObjectType.FUNCTION,
                    definition=defn + ";",
                ))
        return result

    def discover_triggers(self) -> list[DbObject]:
        rows = self._query("""
            SELECT TRIGGER_NAME, EVENT_OBJECT_TABLE,
                   ACTION_TIMING, EVENT_MANIPULATION,
                   ACTION_STATEMENT
            FROM information_schema.TRIGGERS
            WHERE TRIGGER_SCHEMA = %s
            ORDER BY EVENT_OBJECT_TABLE, TRIGGER_NAME
        """, (self._database,))
        result = []
        for tname, table, timing, event, body in rows:
            defn = (
                f"CREATE TRIGGER {_qi(tname)} {timing} {event} "
                f"ON {_qi(table)} FOR EACH ROW {body};"
            )
            result.append(DbObject(
                name=tname,
                schema=self._database,
                object_type=ObjectType.TRIGGER,
                definition=defn,
                dependencies=[f"{self._database}.{table}"],
            ))
        return result

    # --- Table info ---

    def get_table_info(self, schema: str, table: str) -> TableInfo:
        pk_rows = self._query("""
            SELECT COLUMN_NAME
            FROM information_schema.KEY_COLUMN_USAGE
            WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s AND CONSTRAINT_NAME = 'PRIMARY'
            ORDER BY ORDINAL_POSITION
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
            SELECT TABLE_ROWS
            FROM information_schema.TABLES
            WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
        """, (schema, table))
        return rows[0][0] if rows and rows[0][0] else 0

    # --- Data reading ---

    def read_rows(
        self, schema: str, table: str, batch_size: int, offset: int = 0
    ) -> Iterator[list[tuple]]:
        conn = pymysql.connect(
            host=self._host,
            port=self._port,
            user=self._user,
            password=self._password,
            database=self._database,
            charset="utf8mb4",
            cursorclass=pymysql.cursors.SSCursor,
        )
        try:
            with conn.cursor() as cur:
                cols = self.get_columns(schema, table)
                col_list = ", ".join(_qi(c) for c in cols)
                query = f"SELECT {col_list} FROM {_qi(table)}"
                if offset > 0:
                    query += f" LIMIT 18446744073709551615 OFFSET {offset}"
                cur.execute(query)

                batch: list[tuple] = []
                for row in cur:
                    batch.append(tuple(row))
                    if len(batch) >= batch_size:
                        yield batch
                        batch = []
                if batch:
                    yield batch
        finally:
            conn.close()

    def get_columns(self, schema: str, table: str) -> list[str]:
        rows = self._query("""
            SELECT COLUMN_NAME
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
            ORDER BY ORDINAL_POSITION
        """, (schema, table))
        return [r[0] for r in rows]

    # --- Writing ---

    def execute_ddl(self, sql: str) -> None:
        with self._connection.cursor() as cur:
            cur.execute(sql)

    def insert_rows(
        self, schema: str, table: str, columns: list[str], rows: list[tuple]
    ) -> int:
        if not rows:
            return 0
        col_list = ", ".join(_qi(c) for c in columns)
        placeholders = ", ".join(["%s"] * len(columns))
        sql = f"INSERT INTO {_qi(table)} ({col_list}) VALUES ({placeholders})"
        self._connection.autocommit_mode = False
        try:
            self._connection.begin()
            with self._connection.cursor() as cur:
                cur.executemany(sql, rows)
            self._connection.commit()
            return len(rows)
        except Exception:
            self._connection.rollback()
            raise
        finally:
            self._connection.autocommit_mode = True

    def disable_fk_checks(self) -> None:
        self.execute_ddl("SET FOREIGN_KEY_CHECKS = 0;")

    def enable_fk_checks(self) -> None:
        self.execute_ddl("SET FOREIGN_KEY_CHECKS = 1;")

    def update_sequences(self, schema: str, table: str) -> None:
        """Reset AUTO_INCREMENT to max value + 1."""
        rows = self._query("""
            SELECT COLUMN_NAME
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s AND EXTRA LIKE '%%auto_increment%%'
        """, (schema, table))
        if rows:
            col = rows[0][0]
            max_rows = self._query(f"SELECT MAX({_qi(col)}) FROM {_qi(table)}")
            max_val = max_rows[0][0] if max_rows and max_rows[0][0] else 0
            self.execute_ddl(f"ALTER TABLE {_qi(table)} AUTO_INCREMENT = {max_val + 1};")

    def drop_object(self, obj: DbObject) -> None:
        drop_map = {
            ObjectType.TABLE: f"DROP TABLE IF EXISTS {_qi(obj.name)};",
            ObjectType.INDEX: f"DROP INDEX {_qi(obj.name)} ON {_qi(obj.dependencies[0].split('.', 1)[1]) if obj.dependencies else obj.name};",
            ObjectType.VIEW: f"DROP VIEW IF EXISTS {_qi(obj.name)};",
            ObjectType.FUNCTION: f"DROP FUNCTION IF EXISTS {_qi(obj.name)};",
            ObjectType.TRIGGER: f"DROP TRIGGER IF EXISTS {_qi(obj.name)};",
        }
        if obj.object_type == ObjectType.FOREIGN_KEY and obj.dependencies:
            table = obj.dependencies[0].split(".", 1)[1]
            sql = f"ALTER TABLE {_qi(table)} DROP FOREIGN KEY {_qi(obj.name)};"
        else:
            sql = drop_map.get(obj.object_type, "")
        if sql:
            try:
                self.execute_ddl(sql)
            except Exception as e:
                log.warning("drop_object_failed", object=obj.name, error=str(e))

    def object_exists(self, obj: DbObject) -> bool:
        checks = {
            ObjectType.TABLE: (
                "SELECT 1 FROM information_schema.TABLES WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s AND TABLE_TYPE = 'BASE TABLE'",
                (self._database, obj.name),
            ),
            ObjectType.VIEW: (
                "SELECT 1 FROM information_schema.VIEWS WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s",
                (self._database, obj.name),
            ),
        }
        check = checks.get(obj.object_type)
        if check:
            rows = self._query(*check)
            return len(rows) > 0
        return False

    def get_database_info(self) -> dict[str, Any]:
        version = self._query("SELECT VERSION()")[0][0]
        size_rows = self._query("""
            SELECT SUM(DATA_LENGTH + INDEX_LENGTH)
            FROM information_schema.TABLES
            WHERE TABLE_SCHEMA = %s
        """, (self._database,))
        size = size_rows[0][0] if size_rows and size_rows[0][0] else 0

        table_count = self._query("""
            SELECT COUNT(*)
            FROM information_schema.TABLES
            WHERE TABLE_SCHEMA = %s AND TABLE_TYPE = 'BASE TABLE'
        """, (self._database,))[0][0]

        return {
            "type": "MySQL",
            "version": version,
            "database": self._database,
            "size_bytes": int(size),
            "table_count": table_count,
        }


def _qi(identifier: str) -> str:
    """Quote a MySQL identifier with backticks."""
    return f"`{identifier}`"
