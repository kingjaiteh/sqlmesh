import pytest

from sqlmesh.integrations.dlt import format_ducklake_config, generate_incremental_model


def test_generate_incremental_model_filters_on_timestamp_macros() -> None:
    # The DLT-generated model's time column is a timestamp
    # (TO_TIMESTAMP(...)). It must therefore be filtered with the inclusive
    # timestamp macros @start_ts/@end_ts, not the categorical date macros
    # @start_ds/@end_ds, which both render midnight and exclude any rows past
    # 00:00:00 on a single-day run.
    model = generate_incremental_model(
        "dataset_sqlmesh.incremental_equipment",
        "  CAST(c.item_id AS BIGINT) AS item_id",
        "",
        "dataset.equipment",
        "duckdb",
        "c._dlt_load_id",
    )

    assert "BETWEEN @start_ts AND @end_ts" in model
    assert "@start_ds" not in model
    assert "@end_ds" not in model


def _ducklake_credentials(catalog: str, storage: str, **kwargs):  # type: ignore
    from dlt.destinations.impl.ducklake.configuration import DuckLakeCredentials

    return DuckLakeCredentials(catalog=catalog, storage=storage, **kwargs)


def test_format_ducklake_config_duckdb_catalog(tmp_path) -> None:
    credentials = _ducklake_credentials(
        catalog=f"duckdb:///{tmp_path.as_posix()}/catalog.duckdb",
        storage=(tmp_path / "lake_files").as_uri(),
        ducklake_name="my_lake",
    )

    config = format_ducklake_config(credentials)

    assert config == "\n".join(
        [
            "      type: duckdb",
            "      catalogs:",
            "        my_lake:",
            "          type: 'ducklake'",
            f"          path: '{tmp_path.as_posix()}/catalog.duckdb'",
            f"          data_path: '{credentials.storage_url}'",
        ]
    )


def test_format_ducklake_config_sqlite_catalog(tmp_path) -> None:
    credentials = _ducklake_credentials(
        catalog=f"sqlite:///{tmp_path.as_posix()}/catalog.sqlite",
        storage=(tmp_path / "lake_files").as_uri(),
    )

    config = format_ducklake_config(credentials)

    assert "        ducklake:\n" in config
    assert f"          path: 'sqlite:{tmp_path.as_posix()}/catalog.sqlite'\n" in config
    assert "metadata_schema" not in config


def test_format_ducklake_config_postgres_catalog(tmp_path) -> None:
    credentials = _ducklake_credentials(
        catalog="postgresql://loader:secret@localhost:5432/dlt_data",
        storage=(tmp_path / "lake_files").as_uri(),
        ducklake_name="lake",
        metadata_schema="lake_meta",
    )

    config = format_ducklake_config(credentials)

    # sqlalchemy's `postgresql` driver name is not known to DuckDB, dlt attaches it as `postgres`
    assert (
        "          path: 'postgres:postgresql://loader:secret@localhost:5432/dlt_data'\n" in config
    )
    assert config.endswith("          metadata_schema: 'lake_meta'")


def test_format_ducklake_config_unsupported_catalog(tmp_path) -> None:
    import click

    credentials = _ducklake_credentials(
        catalog="mssql://loader:secret@localhost:1433/dlt_data",
        storage=(tmp_path / "lake_files").as_uri(),
    )

    with pytest.raises(click.ClickException, match="Unsupported DuckLake catalog database 'mssql'"):
        format_ducklake_config(credentials)
