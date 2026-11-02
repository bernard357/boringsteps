"""Shared fixtures: a moto DynamoDB table and HTTP API v2 event builders."""

import json
from collections.abc import Iterator
from typing import Any

import boto3
import pytest
from moto import mock_aws

import store

TABLE_NAME = "comments-test"
SLUG = "duckdb-vectors"


@pytest.fixture(autouse=True)
def table(monkeypatch: pytest.MonkeyPatch) -> Iterator[Any]:
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "eu-west-3")
    monkeypatch.setenv("TABLE_NAME", TABLE_NAME)
    for name in (
        "REQUIRE_APPROVAL",
        "MODERATION_KEYWORDS",
        "MAX_COMMENT_LENGTH",
        "WRITE_LIMIT_COUNT",
        "WRITE_LIMIT_WINDOW_SECONDS",
    ):
        monkeypatch.delenv(name, raising=False)
    store.get_table.cache_clear()
    with mock_aws():
        resource = boto3.resource("dynamodb", region_name="eu-west-3")
        created = resource.create_table(
            TableName=TABLE_NAME,
            KeySchema=[
                {"AttributeName": "pk", "KeyType": "HASH"},
                {"AttributeName": "sk", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "pk", "AttributeType": "S"},
                {"AttributeName": "sk", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        yield created
    store.get_table.cache_clear()


def claims(
    sub: str = "user-1",
    name: str | None = "Ada Lovelace",
    groups: str | list[str] | None = None,
) -> dict[str, Any]:
    """Build ID-token claims as the HTTP API JWT authorizer passes them."""
    result: dict[str, Any] = {"sub": sub, "aud": "client", "token_use": "id"}
    if name is not None:
        result["name"] = name
    if groups is not None:
        result["cognito:groups"] = groups
    return result


def api_event(
    route_key: str,
    slug: str = SLUG,
    body: dict[str, Any] | None = None,
    claims: dict[str, Any] | None = None,
    comment_id: str | None = None,
) -> dict[str, Any]:
    """Build an API Gateway HTTP API payload 2.0 event."""
    path_parameters = {"slug": slug}
    if comment_id is not None:
        path_parameters["id"] = comment_id
    request_context: dict[str, Any] = {"http": {"method": route_key.split()[0]}}
    if claims is not None:
        request_context["authorizer"] = {"jwt": {"claims": claims, "scopes": None}}
    event: dict[str, Any] = {
        "version": "2.0",
        "routeKey": route_key,
        "pathParameters": path_parameters,
        "requestContext": request_context,
        "isBase64Encoded": False,
    }
    if body is not None:
        event["body"] = json.dumps(body)
    return event
