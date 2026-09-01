"""src/logic/dynamo.py: acceso de solo lectura a Gold. DynamoDB mockeado (moto), sin red."""
from __future__ import annotations

import boto3
import pytest
from moto import mock_aws

from src.config import get_settings


@pytest.fixture
def dynamo_tables(monkeypatch):
    """Levanta aeronova-flights / aeronova-reservations en DynamoDB mockeado."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    with mock_aws():
        from src.logic import dynamo

        dynamo._resource.cache_clear()
        res = boto3.resource("dynamodb", region_name="us-east-1")
        cfg = get_settings()
        res.create_table(
            TableName=cfg.flights_table,
            KeySchema=[{"AttributeName": "codigo_vuelo", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "codigo_vuelo", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        res.create_table(
            TableName=cfg.reservations_table,
            KeySchema=[{"AttributeName": "pnr", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "pnr", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        res.Table(cfg.flights_table).put_item(Item={"codigo_vuelo": "AN405", "estado": "A_TIEMPO"})
        res.Table(cfg.reservations_table).put_item(Item={"pnr": "ABC123", "estado": "CONFIRMADA"})
        yield
        dynamo._resource.cache_clear()


def test_get_flight_existe(dynamo_tables):
    from src.logic.dynamo import get_flight

    item = get_flight("AN405")
    assert item is not None and item["estado"] == "A_TIEMPO"


def test_get_flight_no_existe(dynamo_tables):
    from src.logic.dynamo import get_flight

    assert get_flight("AN9999") is None


def test_get_reservation_existe(dynamo_tables):
    from src.logic.dynamo import get_reservation

    item = get_reservation("ABC123")
    assert item is not None and item["estado"] == "CONFIRMADA"


def test_get_reservation_no_existe(dynamo_tables):
    from src.logic.dynamo import get_reservation

    assert get_reservation("ZZZZZZ") is None
