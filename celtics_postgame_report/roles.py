from __future__ import annotations

from typing import Any

from .config import CORE_TREND_PRIORITY_NAMES, DEFAULT_ROLE_INFO, PLAYER_CONTEXT, PLAYER_OFFENSIVE_ROLE_MAP, ROLE_PRIORITY

def get_player_role_info(player_name: str) -> dict[str, str]:
    role_info = PLAYER_OFFENSIVE_ROLE_MAP.get(player_name, DEFAULT_ROLE_INFO)
    return {
        "tier": role_info.get("tier", DEFAULT_ROLE_INFO["tier"]),
        "archetype": role_info.get("archetype", DEFAULT_ROLE_INFO["archetype"]),
    }

def get_player_context(player_name: str) -> dict[str, str]:
    return PLAYER_CONTEXT.get(player_name, {})

def role_priority_value(tier: str) -> int:
    return ROLE_PRIORITY.get(tier, 0)

def preferred_name_priority(player_name: str) -> int:
    if player_name in CORE_TREND_PRIORITY_NAMES:
        return len(CORE_TREND_PRIORITY_NAMES) - CORE_TREND_PRIORITY_NAMES.index(player_name)
    return 0

def role_display_text(role_info: dict[str, str]) -> str:
    return f"{role_info['tier']} / {role_info['archetype']}"

def should_apply_context(row: dict[str, Any], role_info: dict[str, str], context: dict[str, str]) -> bool:
    if not context:
        return False

    trend_ts = row.get("trend_ts")
    poor_performance = row.get("ts_pct", 0.0) < 0.50 or (
        isinstance(trend_ts, (int, float)) and row.get("ts_pct", 0.0) < trend_ts - 0.03
    )
    if not poor_performance:
        return False

    support_conditions = 0
    if role_info["tier"] in {"primary_core", "secondary_core"}:
        support_conditions += 1
    if row.get("usage_proxy", 0.0) >= 12:
        support_conditions += 1

    return support_conditions >= 1

def append_context_if_needed(text: str, row: dict[str, Any], role_info: dict[str, str]) -> str:
    context = get_player_context(row["player_name"])
    if not should_apply_context(row, role_info, context):
        return text

    status = context.get("status", "")
    note = context.get("note", "")
    if status == "post_injury":
        context_sentence = "考虑到近期仍处于伤病恢复阶段，这种短期波动具备一定合理性。"
    elif status == "injury_prone":
        context_sentence = "考虑到伤病背景仍然存在，恢复周期内出现效率波动属于可接受区间。"
    else:
        context_sentence = "考虑到当前身体状态背景，这种短期波动具备一定合理性。"

    if note:
        return f"{text} {context_sentence}（{note}）"
    return f"{text} {context_sentence}"

def classify_offensive_impact(row: dict[str, Any], role_info: dict[str, str]) -> str:
    tier = role_info["tier"]
    archetype = role_info["archetype"]
    usage = row.get("usage_proxy", 0.0)
    assists = row.get("assists", 0)
    three_rate = row.get("three_pa_rate", 0.0)

    if tier == "primary_core":
        if archetype == "creator":
            return "primary creator"
        if archetype == "creator_scorer":
            return "primary creator" if assists >= 5 or usage >= 18 else "primary finisher"
        return "primary finisher"
    if tier == "secondary_core":
        if archetype == "creator" or assists >= 5:
            return "secondary creator"
        if archetype == "bench_finisher":
            return "secondary finisher"
        return "secondary creator" if usage >= 14 and assists >= 4 else "secondary finisher"
    if tier == "rotation_finisher":
        if archetype == "rim_finisher":
            return "rim finisher"
        return "low-usage finisher"
    if tier == "rotation_spacer":
        return "spacer"
    if three_rate >= 0.55:
        return "spacer"
    return "low-involvement role player"

def describe_role_aware_positive_takeaway(row: dict[str, Any], role_info: dict[str, str]) -> str:
    from .metrics import percent_text

    name = row["player_name"]
    tier = role_info["tier"]
    archetype = role_info["archetype"]
    ts_text = percent_text(row["ts_pct"])
    points = row["points"]
    assists = row["assists"]

    if tier == "primary_core":
        if archetype in {"creator_scorer", "creator"}:
            return f"{name} 作为核心持球点，在承担主线进攻任务的同时仍交出了 {ts_text} 的 TS，组织和终结都稳住了比赛主线。"
        return f"{name} 作为主攻手维持了 {ts_text} 的终结效率，在核心回合里给出了球队最稳定的得分输出。"
    if tier == "secondary_core":
        if archetype == "creator":
            return f"{name} 更多体现在组织和进攻发起层面，本场送出 {assists} 次助攻，作为次核心把辅助主线撑了起来。"
        if archetype == "bench_finisher":
            return f"{name} 在替补阶段提供了高效火力，拿到 {points} 分并打出 {ts_text} 的 TS，是二阵容的重要得分来源。"
        return f"{name} 作为次核心完成了稳定的终结回应，在主线之外提供了可靠的得分补充。"
    if tier == "rotation_finisher":
        if archetype == "rim_finisher":
            return f"{name} 在内线终结端效率极高，完成了多次高质量吃饼和近框回合，是典型的高效终结回应。"
        return f"{name} 本场更像高效终结点，在有限触球下把近筐机会完成得很扎实，而不是承担进攻发起任务。"
    if tier == "rotation_spacer":
        return f"{name} 作为空间型角色球员给出了不错的终结回应，外线牵制和定点完成度都在线。"
    return f"{name} 作为轮换角色在有限回合里完成了自己的任务，提供了合格的补充价值。"

