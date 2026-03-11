"""Shared test fixtures."""

import pytest

from db_clone.models import ConflictStrategy, DbObject, ObjectType, TableInfo


@pytest.fixture
def sample_table_obj():
    return DbObject(
        name="users",
        schema="public",
        object_type=ObjectType.TABLE,
        definition='CREATE TABLE "public"."users" (\n    "id" integer NOT NULL,\n    "name" text,\n    PRIMARY KEY ("id")\n);',
    )


@pytest.fixture
def sample_table_info():
    return TableInfo(
        name="users",
        schema="public",
        row_count=10000,
        primary_key=["id"],
    )


@pytest.fixture
def sample_objects():
    """A collection of DB objects for testing."""
    return {
        ObjectType.SCHEMA: [
            DbObject(name="app", schema="", object_type=ObjectType.SCHEMA,
                     definition='CREATE SCHEMA IF NOT EXISTS "app";'),
        ],
        ObjectType.TABLE: [
            DbObject(name="users", schema="public", object_type=ObjectType.TABLE,
                     definition='CREATE TABLE "public"."users" ("id" integer PRIMARY KEY);'),
            DbObject(name="orders", schema="public", object_type=ObjectType.TABLE,
                     definition='CREATE TABLE "public"."orders" ("id" integer PRIMARY KEY, "user_id" integer);'),
        ],
        ObjectType.INDEX: [
            DbObject(name="idx_orders_user_id", schema="public",
                     object_type=ObjectType.INDEX,
                     definition='CREATE INDEX "idx_orders_user_id" ON "public"."orders" ("user_id");',
                     dependencies=["public.orders"]),
        ],
        ObjectType.FOREIGN_KEY: [
            DbObject(name="fk_orders_user", schema="public",
                     object_type=ObjectType.FOREIGN_KEY,
                     definition='ALTER TABLE "public"."orders" ADD CONSTRAINT "fk_orders_user" FOREIGN KEY ("user_id") REFERENCES "public"."users" ("id");',
                     dependencies=["public.orders"]),
        ],
    }
