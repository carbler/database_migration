from setuptools import setup, find_packages

setup(
    name="db-migrator",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "pymysql>=1.1.0",
        "psycopg2-binary>=2.9.9",
        "sqlalchemy>=2.0.25",
        "python-decouple>=3.8",
        "click>=8.1.7",
        "rich>=13.7.0",
        "tqdm>=4.66.1",
        "pydantic>=2.5.3",
        "tenacity>=8.2.3",
        "structlog>=24.1.0",
    ],
    entry_points={
        "console_scripts": [
            "db-migrator=src.presentation.cli:cli",
        ],
    },
)
