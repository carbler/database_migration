import psycopg2
import psycopg2.extras
import subprocess
import os
from typing import List, Generator, Any, Optional
from contextlib import contextmanager

from src.core.domain.interfaces import DatabaseConnector
from src.core.domain.entities import Table, Column, ForeignKey, Index
from src.core.domain.value_objects import ConnectionConfig
from src.infrastructure.connectors.base import BaseConnector

class PostgreSQLConnector(BaseConnector):
    def connect(self) -> None:
        self.connection = psycopg2.connect(
            host=self.config.host,
            port=self.config.port,
            user=self.config.user,
            password=self.config.password,
            dbname=self.config.database,
            sslmode=self.config.ssl_mode if self.config.ssl_mode != 'disable' else None
        )

    def disconnect(self) -> None:
        if self.connection:
            self.connection.close()

    def get_tables(self) -> List[Table]:
        tables = []
        with self.connection.cursor() as cursor:
            cursor.execute("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
            """)
            rows = cursor.fetchall()
            for row in rows:
                tables.append(self.get_schema(row[0]))
        return tables

    def get_foreign_keys(self, table_name: str) -> List[ForeignKey]:
        fks = []
        # Complex query for FKs in PG
        query = """
            SELECT
                kcu.column_name,
                ccu.table_name AS foreign_table_name,
                ccu.column_name AS foreign_column_name,
                tc.constraint_name
            FROM
                information_schema.table_constraints AS tc
                JOIN information_schema.key_column_usage AS kcu
                  ON tc.constraint_name = kcu.constraint_name
                  AND tc.table_schema = kcu.table_schema
                JOIN information_schema.constraint_column_usage AS ccu
                  ON ccu.constraint_name = tc.constraint_name
                  AND ccu.table_schema = tc.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_name=%s;
        """
        with self.connection.cursor() as cursor:
            cursor.execute(query, (table_name,))
            rows = cursor.fetchall()
            for row in rows:
                fks.append(ForeignKey(
                    column=row[0],
                    referenced_table=row[1],
                    referenced_column=row[2],
                    name=row[3]
                ))
        return fks

    def get_schema(self, table_name: str) -> Table:
        columns = []
        primary_key = []

        with self.connection.cursor() as cursor:
            # Get columns
            cursor.execute("""
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns
                WHERE table_name = %s
            """, (table_name,))
            rows = cursor.fetchall()
            for row in rows:
                col = Column(
                    name=row[0],
                    data_type=row[1],
                    is_nullable=row[2] == 'YES',
                    default=row[3]
                )
                columns.append(col)

            # Get PK
            cursor.execute("""
                SELECT kcu.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON kcu.constraint_name = tc.constraint_name
                  AND kcu.table_schema = tc.table_schema
                WHERE tc.constraint_type = 'PRIMARY KEY' AND tc.table_name = %s
            """, (table_name,))
            pk_rows = cursor.fetchall()
            primary_key = [row[0] for row in pk_rows]

        # Get raw create statement using pg_dump
        raw_sql = self._get_raw_ddl(table_name)

        return Table(
            name=table_name,
            columns=columns,
            primary_key=primary_key,
            foreign_keys=self.get_foreign_keys(table_name),
            raw_create_statement=raw_sql
        )

    def _get_raw_ddl(self, table_name: str) -> Optional[str]:
        # Try to use pg_dump to get schema
        try:
            env = os.environ.copy()
            env['PGPASSWORD'] = self.config.password
            cmd = [
                'pg_dump',
                '-h', self.config.host,
                '-p', str(self.config.port),
                '-U', self.config.user,
                '-d', self.config.database,
                '-s', '-t', table_name,
                '--no-owner', '--no-acl'
            ]
            result = subprocess.run(cmd, env=env, capture_output=True, text=True)
            if result.returncode == 0:
                return result.stdout
            else:
                # Log warning or fallback
                import structlog
                logger = structlog.get_logger()
                logger.warning(f"pg_dump failed for {table_name}: {result.stderr}")
                return None
        except FileNotFoundError:
            # pg_dump not found
            return None

    def create_table(self, table: Table) -> None:
        if table.raw_create_statement:
            try:
                with self.connection.cursor() as cursor:
                    cursor.execute(table.raw_create_statement)
                    self.connection.commit()
            except Exception:
                self.connection.rollback()
                raise
        else:
            raise ValueError(f"No CREATE TABLE statement found for table '{table.name}'. Ensure pg_dump is available and working.")

    def drop_table(self, table_name: str) -> None:
        with self.connection.cursor() as cursor:
            cursor.execute(f"DROP TABLE IF EXISTS \"{table_name}\" CASCADE")
            self.connection.commit()

    def truncate_table(self, table_name: str) -> None:
        with self.connection.cursor() as cursor:
            cursor.execute(f"TRUNCATE TABLE \"{table_name}\" CASCADE")
            self.connection.commit()

    def fetch_data(self, table_name: str, batch_size: int = 1000) -> Generator[List[Any], None, None]:
        # Use named cursor for server-side streaming
        cursor_name = f"curs_{table_name}"
        with self.connection.cursor(name=cursor_name) as cursor:
            cursor.execute(f"SELECT * FROM \"{table_name}\"")
            while True:
                batch = cursor.fetchmany(batch_size)
                if not batch:
                    break
                yield batch

    def insert_data(self, table_name: str, data: List[Any], columns: List[str], on_conflict: str = 'raise', primary_key: Optional[List[str]] = None) -> int:
        if not data:
            return 0

        columns_str = ', '.join([f"\"{c}\"" for c in columns])
        placeholders = ', '.join(['%s'] * len(columns))
        sql = f"INSERT INTO \"{table_name}\" ({columns_str}) VALUES ({placeholders})"

        if on_conflict != 'raise' and primary_key:
            pk_str = ', '.join([f"\"{c}\"" for c in primary_key])
            if on_conflict == 'ignore':
                sql += f" ON CONFLICT ({pk_str}) DO NOTHING"
            elif on_conflict == 'update':
                update_items = []
                for col in columns:
                    # Don't update PK columns
                    if col not in primary_key:
                        update_items.append(f"\"{col}\" = EXCLUDED.\"{col}\"")

                if update_items:
                    update_clause = ', '.join(update_items)
                    sql += f" ON CONFLICT ({pk_str}) DO UPDATE SET {update_clause}"
                else:
                    # If only PK columns, update does nothing, so DO NOTHING
                    sql += f" ON CONFLICT ({pk_str}) DO NOTHING"

        with self.connection.cursor() as cursor:
            psycopg2.extras.execute_batch(cursor, sql, data)
            self.connection.commit()
            return len(data) # execute_batch doesn't return rowcount

    def disable_foreign_keys(self) -> None:
        with self.connection.cursor() as cursor:
            cursor.execute("SET session_replication_role = 'replica';")

    def enable_foreign_keys(self) -> None:
        with self.connection.cursor() as cursor:
            cursor.execute("SET session_replication_role = 'origin';")

    def count_rows(self, table_name: str) -> int:
        with self.connection.cursor() as cursor:
            cursor.execute(f"SELECT COUNT(*) FROM \"{table_name}\"")
            return cursor.fetchone()[0]

    def get_installed_extensions(self) -> List[str]:
        with self.connection.cursor() as cursor:
            cursor.execute("SELECT extname, extversion FROM pg_extension")
            return [f"{row[0]} ({row[1]})" for row in cursor.fetchall()]

    def fetch_sample_rows(self, table_name: str, pk_columns: List[str], limit: int = 1000) -> List[Any]:
        if not pk_columns:
            return []

        pk_str = ', '.join([f"\"{c}\"" for c in pk_columns])
        with self.connection.cursor() as cursor:
            cursor.execute(f"SELECT * FROM \"{table_name}\" ORDER BY {pk_str} LIMIT {limit}")
            return cursor.fetchall()
