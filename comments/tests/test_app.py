import base64
import json
from typing import Any

import pytest
from conftest import SLUG, api_event, claims

import app
import store

READER = claims(sub="reader-1", name="Ada Lovelace")
MODERATOR = claims(sub="moderator-1", name="Grace Hopper", groups="[moderators]")


def call(event: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    response = app.handler(event, None)
    return response["statusCode"], json.loads(response["body"])


def post(
    text: str,
    who: dict[str, Any] = READER,
    parent_id: str | None = None,
    slug: str = SLUG,
) -> tuple[int, dict[str, Any]]:
    body: dict[str, Any] = {"text": text}
    if parent_id is not None:
        body["parent_id"] = parent_id
    return call(api_event(app.ROUTE_POST_COMMENT, slug=slug, body=body, claims=who))


def patch(comment_id: str, status: str, who: dict[str, Any] = MODERATOR):
    event = api_event(
        app.ROUTE_PATCH_COMMENT,
        body={"status": status},
        claims=who,
        comment_id=comment_id,
    )
    return call(event)


def test_get_returns_only_approved_with_query_not_scan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, approved = post("Approved comment", who=MODERATOR)
    monkeypatch.setenv("REQUIRE_APPROVAL", "true")
    _, pending = post("Pending comment")
    assert pending["status"] == "pending"
    operations: list[str] = []

    def record(**kwargs: Any) -> None:
        operations.append(kwargs["model"].name)

    client = store.get_table().meta.client
    client.meta.events.register("before-call.dynamodb", record)
    status, payload = call(api_event(app.ROUTE_GET_COMMENTS))
    assert status == 200
    assert [comment["id"] for comment in payload["comments"]] == [approved["id"]]
    assert set(payload["comments"][0]) == {
        "id",
        "parent_id",
        "author_name",
        "text",
        "created_at",
    }
    assert "Query" in operations
    assert "Scan" not in operations


def test_get_rejects_bad_slug() -> None:
    status, payload = call(api_event(app.ROUTE_GET_COMMENTS, slug="user#reader-1"))
    assert status == 400
    assert "message" in payload


def test_unknown_route_is_404() -> None:
    status, _ = call(api_event("DELETE /posts/{slug}/comments"))
    assert status == 404


def test_post_requires_claims() -> None:
    event = api_event(app.ROUTE_POST_COMMENT, body={"text": "hello"})
    assert call(event)[0] == 401


def test_post_rejects_empty_and_over_length_text() -> None:
    assert post("   ")[0] == 400
    assert post("x" * 2001)[0] == 400
    status, created = post("x" * 2000)
    assert status == 201
    assert created["status"] == "approved"


def test_post_rejects_invalid_json_body() -> None:
    event = api_event(app.ROUTE_POST_COMMENT, claims=READER)
    event["body"] = "{not json"
    assert call(event)[0] == 400


def test_post_accepts_base64_body() -> None:
    event = api_event(app.ROUTE_POST_COMMENT, claims=READER)
    event["body"] = base64.b64encode(b'{"text": "encoded"}').decode()
    event["isBase64Encoded"] = True
    status, created = call(event)
    assert status == 201
    assert created["text"] == "encoded"


def test_reply_to_reply_is_rejected() -> None:
    _, parent = post("Parent", who=MODERATOR)
    status, reply = post("Reply", parent_id=parent["id"])
    assert status == 201
    assert reply["parent_id"] == parent["id"]
    assert post("Nested", parent_id=reply["id"])[0] == 400


def test_parent_from_another_slug_is_not_found() -> None:
    _, parent = post("Elsewhere", who=MODERATOR, slug="another-post")
    assert post("Reply", parent_id=parent["id"])[0] == 404


def test_invalid_parent_id_is_rejected() -> None:
    assert post("Reply", parent_id="not-an-id")[0] == 400


def test_reply_to_pending_parent_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REQUIRE_APPROVAL", "true")
    _, parent = post("Waiting", who=claims(sub="reader-2"))
    assert parent["status"] == "pending"
    assert post("Reply", parent_id=parent["id"], who=MODERATOR)[0] == 400


def test_keyword_match_is_pending(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MODERATION_KEYWORDS", "casino, spam")
    status, created = post("Best CaSiNo in town")
    assert status == 201
    assert created["status"] == "pending"
    assert post("A plain remark")[1]["status"] == "approved"


def test_require_approval_is_pending(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REQUIRE_APPROVAL", "true")
    assert post("Hello")[1]["status"] == "pending"


def test_moderator_bypasses_approval_and_keywords(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("REQUIRE_APPROVAL", "true")
    monkeypatch.setenv("MODERATION_KEYWORDS", "casino")
    assert post("Casino talk", who=MODERATOR)[1]["status"] == "approved"


def test_write_limit_window(monkeypatch: pytest.MonkeyPatch, table: Any) -> None:
    monkeypatch.setattr(app, "now_seconds", lambda: 6000.0)
    for index in range(5):
        assert post(f"Comment {index}")[0] == 201
    assert post("One too many")[0] == 429
    counter = table.get_item(Key={"pk": "user#reader-1", "sk": "limit#10"})["Item"]
    assert counter["count"] == 5
    assert "expires_at" in counter
    assert counter["expires_at"] > 6000
    monkeypatch.setattr(app, "now_seconds", lambda: 6600.0)
    assert post("New window")[0] == 201


def test_moderator_is_not_exempt_from_write_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WRITE_LIMIT_COUNT", "1")
    assert post("First", who=MODERATOR)[0] == 201
    assert post("Second", who=MODERATOR)[0] == 429


def test_stored_item_has_no_email(table: Any) -> None:
    who = claims(sub="reader-3", name="ada@example.com")
    who["email"] = "ada@example.com"
    status, created = post("Hello", who=who)
    assert status == 201
    assert created["author_name"] == "Reader"
    assert "author_sub" not in created
    items = table.query(
        KeyConditionExpression="pk = :pk",
        ExpressionAttributeValues={":pk": SLUG},
    )["Items"]
    assert len(items) == 1
    item = items[0]
    assert set(item) == {
        "pk",
        "sk",
        "comment_id",
        "slug",
        "status",
        "author_sub",
        "author_name",
        "text",
        "created_at",
    }
    for key, value in item.items():
        assert "@" not in key
        assert "@" not in str(value)


def test_patch_requires_moderator() -> None:
    _, created = post("Hello")
    assert patch(created["id"], "hidden", who=READER)[0] == 403


@pytest.mark.parametrize("groups", ["[moderators]", ["moderators"]])
def test_patch_by_moderator(groups: str | list[str]) -> None:
    _, created = post("Hello")
    who = claims(sub="moderator-2", groups=groups)
    status, updated = patch(created["id"], "hidden", who=who)
    assert status == 200
    assert updated["status"] == "hidden"
    assert updated["id"] == created["id"]
    _, listed = call(api_event(app.ROUTE_GET_COMMENTS))
    assert listed["comments"] == []


def test_patch_rejects_invalid_status() -> None:
    _, created = post("Hello")
    assert patch(created["id"], "deleted")[0] == 400


def test_patch_unknown_comment_is_not_found() -> None:
    assert patch("1767225600123-0123456789ab", "approved")[0] == 404


def test_patch_invalid_comment_id_is_rejected() -> None:
    assert patch("bogus", "approved")[0] == 400


def test_moderation_requires_moderator() -> None:
    event = api_event(app.ROUTE_GET_MODERATION, claims=READER)
    assert call(event)[0] == 403
    assert call(api_event(app.ROUTE_GET_MODERATION))[0] == 401


def test_moderation_lists_every_status(monkeypatch: pytest.MonkeyPatch) -> None:
    _, approved = post("Approved", who=MODERATOR)
    _, hidden = post("To hide", who=claims(sub="reader-4"))
    patch(hidden["id"], "hidden")
    monkeypatch.setenv("REQUIRE_APPROVAL", "true")
    _, pending = post("Pending", who=claims(sub="reader-5"))
    status, payload = call(api_event(app.ROUTE_GET_MODERATION, claims=MODERATOR))
    assert status == 200
    statuses = {comment["id"]: comment["status"] for comment in payload["comments"]}
    assert statuses == {
        approved["id"]: "approved",
        hidden["id"]: "hidden",
        pending["id"]: "pending",
    }
    assert all("author_sub" not in comment for comment in payload["comments"])
