# data/ — 把文件扔进来即可

| 目录 | 放什么 |
|------|--------|
| `raw/screener/` | 用户第一层选股池（`pool-latest.csv`）；Agent 全量五选一后写入日报 §7 |
| `raw/tweets/` | 历史推文、社媒内容 |
| `raw/trades/` | 交易记录（CSV / JSON） |
| `raw/notes/` | 个人笔记、研究心得 |
| `raw/references/` | 参考文章、研报摘录 |
| `feedback/ratings.json` | 对 Agent 产出的评分 |
| `public/` | 对外可读 JSON（个人站可直链）；如 `economic-calendar.json` 金十财经日历 |

Agent 会提炼后直接更新 `soul/my-soul.md` 与 `memory/`，不设中间层。
