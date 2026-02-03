from typing import List, Optional, Any
from dataclasses import dataclass, field

@dataclass
class ForeignKey:
    column: str
    referenced_table: str
    referenced_column: str
    name: Optional[str] = None
    on_delete: str = "NO ACTION"
    on_update: str = "NO ACTION"

@dataclass
class Index:
    name: str
    columns: List[str]
    unique: bool = False

@dataclass
class Column:
    name: str
    data_type: str
    is_nullable: bool = True
    is_primary_key: bool = False
    default: Optional[Any] = None
    extra: Optional[str] = None  # For things like auto_increment

@dataclass
class Table:
    name: str
    columns: List[Column] = field(default_factory=list)
    primary_key: List[str] = field(default_factory=list)
    foreign_keys: List[ForeignKey] = field(default_factory=list)
    indexes: List[Index] = field(default_factory=list)
    raw_create_statement: Optional[str] = None

    def get_column(self, name: str) -> Optional[Column]:
        for col in self.columns:
            if col.name == name:
                return col
        return None

@dataclass
class Database:
    name: str
    tables: List[Table] = field(default_factory=list)

    def get_table(self, name: str) -> Optional[Table]:
        for table in self.tables:
            if table.name == name:
                return table
        return None
