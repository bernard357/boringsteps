"""Lambda handler for the comments HTTP API (payload format 2.0).

One function serves every route and dispatches on ``event["routeKey"]``:

- ``GET /posts/{slug}/comments``: public, approved comments only.
- ``POST /posts/{slug}/comments``: signed-in readers add a comment or a reply.
- ``PATCH /posts/{slug}/comments/{id}``: moderators change a status.
- ``GET /posts/{slug}/moderation``: moderators list comments of every status.

Logs carry route keys, slugs, ids and outcomes only, never text or identity.
"""

import base64
import json
import logging
import os
import time
from collections.abc import Callable
from typing import Any

import store
from rules import (
    STATUSES,
    created_at_for,
    display_name,
    is_moderator,
    is_valid_comment_id,
    is_valid_slug,
    matches_keyword,
    new_comment_id,
    parse_keywords,
    sort_key_for,
    validate_text,
)

logger = logging.getLogger()
logger.setLevel(logging.INFO)

Event = dict[str, Any]
Response = dict[str, Any]

ROUTE_GET_COMMENTS = "GET /posts/{slug}/comments"
ROUTE_POST_COMMENT = "POST /posts/{slug}/comments"
ROUTE_PATCH_COMMENT = "PATCH /posts/{slug}/comments/{id}"
ROUTE_GET_MODERATION = "GET /posts/{slug}/moderation"


class ApiError(Exception):
    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def now_seconds() -> float:
    """Current epoch time in seconds; patched in tests."""
    return time.time()


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


def _require_approval() -> bool:
    return os.environ.get("REQUIRE_APPROVAL", "false").strip().lower() == "true"


def _response(status_code: int, payload: dict[str, Any]) -> Response:
    return {
        "statusCode": status_code,
        "headers": {"content-type": "application/json"},
        "body": json.dumps(payload),
    }


def _claims(event: Event) -> dict[str, Any] | None:
    authorizer = event.get("requestContext", {}).get("authorizer") or {}
    claims = (authorizer.get("jwt") or {}).get("claims")
    if not claims or not claims.get("sub"):
        return None
    return claims


def _require_claims(event: Event) -> dict[str, Any]:
    claims = _claims(event)
    if claims is None:
        raise ApiError(401, "sign-in required")
    return claims


def _require_moderator(event: Event) -> dict[str, Any]:
    claims = _require_claims(event)
    if not is_moderator(claims):
        raise ApiError(403, "moderators only")
    return claims


def _slug(event: Event) -> str:
    slug = (event.get("pathParameters") or {}).get("slug")
    if not is_valid_slug(slug):
        raise ApiError(400, "invalid slug")
    return slug


def _body(event: Event) -> dict[str, Any]:
    raw = event.get("body") or ""
    try:
        if event.get("isBase64Encoded"):
            raw = base64.b64decode(raw).decode("utf-8")
        body = json.loads(raw) if raw else {}
    except (ValueError, UnicodeDecodeError) as error:
        raise ApiError(400, "invalid JSON body") from error
    if not isinstance(body, dict):
        raise ApiError(400, "invalid JSON body")
    return body


def _public(item: dict[str, Any], with_status: bool = False) -> dict[str, Any]:
    public = {
        "id": item["comment_id"],
        "parent_id": item.get("parent_id"),
        "author_name": item["author_name"],
        "text": item["text"],
        "created_at": item["created_at"],
    }
    if with_status:
        public["status"] = item["status"]
    return public


def get_comments(event: Event) -> Response:
    slug = _slug(event)
    items = store.list_comments(slug, ("approved",))
    logger.info("list slug=%s count=%d", slug, len(items))
    return _response(200, {"comments": [_public(item) for item in items]})


def get_moderation(event: Event) -> Response:
    _require_moderator(event)
    slug = _slug(event)
    items = store.list_comments(slug, STATUSES)
    logger.info("moderation slug=%s count=%d", slug, len(items))
    comments = [_public(item, with_status=True) for item in items]
    return _response(200, {"comments": comments})


def _check_parent(slug: str, parent_id: object) -> str | None:
    if parent_id is None:
        return None
    if not is_valid_comment_id(parent_id):
        raise ApiError(400, "invalid parent_id")
    parent = store.get_comment(slug, parent_id)
    if parent is None:
        raise ApiError(404, "parent comment not found")
    if parent.get("parent_id"):
        raise ApiError(400, "replies are limited to one level")
    if parent.get("status") != "approved":
        raise ApiError(400, "parent comment does not accept replies")
    return parent_id


def post_comment(event: Event) -> Response:
    claims = _require_claims(event)
    slug = _slug(event)
    body = _body(event)
    text = validate_text(body.get("text"), _env_int("MAX_COMMENT_LENGTH", 2000))
    if text is None:
        raise ApiError(400, "text is empty or too long")
    parent_id = _check_parent(slug, body.get("parent_id"))
    moderator = is_moderator(claims)
    now = now_seconds()
    allowed = store.consume_write_quota(
        claims["sub"],
        _env_int("WRITE_LIMIT_COUNT", 5),
        max(1, _env_int("WRITE_LIMIT_WINDOW_SECONDS", 600)),
        now,
    )
    if not allowed:
        logger.info("post slug=%s outcome=rate-limited", slug)
        raise ApiError(429, "too many comments, try again later")
    status = "approved"
    if not moderator:
        keywords = parse_keywords(os.environ.get("MODERATION_KEYWORDS"))
        if _require_approval() or matches_keyword(text, keywords):
            status = "pending"
    comment_id = new_comment_id(int(now * 1000))
    item: dict[str, Any] = {
        "pk": slug,
        "sk": sort_key_for(comment_id),
        "comment_id": comment_id,
        "slug": slug,
        "status": status,
        "author_sub": claims["sub"],
        "author_name": display_name(claims),
        "text": text,
        "created_at": created_at_for(comment_id),
    }
    if parent_id:
        item["parent_id"] = parent_id
    store.put_comment(item)
    logger.info("post slug=%s id=%s status=%s", slug, comment_id, status)
    return _response(201, _public(item, with_status=True))


def patch_comment(event: Event) -> Response:
    _require_moderator(event)
    slug = _slug(event)
    comment_id = (event.get("pathParameters") or {}).get("id")
    if not is_valid_comment_id(comment_id):
        raise ApiError(400, "invalid comment id")
    status = _body(event).get("status")
    if status not in STATUSES:
        raise ApiError(400, "invalid status")
    item = store.set_status(slug, comment_id, status)
    if item is None:
        raise ApiError(404, "comment not found")
    logger.info("patch slug=%s id=%s status=%s", slug, comment_id, status)
    return _response(200, _public(item, with_status=True))


ROUTES: dict[str, Callable[[Event], Response]] = {
    ROUTE_GET_COMMENTS: get_comments,
    ROUTE_POST_COMMENT: post_comment,
    ROUTE_PATCH_COMMENT: patch_comment,
    ROUTE_GET_MODERATION: get_moderation,
}


def handler(event: Event, context: object) -> Response:
    route_key = event.get("routeKey", "")
    route = ROUTES.get(route_key)
    if route is None:
        return _response(404, {"message": "route not found"})
    try:
        return route(event)
    except ApiError as error:
        logger.info("route=%s outcome=%d", route_key, error.status_code)
        return _response(error.status_code, {"message": error.message})
