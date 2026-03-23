from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import BASE

def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

def get_generated_index_path(output_dir: Path) -> Path:
    return output_dir / "generated_reports_index.json"

def get_reports_manifest_path(output_dir: Path) -> Path:
    return output_dir / "reports_manifest.json"

def load_generated_index(output_dir: Path) -> dict[str, Any]:
    path = get_generated_index_path(output_dir)
    default = {"generated_event_ids": [], "last_checked_at": ""}
    if not path.exists():
        return default
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default
    event_ids = data.get("generated_event_ids", [])
    if not isinstance(event_ids, list):
        event_ids = []
    return {
        "generated_event_ids": [str(item) for item in event_ids],
        "last_checked_at": data.get("last_checked_at", ""),
    }

def save_generated_index(output_dir: Path, index_data: dict[str, Any]) -> None:
    payload = {
        "generated_event_ids": sorted({str(item) for item in index_data.get("generated_event_ids", [])}),
        "last_checked_at": utc_now_iso(),
    }
    write_json(get_generated_index_path(output_dir), payload)

def load_reports_manifest(output_dir: Path) -> list[dict[str, Any]]:
    path = get_reports_manifest_path(output_dir)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    return data if isinstance(data, list) else []

def save_reports_manifest(output_dir: Path, manifest: list[dict[str, Any]]) -> None:
    write_json(get_reports_manifest_path(output_dir), manifest)

def update_reports_manifest(output_dir: Path, analysis: dict[str, Any], markdown_path: Path) -> None:
    manifest = load_reports_manifest(output_dir)
    event_id = str(analysis.get("event_id") or analysis.get("game_id") or "")
    entry = {
        "event_id": event_id,
        "game_date": analysis.get("game_date", ""),
        "opponent": analysis.get("opponent", ""),
        "result": analysis.get("result", ""),
        "markdown_path": str(markdown_path),
        "generated_at": utc_now_iso(),
    }
    manifest = [item for item in manifest if str(item.get("event_id", "")) != event_id]
    manifest.append(entry)
    manifest.sort(key=lambda item: (item.get("game_date", ""), item.get("event_id", "")))
    save_reports_manifest(output_dir, manifest)

