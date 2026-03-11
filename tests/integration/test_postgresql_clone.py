"""Integration tests for PostgreSQL cloning (requires Docker)."""

import pytest

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def pg_source():
    """Start a PostgreSQL container as source."""
    try:
        from testcontainers.postgres import PostgresContainer
    except ImportError:
        pytest.skip("testcontainers not installed")

    with PostgresContainer("postgres:16") as pg:
        url = pg.get_connection_url()
        # Create test objects
        import psycopg2
        conn = psycopg2.connect(url)
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute("""
                CREATE SCHEMA IF NOT EXISTS app;

                CREATE TABLE public.users (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    email TEXT UNIQUE
                );

                CREATE TABLE public.orders (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES public.users(id),
                    amount NUMERIC(10,2),
                    created_at TIMESTAMP DEFAULT NOW()
                );

                CREATE INDEX idx_orders_user ON public.orders(user_id);

                CREATE VIEW public.active_users AS
                    SELECT * FROM public.users WHERE name IS NOT NULL;

                CREATE OR REPLACE FUNCTION public.get_user_count()
                RETURNS INTEGER AS $$
                BEGIN
                    RETURN (SELECT count(*) FROM public.users);
                END;
                $$ LANGUAGE plpgsql;

                INSERT INTO public.users (name, email) VALUES
                    ('Alice', 'alice@example.com'),
                    ('Bob', 'bob@example.com'),
                    ('Charlie', 'charlie@example.com');

                INSERT INTO public.orders (user_id, amount) VALUES
                    (1, 99.99), (1, 49.50), (2, 150.00);
            """)
        conn.close()
        yield url


@pytest.fixture(scope="module")
def pg_target():
    """Start a PostgreSQL container as target."""
    try:
        from testcontainers.postgres import PostgresContainer
    except ImportError:
        pytest.skip("testcontainers not installed")

    with PostgresContainer("postgres:16") as pg:
        yield pg.get_connection_url()


class TestPostgreSQLClone:
    def test_full_clone(self, pg_source, pg_target):
        from db_clone.config import Settings
        from db_clone.engine.orchestrator import Orchestrator
        from db_clone.models import ConflictStrategy

        settings = Settings(
            source_url=pg_source,
            target_url=pg_target,
            batch_size=100,
            strategy=ConflictStrategy.OVERWRITE,
        )
        orch = Orchestrator(settings)
        result = orch.run()

        assert result.success
        assert result.rows_copied >= 6  # 3 users + 3 orders

    def test_validate_after_clone(self, pg_source, pg_target):
        from db_clone.connectors import create_connector
        from db_clone.engine.validator import Validator

        src = create_connector(pg_source)
        tgt = create_connector(pg_target)
        with src, tgt:
            validator = Validator(src, tgt)
            result = validator.validate()
            # Tables should match
            table_checks = [c for c in result.checks if c.name == "table_count"]
            assert all(c.passed for c in table_checks)
