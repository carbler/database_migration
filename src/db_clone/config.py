"""Configuration management using pydantic-settings."""

from __future__ import annotations

from urllib.parse import urlparse

from pydantic import field_validator
from pydantic_settings import BaseSettings

from db_clone.models import ConflictStrategy, DbType


class Settings(BaseSettings):
    model_config = {"env_prefix": "DB_CLONE_"}

    source_url: str = ""
    target_url: str = ""
    batch_size: int = 5000
    log_level: str = "INFO"
    log_file: str = "db-clone.log"
    strategy: ConflictStrategy = ConflictStrategy.OVERWRITE
    resume: bool = False
    exclude_tables: str = ""
    include_tables: str = ""
    data_only: bool = False
    schema_only: bool = False

    @field_validator("batch_size")
    @classmethod
    def validate_batch_size(cls, v: int) -> int:
        if v < 1:
            raise ValueError("batch_size must be >= 1")
        return v

    @property
    def exclude_table_list(self) -> list[str]:
        if not self.exclude_tables:
            return []
        return [t.strip() for t in self.exclude_tables.split(",") if t.strip()]

    @property
    def include_table_list(self) -> list[str]:
        if not self.include_tables:
            return []
        return [t.strip() for t in self.include_tables.split(",") if t.strip()]


def parse_db_type(url: str) -> DbType:
    """Extract database type from connection URL."""
    parsed = urlparse(url)
    scheme = parsed.scheme.lower().split("+")[0]
    if scheme in ("postgresql", "postgres"):
        return DbType.POSTGRESQL
    elif scheme == "mysql":
        return DbType.MYSQL
    else:
        raise ValueError(f"Unsupported database type: {scheme}")


def validate_urls(source: str, target: str) -> None:
    """Validate that source and target are the same DB type."""
    source_type = parse_db_type(source)
    target_type = parse_db_type(target)
    if source_type != target_type:
        raise ValueError(
            f"Source ({source_type.value}) and target ({target_type.value}) "
            f"must be the same database type"
        )
