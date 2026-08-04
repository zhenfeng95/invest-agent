# 快速上手（给零基础用户）

这份说明用最直白的话，带你把「私人投研助手」跑起来。你不需要会写代码。

---

## 你将得到什么

一个会记住你投资习惯的助手：能写财经日报、查市场信号、帮你写推文/研报草稿。你往文件夹里扔数据，它会越来越懂你。

---

## 第一步：准备电脑上的工具

### 1. 安装 Cursor 或 Claude Code（二选一即可）

**方式 A — 用 Cursor（推荐，你现在很可能已经在用）**

1. 打开 [https://cursor.com](https://cursor.com) 下载并安装 Cursor
2. 打开 Cursor 后，点左上角 **File → Open Folder**
3. 选中本项目所在文件夹（名字一般是 `invest-agent`）
4. 打开后，左侧应能看到 `soul`、`data`、`output` 等文件夹

**方式 B — 用 Claude Code（命令行）**

1. 按 Anthropic 官方说明安装 Claude Code
2. 在终端进入本项目文件夹，输入 `claude` 回车即可对话

### 2.（可选）安装两个插件 — 仅 Claude Code 需要

如果你用的是 **Claude Code**，建议安装长期记忆和定时任务插件。在 Claude Code 对话里依次输入：

```
/plugin marketplace add thedotmack/claude-mem
/plugin install claude-mem
```

```
/plugin marketplace add jshchnz/claude-code-scheduler
/plugin install scheduler@claude-code-scheduler
```

装完后**完全退出再重新打开** Claude Code。

> 若你主要用 Cursor 对话：可以先跳过插件。日常问答、写日报草稿、读你的数据，打开本项目对话即可。定时自动跑任务需要 Claude Code + 调度插件 + API Key。

---

## 第二步：配置定时任务用的密钥（想自动跑日报再做）

日常和助手聊天，用你的订阅即可。  
**只有「到点自动写日报」这类后台任务**才需要 API Key。

1. 打开浏览器，进入 [https://console.anthropic.com/](https://console.anthropic.com/)，注册并登录
2. 点 **Settings → API Keys → Create Key**
3. 复制生成的一串以 `sk-ant-` 开头的密钥（只显示一次，先粘到备忘录）
4. 在本项目根目录，把 `.env.example` **复制**一份，改名为 `.env`
   - Mac：可在终端进入项目文件夹后执行：`cp .env.example .env`
5. 用记事本 / Cursor 打开 `.env`，把 `你的密钥` 换成刚才复制的真实密钥并保存
6. 建议在 Anthropic 控制台里设置**每月消费上限**，防止费用意外升高

**千万不要**把 `.env` 发给别人，也不要上传到公开网盘。

---

## 第三步：告诉助手「你是谁」

1. 在左侧找到文件夹 `soul`
2. 打开文件 `my-soul.md`
3. 按里面的标题，用自己的话填写（不用一次写完美）：
   - 你相信什么投资逻辑
   - 你常看哪些股票 / 币
   - 你怎么买、怎么卖
   - 你能承受多大回撤
   - 你对现在宏观环境的看法
4. 保存文件（Mac 一般是 `Command + S`）

写得越具体，助手越像「懂你的搭档」。空着的部分以后也可以让助手根据你扔进去的数据自动补。

---

## 第四步：开始对话

1. 在 Cursor 里打开右侧 **Chat / Agent** 面板（或 Claude Code 的对话框）
2. 随便问一句，例如：
   - 「按我的关注列表，帮我看看今天市场重点」
   - 「用日报模板写一份今日财经简报」
   - 「解释一下什么是 RSI」
3. 助手会先默默读取 `soul` 和 `memory` 里的信息，再回答你
4. 生成的正式产出，通常会保存在 `output` 文件夹：
   - `output/daily` — 日报
   - `output/research` — 研究/周报月报
   - `output/signals` — 抄底等信号
   - `output/content` — 推文、选题等草稿

---

## 第五步：往 data 里「喂」数据（越喂越聪明）

你只需要把文件放进对应文件夹，下次对话时跟助手说「消化一下 data 里的新文件」即可。

| 放这里 | 放什么 |
|--------|--------|
| `data/raw/tweets/` | 你以前发过的推文、社媒文案（txt/md 均可） |
| `data/raw/trades/` | 交易记录（Excel 导出成 CSV，或 JSON） |
| `data/raw/notes/` | 自己的笔记、心得 |
| `data/raw/references/` | 觉得有用的研报、文章（可粘贴成 md） |

对助手某次产出不满意时，可以编辑 `data/feedback/ratings.json`，按示例加一条评分和意见，让它下次改风格。

**建议节奏**

- 第 1 周：填好 `my-soul.md`，导入一些历史推文或交易记录
- 第 2–3 周：经常对产出打分，继续扔笔记
- 第 4 周起：抽查产出即可，偶尔补充新数据

---

## 第六步：查看产出

1. 打开左侧 `output` 文件夹
2. 点进 `daily` / `research` / `signals` / `content`
3. 用 Cursor 双击任意 `.md` 文件即可阅读

---

## 第七步：定时任务怎么管（装了调度插件之后）

在 Claude Code 里可以输入：

| 你输入 | 会发生什么 |
|--------|------------|
| `/scheduler list` | 列出所有定时任务 |
| `/scheduler pause 某任务编号` | 暂停某个任务 |
| `/scheduler resume 某任务编号` | 恢复某个任务 |
| `/scheduler delete 某任务编号` | 删除某个任务 |

预设任务（时间均为**北京时间**）写在 `scheduler/rules.md`，包括：

- 每天 08:00 财经日报
- 工作日 21:00 盘前提醒
- 每天 09:00 检查 S&P 500 / BTC 抄底信号
- 周日 10:00 周度回顾
- 每月 1 日 10:00 月度复盘
- 周三 10:00 内容选题建议

**第一次注册**：打开对话，对助手说：

> 请读取 `scheduler/rules.md`，用调度器帮我注册里面所有定时任务。

它会按文件里的规则创建任务。之后你改了 `rules.md`，再告诉助手「按新规则同步定时任务」即可。

---

## 常见问题

**Q：我不会填 my-soul.md，能空着吗？**  
可以先空着，但建议至少写「关注哪些标的」和「风险偏好」两段。助手发现几乎为空时会提醒你。

**Q：助手会不会乱删我电脑文件？**  
项目里 `.claude/settings.json` 已禁止高危命令（如强制删除整盘、sudo 等）。默认只在本项目目录内读写。

**Q：内容能当买卖指令吗？**  
不能。所有投研输出仅供参考，不构成投资建议。最终决策由你自己负责。

**Q：API Key 和订阅会不会重复扣费？**  
日常聊天走订阅；只有后台定时任务用 API Key。可在控制台设消费上限。

---

## 下一步可以做什么

1. 填完 `soul/my-soul.md`
2. 扔几份交易记录或笔记到 `data/raw/`
3. 对助手说：「按工作流加载我的画像，然后用日报模板写一版今日简报」

祝你把数据护城河建起来。
