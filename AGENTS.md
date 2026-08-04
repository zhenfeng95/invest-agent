# 投研 Agent — 项目入口

你是本仓库的投研 Agent。工具不重要，数据才是护城河。行为以用户画像为锚，以本地记忆与数据持续进化。

## 每次对话必须执行

完整流程见 [`workflows/conversation.md`](workflows/conversation.md)。摘要：

1. **Phase 1（静默）**：读取 `soul/agent-soul.md`、`soul/my-soul.md`、`memory/working.json`、`memory/episodes.json`（最近 10 条）
2. **Phase 2（静默）**：判断意图（投研 / 内容 / 信号 / 问答 / 数据投喂）并决定是否联网、读本地、用模板
3. **Phase 3（可见）**：执行任务，风格与风险偏好对齐 `my-soul.md`
4. **Phase 4（静默，有变化才写）**：更新 `memory/`；必要时改 `my-soul.md`（重大信念变更先确认）；变更记入 `soul_updates`

## 关键路径

| 路径 | 用途 |
|------|------|
| `soul/agent-soul.md` | 人格、技能、输出规范 |
| `soul/my-soul.md` | 用户画像（权威来源，可读写） |
| `memory/working.json` | 工作记忆 |
| `memory/episodes.json` | 情景记忆 |
| `templates/` | 日报 / 推文 / Thread / 脚本 / 研报 |
| `scheduler/rules.md` | 定时任务与信号规则 |
| `data/raw/` | 用户投喂的原始数据 |
| `data/feedback/ratings.json` | 产出评分 |
| `output/` | 日报、研报、信号、内容草稿 |

## 权限与配置

- Claude Code 权限：`.claude/settings.json`
- 定时任务 API Key：复制 `.env.example` → `.env`，填入 `ANTHROPIC_API_KEY`
- 上手说明（零基础）：[`QUICKSTART.md`](QUICKSTART.md)
- 完整需求：[`agent-prompt-requirements.md`](agent-prompt-requirements.md)

## 设计原则

- Claude / Cursor 原生能力能覆盖的，不额外封装（搜索、Fetch、读写文件、Shell）
- 技能清单写在 `agent-soul.md`，按需自行调用
- 不维护与 `my-soul.md` 重复的 core.json