def describe_role_aware_negative_takeaway(row: dict[str, Any], role_info: dict[str, str]) -> str:
    from .metrics import percent_text

    name = row["player_name"]
    tier = role_info["tier"]
    archetype = role_info["archetype"]
    ts_text = percent_text(row["ts_pct"])

    if tier == "primary_core":
        if archetype in {"creator_scorer", "creator"}:
            return append_context_if_needed(
                f"{name} 作为核心持球点，本场只有 {ts_text} 的 TS，主线发起和终结都低于常态，直接影响了球队进攻上限。",
                row,
                role_info,
            )
        return append_context_if_needed(
            f"{name} 作为主攻手的终结效率只有 {ts_text}，核心回合的产出不够稳，比赛主线因此承压。",
            row,
            role_info,
        )
    if tier == "secondary_core":
        if archetype == "creator":
            return append_context_if_needed(
                f"{name} 在次核心发起层面的支撑不够稳定，进攻梳理和个人终结都没有给主线足够帮助。",
                row,
                role_info,
            )
        if archetype == "bench_finisher":
            return append_context_if_needed(
                f"{name} 这场替补火力没有打出来，作为二阵容得分点的回应偏弱，没能有效分担主线压力。",
                row,
                role_info,
            )
        return append_context_if_needed(
            f"{name} 作为次核心的辅助输出偏弱，未能把主线之外的得分支撑补起来。",
            row,
            role_info,
        )
    if tier == "rotation_finisher":
        if archetype == "rim_finisher":
            return f"{name} 作为内线终结角色，本场近框回应有限，轮换回合里的终结质量没有打出来。"
        return f"{name} 本场更多停留在低影响力终结层面，轮换回合的回应比较有限。"
    if tier == "rotation_spacer":
        return f"{name} 作为空间型角色球员，本场外线终结没有形成足够回应，空间价值没能真正打出来。"
    return f"{name} 作为轮换角色的影响力偏弱，有限出场时间里没有形成足够存在感。"

def build_role_aware_trend_summary(trend: dict[str, Any], role_info: dict[str, str]) -> str:
    tier = role_info["tier"]
    archetype = role_info["archetype"]
    current_ts = trend.get("current_ts", 0.0)
    trend_ts = trend.get("ts_pct_avg", 0.0)
    season_ts = trend.get("season_ts", 0.0)
    fga_avg = trend.get("fga_avg", 0.0)
    three_avg = trend.get("three_pa_rate_avg", 0.0)

    if tier == "primary_core":
        if archetype in {"creator_scorer", "creator"}:
            if current_ts < trend_ts - 0.03:
                return "作为核心持球点，本场效率明显低于近期基线，主线进攻没有完全撑起来。"
            if current_ts > trend_ts + 0.03 and trend_ts >= season_ts:
                return "作为核心持球点，本场延续了近期上升势头，继续稳住了球队进攻主线。"
            return "作为核心持球点，本场整体表现接近近期常态，主线输出大体维持在可接受区间。"
        if current_ts < trend_ts - 0.03:
            return "作为主攻手，本场终结效率低于近期基线，核心得分回合的质量有所下滑。"
        if current_ts > trend_ts + 0.03 and trend_ts >= season_ts:
            return "作为主攻手，本场延续了近期稳定输出，核心终结质量继续维持在上行区间。"
        return "作为主攻手，本场得分效率基本贴近近期常态，核心终结职责完成度中规中矩。"
    if tier == "secondary_core":
        if archetype == "creator":
            if current_ts < trend_ts - 0.03:
                return "作为次核心发起点，本场效率低于近期样本，对主线的辅助支撑有所下滑。"
            return "作为次核心发起点，本场基本完成了辅助主线的任务，组织和终结维持在近期区间。"
        if current_ts > trend_ts + 0.03:
            return "作为替补得分点，本场终结效率高于最近样本，二阵容火力支撑比较明显。"
        return "作为次核心得分点，本场更多承担阶段性火力补充，整体表现接近近期常态。"
    if tier == "rotation_finisher":
        if current_ts > trend_ts + 0.04:
            return "作为内线终结角色，本场完成了高质量近框回合，终结效率明显好于近期样本。"
        return "作为终结型轮换，本场是否完成角色任务主要体现在近框质量，而不是进攻发起。"
    if tier == "rotation_spacer":
        if three_avg >= 0.55 and current_ts >= trend_ts:
            return "作为空间型角色，本场外线回应达到了应有标准，完成了拉开空间后的终结任务。"
        return "作为空间型角色，本场价值仍主要体现在拉开空间和接应终结，而不是高使用率主导回合。"
    if fga_avg >= 10:
        return "作为轮换角色，本场参与度略高于常态，但影响力仍更偏补充型。"
    return "作为轮换角色，本场是否达标主要看是否完成有限回合的功能性任务。"
