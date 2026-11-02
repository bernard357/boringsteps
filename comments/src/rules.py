"""Pure validation and moderation rules for the comments back-end.

The rules are adapted from Artalk (statuses, keyword filter, one reply level,
write limit, moderators) and are free of AWS dependencies so they are easy to
unit-test.
"""

import re
import secrets
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,99}$")
COMMENT_ID_RE = re.compile(r"^\d{13}-[0-9a-f]{12}$")
STATUSES = ("approved", "pending", "hidden")
MODERATORS_GROUP = "moderators"
DEFAULT_NAME = "Reader"
MAX_NAME_LENGTH = 80


def new_comment_id(now_ms: int) -> str:
    """Return a comment id that encodes its creation time in milliseconds."""
    return f"{now_ms:013d}-{secrets.token_hex(6)}"


def created_at_for(comment_id: str) -> str:
    """Return the ISO-8601 UTC timestamp (milliseconds) encoded in an id."""
    epoch_ms = int(comment_id.split("-", 1)[0])
    moment = datetime.fromtimestamp(epoch_ms / 1000, tz=UTC)
    return moment.strftime("%Y-%m-%dT%H:%M:%S.") + f"{epoch_ms % 1000:03d}Z"


def sort_key_for(comment_id: str) -> str:
    """Rebuild the table sort key of a comment from its id alone."""
    return f"{created_at_for(comment_id)}#{comment_id}"


def is_valid_slug(slug: object) -> bool:
    return isinstance(slug, str) and SLUG_RE.fullmatch(slug) is not None


def is_valid_comment_id(comment_id: object) -> bool:
    if not isinstance(comment_id, str):
        return False
    return COMMENT_ID_RE.fullmatch(comment_id) is not None


def validate_text(text: object, max_len: int) -> str | None:
    """Return the stripped text, or None when empty, too long or not a string."""
    if not isinstance(text, str):
        return None
    stripped = text.strip()
    if not stripped or len(stripped) > max_len:
        return None
    return stripped


def parse_keywords(raw: str | None) -> list[str]:
    """Split a comma-separated keyword list into casefolded, non-empty keywords."""
    if not raw:
        return []
    return [word.strip().casefold() for word in raw.split(",") if word.strip()]


def matches_keyword(text: str, keywords: list[str]) -> bool:
    """Case-insensitive substring match of any keyword in the text."""
    folded = text.casefold()
    return any(keyword.casefold() in folded for keyword in keywords if keyword)


def display_name(claims: Mapping[str, Any]) -> str:
    """Pick a public display name from ID-token claims, never an email."""
    for key in ("name", "preferred_username"):
        value = claims.get(key)
        if isinstance(value, str) and value.strip():
            name = value.strip()
            if "@" in name:
                return DEFAULT_NAME
            return name[:MAX_NAME_LENGTH]
    return DEFAULT_NAME


def groups_of(claims: Mapping[str, Any]) -> list[str]:
    """Parse cognito:groups, either a list or the HTTP API flattened string."""
    raw = claims.get("cognito:groups")
    if isinstance(raw, list):
        return [str(group) for group in raw]
    if isinstance(raw, str):
        cleaned = raw.strip().strip("[]")
        return [group for group in re.split(r"[\s,]+", cleaned) if group]
    return []


def is_moderator(claims: Mapping[str, Any]) -> bool:
    return MODERATORS_GROUP in groups_of(claims)
