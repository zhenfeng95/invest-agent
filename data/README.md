# data/ — 把文件扔进来即可

| 目录 | 放什么 |
|------|--------|
| `raw/screener/` | 用户第一层选股池（`pool-latest.csv`）；Agent 全量五选一后写入日报 §7 |
| `raw/tweets/` | 历史推文、社媒内容 |
| `raw/trades/` | 交易记录（CSV / JSON） |
| `raw/notes/` | 个人笔记、研究心得 |
| `raw/references/` | 参考文章、研报摘录 |
| `feedback/ratings.json` | 对 Agent 产出的评分 |
| `public/` | 对外可读（个人站可直链）：`economic-calendar.json` 金十财经日历；`ashare-daily-snapshot.csv` A股收盘评分快照（ECharts） |

Agent 会提炼后直接更新 `soul/my-soul.md` 与 `memory/`，不设中间层。

## `public/ashare-daily-snapshot.csv`

A 股收盘日报的评分快照。每天 17:00 写完 `output/daily/ashare-close-YYYY-MM-DD.md` 后跑 `python3 tools/ashare_daily_snapshot.py` 全量重扫生成。本机补跑同一条命令即可。

直链（进 **main** 后）：

- `https://raw.githubusercontent.com/zhenfeng95/invest-agent/main/data/public/ashare-daily-snapshot.csv`
- `https://cdn.jsdelivr.net/gh/zhenfeng95/invest-agent@main/data/public/ashare-daily-snapshot.csv`（浏览器 CORS 更稳）

| 列 | 含义 | ECharts |
| -- | ---- | ------- |
| `date` | 交易日 `YYYY-MM-DD` | xAxis |
| `score` | 市场评分 0–100 | yAxis 柱高 |
| `confidence` | 高 / 中 / 低 | tooltip |
| `market_state` | 六选一周期 | tooltip |
| `strategy` | 防守 / 轻仓试错 / 积极参与 / 进攻 | tooltip；柱颜色 |
| `attack_ok` | `true` / `false` / 空（9/9 前日报无进攻四条件） | tooltip |
| `attack_met` | 0–4 / 空 | tooltip |
| `attack_note` | 四条件一行说明 | tooltip |
| `account_focus` | 账户重心 | tooltip |
| `suggested_position` | 建议总仓展示串 | tooltip |
| `position_low` / `position_high` | 仓位数字带（`≤20%` 时 low 为空） | 可选 |
| `operation_hint` | §1 操作提示 | tooltip |

柱颜色建议：防守 `#8c8c8c`；轻仓试错 `#faad14`；积极参与 `#fa8c16`；进攻 `#f5222d`。空字段不要写「未获取」。UTF-8，无 BOM。
