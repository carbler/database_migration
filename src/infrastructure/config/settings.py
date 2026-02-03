from decouple import config
from src.core.domain.value_objects import ConnectionConfig, DatabaseType, SSLMode

class Settings:
    # Source DB
    SOURCE_DB_TYPE = config('SOURCE_DB_TYPE', default='mysql')
    SOURCE_DB_HOST = config('SOURCE_DB_HOST', default='localhost')
    SOURCE_DB_PORT = config('SOURCE_DB_PORT', default=3306, cast=int)
    SOURCE_DB_NAME = config('SOURCE_DB_NAME', default='source_db')
    SOURCE_DB_USER = config('SOURCE_DB_USER', default='root')
    SOURCE_DB_PASSWORD = config('SOURCE_DB_PASSWORD', default='secret')
    SOURCE_DB_SSL_MODE = config('SOURCE_DB_SSL_MODE', default='disable')

    # Target DB
    TARGET_DB_TYPE = config('TARGET_DB_TYPE', default='mysql')
    TARGET_DB_HOST = config('TARGET_DB_HOST', default='localhost')
    TARGET_DB_PORT = config('TARGET_DB_PORT', default=3306, cast=int)
    TARGET_DB_NAME = config('TARGET_DB_NAME', default='target_db')
    TARGET_DB_USER = config('TARGET_DB_USER', default='root')
    TARGET_DB_PASSWORD = config('TARGET_DB_PASSWORD', default='secret')
    TARGET_DB_SSL_MODE = config('TARGET_DB_SSL_MODE', default='disable')

    # Migration Settings
    BATCH_SIZE = config('BATCH_SIZE', default=1000, cast=int)
    MAX_WORKERS = config('MAX_WORKERS', default=4, cast=int)
    ENABLE_VALIDATION = config('ENABLE_VALIDATION', default=True, cast=bool)
    CONFLICT_STRATEGY = config('CONFLICT_STRATEGY', default='fail')
    LOG_LEVEL = config('LOG_LEVEL', default='INFO')

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
