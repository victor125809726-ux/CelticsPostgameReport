#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import plistlib
import subprocess
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError

from .config import DEFAULT_MARKDOWN_DIR, DEFAULT_OUTPUT_DIR, DEFAULT_SCHEDULE_HOUR, DEFAULT_SCHEDULE_MINUTE, LAUNCHD_LABEL
from .fetchers import analyze_celtics_game, build_daily_report, get_boxscore, get_last_completed_event_id, get_scoreboard, get_standings
from .storage import backfill_missing_reports, ensure_generated_index, generate_event_report, persist_generated_report, write_json
from .fetchers import write_csv
from .renderers import build_celtics_markdown

def get_launch_agents_dir() -> Path:
    return Path.home() / "Library" / "LaunchAgents"

def get_launchd_plist_path() -> Path:
    return get_launch_agents_dir() / f"{LAUNCHD_LABEL}.plist"

def get_log_dir() -> Path:
    return Path.home() / "Library" / "Logs" / "celtics-report"

def build_launchd_plist(script_path: Path, output_dir: Path, markdown_dir: Path, hour: int, minute: int) -> dict[str, Any]:
    log_dir = get_log_dir()
    return {
        "Label": LAUNCHD_LABEL,
        "ProgramArguments": [
            sys.executable,
            str(script_path),
            "--output-dir",
            str(output_dir),
            "--markdown-dir",
            str(markdown_dir),
            "--quiet",
        ],
        "StartCalendarInterval": {"Hour": hour, "Minute": minute},
        "WorkingDirectory": str(script_path.parent),
        "StandardOutPath": str(log_dir / "stdout.log"),
        "StandardErrorPath": str(log_dir / "stderr.log"),
        "RunAtLoad": False,
    }

def run_launchctl(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["launchctl", *args], capture_output=True, text=True, check=check)

def install_launchd_job(script_path: Path, output_dir: Path, markdown_dir: Path, hour: int, minute: int) -> None:
    get_launch_agents_dir().mkdir(parents=True, exist_ok=True)
    get_log_dir().mkdir(parents=True, exist_ok=True)
    plist_path = get_launchd_plist_path()
    with plist_path.open("wb") as file:
        plistlib.dump(build_launchd_plist(script_path, output_dir, markdown_dir, hour, minute), file)
    domain_target = f"gui/{os.getuid()}"
    run_launchctl("bootout", domain_target, str(plist_path), check=False)
    run_launchctl("bootstrap", domain_target, str(plist_path))

def uninstall_launchd_job() -> None:
    plist_path = get_launchd_plist_path()
    if plist_path.exists():
        run_launchctl("bootout", f"gui/{os.getuid()}", str(plist_path), check=False)
        plist_path.unlink()

def get_launchd_status() -> tuple[bool, str]:
    plist_path = get_launchd_plist_path()
    if not plist_path.exists():
        return False, "未安装"
    result = run_launchctl("print", f"gui/{os.getuid()}/{LAUNCHD_LABEL}", check=False)
    if result.returncode == 0:
        return True, result.stdout.strip()
    return False, result.stderr.strip() or result.stdout.strip() or "已安装，但当前未加载"

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Boston Celtics 赛后诊断系统")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="输出目录")
    parser.add_argument("--markdown-dir", default=str(DEFAULT_MARKDOWN_DIR), help="Markdown 输出目录")
    parser.add_argument("--last-completed-game", action="store_true", help="回跑上一场已结束的 Celtics 比赛")
    parser.add_argument("--event-id", default="", help="指定 ESPN event id 生成单场诊断")
    parser.add_argument("--backfill-missing", action="store_true", help="补跑所有缺失的已结束比赛")
    parser.add_argument("--force-regenerate", action="store_true", help="即使已存在也重新生成并覆盖")
    parser.add_argument("--limit-backfill", type=int, default=None, help="补跑时最多处理最近 N 场缺失比赛")
    parser.add_argument("--dry-run", action="store_true", help="只打印缺失比赛，不真正生成文件")
    parser.add_argument("--quiet", action="store_true", help="安静模式")
    parser.add_argument("--install-launchd", action="store_true", help="安装 launchd 定时任务")
    parser.add_argument("--uninstall-launchd", action="store_true", help="卸载 launchd 定时任务")
    parser.add_argument("--launchd-status", action="store_true", help="查看 launchd 定时任务状态")
    parser.add_argument("--schedule-hour", type=int, default=DEFAULT_SCHEDULE_HOUR, help="定时任务小时")
    parser.add_argument("--schedule-minute", type=int, default=DEFAULT_SCHEDULE_MINUTE, help="定时任务分钟")
    return parser.parse_args()

