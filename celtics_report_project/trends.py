from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .config import DEFAULT_ROLE_INFO
from .metrics import round2, round4
from .roles import build_role_aware_trend_summary, classify_offensive_impact, get_player_role_info, preferred_name_priority, role_priority_value

def get_recent_completed_event_ids(limit: int = 5, through_event_id: str = "") -> list[str]:
    from .fetchers import get_celtics_schedule

    schedule = get_celtics_schedule()
    now = datetime.now(timezone.utc)
    completed_events: list[tuple[datetime, str]] = []

    for event in schedule.get("events", []):
        competition = event.get("competitions", [{}])[0]
        event_date_text = competition.get("date") or event.get("date")
        if not event_date_text:
            continue
        event_date = datetime.fromisoformat(event_date_text.replace("Z", "+00:00"))
        completed = competition.get("status", {}).get("type", {}).get("completed", False)
        if completed and event_date <= now:
            completed_events.append((event_date, event["id"]))

    completed_events.sort(key=lambda item: item[0])
    ids = [event_id for _, event_id in completed_events]
    if through_event_id and through_event_id in ids:
        ids = ids[: ids.index(through_event_id) + 1]
    return ids[-limit:]

def get_recent_completed_event_ids_excluding_current(current_event_id: str, limit: int) -> list[str]:
    ids = get_recent_completed_event_ids(limit=limit + 1, through_event_id=current_event_id)
    return [event_id for event_id in ids if event_id != current_event_id][-limit:]

def get_player_row_by_name(player_rows: list[dict[str, Any]], player_name: str) -> dict[str, Any] | None:
    for row in player_rows:
        if row["player_name"] == player_name:
            return row
    return None

def build_event_analysis_cache(event_ids: list[str]) -> dict[str, dict[str, Any]]:
    from .fetchers import build_analysis_from_espn_event

    cache: dict[str, dict[str, Any]] = {}
    for event_id in event_ids:
        if event_id not in cache:
            cache[event_id] = build_analysis_from_espn_event(event_id, include_trends=False)
    return cache
def compute_player_trend(player_name: str, event_ids: list[str], analysis_cache: dict[str, dict[str, Any]]) -> dict[str, Any]:
    samples: list[dict[str, Any]] = []

    for event_id in event_ids:
        analysis = analysis_cache[event_id]
        row = get_player_row_by_name(analysis.get("player_advanced", []), player_name)
        if not row:
            continue
        samples.append(
            {
                "event_id": event_id,
                "game_date": analysis["game_date"],
                "ts_pct": row["ts_pct"],
                "efg_pct": row["efg_pct"],
                "fga": row["fga"],
                "three_pa_rate": row["three_pa_rate"],
                "points": row["points"],
                "minutes_seconds": row["minutes_seconds"],
            }
        )

    count = len(samples) or 1
    return {
        "player_name": player_name,
        "games": len(samples),
        "ts_pct_avg": round4(sum(item["ts_pct"] for item in samples) / count),
        "efg_pct_avg": round4(sum(item["efg_pct"] for item in samples) / count),
        "fga_avg": round2(sum(item["fga"] for item in samples) / count),
        "three_pa_rate_avg": round4(sum(item["three_pa_rate"] for item in samples) / count),
        "points_avg": round2(sum(item["points"] for item in samples) / count),
        "samples": samples,
    }

def build_player_profile(current_row: dict[str, Any], trend: dict[str, Any], season_baseline: dict[str, Any]) -> dict[str, Any]:
    current_ts = current_row["ts_pct"]
    trend_ts = trend["ts_pct_avg"]
    season_ts = season_baseline["ts_pct_avg"]
    return {
        "player_name": current_row["player_name"],
        "role_tier": current_row.get("role_tier", DEFAULT_ROLE_INFO["tier"]),
        "role_archetype": current_row.get("role_archetype", DEFAULT_ROLE_INFO["archetype"]),
        "current_ts": current_ts,
        "trend_ts": trend_ts,
        "season_ts": season_ts,
        "delta_vs_season": round4(current_ts - season_ts),
        "delta_vs_trend": round4(current_ts - trend_ts),
    }

