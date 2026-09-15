"""
Normalization stage: converts provider-specific raw shapes into the
common shape our database and downstream stages expect. Also handles
deduplication -- if the same external_id shows up twice in one batch,
only the first occurrence survives.
"""

from datetime import datetime, timezone
from typing import List, Dict, Any


def normalize_game_record(record: Dict[str, Any], provider: str) -> Dict[str, Any]:
    return {
        "external_id": record["external_id"],
        "provider": provider,
        "season": record.get("season"),
        "game_date": datetime.fromisoformat(record["game_date"].replace("Z", "+00:00")),
        "home_team": record["home_team"],
        "away_team": record["away_team"],
        "venue_name": record.get("venue_name"),
        "status": record.get("status", "scheduled"),
        "home_score": record.get("home_score"),
        "away_score": record.get("away_score"),
        "ingested_at": datetime.now(timezone.utc),
    }


def normalize_and_dedupe_games(records: List[Dict[str, Any]], provider: str) -> List[Dict[str, Any]]:
    seen_ids = set()
    normalized = []
    for record in records:
        normalized_record = normalize_game_record(record, provider)
        key = normalized_record["external_id"]
        if key in seen_ids:
            continue
        seen_ids.add(key)
        normalized.append(normalized_record)
    return normalized