def recover_generated_event_ids(output_dir: Path) -> set[str]:
    recovered: set[str] = set()
    if not output_dir.exists():
        return recovered
    for path in output_dir.glob("*/celtics_diagnosis.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        event_id = data.get("event_id") or data.get("game_id")
        if event_id:
            recovered.add(str(event_id))
    return recovered

def ensure_generated_index(output_dir: Path) -> dict[str, Any]:
    index_data = load_generated_index(output_dir)
    recovered = recover_generated_event_ids(output_dir)
    merged = sorted(set(index_data.get("generated_event_ids", [])) | recovered)
    index_data["generated_event_ids"] = merged
    save_generated_index(output_dir, index_data)
    return index_data

from .fetchers import build_analysis_from_espn_event, get_completed_celtics_events, write_csv
from .renderers import build_celtics_markdown

def get_missing_event_items(output_dir: Path, limit_backfill: int | None = None, force_regenerate: bool = False) -> list[dict[str, Any]]:
    completed_events = get_completed_celtics_events()
    if force_regenerate:
        missing = completed_events
    else:
        index_data = ensure_generated_index(output_dir)
        generated = set(index_data.get("generated_event_ids", []))
        missing = [item for item in completed_events if item["event_id"] not in generated]
    if limit_backfill is not None:
        missing = missing[-limit_backfill:]
    return missing

def get_missing_event_ids(output_dir: Path, limit_backfill: int | None = None, force_regenerate: bool = False) -> list[str]:
    return [item["event_id"] for item in get_missing_event_items(output_dir, limit_backfill, force_regenerate)]

def build_event_daily_report_placeholder(analysis: dict[str, Any], source_mode: str = "espn_summary") -> dict[str, Any]:
    return {
        "game_date": analysis.get("game_date", ""),
        "games": [],
        "teams": [],
        "players": [],
        "source_mode": source_mode,
        "event_id": str(analysis.get("event_id") or analysis.get("game_id") or ""),
    }

def report_exists_for_event(output_dir: Path, markdown_dir: Path, event_id: str) -> bool:
    index_data = ensure_generated_index(output_dir)
    if str(event_id) in set(index_data.get("generated_event_ids", [])):
        return True
    for path in output_dir.glob("*/celtics_diagnosis.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        existing_event_id = data.get("event_id") or data.get("game_id")
        if str(existing_event_id) == str(event_id):
            return True
    return False

def persist_generated_report(
    analysis: dict[str, Any],
    daily_report: dict[str, Any],
    output_dir: Path,
    markdown_dir: Path,
    force_regenerate: bool = False,
) -> dict[str, Any]:
    event_id = str(analysis.get("event_id") or analysis.get("game_id") or daily_report.get("event_id") or "")
    date_dir = output_dir / (daily_report["game_date"] or analysis.get("game_date") or "unknown_date")
    markdown_path = markdown_dir / f"{daily_report['game_date'] or analysis.get('game_date')}.md"

    if not force_regenerate and event_id and report_exists_for_event(output_dir, markdown_dir, event_id):
        return {"status": "skipped", "event_id": event_id, "markdown_path": markdown_path, "date_dir": date_dir}

    date_dir.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)

    analysis_payload = {
        **analysis,
        "event_id": event_id,
        "game_date": analysis.get("game_date", daily_report.get("game_date", "")),
        "source_mode": daily_report.get("source_mode", analysis.get("source_mode", "espn_summary")),
    }
    daily_payload = {
        **daily_report,
        "event_id": event_id,
        "game_date": daily_report.get("game_date", analysis.get("game_date", "")),
    }

    write_json(date_dir / "daily_report.json", daily_payload)
    write_csv(date_dir / "games.csv", daily_payload.get("games", []))
    write_csv(date_dir / "teams.csv", daily_payload.get("teams", []))
    write_csv(date_dir / "players.csv", daily_payload.get("players", []))
    write_json(date_dir / "celtics_diagnosis.json", analysis_payload)
    markdown_path.write_text(build_celtics_markdown(analysis_payload), encoding="utf-8")

    index_data = ensure_generated_index(output_dir)
    generated = set(index_data.get("generated_event_ids", []))
    generated.add(event_id)
    index_data["generated_event_ids"] = sorted(generated)
    save_generated_index(output_dir, index_data)
    update_reports_manifest(output_dir, analysis_payload, markdown_path)

    return {
        "status": "generated",
        "event_id": event_id,
        "markdown_path": markdown_path,
        "date_dir": date_dir,
        "analysis": analysis_payload,
        "daily_report": daily_payload,
    }

def generate_event_report(
    event_id: str,
    output_dir: Path,
    markdown_dir: Path,
    force_regenerate: bool = False,
) -> dict[str, Any]:
    analysis = build_analysis_from_espn_event(event_id)
    daily_report = build_event_daily_report_placeholder(analysis, source_mode="espn_summary")
    return persist_generated_report(analysis, daily_report, output_dir, markdown_dir, force_regenerate=force_regenerate)

def backfill_missing_reports(
    output_dir: Path,
    markdown_dir: Path,
    quiet: bool = False,
    force_regenerate: bool = False,
    limit_backfill: int | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    missing_items = get_missing_event_items(output_dir, limit_backfill=limit_backfill, force_regenerate=force_regenerate)
    generated: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []

    if not quiet:
        if missing_items:
            print(f"检查到 {len(missing_items)} 场缺失比赛")
        else:
            print("未发现缺失比赛")

    if dry_run:
        if not quiet and missing_items:
            print(f"发现缺失比赛 {len(missing_items)} 场：")
            for item in missing_items:
                print(f"- {item['game_date']} vs {item['opponent']}")
        return {"missing": missing_items, "generated": generated, "skipped": skipped, "failed": failed}

    for item in missing_items:
        if not quiet:
            print(f"正在补生成：{item['game_date']} vs {item['opponent']}")
        try:
            result = generate_event_report(
                item["event_id"],
                output_dir,
                markdown_dir,
                force_regenerate=force_regenerate,
            )
        except Exception as error:
            failed.append({"event_id": item["event_id"], "error": str(error), "game_date": item["game_date"]})
            if not quiet:
                print(f"补生成失败：event_id {item['event_id']} - {error}")
            continue
        if result["status"] == "generated":
            generated.append(item)
            if not quiet:
                print(f"已生成：{result['markdown_path'].name}")
        else:
            skipped.append(item)
            if not quiet:
                print(f"已跳过：event_id {item['event_id']}（已存在）")

    if not quiet:
        print(f"补跑完成，共生成 {len(generated)} 场报告")
        if failed:
            print(f"补跑失败 {len(failed)} 场")

    return {"missing": missing_items, "generated": generated, "skipped": skipped, "failed": failed}