def build_player_trend_takeaways(player_profiles: list[dict[str, Any]], player_trends: list[dict[str, Any]], current_rows: list[dict[str, Any]]) -> list[str]:
    takeaways: list[str] = []
    trend_map = {item["player_name"]: item for item in player_trends}
    row_map = {item["player_name"]: item for item in current_rows}

    upward_candidates = []
    downward_candidates = []
    volatile_candidates = []

    for profile in player_profiles:
        name = profile["player_name"]
        trend = trend_map.get(name)
        row = row_map.get(name)
        if not trend or not row:
            continue
        role_priority = row.get("role_priority", role_priority_value(profile.get("role_tier", "")))
        season_ts = profile["season_ts"]
        trend_ts = profile["trend_ts"]
        current_ts = profile["current_ts"]
        upward_score = (current_ts - trend_ts) + (trend_ts - season_ts)
        downward_score = (season_ts - trend_ts) + (trend_ts - current_ts)
        volatile_score = abs(current_ts - trend_ts) + abs(trend_ts - season_ts)
        upward_candidates.append((role_priority, upward_score, name))
        downward_candidates.append((role_priority, downward_score, name))
        volatile_candidates.append((role_priority, volatile_score, name))

    upward_candidates.sort(reverse=True)
    downward_candidates.sort(reverse=True)
    volatile_candidates.sort(reverse=True)

    if upward_candidates and upward_candidates[0][1] > 0.02:
        name = upward_candidates[0][2]
        profile = next(item for item in player_profiles if item["player_name"] == name)
        role_info = get_player_role_info(name)
        if role_info["tier"] == "primary_core":
            takeaways.append(f"{name} 本场效率高于最近5场平均，并且近期样本也高于近10场基线，说明核心主线仍在上行。")
        elif role_info["tier"] == "secondary_core":
            takeaways.append(f"{name} 本场输出高于最近样本，作为次核心的辅助火力正在回暖。")
        else:
            takeaways.append(f"{name} 本场终结效率高于最近样本，作为角色球员完成任务的质量在提升。")

    if downward_candidates and downward_candidates[0][1] > 0.02:
        name = downward_candidates[0][2]
        role_info = get_player_role_info(name)
        if role_info["tier"] == "primary_core":
            takeaways.append(f"{name} 本场效率低于最近5场和近10场基线，核心主线的稳定性需要继续观察。")
        elif role_info["tier"] == "secondary_core":
            takeaways.append(f"{name} 本场低于近期和阶段基线，次核心层面的辅助支撑有所走弱。")
        else:
            takeaways.append(f"{name} 本场低于近期基线，角色回合的完成质量有所下滑。")

    if volatile_candidates:
        name = volatile_candidates[0][2]
        if name not in " ".join(takeaways):
            role_info = get_player_role_info(name)
            if role_info["tier"] in {"primary_core", "secondary_core"}:
                takeaways.append(f"{name} 的本场表现与近期均值差异较大，属于核心轮转里的波动型输出，需要继续观察稳定性。")
            else:
                takeaways.append(f"{name} 的本场表现与近期均值差异较大，说明角色回合的稳定性仍在波动。")

    return takeaways[:3]

def sort_players_by_role_priority(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        rows,
        key=lambda row: (
            row.get("role_priority", role_priority_value(row.get("role_tier", ""))),
            preferred_name_priority(row["player_name"]),
            row.get("minutes_seconds", 0),
            row.get("points", 0),
        ),
        reverse=True,
    )

