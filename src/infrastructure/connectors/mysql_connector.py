import pymysql
import pymysql.cursors
from typing import List, Generator, Any, Optional
from contextlib import contextmanager

from src.core.domain.interfaces import DatabaseConnector
from src.core.domain.entities import Table, Column, ForeignKey, Index
from src.core.domain.value_objects import ConnectionConfig
from src.infrastructure.connectors.base import BaseConnector

class MySQLConnector(BaseConnector):
    def connect(self) -> None:
        self.connection = pymysql.connect(
            host=self.config.host,
            port=self.config.port,
            user=self.config.user,
            password=self.config.password,
            database=self.config.database,
            cursorclass=pymysql.cursors.DictCursor,
            ssl={'ssl': {'ca': '/etc/ssl/certs/ca-certificates.crt'}} if self.config.ssl_mode != 'disable' else None
        )

    def disconnect(self) -> None:
        if self.connection:
            self.connection.close()

    def get_tables(self) -> List[Table]:
        tables = []
        with self.connection.cursor() as cursor:
            cursor.execute("SHOW TABLES")
            rows = cursor.fetchall()
            for row in rows:
                table_name = list(row.values())[0]
                tables.append(self.get_schema(table_name))
        return tables

    def get_foreign_keys(self, table_name: str) -> List[ForeignKey]:
        fks = []
        query = """
            SELECT
                COLUMN_NAME,
                REFERENCED_TABLE_NAME,
                REFERENCED_COLUMN_NAME,
                CONSTRAINT_NAME
            FROM information_schema.KEY_COLUMN_USAGE
            WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s AND REFERENCED_TABLE_NAME IS NOT NULL
        """
        with self.connection.cursor() as cursor:
            cursor.execute(query, (self.config.database, table_name))
            rows = cursor.fetchall()
            for row in rows:
                fks.append(ForeignKey(
                    column=row['COLUMN_NAME'],
                    referenced_table=row['REFERENCED_TABLE_NAME'],
                    referenced_column=row['REFERENCED_COLUMN_NAME'],
                    name=row['CONSTRAINT_NAME']
                ))
        return fks

    def get_schema(self, table_name: str) -> Table:
        columns = []
        primary_key = []
        indexes = []

        # Columns
        with self.connection.cursor() as cursor:
            cursor.execute(f"DESCRIBE `{table_name}`")
            rows = cursor.fetchall()
            for row in rows:
                col = Column(
                    name=row['Field'],
                    data_type=row['Type'],
                    is_nullable=row['Null'] == 'YES',
                    is_primary_key=row['Key'] == 'PRI',
                    default=row['Default'],
                    extra=row['Extra']
                )
                columns.append(col)
                if col.is_primary_key:
                    primary_key.append(col.name)

        # Raw Create Statement
        raw_sql = None
        with self.connection.cursor() as cursor:
            cursor.execute(f"SHOW CREATE TABLE `{table_name}`")
            result = cursor.fetchone()
            if result:
                raw_sql = result['Create Table']

        # Indexes (simplified for now, SHOW INDEX handles more details)
        # Using information_schema.STATISTICS for comprehensive index info is better but SHOW INDEX works.

        table = Table(
            name=table_name,
            columns=columns,
            primary_key=primary_key,
            foreign_keys=self.get_foreign_keys(table_name),
            indexes=indexes, # TODO: Parse indexes properly if needed for validation
            raw_create_statement=raw_sql
        )
        return table

    def create_table(self, table: Table) -> None:
        with self.connection.cursor() as cursor:
            if table.raw_create_statement:
                 # Use raw SQL for exact replication
                 # But need to handle "CREATE TABLE `name`" if name changed? No, exact replica.
                 # Also need to handle "IF NOT EXISTS"?
                 # And handle foreign key checks temporarily if table order is not strictly topological (though the prompt says topological sort).
                 # Wait, prompt says: "Topological sort of tables based on dependencies".
                 cursor.execute(table.raw_create_statement)
            else:
                # Fallback implementation
                pass

    def drop_table(self, table_name: str) -> None:
        with self.connection.cursor() as cursor:
            cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
            cursor.execute(f"DROP TABLE IF EXISTS `{table_name}`")
            cursor.execute("SET FOREIGN_KEY_CHECKS = 1")

    def truncate_table(self, table_name: str) -> None:
        with self.connection.cursor() as cursor:
            cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
            cursor.execute(f"TRUNCATE TABLE `{table_name}`")
            cursor.execute("SET FOREIGN_KEY_CHECKS = 1")

    def fetch_data(self, table_name: str, columns: List[str] = None, batch_size: int = 1000) -> Generator[List[Any], None, None]:
        # Server-side cursor for large tables
        ss_cursor = pymysql.cursors.SSCursor(self.connection)
        try:
            if columns:
                cols_str = ', '.join([f"`{c}`" for c in columns])
                query = f"SELECT {cols_str} FROM `{table_name}`"
            else:
                query = f"SELECT * FROM `{table_name}`"

            ss_cursor.execute(query)
            while True:
                batch = ss_cursor.fetchmany(batch_size)
                if not batch:
                    break
                yield batch
        finally:
            ss_cursor.close()

    def insert_data(self, table_name: str, data: List[Any], columns: List[str], on_conflict: str = 'raise', primary_key: Optional[List[str]] = None) -> int:
        if not data:
            return 0

        placeholders = ', '.join(['%s'] * len(columns))
        columns_str = ', '.join([f"`{c}`" for c in columns])

        if on_conflict == 'ignore':
            sql = f"INSERT IGNORE INTO `{table_name}` ({columns_str}) VALUES ({placeholders})"
        elif on_conflict == 'update':
            update_clause = ', '.join([f"`{col}`=VALUES(`{col}`)" for col in columns])
            sql = f"INSERT INTO `{table_name}` ({columns_str}) VALUES ({placeholders}) ON DUPLICATE KEY UPDATE {update_clause}"
        else:
            sql = f"INSERT INTO `{table_name}` ({columns_str}) VALUES ({placeholders})"

        with self.connection.cursor() as cursor:
            cursor.executemany(sql, data)
            self.connection.commit()
            return cursor.rowcount

    def disable_foreign_keys(self) -> None:
        with self.connection.cursor() as cursor:
            cursor.execute("SET FOREIGN_KEY_CHECKS = 0")

    def enable_foreign_keys(self) -> None:
        with self.connection.cursor() as cursor:
            cursor.execute("SET FOREIGN_KEY_CHECKS = 1")

    def count_rows(self, table_name: str) -> int:
        with self.connection.cursor() as cursor:
            cursor.execute(f"SELECT COUNT(*) as count FROM `{table_name}`")
            result = cursor.fetchone()
            return result['count']

    def fetch_sample_rows(self, table_name: str, pk_columns: List[str], limit: int = 1000) -> List[Any]:
        if not pk_columns:
            return []

        pk_str = ', '.join([f"`{c}`" for c in pk_columns])
        with self.connection.cursor() as cursor:
            cursor.execute(f"SELECT * FROM `{table_name}` ORDER BY {pk_str} LIMIT {limit}")
            return cursor.fetchall()
