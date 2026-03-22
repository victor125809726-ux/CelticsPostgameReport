from __future__ import annotations

from typing import Any

from .metrics import percent_text, round2, round4
from .roles import get_player_role_info, describe_role_aware_positive_takeaway, describe_role_aware_negative_takeaway, role_priority_value

def make_scored_item(kind: str, text: str, score: float, key: str) -> dict[str, Any]:
    return {"kind": kind, "text": text, "score": round2(score), "key": key}

def dedupe_scored_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen_keys: set[str] = set()
    for item in sorted(items, key=lambda row: row["score"], reverse=True):
        unique_key = f"{item['kind']}::{item['key']}::{item['text']}"
        if unique_key in seen_keys:
            continue
        seen_keys.add(unique_key)
        deduped.append(item)
    return deduped

def build_reason_items(
    celtics: dict[str, Any],
    opponent: dict[str, Any],
    team_name: str,
    result: str,
    team_assists: int,
    bench_points: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    reasons: list[dict[str, Any]] = []
    risks: list[dict[str, Any]] = []

    efg_diff = celtics["efg_pct"] - opponent["efg_pct"]
    three_rate_diff = celtics["three_pa_rate"] - opponent["three_pa_rate"]
    tov_diff = celtics["tov_pct"] - opponent["tov_pct"]
    oreb_diff = celtics["oreb_pct"] - opponent["oreb_pct"]
    net_rating = celtics["net_rating"]

    if result == "win":
        if efg_diff > 0:
            reasons.append(
                make_scored_item(
                    "reason",
                    f"投篮效率优势明显，Celtics eFG% {percent_text(celtics['efg_pct'])}，高于对手 {percent_text(opponent['efg_pct'])}。",
                    abs(efg_diff) * 180,
                    "efg_win",
                )
            )
        if celtics["three_pa_rate"] >= 0.45 and celtics["efg_pct"] >= 0.54:
            reasons.append(
                make_scored_item(
                    "reason",
                    f"外线驱动明显，3PA Rate 达到 {percent_text(celtics['three_pa_rate'])}，同时整体效率保持稳定。",
                    6 + max(celtics["three_pa_rate"] - 0.45, 0) * 100 + max(celtics["efg_pct"] - 0.54, 0) * 120,
                    "three_structure_win",
                )
            )
        if tov_diff < 0:
            reasons.append(
                make_scored_item(
                    "reason",
                    f"失误控制优于对手，Celtics TOV% {percent_text(celtics['tov_pct'])}，明显压低了对手转换机会。",
                    abs(tov_diff) * 170,
                    "tov_win",
                )
            )
        if oreb_diff > 0:
            reasons.append(
                make_scored_item(
                    "reason",
                    f"前场篮板积极，OREB% 达到 {percent_text(celtics['oreb_pct'])}，带来了二次进攻。",
                    abs(oreb_diff) * 150,
                    "oreb_win",
                )
            )
        if opponent["efg_pct"] <= 0.5:
            reasons.append(
                make_scored_item(
                    "reason",
                    f"防守端压制到位，把 {team_name} 的 eFG% 压到了 {percent_text(opponent['efg_pct'])}。",
                    max(0.5 - opponent["efg_pct"], 0) * 170,
                    "defense_win",
                )
            )
    else:
        if efg_diff < 0:
            reasons.append(
                make_scored_item(
                    "reason",
                    f"投篮效率吃亏，Celtics eFG% {percent_text(celtics['efg_pct'])}，落后对手 {percent_text(opponent['efg_pct'])}。",
                    abs(efg_diff) * 180,
                    "efg_loss",
                )
            )
        if celtics["three_pa_rate"] < 0.4 or three_rate_diff < -0.08:
            reasons.append(
                make_scored_item(
                    "reason",
                    f"外线结构不占优，3PA Rate 仅 {percent_text(celtics['three_pa_rate'])}，低于对手 {percent_text(opponent['three_pa_rate'])}。",
                    max(0.4 - celtics["three_pa_rate"], 0) * 120 + max(-three_rate_diff, 0) * 100,
                    "three_structure_loss",
                )
            )
        if celtics["tov_pct"] >= 0.14 or tov_diff > 0:
            reasons.append(
                make_scored_item(
                    "reason",
                    f"失误偏多，TOV% 达到 {percent_text(celtics['tov_pct'])}，回合质量受到影响。",
                    max(celtics["tov_pct"] - 0.14, 0) * 150 + max(tov_diff, 0) * 120,
                    "tov_loss",
                )
            )
        if oreb_diff < 0:
            reasons.append(
                make_scored_item(
                    "reason",
                    f"篮板争夺处于下风，OREB% 只有 {percent_text(celtics['oreb_pct'])}，缺少额外回合。",
                    abs(oreb_diff) * 130,
                    "oreb_loss",
                )
            )
        if opponent["efg_pct"] >= 0.55:
            reasons.append(
                make_scored_item(
                    "reason",
                    f"防守质量不足，让对手打出了 {percent_text(opponent['efg_pct'])} 的 eFG%。",
                    max(opponent["efg_pct"] - 0.55, 0) * 180 + 5,
                    "defense_loss",
                )
            )

    if celtics["tov_pct"] >= 0.14 or tov_diff > 0:
        risks.append(
            make_scored_item(
                "risk",
                f"若继续维持 {percent_text(celtics['tov_pct'])} 的失误率，强队对位时容易被反击惩罚。",
                max(celtics["tov_pct"] - 0.12, 0) * 170 + max(tov_diff, 0) * 120,
                "risk_tov",
            )
        )
    if opponent["efg_pct"] >= 0.54:
        risks.append(
            make_scored_item(
                "risk",
                f"对手 eFG% 达到 {percent_text(opponent['efg_pct'])}，说明外线和禁区的防守同时承压。",
                max(opponent["efg_pct"] - 0.52, 0) * 180,
                "risk_opp_efg",
            )
        )
    if celtics["three_pa_rate"] < 0.4:
        risks.append(
            make_scored_item(
                "risk",
                f"三分出手占比只有 {percent_text(celtics['three_pa_rate'])}，没有完全打出 Celtics 典型外线体系。",
                max(0.4 - celtics["three_pa_rate"], 0) * 160 + 4,
                "risk_three_rate",
            )
        )
    if team_assists < 24:
        risks.append(
            make_scored_item(
                "risk",
                f"本场助攻仅 {team_assists} 次，组织端需要更稳定地制造简单机会。",
                max(24 - team_assists, 0) * 0.8 + 4,
                "risk_assists",
            )
        )
    if bench_points < 25:
        risks.append(
            make_scored_item(
                "risk",
                f"替补仅贡献 {bench_points} 分，轮换深度仍需提升。",
                max(25 - bench_points, 0) * 0.7 + 3,
                "risk_bench",
            )
        )
    if oreb_diff < -0.05:
        risks.append(
            make_scored_item(
                "risk",
                f"前场篮板率落后对手，额外回合不足会放大进攻波动。",
                abs(oreb_diff) * 120,
                "risk_oreb",
            )
        )
    if net_rating < 0:
        risks.append(
            make_scored_item(
                "risk",
                f"本场 Net Rating 为 {net_rating:.2f}，说明攻防两端至少有一端持续失衡。",
                abs(net_rating) * 0.6 + 3,
                "risk_net",
            )
        )

    return dedupe_scored_items(reasons), dedupe_scored_items(risks)

def build_fallback_risks(summary_payload: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = []
    celtics = summary_payload["celtics_metrics"]
    opponent = summary_payload["opponent_metrics"]
    bench = summary_payload["bench"]

    candidates.append(
        make_scored_item(
            "risk",
            f"本场助攻仅 {summary_payload['team_assists']} 次，组织端需要更稳定地制造简单机会。",
            max(24 - summary_payload["team_assists"], 0) * 0.8 + 2,
            "fallback_assists",
        )
    )
    candidates.append(
        make_scored_item(
            "risk",
            f"对手 eFG% 达到 {percent_text(opponent['efg_pct'])}，防守细节仍有提升空间。",
            max(opponent["efg_pct"] - 0.50, 0) * 160 + 2,
            "fallback_opp_efg",
        )
    )
    candidates.append(
        make_scored_item(
            "risk",
            f"本场 TOV% 为 {percent_text(celtics['tov_pct'])}，处理球稳定性仍值得持续观察。",
            max(celtics["tov_pct"] - 0.12, 0) * 150 + 2,
            "fallback_tov",
        )
    )
    candidates.append(
        make_scored_item(
            "risk",
            f"替补贡献为 {bench['bench_points']} 分，轮换深度还需要更持续的支撑。",
            max(25 - bench["bench_points"], 0) * 0.7 + 1,
            "fallback_bench",
        )
    )
    candidates.append(
        make_scored_item(
            "risk",
            f"三分出手占比为 {percent_text(celtics['three_pa_rate'])}，体系表现需要结合后续几场继续确认。",
            abs(celtics["three_pa_rate"] - 0.45) * 100 + 1,
            "fallback_three_rate",
        )
    )
    return dedupe_scored_items(candidates)

def build_fallback_reasons(summary_payload: dict[str, Any]) -> list[dict[str, Any]]:
    celtics = summary_payload["celtics_metrics"]
    opponent_bench = summary_payload["opponent_bench"]
    bench = summary_payload["bench"]
    candidates = [
        make_scored_item(
            "reason",
            f"Net Rating 为 {celtics['net_rating']:.2f}，整体回合质量 {'占优' if celtics['net_rating'] >= 0 else '落后'}。",
            abs(celtics["net_rating"]) * 0.8 + 3,
            "fallback_net",
        ),
        make_scored_item(
            "reason",
            f"TS% 为 {percent_text(celtics['ts_pct'])}，真实命中效率 {'稳定' if celtics['ts_pct'] >= 0.58 else '一般'}。",
            abs(celtics["ts_pct"] - 0.58) * 100 + 2,
            "fallback_ts",
        ),
        make_scored_item(
            "reason",
            f"替补得到 {bench['bench_points']} 分，对比对手替补 {opponent_bench['bench_points']} 分。",
            abs(bench["bench_points"] - opponent_bench["bench_points"]) * 0.3 + 1,
            "fallback_bench_compare",
        ),
    ]
    return dedupe_scored_items(candidates)

def positive_takeaway_score(row: dict[str, Any]) -> float:
    return (
        row.get("role_priority", 0) * 120
        + row.get("ts_pct", 0) * 100
        + row.get("usage_proxy", 0) * 1.6
        + row.get("playmaking_proxy", 0) * 5
        + row.get("points", 0) * 1.2
        + max(row.get("plus_minus", 0), 0) * 0.8
    )

def negative_takeaway_score(row: dict[str, Any]) -> float:
    return (
        row.get("role_priority", 0) * 140
        + max(0.56 - row.get("ts_pct", 0), 0) * 220
        + row.get("usage_proxy", 0) * 1.8
        + max(-row.get("plus_minus", 0), 0) * 1.1
        + row.get("minutes_seconds", 0) / 60 * 0.35
    )

def build_player_takeaways(player_rows: list[dict[str, Any]]) -> dict[str, str]:
    eligible = [row for row in player_rows if row["minutes_seconds"] >= 18 * 60]
    if not eligible:
        return {
            "best": "本场有效样本不足，暂不生成正面球员点评。",
            "worst": "本场有效样本不足，暂不生成负面球员点评。",
        }

    sorted_positive = sorted(eligible, key=positive_takeaway_score, reverse=True)
    sorted_negative = sorted(eligible, key=negative_takeaway_score, reverse=True)
    best = sorted_positive[0]
    worst = sorted_negative[0]
    best_role = get_player_role_info(best["player_name"])
    worst_role = get_player_role_info(worst["player_name"])

    return {
        "best": describe_role_aware_positive_takeaway(best, best_role),
        "worst": describe_role_aware_negative_takeaway(worst, worst_role),
    }

def build_one_liner(result: str, top_reason: str, top_risk: str) -> str:
    if result == "win":
        return f"Celtics 赢在 {top_reason.replace('。', '')}，但 {top_risk.replace('。', '')} 仍是后续必须处理的隐患。"
    return f"Celtics 输球的主线在于 {top_reason.replace('。', '')}，而且 {top_risk.replace('。', '')} 让问题被进一步放大。"

def detect_narrative_signals(analysis: dict[str, Any]) -> dict[str, Any]:
    player_trends = analysis.get("player_trends", [])
    primary_core = [item for item in player_trends if item.get("role_tier") == "primary_core"]
    secondary_core = [item for item in player_trends if item.get("role_tier") == "secondary_core"]
    celtics_metrics = analysis["celtics_metrics"]
    opponent_metrics = analysis["opponent_metrics"]

    primary_core_big_drop = [
        item for item in primary_core if item.get("delta_vs_trend", 0.0) <= -0.05 or item.get("delta_vs_season", 0.0) <= -0.05
    ]
    primary_core_season_drop = [item for item in primary_core if item.get("delta_vs_season", 0.0) <= -0.03]
    white_support = next((item for item in secondary_core if item["player_name"] == "Derrick White"), None)

    bench_firepower_players = [
        item["player_name"]
        for item in player_trends
        if item.get("role_tier") in {"secondary_core", "rotation_finisher", "rotation_spacer"}
        and item.get("current_ts", 0.0) >= 0.60
        and item.get("points_avg", 0.0) >= 10
    ]

    signals = {
        "core_player_efficiency_drop": bool(primary_core_big_drop) or len(primary_core_season_drop) >= 2,
        "core_stability": any(
            item.get("current_ts", 0.0) >= max(item.get("ts_pct_avg", 0.0) - 0.02, 0.54) for item in primary_core
        )
        and bool(white_support)
        and white_support.get("current_ts", 0.0) >= white_support.get("ts_pct_avg", 0.0) - 0.03,
        "bench_support": analysis["bench"]["bench_points"] >= 30 or bool(bench_firepower_players),
        "bench_firepower_players": bench_firepower_players,
        "oreb_advantage": celtics_metrics["oreb_pct"] - opponent_metrics["oreb_pct"] >= 0.06,
        "oreb_gap": round4(celtics_metrics["oreb_pct"] - opponent_metrics["oreb_pct"]),
        "defensive_leak": opponent_metrics["efg_pct"] >= 0.55 or celtics_metrics["def_rating"] >= 118,
        "turnover_issue": celtics_metrics["tov_pct"] - opponent_metrics["tov_pct"] >= 0.025 or celtics_metrics["tov_pct"] >= 0.15,
        "result": analysis["result"],
        "core_drop_players": [item["player_name"] for item in primary_core_big_drop],
    }
    return signals

def build_game_narrative(analysis: dict[str, Any]) -> str:
    signals = analysis.get("narrative_signals") or detect_narrative_signals(analysis)
    result = analysis["result"]
    opponent = analysis["opponent"]
    celtics_metrics = analysis["celtics_metrics"]
    bench = analysis["bench"]
    sentences: list[str] = []

    if signals["core_player_efficiency_drop"]:
        sentences.append("本场比赛的主线在于核心进攻端出现了明显波动，主攻回合的终结质量没有维持在常态区间。")
    elif signals["core_stability"]:
        sentences.append("本场比赛的主线在于核心持球与终结端维持住了稳定输出，球队主攻框架没有出现明显失衡。")
    elif signals["defensive_leak"] and result == "loss":
        sentences.append(f"本场输球更像是防守质量主导的结果，Celtics 没能把 {opponent} 的进攻效率压到可控区间。")
    elif signals["turnover_issue"] and result == "loss":
        sentences.append("本场失利的主线更多来自处理球不稳，失误直接破坏了连续回合的质量。")
    else:
        sentences.append("本场比赛的主线更多体现在球队整体结构的起伏上，攻防两端都存在阶段性的拉扯。")

    support_parts: list[str] = []
    if signals["bench_support"]:
        support_parts.append(f"替补阶段提供了 {bench['bench_points']} 分的额外火力，二阵容回合缓解了主线压力")
    if signals["oreb_advantage"]:
        support_parts.append("前场篮板优势带来了稳定的二次进攻和额外回合")
    if signals["defensive_leak"] and result == "loss":
        support_parts.append(f"对手 eFG% 高达 {percent_text(analysis['opponent_metrics']['efg_pct'])}，防守端始终没能真正降温比赛")
    if signals["turnover_issue"] and result == "loss":
        support_parts.append(f"TOV% 达到 {percent_text(celtics_metrics['tov_pct'])}，处理球波动让进攻结构难以持续")

    if support_parts:
        if len(support_parts) == 1:
            sentences.append(f"{support_parts[0]}。")
        else:
            sentences.append("同时，" + "，".join(support_parts[:-1]) + "，" + support_parts[-1] + "。")

    if result == "win":
        if signals["core_player_efficiency_drop"] and (signals["bench_support"] or signals["oreb_advantage"]):
            sentences.append("最终，球队靠轮换火力和额外回合弥补了核心输出波动，把比赛稳稳收了下来。")
        elif signals["core_stability"]:
            sentences.append("最终，核心主线稳定输出带动了整体体系运转，比赛走势也因此始终掌握在自己手里。")
        else:
            sentences.append("最终，Celtics 还是依靠更完整的回合质量把优势兑现成了胜利。")
    else:
        if signals["defensive_leak"]:
            sentences.append("最终，防守端持续给出的高质量机会被对手兑现，比赛也就被拖向了不利方向。")
        elif signals["turnover_issue"]:
            sentences.append("最终，失误放大的回合损耗削弱了追分和维持节奏的能力，输球也就顺着这条主线形成。")
        elif signals["core_player_efficiency_drop"]:
            sentences.append("最终，核心主线没有撑起足够的常态输出，比赛也在这种效率缺口里被慢慢拉开。")
        else:
            sentences.append("最终，几个关键环节都没能形成足够回应，比赛结果也顺着这种结构性劣势落定。")

    return " ".join(sentences[:3])

def build_system_evaluation(metrics: dict[str, Any]) -> list[str]:
    notes: list[str] = []

    if metrics["celtics_metrics"]["three_pa_rate"] < 0.4:
        notes.append("未打出典型外线体系，三分出手占比偏低。")
    else:
        notes.append("外线体系保持在合理区间，战术重心仍然围绕空间展开。")

    if metrics["team_assists"] < 24:
        notes.append("进攻流动性不足，球队助攻数偏低。")
    else:
        notes.append("球的转移基本顺畅，团队助攻产出达标。")

    if metrics["bench"]["bench_points"] < 25:
        notes.append("替补贡献不足，第二阵容得分偏低。")
    else:
        notes.append("替补席提供了可接受的火力支持。")

    return notes
