from pydantic import BaseModel, Field, validator
from typing import Optional
from enum import Enum

class DatabaseType(str, Enum):
    MYSQL = "mysql"
    POSTGRESQL = "postgresql"

class SSLMode(str, Enum):
    DISABLE = "disable"
    REQUIRE = "require"
    VERIFY_CA = "verify-ca"
    VERIFY_FULL = "verify-full"

class ConnectionConfig(BaseModel):
    db_type: DatabaseType
    host: str
    port: int = Field(gt=0, lt=65536)
    database: str
    user: str
    password: str
    ssl_mode: SSLMode = SSLMode.DISABLE

    @validator('db_type', pre=True)
    def validate_db_type(cls, v):
        if isinstance(v, str):
            return v.lower()
        return v

class MigrationStats(BaseModel):
    total_tables: int = 0
    migrated_tables: int = 0
    failed_tables: int = 0
    total_rows: int = 0
    migrated_rows: int = 0
    duration_seconds: float = 0.0
    errors: list[str] = Field(default_factory=list)

    def add_error(self, error: str):
        self.errors.append(error)
        self.failed_tables += 1
