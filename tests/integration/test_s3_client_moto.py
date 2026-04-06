"""Integration tests for S3Client using moto (in-memory S3)."""

import pyarrow as pa
import pytest

from fpl_lib.clients.s3 import S3Client


@pytest.mark.integration
class TestS3ClientMoto:
    """Verify S3Client operations against moto's in-memory S3."""

    def test_json_roundtrip(self, moto_s3: str) -> None:
        """put_json → read_json round-trip preserves data."""
        s3 = S3Client()
        data = {"players": [{"id": 1, "name": "Haaland"}], "count": 1}

        s3.put_json(moto_s3, "test/data.json", data)
        result = s3.read_json(moto_s3, "test/data.json")

        assert result == data

    def test_parquet_roundtrip(self, moto_s3: str) -> None:
        """write_parquet → read_parquet preserves schema and data."""
        s3 = S3Client()
        table = pa.table(
            {
                "id": [1, 2, 3],
                "name": ["Haaland", "Saka", "Fernandes"],
                "points": [197, 155, 189],
            }
        )

        s3.write_parquet(moto_s3, "test/players.parquet", table)
        result = s3.read_parquet(moto_s3, "test/players.parquet")

        assert result.num_rows == 3
        assert result.schema == table.schema
        assert result.to_pydict() == table.to_pydict()

    def test_list_objects(self, moto_s3: str) -> None:
        """list_objects returns all keys under prefix."""
        s3 = S3Client()
        for i in range(3):
            s3.put_json(moto_s3, f"prefix/file_{i}.json", {"i": i})

        keys = s3.list_objects(moto_s3, "prefix/")
        assert len(keys) == 3
        assert all(k.startswith("prefix/") for k in keys)

    def test_object_exists(self, moto_s3: str) -> None:
        """object_exists returns True for existing, False for missing keys."""
        s3 = S3Client()
        s3.put_json(moto_s3, "exists.json", {"ok": True})

        assert s3.object_exists(moto_s3, "exists.json") is True
        assert s3.object_exists(moto_s3, "missing.json") is False
