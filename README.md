# 个人风格书评生成器

上传电子书（docx / epub / mobi / azw3），自动生成**你自己风格**的书评。
再上传你过去的书评，软件会学习你的语气、句式、结构和口头禅。

## 当前进度

已完成 P0–P5（CLI 与 GUI 均可跑通全流程）。

| 阶段 | 状态 | 说明 |
|---|---|---|
| P0 骨架 | 完成 | 配置层、SQLite、LLM 客户端（含 429 退避重试） |
| P1 解析 | 完成 | docx / epub / mobi / azw3 四种格式，均实测通过 |
| P2 理解 | 完成 | 智能分块 → 并发块摘要 → 阶段合并 → 全书理解卡 + 缓存 |
| P3 风格 | 完成 | 统计特征 + LLM 提炼 → 可编辑风格画像卡 |
| P4 生成 | 完成 | 3 档长度 × 5 种侧重，含防"内容简介化"与防泄底约束 |
| P5 GUI | 完成 | PySide6 Widgets，四个页面 + 后台线程 + 流式输出 |
| P6 打包 | 未开始 | PyInstaller |

## 图形界面

```bash
python -m bookreview.gui          # 或 python -m bookreview.cli gui
```

四个页面：

| 页面 | 能力 |
|---|---|
| 生成书评 | 选书（支持拖放）→ 构建理解卡（带进度条）→ 选风格卡/长度/侧重 → 流式生成 → 复制/导出 |
| 书评库 | 已生成的书评列表、预览、编辑后保存、导出 md/txt |
| 风格画像 | 从样本学习 / 导入导出 JSON / 可视化编辑自称·人设·剧透策略·语气滑块 |
| 设置 | 服务商、API Key、双模型分流、推理预算系数、并发，带连接测试 |

耗时操作全部走后台线程，界面不会卡死；长篇构建理解卡时会显示进度。

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置模型
python -m bookreview.cli switch deepseek              # 切换服务商，保留已填的 Key
python -m bookreview.cli config --key sk-xxxxxxxx     # 填 Key
python -m bookreview.cli ping                         # 验证连通性

# 3. 解析电子书
python -m bookreview.cli parse 我的书.epub

# 4. 生成全书理解卡（会缓存，重复调用不烧 token）
python -m bookreview.cli digest 我的书.epub

# 5. 学习你的书评风格（多篇用 --- 分隔）
python -m bookreview.cli style 我的书评.txt --name "我的风格"
python -m bookreview.cli profiles

# 或者导入现成的风格卡
python -m bookreview.cli import-profile style_presets/非帅_推理向.json

# 6. 生成书评
python -m bookreview.cli review 我的书.epub --profile 1 --length standard --focus general
```

也可以使用环境变量提供密钥（推荐，不会写入 `config.json`）：

```powershell
$env:BOOKREVIEW_API_KEY = "sk-xxxxxxxx"
```

理解卡缓存会绑定书籍内容、摘要模型和分块参数；修改这些设置后会自动重建，不会复用旧结果。
测试会通过 `BOOKREVIEW_DATA_DIR` 使用独立的临时数据库和日志目录，不会污染正式 `data` 数据。

## 服务商与模型

| provider | base_url | 默认模型 |
|---|---|---|
| deepseek | https://api.deepseek.com | `deepseek-v4-flash` |
| deepseek-pro | https://api.deepseek.com | `deepseek-v4-pro` |
| glm | https://open.bigmodel.cn/api/paas/v4 | `glm-4.7` |
| qwen | https://dashscope.aliyuncs.com/compatible-mode/v1 | `qwen-plus` |
| openai | https://api.openai.com/v1 | `gpt-4o-mini` |
| custom | 自行填写 | 自行填写 |

DeepSeek 官方（2026-09）已不再推荐 `deepseek-chat` / `deepseek-reasoner`，
现用 `deepseek-v4-flash`（快、便宜）与 `deepseek-v4-pro`（推理更强）。

### 双模型分流（省钱）

一本书的分块摘要要调用几十次，最终生成书评只有一次。所以两者分开配：

- `llm.model` —— **分块摘要**用，建议便宜的 `deepseek-v4-flash`
- `llm.review_model` —— **生成书评**用，建议 `deepseek-v4-pro`；留空则复用 `llm.model`

```bash
python -m bookreview.cli switch deepseek --review-model deepseek-v4-pro
```

### 推理模型的输出预算（重要）

`deepseek-v4-*` 是**推理模型**：思维链 token 和正文共用同一份 `max_tokens`。
按常规配置（比如 4096）生成长评时，思维链会把预算吃光，正文返回空字符串。

程序已内置补偿：请求预算 = `min(max_tokens × reasoning_reserve, max_output_cap)`，
默认 `reasoning_reserve = 4.0`、`max_output_cap = 32768`。
若仍被截断会明确报错提示调大，不会静默返回空。

换用非推理模型（如 GLM、qwen）时把 `reasoning_reserve` 设为 `1.0` 即可。

## 样本净化（重要）

你的"书评"文件里很可能混着 AI 生成的内容——比如自己写完又让 AI 润色过，
或者同时存了小红书版本。直接拿去学习，学到的会是 AI 的腔调，不是你的。

程序会自动剔除：给 AI 的指令行、`#User:` / `#DeepSeek:` 等对话标记、
"这是我润色后的版本"之后的全部内容、emoji、社媒标签行（`#推理小说 #本格推理`）、
"主要修改："这类元叙述。剔除记录会在学习时打印出来，可自行核对。

实测：一份 4017 字的文件（原文 + AI 润色版 + 小红书版）净化后精确保留 1574 字原文。

## 风格词 vs 内容词

统计层严格区分两者：
- **风格词**（只从语气/连接词白名单提取）：说实话、没想到、相当、结果…
- **内容词**（这本书讲什么，禁止作为风格特征）：侦探、诡计、实施者、游戏…

否则给一本推理小说做风格学习，模型会以为你的写作风格是"爱用'侦探'这个词"。

参数说明：
- `--length`：short(200-300字) / standard(800-1200字) / deep(2000-3000字)
- `--focus`：general / plot / character / prose / theme
- `--force`：忽略理解卡缓存，重新分析

## 环境要求

- Python 3.13（已验证）
- **mobi / azw3 建议安装 Calibre**。程序会先用 `mobi` 库解包，失败时自动降级到
  Calibre 的 `ebook-convert`。两者都没有时给出明确报错。
- DRM 加密的电子书任何工具都无法提取正文，需先去除版权保护。

## 目录结构

```
bookreview/
├── cli.py                  命令行入口
└── core/
    ├── config.py           配置与服务商预设
    ├── models.py           Book / Chapter / BookDigest
    ├── llm.py              LLM 客户端（OpenAI 兼容 + 限流重试）
    ├── db.py               SQLite（书 / 理解卡 / 风格卡 / 书评）
    ├── parsers/            四种格式解析器 + 文本清洗
    ├── chunker.py          智能分块
    ├── digest.py           分层摘要 → 全书理解卡
    ├── style.py            风格特征提取与画像
    ├── generator.py        书评生成
    ├── prompts.py          全部提示词模板
    └── pipeline.py         全流程编排（GUI 也用它）
```

## 测试

```bash
python bookreview/tests/make_samples.py        # 生成 docx/epub 测试书
python bookreview/tests/test_pipeline_mock.py  # 全链路测试（用假模型，不烧 token）
```
