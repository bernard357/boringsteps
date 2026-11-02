import rules


def test_comment_id_and_sort_key_round_trip() -> None:
    comment_id = rules.new_comment_id(1_767_225_600_123)
    assert rules.is_valid_comment_id(comment_id)
    assert rules.created_at_for(comment_id) == "2026-01-01T00:00:00.123Z"
    assert rules.sort_key_for(comment_id) == f"2026-01-01T00:00:00.123Z#{comment_id}"


def test_comment_ids_sort_by_time() -> None:
    earlier = rules.sort_key_for(rules.new_comment_id(1_000_000_000_000))
    later = rules.sort_key_for(rules.new_comment_id(1_000_000_000_001))
    assert earlier < later


def test_invalid_ids_and_slugs() -> None:
    assert not rules.is_valid_comment_id("123-abc")
    assert not rules.is_valid_comment_id(None)
    assert rules.is_valid_slug("duckdb-vectors")
    assert not rules.is_valid_slug("user#abc")
    assert not rules.is_valid_slug("-leading")
    assert not rules.is_valid_slug("Upper")


def test_parse_keywords() -> None:
    assert rules.parse_keywords("") == []
    assert rules.parse_keywords(None) == []
    assert rules.parse_keywords(" Casino , ,SPAM ") == ["casino", "spam"]


def test_matches_keyword_is_case_insensitive() -> None:
    keywords = rules.parse_keywords("casino")
    assert rules.matches_keyword("Visit the CaSiNo now", keywords)
    assert not rules.matches_keyword("Nothing to see", keywords)
    assert not rules.matches_keyword("anything", [])


def test_validate_text() -> None:
    assert rules.validate_text("  hello  ", 10) == "hello"
    assert rules.validate_text("   ", 10) is None
    assert rules.validate_text("x" * 11, 10) is None
    assert rules.validate_text(42, 10) is None


def test_display_name() -> None:
    assert rules.display_name({"name": "Ada"}) == "Ada"
    assert rules.display_name({"preferred_username": "ada"}) == "ada"
    assert rules.display_name({}) == "Reader"
    assert rules.display_name({"name": "ada@example.com"}) == "Reader"
    assert rules.display_name({"name": "x" * 100}) == "x" * 80


def test_is_moderator_parses_flattened_and_list_groups() -> None:
    assert rules.is_moderator({"cognito:groups": "[moderators]"})
    assert rules.is_moderator({"cognito:groups": "[editors moderators]"})
    assert rules.is_moderator({"cognito:groups": "[editors, moderators]"})
    assert rules.is_moderator({"cognito:groups": ["moderators"]})
    assert not rules.is_moderator({"cognito:groups": "[editors]"})
    assert not rules.is_moderator({})
