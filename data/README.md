# data/ — 把文件扔进来即可

| 目录 | 放什么 |
|------|--------|
| `raw/screener/` | 已停用投喂；公式一层由脚本写入 `output/screener/`；二筛只进日报 §15.6 |
| `raw/tweets/` | 历史推文、社媒内容 |
| `raw/trades/` | 交易记录（CSV / JSON） |
| `raw/notes/` | 个人笔记、研究心得 |
| `raw/references/` | 参考文章、研报摘录 |
| `feedback/ratings.json` | 对 Agent 产出的评分 |

Agent 会提炼后直接更新 `soul/my-soul.md` 与 `memory/`，不设中间层。
