from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from urllib.request import Request, urlopen

from .config import BASE, ESPN_SUMMARY_URL_TEMPLATE, ESPN_TEAM_SCHEDULE_URL, SUMMARY_CACHE, TEAM_CONFIG
from .metrics import compute_bench_stats, compute_player_advanced_rows, compute_team_advanced_metrics, parse_int, parse_made_attempted, parse_minutes_text, parse_percentage_from_int_text, safe_div, stat_value_map
from .narrative import build_fallback_reasons, build_fallback_risks, build_game_narrative, build_one_liner, build_player_takeaways, build_reason_items, build_system_evaluation, detect_narrative_signals
from .trends import build_core_player_trends, build_recent_trend, build_trend_takeaway

def get_scoreboard() -> dict[str, Any]:
    return BASE["get_scoreboard"]()

def get_standings() -> dict[str, Any]:
    return BASE["get_standings"]()

def get_boxscore(game_id: str) -> dict[str, Any]:
    return BASE["get_boxscore"](game_id)

def build_daily_report(scoreboard_data: dict[str, Any], standings_data: dict[str, Any]) -> dict[str, Any]:
    return BASE["build_daily_report"](scoreboard_data, standings_data)

def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    BASE["write_csv"](path, rows)

def fetch_json(url: str) -> dict[str, Any]:
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=45) as response:
        return json.loads(response.read().decode("utf-8", errors="ignore"))

def get_celtics_schedule() -> dict[str, Any]:
    return fetch_json(ESPN_TEAM_SCHEDULE_URL)

def get_espn_summary(event_id: str) -> dict[str, Any]:
    if event_id not in SUMMARY_CACHE:
        SUMMARY_CACHE[event_id] = fetch_json(ESPN_SUMMARY_URL_TEMPLATE.format(event_id=event_id))
    return SUMMARY_CACHE[event_id]

def get_last_completed_event_id() -> str:
    schedule = get_celtics_schedule()
    now = datetime.now(timezone.utc)
    last_event: dict[str, Any] | None = None

    for event in schedule.get("events", []):
        competition = event.get("competitions", [{}])[0]
        event_date_text = competition.get("date") or event.get("date")
        if not event_date_text:
            continue
        event_date = datetime.fromisoformat(event_date_text.replace("Z", "+00:00"))
        completed = competition.get("status", {}).get("type", {}).get("completed", False)
        if completed and event_date <= now:
            last_event = event

    if not last_event:
        raise ValueError("未找到上一场已结束的 Celtics 比赛")

    return last_event["id"]

def get_completed_celtics_events() -> list[dict[str, Any]]:
    schedule = get_celtics_schedule()
    now = datetime.now(timezone.utc)
    completed_events: list[dict[str, Any]] = []

    for event in schedule.get("events", []):
        competition = event.get("competitions", [{}])[0]
        event_date_text = competition.get("date") or event.get("date")
        if not event_date_text:
            continue
        event_date = datetime.fromisoformat(event_date_text.replace("Z", "+00:00"))
        completed = competition.get("status", {}).get("type", {}).get("completed", False)
        if not completed or event_date > now:
            continue
        competitors = competition.get("competitors", [])
        opponent = ""
        for item in competitors:
            team = item.get("team", {})
            if team.get("abbreviation") != TEAM_CONFIG["BOS"]["tricode"]:
                opponent = team.get("abbreviation", "")
        completed_events.append(
            {
                "event_id": str(event.get("id", "")),
                "game_date": event_date_text.split("T")[0],
                "opponent": opponent,
                "event_date": event_date,
            }
        )

    completed_events.sort(key=lambda item: item["event_date"])
    return completed_events

def get_completed_celtics_event_ids() -> list[str]:
    return [item["event_id"] for item in get_completed_celtics_events()]

