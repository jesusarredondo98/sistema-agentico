"""pipelines/build_gold_rag.py: podado de versiones antiguas (§2.4). S3 mockeado."""
from __future__ import annotations

import boto3
import pytest
from moto import mock_aws

from pipelines.build_gold_rag import INDEX_PREFIX, prune_old_versions

BUCKET = "aeronova-lake-test"


@pytest.fixture
def s3_con_versiones(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket=BUCKET)
        for v in ["v=20260101T000000Z", "v=20260102T000000Z", "v=20260103T000000Z",
                  "v=20260104T000000Z", "v=20260105T000000Z"]:
            s3.put_object(Bucket=BUCKET, Key=f"{INDEX_PREFIX}/{v}/_manifest.json", Body=b"{}")
            s3.put_object(Bucket=BUCKET, Key=f"{INDEX_PREFIX}/{v}/data.lance", Body=b"x")
        monkeypatch.setattr("pipelines.build_gold_rag.s3", lambda: s3)
        yield s3


def _versiones(s3):
    out = set()
    for page in s3.get_paginator("list_objects_v2").paginate(
        Bucket=BUCKET, Prefix=f"{INDEX_PREFIX}/", Delimiter="/"
    ):
        for cp in page.get("CommonPrefixes", []):
            out.add(cp["Prefix"].rstrip("/").split("/")[-1])
    return out


def test_conserva_las_3_mas_nuevas(s3_con_versiones):
    borradas = prune_old_versions(BUCKET, keep=3)
    assert set(borradas) == {"v=20260101T000000Z", "v=20260102T000000Z"}
    assert _versiones(s3_con_versiones) == {
        "v=20260103T000000Z", "v=20260104T000000Z", "v=20260105T000000Z"
    }


def test_protege_la_version_de_current_aunque_sea_antigua(s3_con_versiones):
    borradas = prune_old_versions(BUCKET, keep=3, protect="v=20260101T000000Z")
    assert "v=20260101T000000Z" not in borradas
    assert "v=20260101T000000Z" in _versiones(s3_con_versiones)


def test_nada_que_podar(s3_con_versiones):
    prune_old_versions(BUCKET, keep=3)
    assert prune_old_versions(BUCKET, keep=3) == []
