"""DynamoDB access for comments and per-user write counters.

Comments live in the partition of their post slug (``pk = slug``) with a sort
key rebuilt from the comment id. Write counters live in ``pk = user#<sub>``,
which a slug can never match, and expire through the ``expires_at`` TTL.
"""

import functools
import os
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

from rules import sort_key_for


@functools.cache
def get_table() -> Any:
    """Return the comments table resource named by env ``TABLE_NAME``."""
    return boto3.resource("dynamodb").Table(os.environ["TABLE_NAME"])


def _is_conditional_failure(error: ClientError) -> bool:
    code = error.response.get("Error", {}).get("Code")
    return code == "ConditionalCheckFailedException"


def list_comments(slug: str, statuses: tuple[str, ...]) -> list[dict[str, Any]]:
    """Query every comment of a post, oldest first, keeping given statuses."""
    table = get_table()
    items: list[dict[str, Any]] = []
    kwargs: dict[str, Any] = {"KeyConditionExpression": Key("pk").eq(slug)}
    while True:
        page = table.query(**kwargs)
        items.extend(page.get("Items", []))
        last_key = page.get("LastEvaluatedKey")
        if not last_key:
            break
        kwargs["ExclusiveStartKey"] = last_key
    return [item for item in items if item.get("status") in statuses]


def get_comment(slug: str, comment_id: str) -> dict[str, Any] | None:
    key = {"pk": slug, "sk": sort_key_for(comment_id)}
    return get_table().get_item(Key=key).get("Item")


def put_comment(item: dict[str, Any]) -> None:
    get_table().put_item(
        Item=item,
        ConditionExpression="attribute_not_exists(pk)",
    )


def set_status(slug: str, comment_id: str, status: str) -> dict[str, Any] | None:
    """Change the status of an existing comment; None when it does not exist."""
    try:
        response = get_table().update_item(
            Key={"pk": slug, "sk": sort_key_for(comment_id)},
            UpdateExpression="SET #status = :status",
            ConditionExpression="attribute_exists(pk)",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={":status": status},
            ReturnValues="ALL_NEW",
        )
    except ClientError as error:
        if _is_conditional_failure(error):
            return None
        raise
    return response.get("Attributes")


def consume_write_quota(sub: str, count: int, window: int, now: float) -> bool:
    """Atomically count one write in the current fixed window.

    Returns False when the user already reached ``count`` writes in the window.
    """
    bucket = int(now) // window
    try:
        get_table().update_item(
            Key={"pk": f"user#{sub}", "sk": f"limit#{bucket}"},
            UpdateExpression="ADD #count :one SET expires_at = :expires_at",
            ConditionExpression="attribute_not_exists(#count) OR #count < :limit",
            ExpressionAttributeNames={"#count": "count"},
            ExpressionAttributeValues={
                ":one": 1,
                ":limit": count,
                ":expires_at": (bucket + 2) * window,
            },
        )
    except ClientError as error:
        if _is_conditional_failure(error):
            return False
        raise
    return True
