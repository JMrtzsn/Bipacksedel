import pytest

from bipacksedel import store
from bipacksedel.store import is_supported


def test_database_dsn_is_the_compose_database():
    assert store.DATABASE_DSN == "postgresql://postgres:postgres@localhost:5432/druglabels"


def test_supported_flips_around_threshold():
    assert is_supported([{"score": 0.8}], 0.8)
    assert not is_supported([{"score": 0.79}], 0.8)
    assert not is_supported([], 0.8)


@pytest.mark.integration
def test_database_schema_can_be_created():
    psycopg = pytest.importorskip("psycopg")
    from bipacksedel.store import connect, create_schema

    try:
        with connect() as connection:
            create_schema(connection)
            assert connection.execute("SELECT to_regclass('label_chunks')").fetchone()[0]
    except psycopg.OperationalError:
        pytest.skip("database is unreachable")