def convert_espn_team_to_nba_shape(team_entry: dict[str, Any]) -> dict[str, Any]:
    stats = stat_value_map(team_entry.get("statistics", []))
    fgm, fga = parse_made_attempted(stats.get("fieldGoalsMade-fieldGoalsAttempted", "0-0"))
    tpm, tpa = parse_made_attempted(stats.get("threePointFieldGoalsMade-threePointFieldGoalsAttempted", "0-0"))
    ftm, fta = parse_made_attempted(stats.get("freeThrowsMade-freeThrowsAttempted", "0-0"))
    turnovers = parse_int(stats.get("totalTurnovers", stats.get("turnovers", "0")))

    return {
        "teamId": team_entry.get("team", {}).get("id", ""),
        "teamTricode": team_entry.get("team", {}).get("abbreviation", ""),
        "teamCity": team_entry.get("team", {}).get("location", ""),
        "teamName": team_entry.get("team", {}).get("name", ""),
        "logo": team_entry.get("team", {}).get("logo", ""),
        "score": parse_int(stats.get("points", "0")) if "points" in stats else fgm * 2 + tpm + ftm,
        "statistics": {
            "points": parse_int(stats.get("points", "0")) if "points" in stats else fgm * 2 + tpm + ftm,
            "fieldGoalsMade": fgm,
            "fieldGoalsAttempted": fga,
            "fieldGoalsPercentage": parse_percentage_from_int_text(stats.get("fieldGoalPct", "0")),
            "threePointersMade": tpm,
            "threePointersAttempted": tpa,
            "threePointersPercentage": parse_percentage_from_int_text(stats.get("threePointFieldGoalPct", "0")),
            "freeThrowsMade": ftm,
            "freeThrowsAttempted": fta,
            "freeThrowsPercentage": parse_percentage_from_int_text(stats.get("freeThrowPct", "0")),
            "reboundsTotal": parse_int(stats.get("totalRebounds", "0")),
            "reboundsOffensive": parse_int(stats.get("offensiveRebounds", "0")),
            "reboundsDefensive": parse_int(stats.get("defensiveRebounds", "0")),
            "assists": parse_int(stats.get("assists", "0")),
            "steals": parse_int(stats.get("steals", "0")),
            "blocks": parse_int(stats.get("blocks", "0")),
            "turnovers": turnovers,
            "foulsPersonal": parse_int(stats.get("fouls", "0")),
        },
    }

