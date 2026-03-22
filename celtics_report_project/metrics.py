from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .roles import get_player_role_info, role_priority_value, classify_offensive_impact


@dataclass
class TeamMetrics:
    possessions: float
    off_rating: float
    def_rating: float
    net_rating: float
    efg_pct: float
    ts_pct: float
    three_pa_rate: float
    tov_pct: float
    oreb_pct: float
    opp_efg_pct: float

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TeamMetrics":
        return cls(
            possessions=data["possessions"],
            off_rating=data["off_rating"],
            def_rating=data["def_rating"],
            net_rating=data["net_rating"],
            efg_pct=data["efg_pct"],
            ts_pct=data["ts_pct"],
            three_pa_rate=data["three_pa_rate"],
            tov_pct=data["tov_pct"],
            oreb_pct=data["oreb_pct"],
            opp_efg_pct=data["opp_efg_pct"],
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PlayerAdvancedRow:
    player_name: str
    starter: bool
    minutes: str
    minutes_seconds: int
    points: int
    rebounds: int
    assists: int
    plus_minus: int
    efg_pct: float
    ts_pct: float
    three_pa_rate: float
    ast_to_ratio: float
    fga: int
    fgm: int
    tpa: int
    tpm: int
    fta: int
    turnovers: int
    role_tier: str
    role_archetype: str
    role_priority: int
    usage_proxy: float
    playmaking_proxy: int
    finishing_proxy: float
    offensive_impact: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PlayerAdvancedRow":
        return cls(
            player_name=data["player_name"],
            starter=data["starter"],
            minutes=data["minutes"],
            minutes_seconds=data["minutes_seconds"],
            points=data["points"],
            rebounds=data["rebounds"],
            assists=data["assists"],
            plus_minus=data["plus_minus"],
            efg_pct=data["efg_pct"],
            ts_pct=data["ts_pct"],
            three_pa_rate=data["three_pa_rate"],
            ast_to_ratio=data["ast_to_ratio"],
            fga=data["fga"],
            fgm=data["fgm"],
            tpa=data["tpa"],
            tpm=data["tpm"],
            fta=data["fta"],
            turnovers=data["turnovers"],
            role_tier=data["role_tier"],
            role_archetype=data["role_archetype"],
            role_priority=data["role_priority"],
            usage_proxy=data["usage_proxy"],
            playmaking_proxy=data["playmaking_proxy"],
            finishing_proxy=data["finishing_proxy"],
            offensive_impact=data["offensive_impact"],
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def safe_div(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator


def round4(value: float) -> float:
    return round(value, 4)


def round2(value: float) -> float:
    return round(value, 2)


def stat_value_map(stat_list: list[dict[str, Any]]) -> dict[str, str]:
    return {item.get("name", ""): item.get("displayValue", "0") for item in stat_list}


def parse_made_attempted(value: str) -> tuple[int, int]:
    made, attempted = value.split("-")
    return int(made), int(attempted)


def parse_int(value: str) -> int:
    try:
        return int(value)
    except Exception:
        return 0


def parse_percentage_from_int_text(value: str) -> float:
    try:
        return round(float(value) / 100, 4)
    except Exception:
        return 0.0


def parse_minutes_text(value: str) -> str:
    if ":" in value:
        return value
    try:
        minutes = int(value)
        return f"{minutes}:00"
    except Exception:
        return value or "0:00"


def minutes_text_to_seconds(value: str) -> int:
    if not value:
        return 0
    text = parse_minutes_text(value)
    if ":" not in text:
        return 0
    minutes, seconds = text.split(":", 1)
    try:
        return int(minutes) * 60 + int(seconds)
    except Exception:
        return 0


def compute_possessions(stats: dict[str, Any]) -> float:
    return (
        stats.get("fieldGoalsAttempted", 0)
        - stats.get("reboundsOffensive", 0)
        + stats.get("turnovers", 0)
        + 0.44 * stats.get("freeThrowsAttempted", 0)
    )


def compute_team_advanced_metrics(team: dict[str, Any], opponent: dict[str, Any]) -> dict[str, float]:
    team_stats = team.get("statistics", {})
    opp_stats = opponent.get("statistics", {})

    team_poss = compute_possessions(team_stats)
    opp_poss = compute_possessions(opp_stats)

    efg = safe_div(
        team_stats.get("fieldGoalsMade", 0) + 0.5 * team_stats.get("threePointersMade", 0),
        team_stats.get("fieldGoalsAttempted", 0),
    )
    opp_efg = safe_div(
        opp_stats.get("fieldGoalsMade", 0) + 0.5 * opp_stats.get("threePointersMade", 0),
        opp_stats.get("fieldGoalsAttempted", 0),
    )
    ts = safe_div(
        team_stats.get("points", team.get("score", 0)),
        2 * (team_stats.get("fieldGoalsAttempted", 0) + 0.44 * team_stats.get("freeThrowsAttempted", 0)),
    )
    three_pa_rate = safe_div(
        team_stats.get("threePointersAttempted", 0),
        team_stats.get("fieldGoalsAttempted", 0),
    )
    tov_pct = safe_div(team_stats.get("turnovers", 0), team_poss)
    oreb_pct = safe_div(
        team_stats.get("reboundsOffensive", 0),
        team_stats.get("reboundsOffensive", 0) + opp_stats.get("reboundsDefensive", 0),
    )

    return TeamMetrics(
        possessions=round2(team_poss),
        off_rating=round2(safe_div(team_stats.get("points", team.get("score", 0)) * 100, team_poss)),
        def_rating=round2(safe_div(opp_stats.get("points", opponent.get("score", 0)) * 100, opp_poss)),
        net_rating=round2(
            safe_div(team_stats.get("points", team.get("score", 0)) * 100, team_poss)
            - safe_div(opp_stats.get("points", opponent.get("score", 0)) * 100, opp_poss)
        ),
        efg_pct=round4(efg),
        ts_pct=round4(ts),
        three_pa_rate=round4(three_pa_rate),
        tov_pct=round4(tov_pct),
        oreb_pct=round4(oreb_pct),
        opp_efg_pct=round4(opp_efg),
    ).to_dict()


def compute_bench_stats(players: list[dict[str, Any]]) -> dict[str, int]:
    bench_points = 0
    bench_rebounds = 0
    bench_assists = 0

    for player in players:
        if player.get("starter", "0") == "1":
            continue
        if player.get("played", "0") != "1":
            continue
        stats = player.get("statistics", {})
        bench_points += stats.get("points", 0)
        bench_rebounds += stats.get("reboundsTotal", 0)
        bench_assists += stats.get("assists", 0)

    return {
        "bench_points": bench_points,
        "bench_rebounds": bench_rebounds,
        "bench_assists": bench_assists,
    }


def percent_text(value: float) -> str:
    return f"{value * 100:.1f}%"


METRIC_LABELS = {
    "possessions": "回合数 Possessions",
    "off_rating": "进攻效率 Offensive Rating",
    "def_rating": "防守效率 Defensive Rating",
    "net_rating": "净效率 Net Rating",
    "efg_pct": "有效命中率 eFG%",
    "ts_pct": "真实命中率 TS%",
    "three_pa_rate": "三分出手占比 3PA Rate",
    "tov_pct": "失误率 TOV%",
    "oreb_pct": "前场篮板率 OREB%",
    "opp_efg_pct": "对手有效命中率 Opponent eFG%",
}


def is_played(player: dict[str, Any]) -> bool:
    value = player.get("played", "0")
    return value is True or value == "1"


def compute_player_advanced_rows(players: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    for player in players:
        if not is_played(player):
            continue

        stats = player.get("statistics", {})
        minutes_text = stats.get("minutes", "0:00")
        if minutes_text in {"0", "0:00", "00:00", "PT0M", "PT0M0.00S"}:
            continue
        fga = stats.get("fieldGoalsAttempted", 0)
        fgm = stats.get("fieldGoalsMade", 0)
        tpa = stats.get("threePointersAttempted", 0)
        tpm = stats.get("threePointersMade", 0)
        fta = stats.get("freeThrowsAttempted", 0)
        points = stats.get("points", 0)
        turnovers = stats.get("turnovers", 0)
        assists = stats.get("assists", 0)
        ts_pct = round4(safe_div(points, 2 * (fga + 0.44 * fta)))
        role_info = get_player_role_info(player.get("name", ""))
        usage_proxy = round2(fga + 0.44 * fta + turnovers)
        playmaking_proxy = assists
        finishing_proxy = round2(points + ts_pct * 100)
        base_row = {
            "player_name": player.get("name", ""),
            "starter": player.get("starter", "0") == "1",
            "minutes": minutes_text,
            "minutes_seconds": minutes_text_to_seconds(minutes_text),
            "points": points,
            "rebounds": stats.get("reboundsTotal", 0),
            "assists": assists,
            "plus_minus": stats.get("plusMinusPoints", 0),
            "efg_pct": round4(safe_div(fgm + 0.5 * tpm, fga)),
            "ts_pct": ts_pct,
            "three_pa_rate": round4(safe_div(tpa, fga)),
            "ast_to_ratio": round2(assists / turnovers) if turnovers else round2(float(assists)),
            "fga": fga,
            "fgm": fgm,
            "tpa": tpa,
            "tpm": tpm,
            "fta": fta,
            "turnovers": turnovers,
            "role_tier": role_info["tier"],
            "role_archetype": role_info["archetype"],
            "role_priority": role_priority_value(role_info["tier"]),
            "usage_proxy": usage_proxy,
            "playmaking_proxy": playmaking_proxy,
            "finishing_proxy": finishing_proxy,
        }
        base_row["offensive_impact"] = classify_offensive_impact(base_row, role_info)

        rows.append(
            PlayerAdvancedRow(
                player_name=base_row["player_name"],
                starter=base_row["starter"],
                minutes=base_row["minutes"],
                minutes_seconds=base_row["minutes_seconds"],
                points=base_row["points"],
                rebounds=base_row["rebounds"],
                assists=base_row["assists"],
                plus_minus=base_row["plus_minus"],
                efg_pct=base_row["efg_pct"],
                ts_pct=base_row["ts_pct"],
                three_pa_rate=base_row["three_pa_rate"],
                ast_to_ratio=base_row["ast_to_ratio"],
                fga=base_row["fga"],
                fgm=base_row["fgm"],
                tpa=base_row["tpa"],
                tpm=base_row["tpm"],
                fta=base_row["fta"],
                turnovers=base_row["turnovers"],
                role_tier=base_row["role_tier"],
                role_archetype=base_row["role_archetype"],
                role_priority=base_row["role_priority"],
                usage_proxy=base_row["usage_proxy"],
                playmaking_proxy=base_row["playmaking_proxy"],
                finishing_proxy=base_row["finishing_proxy"],
                offensive_impact=base_row["offensive_impact"],
            ).to_dict()
        )

    rows.sort(key=lambda row: (row["minutes_seconds"], row["points"]), reverse=True)
    return rows
