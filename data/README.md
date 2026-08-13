# data/ — 把文件扔进来即可

| 目录 | 放什么 |
|------|--------|
| `raw/screener/` | 用户第一层选股池（`pool-latest.csv`）；Agent 全量四选一后写入日报 §9 |
| `raw/tweets/` | 历史推文、社媒内容 |
| `raw/trades/` | 交易记录（CSV / JSON） |
| `raw/notes/` | 个人笔记、研究心得 |
| `raw/references/` | 参考文章、研报摘录 |
| `feedback/ratings.json` | 对 Agent 产出的评分 |

Agent 会提炼后直接更新 `soul/my-soul.md` 与 `memory/`，不设中间层。
