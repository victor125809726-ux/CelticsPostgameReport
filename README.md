# Celtics Postgame Report

Boston Celtics 赛后诊断系统。

当前项目会抓取 Celtics 比赛数据，并生成：

- 单场赛后诊断 JSON
- Markdown 日报
- 历史比赛补跑索引
- `launchd` 定时任务支持

## 目录结构

```text
CelticsPostgameReport/
├── run.py
├── README.md
└── celtics_postgame_report/
    ├── __init__.py
    ├── config.py
    ├── fetchers.py
    ├── main.py
    ├── metrics.py
    ├── narrative.py
    ├── renderers.py
    ├── roles.py
    ├── storage.py
    └── trends.py
```

## 运行方式

直接运行入口脚本：

```bash
python3 "/Users/shiyan/CelticsPostgameReport/run.py"
```

回跑上一场已结束的 Celtics 比赛：

```bash
python3 "/Users/shiyan/CelticsPostgameReport/run.py" --last-completed-game
```

强制重生成上一场比赛报告：

```bash
python3 "/Users/shiyan/CelticsPostgameReport/run.py" --last-completed-game --force-regenerate
```

检查是否有漏掉的历史比赛：

```bash
python3 "/Users/shiyan/CelticsPostgameReport/run.py" --backfill-missing --dry-run
```

补跑缺失比赛：

```bash
python3 "/Users/shiyan/CelticsPostgameReport/run.py" --backfill-missing
```

## 输出位置

历史数据输出目录：

```text
/Users/shiyan/celtics_reports
```

Obsidian Markdown 输出目录：

```text
/Users/shiyan/Library/Mobile Documents/iCloud~md~obsidian/Documents/Obsidian/Celtics Report
```

## 常用参数

- `--last-completed-game`：回跑上一场已结束比赛
- `--event-id`：指定 ESPN event id 生成单场报告
- `--backfill-missing`：补跑缺失比赛
- `--force-regenerate`：强制覆盖重生成
- `--limit-backfill N`：补跑时只处理最近 N 场缺失比赛
- `--dry-run`：只检查，不真正生成文件
- `--quiet`：安静模式

## 定时任务

查看状态：

```bash
python3 "/Users/shiyan/CelticsPostgameReport/run.py" --launchd-status
```

安装或刷新定时任务：

```bash
python3 "/Users/shiyan/CelticsPostgameReport/run.py" --install-launchd --schedule-hour 15 --schedule-minute 0
```

卸载定时任务：

```bash
python3 "/Users/shiyan/CelticsPostgameReport/run.py" --uninstall-launchd
```

## 说明

- 项目保留了补跑机制，会检查是否有已结束但未生成报告的比赛
- Markdown 报告会包含比赛主线、核心指标、原因、风险点、趋势分析等内容
- 历史索引和 manifest 会写入数据目录，方便后续追踪