def convert_espn_players_to_nba_shape(player_section: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for stat_group in player_section.get("statistics", []):
        keys = stat_group.get("keys", [])
        for athlete in stat_group.get("athletes", []):
            raw_stats = athlete.get("stats", [])
            stat_map = {key: raw_stats[index] for index, key in enumerate(keys) if index < len(raw_stats)}
            fgm, fga = parse_made_attempted(stat_map.get("fieldGoalsMade-fieldGoalsAttempted", "0-0"))
            tpm, tpa = parse_made_attempted(stat_map.get("threePointFieldGoalsMade-threePointFieldGoalsAttempted", "0-0"))
            ftm, fta = parse_made_attempted(stat_map.get("freeThrowsMade-freeThrowsAttempted", "0-0"))
            athlete_info = athlete.get("athlete", {})
            rows.append(
                {
                    "personId": athlete_info.get("id", ""),
                    "jerseyNum": athlete_info.get("jersey", ""),
                    "position": athlete_info.get("position", {}).get("abbreviation", ""),
                    "starter": "1" if athlete.get("starter") else "0",
                    "played": "0" if athlete.get("didNotPlay") else "1",
                    "status": "INACTIVE" if athlete.get("didNotPlay") else "ACTIVE",
                    "name": athlete_info.get("displayName", ""),
                    "statistics": {
                        "minutes": parse_minutes_text(stat_map.get("minutes", "0")),
                        "points": parse_int(stat_map.get("points", "0")),
                        "fieldGoalsMade": fgm,
                        "fieldGoalsAttempted": fga,
                        "fieldGoalsPercentage": safe_div(fgm, fga),
                        "threePointersMade": tpm,
                        "threePointersAttempted": tpa,
                        "threePointersPercentage": safe_div(tpm, tpa),
                        "freeThrowsMade": ftm,
                        "freeThrowsAttempted": fta,
                        "freeThrowsPercentage": safe_div(ftm, fta),
                        "reboundsTotal": parse_int(stat_map.get("rebounds", "0")),
                        "reboundsOffensive": parse_int(stat_map.get("offensiveRebounds", "0")),
                        "reboundsDefensive": parse_int(stat_map.get("defensiveRebounds", "0")),
                        "assists": parse_int(stat_map.get("assists", "0")),
                        "turnovers": parse_int(stat_map.get("turnovers", "0")),
                        "steals": parse_int(stat_map.get("steals", "0")),
                        "blocks": parse_int(stat_map.get("blocks", "0")),
                        "foulsPersonal": parse_int(stat_map.get("fouls", "0")),
                        "plusMinusPoints": parse_int(stat_map.get("plusMinus", "0").replace("+", "")),
                    },
                }
            )
    return rows

def assemble_analysis(summary_payload: dict[str, Any], include_trends: bool = True) -> dict[str, Any]:
    system_notes = build_system_evaluation(summary_payload)
    reason_items, risk_items = build_reason_items(
        summary_payload["celtics_metrics"],
        summary_payload["opponent_metrics"],
        summary_payload["opponent"],
        summary_payload["result"],
        summary_payload["team_assists"],
        summary_payload["bench"]["bench_points"],
    )
    fallback_reasons = build_fallback_reasons(summary_payload)
    existing_reason_texts = {item["text"] for item in reason_items}
    for fallback in fallback_reasons:
        if fallback["text"] not in existing_reason_texts:
            reason_items.append(fallback)
            existing_reason_texts.add(fallback["text"])
        if len(existing_reason_texts) >= 3:
            break
    fallback_risks = build_fallback_risks(summary_payload)
    existing_risk_texts = {item["text"] for item in risk_items}
    for fallback in fallback_risks:
        if fallback["text"] not in existing_risk_texts:
            risk_items.append(fallback)
            existing_risk_texts.add(fallback["text"])
        if len(existing_risk_texts) >= 2:
            break

    current_event_id = str(summary_payload.get("game_id", ""))
    trend_5_games = build_recent_trend(current_event_id) if include_trends else {"games": 0, "samples": []}
    trend_takeaway = (
        build_trend_takeaway(summary_payload["celtics_metrics"], trend_5_games, summary_payload["result"])
        if include_trends
        else ""
    )
    player_trends, player_profiles, player_trend_takeaways = (
        build_core_player_trends(summary_payload["player_advanced"], current_event_id)
        if include_trends
        else ([], [], [])
    )
    trend_ts_map = {item["player_name"]: item.get("ts_pct_avg", 0.0) for item in player_trends}
    for row in summary_payload["player_advanced"]:
        if row["player_name"] in trend_ts_map:
            row["trend_ts"] = trend_ts_map[row["player_name"]]
    player_takeaways = build_player_takeaways(summary_payload["player_advanced"])
    top_reason = reason_items[0]["text"] if reason_items else "整体回合质量决定了比赛走势。"
    top_risk = risk_items[0]["text"] if risk_items else "防守细节仍有提升空间。"
    reasons = [item["text"] for item in sorted(reason_items, key=lambda row: row["score"], reverse=True)[:3]]
    risks = [item["text"] for item in sorted(risk_items, key=lambda row: row["score"], reverse=True)[:2]]
    analysis_for_narrative = {
        **summary_payload,
        "player_trends": player_trends,
        "player_takeaways": player_takeaways,
        "reasons": reasons,
        "risks": risks,
    }
    narrative_signals = detect_narrative_signals(analysis_for_narrative)

    return {
        **summary_payload,
        "core_metrics": {
            "possessions": summary_payload["celtics_metrics"]["possessions"],
            "off_rating": summary_payload["celtics_metrics"]["off_rating"],
            "def_rating": summary_payload["celtics_metrics"]["def_rating"],
            "net_rating": summary_payload["celtics_metrics"]["net_rating"],
            "efg_pct": summary_payload["celtics_metrics"]["efg_pct"],
            "ts_pct": summary_payload["celtics_metrics"]["ts_pct"],
            "three_pa_rate": summary_payload["celtics_metrics"]["three_pa_rate"],
            "tov_pct": summary_payload["celtics_metrics"]["tov_pct"],
            "oreb_pct": summary_payload["celtics_metrics"]["oreb_pct"],
            "opp_efg_pct": summary_payload["celtics_metrics"]["opp_efg_pct"],
        },
        "reason_items": sorted(reason_items, key=lambda row: row["score"], reverse=True),
        "risk_items": sorted(risk_items, key=lambda row: row["score"], reverse=True),
        "reasons": reasons,
        "risks": risks,
        "system_evaluation": system_notes,
        "trend_5_games": trend_5_games,
        "trend_takeaway": trend_takeaway,
        "player_takeaways": player_takeaways,
        "player_trends": player_trends,
        "player_profiles": player_profiles,
        "player_trend_takeaways": player_trend_takeaways,
        "narrative_signals": narrative_signals,
        "game_narrative": build_game_narrative({**analysis_for_narrative, "narrative_signals": narrative_signals}),
        "one_liner": build_one_liner(summary_payload["result"], top_reason, top_risk),
    }

def build_analysis_from_espn_event(event_id: str, team_code: str = "BOS", include_trends: bool = True) -> dict[str, Any]:
    team_config = TEAM_CONFIG[team_code]
    summary = get_espn_summary(event_id)
    header_comp = summary.get("header", {}).get("competitions", [{}])[0]
    competitors = header_comp.get("competitors", [])
    boxscore_teams = summary.get("boxscore", {}).get("teams", [])
    boxscore_players = summary.get("boxscore", {}).get("players", [])

    if len(boxscore_teams) != 2 or len(boxscore_players) != 2:
        raise ValueError("ESPN 单场数据结构不完整")

    home_comp = next(item for item in competitors if item.get("homeAway") == "home")
    away_comp = next(item for item in competitors if item.get("homeAway") == "away")

    team_entries = {}
    for entry in boxscore_teams:
        team_entries[entry.get("team", {}).get("abbreviation", "")] = convert_espn_team_to_nba_shape(entry)
    player_entries = {}
    for entry in boxscore_players:
        player_entries[entry.get("team", {}).get("abbreviation", "")] = convert_espn_players_to_nba_shape(entry)

    celtics_team = team_entries[team_config["tricode"]]
    opponent_tricode = home_comp["team"]["abbreviation"] if away_comp["team"]["abbreviation"] == team_config["tricode"] else away_comp["team"]["abbreviation"]
    opponent_team = team_entries[opponent_tricode]
    celtics_players = player_entries.get(team_config["tricode"], [])
    opponent_players = player_entries.get(opponent_tricode, [])

    celtics_metrics = compute_team_advanced_metrics(celtics_team, opponent_team)
    opponent_metrics = compute_team_advanced_metrics(opponent_team, celtics_team)
    bench = compute_bench_stats(celtics_players)
    opponent_bench = compute_bench_stats(opponent_players)

    team_stats = celtics_team.get("statistics", {})

    game_date = (header_comp.get("date") or "").split("T")[0]
    result = "win"
    for comp in competitors:
        if comp["team"]["abbreviation"] == team_config["tricode"]:
            result = "win" if comp.get("winner") else "loss"

    summary_payload = {
        "team": team_config["name"],
        "team_code": team_code,
        "game_date": game_date,
        "played_today": True,
        "game_id": event_id,
        "game_status_text": header_comp.get("status", {}).get("type", {}).get("shortDetail", "Final"),
        "result": result,
        "opponent": opponent_tricode,
        "opponent_name": opponent_team.get("teamCity", "") + " " + opponent_team.get("teamName", ""),
        "team_score": celtics_team.get("score", 0),
        "opponent_score": opponent_team.get("score", 0),
        "logo_url": celtics_team.get("logo", "") or BASE["get_nba_logo_url"](team_config["team_id"]),
        "opponent_logo_url": opponent_team.get("logo", ""),
        "celtics_metrics": celtics_metrics,
        "opponent_metrics": opponent_metrics,
        "team_assists": team_stats.get("assists", 0),
        "team_rebounds": team_stats.get("reboundsTotal", 0),
        "bench": bench,
        "opponent_bench": opponent_bench,
        "player_advanced": compute_player_advanced_rows(celtics_players),
    }
    return {
        **assemble_analysis(summary_payload, include_trends=include_trends),
        "event_id": str(event_id),
        "source_mode": "espn_summary",
    }

def get_celtics_game(report: dict[str, Any], tricode: str) -> dict[str, Any] | None:
    for game in report["games"]:
        if game["home_team"] == tricode or game["away_team"] == tricode:
            return game
    return None

def get_team_players(boxscore_game: dict[str, Any], tricode: str) -> list[dict[str, Any]]:
    for team_key in ("homeTeam", "awayTeam"):
        team = boxscore_game.get(team_key, {})
        if team.get("teamTricode") == tricode:
            return team.get("players", [])
    return []

def get_team_block(boxscore_game: dict[str, Any], tricode: str) -> dict[str, Any]:
    for team_key in ("homeTeam", "awayTeam"):
        team = boxscore_game.get(team_key, {})
        if team.get("teamTricode") == tricode:
            return team
    return {}

def analyze_celtics_game(report: dict[str, Any], team_code: str = "BOS") -> dict[str, Any]:
    team_config = TEAM_CONFIG[team_code]
    game = get_celtics_game(report, team_config["tricode"])

    if not game:
        return {
            "team": team_config["name"],
            "team_code": team_code,
            "game_date": report["game_date"],
            "played_today": False,
            "message": "今日 Boston Celtics 无比赛，未生成赛后诊断。",
        }

    boxscore = get_boxscore(game["game_id"]).get("game", {})
    celtics_team = get_team_block(boxscore, team_config["tricode"])
    opponent_team = boxscore.get("awayTeam", {}) if celtics_team == boxscore.get("homeTeam", {}) else boxscore.get("homeTeam", {})
    celtics_players = get_team_players(boxscore, team_config["tricode"])
    opponent_players = get_team_players(boxscore, opponent_team.get("teamTricode", ""))

    celtics_metrics = compute_team_advanced_metrics(celtics_team, opponent_team)
    opponent_metrics = compute_team_advanced_metrics(opponent_team, celtics_team)
    bench = compute_bench_stats(celtics_players)
    opponent_bench = compute_bench_stats(opponent_players)

    team_stats = celtics_team.get("statistics", {})

    summary = {
        "team": team_config["name"],
        "team_code": team_code,
        "game_date": report["game_date"],
        "played_today": True,
        "game_id": game["game_id"],
        "game_status_text": game["game_status_text"],
        "result": "win" if game["winner"] == team_config["tricode"] else "loss",
        "opponent": opponent_team.get("teamTricode", ""),
        "opponent_name": f"{opponent_team.get('teamCity', '')} {opponent_team.get('teamName', '')}".strip(),
        "team_score": celtics_team.get("score", 0),
        "opponent_score": opponent_team.get("score", 0),
        "logo_url": BASE["get_nba_logo_url"](team_config["team_id"]),
        "opponent_logo_url": BASE["get_nba_logo_url"](opponent_team.get("teamId")),
        "celtics_metrics": celtics_metrics,
        "opponent_metrics": opponent_metrics,
        "team_assists": team_stats.get("assists", 0),
        "team_rebounds": team_stats.get("reboundsTotal", 0),
        "bench": bench,
        "opponent_bench": opponent_bench,
        "player_advanced": compute_player_advanced_rows(celtics_players),
    }
    return {
        **assemble_analysis(summary, include_trends=True),
        "event_id": str(summary.get("game_id", "")),
        "source_mode": "daily_report",
    }
