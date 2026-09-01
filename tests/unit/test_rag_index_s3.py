"""src/logic/rag_index.py contra S3 mockeado (moto): resuelve CURRENT, descarga, abre."""
from __future__ import annotations

import json

import boto3
import lancedb
import pytest
from moto import mock_aws

from src.logic import rag_index as ri

BUCKET = "aeronova-lake-test"
VERSION = "v=20260828T120000Z"
PREFIX = f"gold/rag/{ri.TABLE_NAME}.lance/{VERSION}"


@pytest.fixture
def indice_en_s3(tmp_path, monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("S3_BUCKET_LAKE", BUCKET)
    monkeypatch.setenv("RAG_LOCAL_DIR", str(tmp_path / "local"))
    ri.reset_cache()
    monkeypatch.setattr(ri, "get_settings", lambda: type("C", (), {
        "aws_region": "us-east-1", "s3_bucket_lake": BUCKET,
        "rag_current_pointer": "gold/rag/CURRENT", "rag_contract_version_min": "1.0.0",
    })())

    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket=BUCKET)

        # construir un indice local y subirlo entero al prefijo de la version
        build_dir = tmp_path / "build"
        db = lancedb.connect(str(build_dir))
        db.create_table(ri.TABLE_NAME, data=[{
            "vector": [0.1] * 8, "doc_id": "POL-MAS-001", "titulo": "Mascotas",
            "categoria": "MASCOTAS", "vigencia_desde": "2025-01-01",
            "fragmento": "Se permite una mascota en cabina.", "chunk_index": 0,
        }])
        (build_dir / "_manifest.json").write_text(json.dumps({
            "version": VERSION, "contract_version": "1.0.0", "counts": {"chunks": 1},
        }))
        for p in sorted(build_dir.rglob("*")):
            if p.is_file():
                s3.upload_file(str(p), BUCKET, f"{PREFIX}/{p.relative_to(build_dir).as_posix()}")
        s3.put_object(Bucket=BUCKET, Key="gold/rag/CURRENT", Body=PREFIX.encode())
        yield s3
    ri.reset_cache()


def test_read_current(indice_en_s3):
    assert ri.read_current() == PREFIX


def test_load_index_descarga_y_abre(indice_en_s3):
    idx = ri.load_index()
    assert idx.version == VERSION
    assert idx.manifest["contract_version"] == "1.0.0"
    assert idx.table.count_rows() == 1
    # get_index() devuelve la cache sin recargar
    assert ri.get_index() is idx


def test_load_index_sin_objetos_es_unavailable(indice_en_s3):
    indice_en_s3.put_object(Bucket=BUCKET, Key="gold/rag/CURRENT",
                            Body=b"gold/rag/politicas.lance/v=inexistente")
    ri.reset_cache()
    with pytest.raises(ri.RagUnavailable):
        ri.load_index()


def test_read_current_ausente_es_unavailable(indice_en_s3):
    indice_en_s3.delete_object(Bucket=BUCKET, Key="gold/rag/CURRENT")
    with pytest.raises(ri.RagUnavailable):
        ri.read_current()


def test_refresh_detecta_cambio_de_current(indice_en_s3, tmp_path):
    ri.load_index()
    assert ri.refresh_if_changed() is False  # sin cambio
    # apuntar CURRENT a una version nueva identica en contenido
    v2 = "v=20260828T130000Z"
    for obj in indice_en_s3.list_objects_v2(Bucket=BUCKET, Prefix=PREFIX + "/")["Contents"]:
        rel = obj["Key"].split(PREFIX + "/", 1)[1]
        indice_en_s3.copy_object(
            Bucket=BUCKET, Key=f"gold/rag/{ri.TABLE_NAME}.lance/{v2}/{rel}",
            CopySource={"Bucket": BUCKET, "Key": obj["Key"]},
        )
    manifest = json.loads(indice_en_s3.get_object(
        Bucket=BUCKET, Key=f"gold/rag/{ri.TABLE_NAME}.lance/{v2}/_manifest.json")["Body"].read())
    manifest["version"] = v2
    indice_en_s3.put_object(Bucket=BUCKET, Key=f"gold/rag/{ri.TABLE_NAME}.lance/{v2}/_manifest.json",
                            Body=json.dumps(manifest).encode())
    indice_en_s3.put_object(Bucket=BUCKET, Key="gold/rag/CURRENT",
                            Body=f"gold/rag/{ri.TABLE_NAME}.lance/{v2}".encode())
    assert ri.refresh_if_changed() is True
    assert ri.get_index().version == v2