def build_core_player_trends(current_rows: list[dict[str, Any]], current_event_id: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    core_players = sort_players_by_role_priority([row for row in current_rows if row["minutes_seconds"] >= 18 * 60])
    recent_5_ids = get_recent_completed_event_ids(limit=5, through_event_id=current_event_id)
    recent_10_ids = get_recent_completed_event_ids(limit=10, through_event_id=current_event_id)
    combined_ids = list(dict.fromkeys(recent_5_ids + recent_10_ids))
    analysis_cache = build_event_analysis_cache(combined_ids)

    player_trends: list[dict[str, Any]] = []
    player_profiles: list[dict[str, Any]] = []

    for row in core_players:
        trend_5 = compute_player_trend(row["player_name"], recent_5_ids, analysis_cache)
        season_like = compute_player_trend(row["player_name"], recent_10_ids, analysis_cache)
        profile = build_player_profile(row, trend_5, season_like)
        role_info = get_player_role_info(row["player_name"])
        trend_5["current_ts"] = row["ts_pct"]
        trend_5["season_ts"] = season_like["ts_pct_avg"]
        trend_5["delta_vs_trend"] = profile["delta_vs_trend"]
        trend_5["delta_vs_season"] = profile["delta_vs_season"]
        trend_5["role_tier"] = role_info["tier"]
        trend_5["role_archetype"] = role_info["archetype"]
        trend_5["offensive_impact"] = row.get("offensive_impact", classify_offensive_impact(row, role_info))
        trend_5["role_summary"] = build_role_aware_trend_summary(trend_5, role_info)
        trend_5["role_priority"] = role_priority_value(role_info["tier"])
        player_trends.append(trend_5)
        player_profiles.append(profile)

    player_trends = sort_players_by_role_priority(player_trends)
    player_takeaways = build_player_trend_takeaways(player_profiles, player_trends, current_rows)
    return player_trends, player_profiles, player_takeaways

def build_recent_trend(event_id: str) -> dict[str, Any]:
    from .fetchers import build_analysis_from_espn_event

    event_ids = get_recent_completed_event_ids(limit=5, through_event_id=event_id)
    samples = []
    for recent_event_id in event_ids:
        analysis = build_analysis_from_espn_event(recent_event_id, include_trends=False)
        samples.append(
            {
                "event_id": recent_event_id,
                "game_date": analysis["game_date"],
                "net_rating": analysis["celtics_metrics"]["net_rating"],
                "efg_pct": analysis["celtics_metrics"]["efg_pct"],
                "tov_pct": analysis["celtics_metrics"]["tov_pct"],
                "three_pa_rate": analysis["celtics_metrics"]["three_pa_rate"],
            }
        )

    count = len(samples) or 1
    averages = {
        "games": len(samples),
        "net_rating_avg": round2(sum(item["net_rating"] for item in samples) / count),
        "efg_pct_avg": round4(sum(item["efg_pct"] for item in samples) / count),
        "tov_pct_avg": round4(sum(item["tov_pct"] for item in samples) / count),
        "three_pa_rate_avg": round4(sum(item["three_pa_rate"] for item in samples) / count),
        "samples": samples,
    }
    return averages
def build_trend_takeaway(current_metrics: dict[str, Any], trend: dict[str, Any], result: str) -> str:
    net_gap = current_metrics["net_rating"] - trend["net_rating_avg"]
    efg_gap = current_metrics["efg_pct"] - trend["efg_pct_avg"]
    tov_gap = current_metrics["tov_pct"] - trend["tov_pct_avg"]
    three_gap = current_metrics["three_pa_rate"] - trend["three_pa_rate_avg"]

    if trend["games"] == 0:
        return "最近5场样本不足，暂时无法形成稳定趋势判断。"
    if current_metrics["three_pa_rate"] < 0.4 and trend["three_pa_rate_avg"] < 0.42:
        return "最近5场外线出手占比持续偏低，这场并非偶然，体系外线压力需要继续关注。"
    if tov_gap > 0.02 and trend["tov_pct_avg"] <= 0.13:
        return "最近5场失误控制本来相对稳定，这场更像单场处理球波动。"
    if net_gap < -5 and trend["net_rating_avg"] > 0:
        return "最近5场 Net Rating 仍为正，本场的起伏更像短期波动，而非整体走势反转。"
    if efg_gap < -0.04:
        return "本场终结效率明显低于最近5场平均，进攻端属于偏离常态的低效输出。"
    if result == "win" and net_gap > 3:
        return "本场整体表现高于最近5场均值，属于近期状态延续中的一次高质量输出。"
    return "本场整体表现大体贴近最近5场均值，说明当前比赛内容更像近期趋势的延续。"