def main() -> int:
    args = parse_args()
    if not 0 <= args.schedule_hour <= 23:
        print("schedule-hour 必须在 0 到 23 之间", file=sys.stderr)
        return 1
    if not 0 <= args.schedule_minute <= 59:
        print("schedule-minute 必须在 0 到 59 之间", file=sys.stderr)
        return 1

    script_path = Path(sys.argv[0]).resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    markdown_dir = Path(args.markdown_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    markdown_dir.mkdir(parents=True, exist_ok=True)

    if args.install_launchd:
        try:
            install_launchd_job(script_path, output_dir, markdown_dir, args.schedule_hour, args.schedule_minute)
        except Exception as error:
            print(f"安装 launchd 定时任务失败: {error}", file=sys.stderr)
            return 1
        print(f"已安装定时任务: {LAUNCHD_LABEL}")
        print(f"执行时间: 每天 {args.schedule_hour:02d}:{args.schedule_minute:02d}")
        print(f"plist 文件: {get_launchd_plist_path()}")
        print(f"日志目录: {get_log_dir()}")
        return 0

    if args.uninstall_launchd:
        try:
            uninstall_launchd_job()
        except Exception as error:
            print(f"卸载 launchd 定时任务失败: {error}", file=sys.stderr)
            return 1
        print(f"已卸载定时任务: {LAUNCHD_LABEL}")
        return 0

    if args.launchd_status:
        installed, detail = get_launchd_status()
        print(f"定时任务标签: {LAUNCHD_LABEL}")
        print(f"状态: {'已安装' if installed else '未安装或未加载'}")
        if detail:
            print(detail)
        return 0

    try:
        ensure_generated_index(output_dir)

        if args.backfill_missing or args.dry_run:
            backfill_missing_reports(
                output_dir,
                markdown_dir,
                quiet=args.quiet,
                force_regenerate=args.force_regenerate,
                limit_backfill=args.limit_backfill,
                dry_run=args.dry_run,
            )
            return 0

        backfill_missing_reports(
            output_dir,
            markdown_dir,
            quiet=args.quiet,
            force_regenerate=False,
            limit_backfill=args.limit_backfill,
            dry_run=False,
        )

        if args.event_id or args.last_completed_game:
            event_id = args.event_id or get_last_completed_event_id()
            result = generate_event_report(
                event_id,
                output_dir,
                markdown_dir,
                force_regenerate=args.force_regenerate,
            )
            if result["status"] == "skipped":
                if not args.quiet:
                    print(f"已跳过：event_id {event_id}（已存在）")
                return 0
            celtics_analysis = result["analysis"]
            daily_report = result["daily_report"]
            markdown_path = result["markdown_path"]
        else:
            scoreboard_data = get_scoreboard()
            standings_data = get_standings()
            daily_report = build_daily_report(scoreboard_data, standings_data)
            celtics_analysis = analyze_celtics_game(daily_report)
            event_id = str(celtics_analysis.get("event_id") or celtics_analysis.get("game_id") or "")
            markdown_path = markdown_dir / f"{daily_report['game_date']}.md"

            if celtics_analysis["played_today"] and event_id:
                result = persist_generated_report(
                    celtics_analysis,
                    {
                        **daily_report,
                        "source_mode": daily_report.get("source_mode", "daily_report"),
                        "event_id": event_id,
                    },
                    output_dir,
                    markdown_dir,
                    force_regenerate=args.force_regenerate,
                )
                if result["status"] == "skipped":
                    if not args.quiet:
                        print(f"已跳过：event_id {event_id}（已存在）")
                    return 0
                celtics_analysis = result["analysis"]
                daily_report = result["daily_report"]
                markdown_path = result["markdown_path"]
            else:
                date_dir = output_dir / (daily_report["game_date"] or "unknown_date")
                date_dir.mkdir(parents=True, exist_ok=True)
                write_json(date_dir / "daily_report.json", daily_report)
                write_csv(date_dir / "games.csv", daily_report.get("games", []))
                write_csv(date_dir / "teams.csv", daily_report.get("teams", []))
                write_csv(date_dir / "players.csv", daily_report.get("players", []))
                write_json(
                    date_dir / "celtics_diagnosis.json",
                    {
                        **celtics_analysis,
                        "event_id": "",
                        "source_mode": daily_report.get("source_mode", "daily_report"),
                        "game_date": celtics_analysis.get("game_date", daily_report.get("game_date", "")),
                    },
                )
                markdown_path.parent.mkdir(parents=True, exist_ok=True)
                markdown_path.write_text(build_celtics_markdown(celtics_analysis), encoding="utf-8")
    except HTTPError as error:
        print(f"请求数据失败，HTTP 状态码: {error.code}", file=sys.stderr)
        return 1
    except URLError as error:
        print(f"网络请求失败: {error.reason}", file=sys.stderr)
        return 1
    except Exception as error:
        print(f"执行失败: {error}", file=sys.stderr)
        return 1

    if not args.quiet:
        if celtics_analysis["played_today"]:
            result_text = "赢球" if celtics_analysis["result"] == "win" else "输球"
            print(f"Celtics 比赛日期: {celtics_analysis['game_date']}")
            print(
                f"Celtics {celtics_analysis['team_score']} : {celtics_analysis['opponent_score']} "
                f"{celtics_analysis['opponent']} [{result_text}]"
            )
            print(f"Net Rating: {celtics_analysis['celtics_metrics']['net_rating']:.2f}")
            print(f"Markdown 已保存到: {markdown_path}")
        else:
            print(celtics_analysis["message"])
            print(f"Markdown 已保存到: {markdown_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
