from __future__ import annotations

from .config import DEFAULT_ROLE_INFO
from .metrics import METRIC_LABELS, percent_text

def build_celtics_markdown(analysis: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append(f"# Celtics 赛后诊断 {analysis['game_date']}")
    lines.append("")

    if not analysis["played_today"]:
        lines.append("## 比赛结果")
        lines.append("")
        lines.append(analysis["message"])
        lines.append("")
        lines.append("## 一句话总结")
        lines.append("")
        lines.append("今日无 Celtics 比赛，系统未触发赛后诊断。")
        lines.append("")
        return "\n".join(lines)

    lines.append("## 比赛结果")
    lines.append("")
    lines.append(
        f"<img src=\"{analysis['logo_url']}\" alt=\"BOS\" width=\"22\" /> **BOS** {analysis['team_score']} : "
        f"{analysis['opponent_score']} **{analysis['opponent']}** "
        f"<img src=\"{analysis['opponent_logo_url']}\" alt=\"{analysis['opponent']}\" width=\"22\" />"
    )
    lines.append("")
    lines.append(
        f"- 结果: {'赢球' if analysis['result'] == 'win' else '输球'}"
    )
    lines.append(f"- 对手: {analysis['opponent_name']}")
    lines.append(f"- 状态: {analysis['game_status_text']}")
    lines.append("")

    lines.append("## 比赛主线")
    lines.append("")
    lines.append(analysis.get("game_narrative", "本场比赛缺少足够信号来提炼稳定主线，但整体仍然由攻防效率差决定。"))
    lines.append("")

    lines.append("## 核心指标")
    lines.append("")
    lines.append("| 指标 | Celtics | 对手 |")
    lines.append("| --- | ---: | ---: |")
    lines.append(f"| {METRIC_LABELS['possessions']} | {analysis['celtics_metrics']['possessions']:.2f} | {analysis['opponent_metrics']['possessions']:.2f} |")
    lines.append(f"| {METRIC_LABELS['off_rating']} | {analysis['celtics_metrics']['off_rating']:.2f} | {analysis['opponent_metrics']['off_rating']:.2f} |")
    lines.append(f"| {METRIC_LABELS['def_rating']} | {analysis['celtics_metrics']['def_rating']:.2f} | {analysis['opponent_metrics']['def_rating']:.2f} |")
    lines.append(f"| {METRIC_LABELS['net_rating']} | {analysis['celtics_metrics']['net_rating']:.2f} | {analysis['opponent_metrics']['net_rating']:.2f} |")
    lines.append(f"| {METRIC_LABELS['efg_pct']} | {percent_text(analysis['celtics_metrics']['efg_pct'])} | {percent_text(analysis['opponent_metrics']['efg_pct'])} |")
    lines.append(f"| {METRIC_LABELS['ts_pct']} | {percent_text(analysis['celtics_metrics']['ts_pct'])} | {percent_text(analysis['opponent_metrics']['ts_pct'])} |")
    lines.append(f"| {METRIC_LABELS['three_pa_rate']} | {percent_text(analysis['celtics_metrics']['three_pa_rate'])} | {percent_text(analysis['opponent_metrics']['three_pa_rate'])} |")
    lines.append(f"| {METRIC_LABELS['tov_pct']} | {percent_text(analysis['celtics_metrics']['tov_pct'])} | {percent_text(analysis['opponent_metrics']['tov_pct'])} |")
    lines.append(f"| {METRIC_LABELS['oreb_pct']} | {percent_text(analysis['celtics_metrics']['oreb_pct'])} | {percent_text(analysis['opponent_metrics']['oreb_pct'])} |")
    lines.append(f"| {METRIC_LABELS['opp_efg_pct']} | {percent_text(analysis['celtics_metrics']['opp_efg_pct'])} | {percent_text(analysis['opponent_metrics']['opp_efg_pct'])} |")
    lines.append("")

    lines.append(f"## {'赢球' if analysis['result'] == 'win' else '输球'}原因（3条）")
    lines.append("")
    for item in analysis["reasons"]:
        lines.append(f"- {item}")
    lines.append("")

    lines.append("## 风险点（2条）")
    lines.append("")
    for item in analysis["risks"]:
        lines.append(f"- {item}")
    lines.append("")

    lines.append("## Celtics体系评价")
    lines.append("")
    for item in analysis["system_evaluation"]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append(
        f"- 替补贡献: {analysis['bench']['bench_points']}分 / {analysis['bench']['bench_rebounds']}板 / {analysis['bench']['bench_assists']}助"
    )
    lines.append(f"- 团队助攻: {analysis['team_assists']}")
    lines.append("")

    lines.append("## 最近5场趋势")
    lines.append("")
    trend = analysis.get("trend_5_games", {})
    lines.append("| 指标 | 最近5场平均 |")
    lines.append("| --- | ---: |")
    lines.append(f"| 最近5场平均净效率 Avg Net Rating | {trend.get('net_rating_avg', 0):.2f} |")
    lines.append(f"| 最近5场平均有效命中率 Avg eFG% | {percent_text(trend.get('efg_pct_avg', 0))} |")
    lines.append(f"| 最近5场平均失误率 Avg TOV% | {percent_text(trend.get('tov_pct_avg', 0))} |")
    lines.append(f"| 最近5场平均三分出手占比 Avg 3PA Rate | {percent_text(trend.get('three_pa_rate_avg', 0))} |")
    lines.append("")
    if analysis.get("trend_takeaway"):
        lines.append(f"- 趋势结论: {analysis['trend_takeaway']}")
        lines.append("")

    lines.append("## 球员点评")
    lines.append("")
    takeaways = analysis.get("player_takeaways", {})
    if takeaways.get("best"):
        lines.append(f"- {takeaways['best']}")
    if takeaways.get("worst"):
        lines.append(f"- {takeaways['worst']}")
    lines.append("")

    lines.append("## 核心球员趋势")
    lines.append("")
    for trend in analysis.get("player_trends", []):
        lines.append(f"### {trend['player_name']}")
        lines.append(f"- 角色 Role: {trend.get('role_tier', DEFAULT_ROLE_INFO['tier'])} / {trend.get('role_archetype', DEFAULT_ROLE_INFO['archetype'])}")
        lines.append(f"- 进攻参与画像 Offensive Impact: {trend.get('offensive_impact', 'unknown')}")
        lines.append(f"- 本场 TS% Current TS%: {percent_text(trend['current_ts'])}")
        lines.append(f"- 最近5场 TS% Last 5 TS%: {percent_text(trend['ts_pct_avg'])}")
        lines.append(f"- 赛季近似 TS% Season-like TS%: {percent_text(trend['season_ts'])}")
        lines.append(f"- 最近5场 eFG% Last 5 eFG%: {percent_text(trend['efg_pct_avg'])}")
        lines.append(f"- 最近5场 FGA Last 5 FGA: {trend['fga_avg']:.1f}")
        lines.append(f"- 最近5场 3PA Rate Last 5 3PA Rate: {percent_text(trend['three_pa_rate_avg'])}")
        lines.append(f"- 最近5场得分 Last 5 PTS: {trend['points_avg']:.1f}")
        lines.append(f"- 变化 Delta vs Season: {percent_text(trend['delta_vs_season'])}")
        lines.append("- 结论:")
        lines.append(f"  {trend.get('role_summary', '本场表现接近近期样本。')}")
        lines.append("")

    if analysis.get("player_trend_takeaways"):
        for item in analysis["player_trend_takeaways"]:
            lines.append(f"- {item}")
        lines.append("")

    lines.append("## 登场球员进阶数据")
    lines.append("")
    lines.append("| 球员 Player | 首发 Starter | 时间 MIN | 得分 PTS | 篮板 REB | 助攻 AST | 正负值 Plus/Minus | 有效命中率 eFG% | 真实命中率 TS% | 三分出手占比 3PA Rate | 助失比 AST/TO |")
    lines.append("| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    for row in analysis.get("player_advanced", []):
        starter_text = "是 Yes" if row["starter"] else "否 No"
        lines.append(
            f"| {row['player_name']} | {starter_text} | {row['minutes']} | {row['points']} | {row['rebounds']} | "
            f"{row['assists']} | {row['plus_minus']:+} | {percent_text(row['efg_pct'])} | {percent_text(row['ts_pct'])} | "
            f"{percent_text(row['three_pa_rate'])} | {row['ast_to_ratio']:.2f} |"
        )
    lines.append("")

    lines.append("## 一句话总结")
    lines.append("")
    lines.append(f"- {analysis['one_liner']}")
    lines.append("")
    return "\n".join(lines)
