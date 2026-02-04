from decouple import config
from src.core.domain.value_objects import ConnectionConfig, DatabaseType, SSLMode

def clean_config(value):
    """Strip comments and whitespace from configuration values."""
    if isinstance(value, str):
        return value.split('#')[0].strip()
    return value

class Settings:
    # Source DB
    SOURCE_DB_TYPE = clean_config(config('SOURCE_DB_TYPE', default='mysql'))
    SOURCE_DB_HOST = clean_config(config('SOURCE_DB_HOST', default='localhost'))
    SOURCE_DB_PORT = config('SOURCE_DB_PORT', default=3306, cast=int)
    SOURCE_DB_NAME = clean_config(config('SOURCE_DB_NAME', default='source_db'))
    SOURCE_DB_USER = clean_config(config('SOURCE_DB_USER', default='root'))
    # Do not clean passwords to allow # character
    SOURCE_DB_PASSWORD = config('SOURCE_DB_PASSWORD', default='secret')
    SOURCE_DB_SSL_MODE = clean_config(config('SOURCE_DB_SSL_MODE', default='disable'))

    # Target DB
    TARGET_DB_TYPE = clean_config(config('TARGET_DB_TYPE', default='mysql'))
    TARGET_DB_HOST = clean_config(config('TARGET_DB_HOST', default='localhost'))
    TARGET_DB_PORT = config('TARGET_DB_PORT', default=3306, cast=int)
    TARGET_DB_NAME = clean_config(config('TARGET_DB_NAME', default='target_db'))
    TARGET_DB_USER = clean_config(config('TARGET_DB_USER', default='root'))
    # Do not clean passwords to allow # character
    TARGET_DB_PASSWORD = config('TARGET_DB_PASSWORD', default='secret')
    TARGET_DB_SSL_MODE = clean_config(config('TARGET_DB_SSL_MODE', default='disable'))

    # Migration Settings
    BATCH_SIZE = config('BATCH_SIZE', default=1000, cast=int)
    MAX_WORKERS = config('MAX_WORKERS', default=4, cast=int)
    ENABLE_VALIDATION = config('ENABLE_VALIDATION', default=True, cast=bool)
    CONFLICT_STRATEGY = clean_config(config('CONFLICT_STRATEGY', default='fail'))
    LOG_LEVEL = clean_config(config('LOG_LEVEL', default='INFO'))

    @classmethod
    def get_source_config(cls) -> ConnectionConfig:
        return ConnectionConfig(
            db_type=cls.SOURCE_DB_TYPE,
            host=cls.SOURCE_DB_HOST,
            port=cls.SOURCE_DB_PORT,
            database=cls.SOURCE_DB_NAME,
            user=cls.SOURCE_DB_USER,
            password=cls.SOURCE_DB_PASSWORD,
            ssl_mode=cls.SOURCE_DB_SSL_MODE
        )

    @classmethod
    def get_target_config(cls) -> ConnectionConfig:
        return ConnectionConfig(
            db_type=cls.TARGET_DB_TYPE,
            host=cls.TARGET_DB_HOST,
            port=cls.TARGET_DB_PORT,
            database=cls.TARGET_DB_NAME,
            user=cls.TARGET_DB_USER,
            password=cls.TARGET_DB_PASSWORD,
            ssl_mode=cls.TARGET_DB_SSL_MODE
        )
