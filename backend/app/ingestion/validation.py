"""
Validation stage: rejects malformed raw records before they can reach
normalization or the database. Every rejection is recorded (via the
caller's logger) rather than silently dropped, so data-quality issues
are visible instead of hidden.
"""

from typing import List, Dict, Any, Tuple

REQUIRED_GAME_FIELDS = ["external_id", "game_date", "home_team", "away_team"]


def validate_game_record(record: Dict[str, Any]) -> Tuple[bool, str]:
    """Returns (is_valid, reason). reason is empty when valid."""
    for field in REQUIRED_GAME_FIELDS:
        if record.get(field) in (None, ""):
            return False, f"missing required field: {field}"

    home = record["home_team"]
    away = record["away_team"]
    if not isinstance(home, dict) or not home.get("external_id"):
        return False, "home_team missing external_id"
    if not isinstance(away, dict) or not away.get("external_id"):
        return False, "away_team missing external_id"

    if home.get("external_id") == away.get("external_id"):
        return False, "home_team and away_team are identical"

    return True, ""


def validate_games(records: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Splits records into (valid, rejected). Each rejected entry keeps
    the original record plus a 'reason' key so it's clear why it was
    dropped.
    """
    valid, rejected = [], []
    for record in records:
        is_valid, reason = validate_game_record(record)
        if is_valid:
            valid.append(record)
        else:
            rejected.append({**record, "_rejection_reason": reason})
    return valid, rejected
