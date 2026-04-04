"""Tests for S3Client with mocked boto3."""

import json
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest

from fpl_lib.clients.s3 import S3Client


@pytest.mark.unit
class TestS3Client:
    @patch("fpl_lib.clients.s3.boto3")
    def test_put_json(self, mock_boto3: MagicMock) -> None:
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client

        client = S3Client()
        client.put_json("my-bucket", "data/test.json", {"key": "value"})

        mock_client.put_object.assert_called_once()
        call_kwargs = mock_client.put_object.call_args[1]
        assert call_kwargs["Bucket"] == "my-bucket"
        assert call_kwargs["Key"] == "data/test.json"
        assert json.loads(call_kwargs["Body"]) == {"key": "value"}

    @patch("fpl_lib.clients.s3.boto3")
    def test_read_json(self, mock_boto3: MagicMock) -> None:
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client

        body_content = json.dumps({"players": [1, 2, 3]}).encode()
        mock_client.get_object.return_value = {
            "Body": BytesIO(body_content),
        }

        client = S3Client()
        result = client.read_json("my-bucket", "data/test.json")

        assert result == {"players": [1, 2, 3]}

    @patch("fpl_lib.clients.s3.boto3")
    def test_object_exists_true(self, mock_boto3: MagicMock) -> None:
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        mock_client.head_object.return_value = {}

        client = S3Client()
        assert client.object_exists("my-bucket", "data/test.json") is True

    @patch("fpl_lib.clients.s3.boto3")
    def test_object_exists_false(self, mock_boto3: MagicMock) -> None:
        from botocore.exceptions import ClientError

        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        mock_client.exceptions.ClientError = ClientError
        mock_client.head_object.side_effect = ClientError(
            {"Error": {"Code": "404", "Message": "Not Found"}}, "HeadObject"
        )

        client = S3Client()
        assert client.object_exists("my-bucket", "data/missing.json") is False

    @patch("fpl_lib.clients.s3.boto3")
    def test_list_objects(self, mock_boto3: MagicMock) -> None:
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client

        paginator = MagicMock()
        mock_client.get_paginator.return_value = paginator
        paginator.paginate.return_value = [
            {"Contents": [{"Key": "data/a.json"}, {"Key": "data/b.json"}]},
        ]

        client = S3Client()
        keys = client.list_objects("my-bucket", "data/")

        assert keys == ["data/a.json", "data/b.json"]
