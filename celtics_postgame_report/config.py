from __future__ import annotations

import runpy
from pathlib import Path
from typing import Any

BASE_SCRIPT_PATH = Path("/Users/shiyan/NBA report")
LAUNCHD_LABEL = "com.shiyan.celtics-report"
DEFAULT_SCHEDULE_HOUR = 15
DEFAULT_SCHEDULE_MINUTE = 0
DEFAULT_OUTPUT_DIR = Path("/Users/shiyan/celtics_reports")
DEFAULT_MARKDOWN_DIR = Path(
    "/Users/shiyan/Library/Mobile Documents/iCloud~md~obsidian/Documents/Obsidian/Celtics Report"
)
TEAM_CONFIG = {
    "BOS": {
        "team_id": "1610612738",
        "name": "Boston Celtics",
        "tricode": "BOS",
    }
}
PLAYER_OFFENSIVE_ROLE_MAP = {
    "Jayson Tatum": {"tier": "primary_core", "archetype": "creator_scorer"},
    "Jaylen Brown": {"tier": "primary_core", "archetype": "scorer"},
    "Derrick White": {"tier": "secondary_core", "archetype": "creator"},
    "Payton Pritchard": {"tier": "secondary_core", "archetype": "bench_finisher"},
    "Neemias Queta": {"tier": "rotation_finisher", "archetype": "rim_finisher"},
    "Luka Garza": {"tier": "rotation_finisher", "archetype": "interior_finisher"},
    "Sam Hauser": {"tier": "rotation_spacer", "archetype": "spacer"},
    "Baylor Scheierman": {"tier": "rotation_spacer", "archetype": "spacer"},
    "Jordan Walsh": {"tier": "rotation_role", "archetype": "defense_role"},
    "Hugo Gonzalez": {"tier": "rotation_role", "archetype": "development_role"},
}
ROLE_PRIORITY = {
    "primary_core": 5,
    "secondary_core": 4,
    "rotation_finisher": 3,
    "rotation_spacer": 2,
    "rotation_role": 1,
}
DEFAULT_ROLE_INFO = {"tier": "rotation_role", "archetype": "unknown_role"}
CORE_TREND_PRIORITY_NAMES = ["Jayson Tatum", "Jaylen Brown", "Derrick White", "Payton Pritchard"]
PLAYER_CONTEXT = {
    "Jayson Tatum": {
        "status": "post_injury",
        "note": "近期刚从跟腱伤势中回归",
    },
    "Kristaps Porzingis": {
        "status": "injury_prone",
        "note": "存在长期伤病隐患",
    },
}
TEAM_CONTEXT = {
    "BOS": {
        "missing_players": ["Porzingis"],
        "note": "内线轮换受损",
    }
}
ESPN_TEAM_SCHEDULE_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/2/schedule?seasontype=2"
ESPN_SUMMARY_URL_TEMPLATE = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event={event_id}"
SUMMARY_CACHE: dict[str, dict[str, Any]] = {}

def load_base_namespace() -> dict[str, Any]:
    return runpy.run_path(str(BASE_SCRIPT_PATH))

BASE = load_base_namespace()
