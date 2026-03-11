"""Integration tests for MySQL cloning (requires Docker)."""

import pytest

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def mysql_source():
    """Start a MySQL container as source."""
    try:
        from testcontainers.mysql import MySqlContainer
    except ImportError:
        pytest.skip("testcontainers not installed")

    with MySqlContainer("mysql:8.0") as mysql:
        url = mysql.get_connection_url()
        # Adapt URL scheme
        url = url.replace("mysql+pymysql://", "mysql://")

        import pymysql
        from urllib.parse import urlparse
        parsed = urlparse(url)
        conn = pymysql.connect(
            host=parsed.hostname,
            port=parsed.port,
            user=parsed.username,
            password=parsed.password,
            database=parsed.path.lstrip("/"),
            autocommit=True,
        )
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE users (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    email VARCHAR(200) UNIQUE
                )
            """)
            cur.execute("""
                CREATE TABLE orders (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT,
                    amount DECIMAL(10,2),
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            """)
            cur.execute("""
                INSERT INTO users (name, email) VALUES
                ('Alice', 'alice@example.com'),
                ('Bob', 'bob@example.com')
            """)
            cur.execute("""
                INSERT INTO orders (user_id, amount) VALUES
                (1, 99.99), (2, 50.00)
            """)
        conn.close()
        yield url


@pytest.fixture(scope="module")
def mysql_target():
    """Start a MySQL container as target."""
    try:
        from testcontainers.mysql import MySqlContainer
    except ImportError:
        pytest.skip("testcontainers not installed")

    with MySqlContainer("mysql:8.0") as mysql:
        url = mysql.get_connection_url().replace("mysql+pymysql://", "mysql://")
        yield url


class TestMySQLClone:
    def test_full_clone(self, mysql_source, mysql_target):
        from db_clone.config import Settings
        from db_clone.engine.orchestrator import Orchestrator
        from db_clone.models import ConflictStrategy

        settings = Settings(
            source_url=mysql_source,
            target_url=mysql_target,
            batch_size=100,
            strategy=ConflictStrategy.OVERWRITE,
        )
        orch = Orchestrator(settings)
        result = orch.run()

        assert result.success
        assert result.rows_copied >= 4  # 2 users + 2 orders
