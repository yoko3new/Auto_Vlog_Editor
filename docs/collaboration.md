# 两人分工与交接

**中文** · [English](collaboration.en.md)

[返回总览](../README.md) · [当前进度](status.md) · [MVP 功能对照](mvp-coverage.md)

2026-10-10 起采用本页分工；旧文档中“B 负责渲染/标题布局”的安排由本页替代。当前基线是 `kang` 的 Vlogii 本地网页 MVP，不再从空仓库重复搭骨架。

<a id="s13"></a>

## 两人分工与协作

<a id="s13-1"></a>

### 唯一负责人和文件范围

**A = 杨康：负责视频生成逻辑、全部视频模块、后端和集成。B = 队友：负责前端。** 成片视觉由 A 实现，页面视觉由 B 实现；双方共同观看成片、确认需求并验收闭环。编码助手领取具体文件范围后才修改。

| 当前文件 / 范围 | 主负责人 | 交接边界 |
| --- | --- | --- |
| `src/vlogii/ai.py`、`speech.py` | A | Gemini 视频理解、独立语音转录、选片、排序、提示词和计划校验 |
| `src/vlogii/media.py`、`timeline.py`、`editorial.py` | A | 元数据、代理、编码/色彩、保留/快剪模式、时间范围删除/调速、帧时间线、字幕映射；B 不在浏览器重算剪辑结果 |
| `src/vlogii/render.py` | A | FFmpeg、原声/字幕、标题布局、暖度、输出校验；新增 BGM/卡点/成片风格也归 A |
| `src/vlogii/pipeline.py`、`storage.py` | A | 分析缓存、生成/编辑/撤销、版本、锁、保存与恢复 |
| `src/vlogii/api.py`、`models.py`、`cli.py` | A | HTTP、任务队列、上传、媒体路由、数据模型、调试入口 |
| `tests/**`、`pyproject.toml`、`uv.lock`、`.env.example` | A | 后端/媒体检查、Python 依赖与服务端配置；未来部署配置也归 A |
| `frontend/**`（含 package.json、锁文件、Vite/TS 配置） | B | 页面布局/样式、文件选择/拖拽、请求与轮询、播放器、编辑控件、撤销/下载、响应式与可访问性 |
| `docs/vlogii.openapi.json`、`contracts/**` | A | A 维护结构，B 提交页面所需字段；两边调用代码随变更同步 |
| 视频用字体、音乐、装饰、风格预设及渲染样片 | A | B 可提设计建议，不直接修改渲染实现；前端图片和 CSS 归 B |
| README、status、decisions、集成与部署文档 | A | B 提供前端启动/构建/联调证据；[视觉规范](visual-design.md)由 A 管成片部分、B 管页面部分 |

表中 `src/vlogii/` 路径除第一行外的简写均指该目录内文件。原规划 `api/`、`core/`、`style/` 和 `tools/render_fixture.py` 若以后实现，同样由 A 负责，不因旧文档路径而归 B。目录迁移需单独任务，本次不移动现有代码。

<a id="s13-2"></a>

### 共同基线和当前 API

两人先同步 `kang` 的同一提交，按 [Vlogii 指南](vlogii-guide.zh.md)复现启动。队友在自己的目录/分支做前端；杨康维护 `kang` 上的视频与后端逻辑。合并到 `main` 和正式发布仍由 A 负责，当前 MVP 上传不等于已合并或部署。

- 当前接口为 `/api/vlogii`；字段看 [现行 OpenAPI](vlogii.openapi.json)，运行时看 `/openapi.json` 和 `/docs`。
- 生成 POST 返回任务状态，前端轮询项目 GET 获取 `job`、`latest`、`video_url`；当前任务状态是 `queued/running/complete/failed`。
- 编辑提交 `title`、`warmth`、`exclude_clip_ids`；撤销走 `/undo`。前端从响应使用媒体 URL，不拼磁盘路径。
- 本轮体验修复增加 `/retry`（无请求体）、`job.retryable/kind` 与可选 `language`；模型默认及真实验收限制见 [修复记录](mvp-fixes.md)。已同步前端切换中英文与重试按钮，后续由 B 维护。
- 新增生成 `mode`、可空 `target_seconds`、`remove_no_speech`，编辑 `remove_ranges/instruction`，以及版本 `selection`；页面已同步模式和可点击示例。省略时长由默认 30 秒改为 AI 决定，旧调用方可显式传 30；见[剪辑模式](editing-modes.md)。
- 生成新增 `speed/shot_seconds`，编辑新增可空 `speed` 和 `speed_ranges`；时间指令支持删除/倍速，时间坐标取同一当前成片。页面单选栏与现行 OpenAPI 同步；[Shorts 作品结构](shorts-direction.md)是下一批方向，封面/贴画/开头正文拼接仍待实现。
- 内置资源接口为 `GET /api/vlogii/presets`；生成/编辑可选 `appearance` 包含 `font/music/music_volume/duck_music`，项目响应返回当前成功版本的外观。旧请求省略时保持无配乐；字体与音乐登记、版本/撤销及渲染由 A 维护，页面调用已同步，见[资源说明](free-resources.md)。

- 旧 `/api` OpenAPI、`simulation`、`request_id`、`base_version_id` 与 mock 是原比赛设计；当前 Vlogii 没有这些兼容保证。不能把旧 mock 换成 Vlogii 后端就假设前端字段不变。

<a id="s13-3"></a>

### 接下来按现有 MVP 交接

| 节点 | A：视频与后端 | B：前端 | 共同证据 |
| --- | --- | --- | --- |
| 复现当前版本 | 核对环境/密钥/FFmpeg，提供启动方式、现行 API 和真实测试素材要求 | 构建现有前端，验证上传、生成状态、预览、编辑和撤销/下载 | 同一提交的本地闭环；明确未经验证的控件/环境 |
| 明确下一批需求 | 对照比赛差距评估 BGM、节拍、杂志风、时长、自然语言编辑和部署 | 基于实际能力整理页面状态与设计需求 | 每项范围、文件负责人、验收标准；不把差距清单当作自动开工授权 |
| 已授权开发 | 实现视频/后端模块，交出请求响应样例、可播放输出和限制 | 实现对应控件、状态、错误反馈；保持接口一致 | 上传到播放及各修改效果共同核对 |
| 集成与发布验收 | 合并、依赖、云端保存/恢复、正式运行配置、成片/资源测试 | 真 API 联调、浏览器操作、显示与下载验收 | 已同步提交、构建/测试摘要、真实 MP4 和恢复结果 |

<a id="s13-4"></a>

### 依赖未就绪时如何继续

| 缺口 | 可继续的工作 | 不能宣称通过 |
| --- | --- | --- |
| 当前后端暂不可用 | B 用符合 `/api/vlogii` 字段的前端 fixture 开发页面；现有旧 mock 仅用于旧合同页面 | 真实上传/生成/恢复 |
| 渲染或字体未完成 | A 用固定计划定位视频问题；B 用明确标记的样片核对播放器和版式 | 真实风格出片或标题修改 |
| AI 调用失败 | A 复用已有计划检查真实渲染；B 完善失败和重试状态 | 本次 AI 理解/选片 |
| 部署未完成 | A 处理部署；B 继续本地真 API 联调 | Replit 正式验证 |

有阻塞时保存可复现输入、错误和最小命令，交给对应文件负责人。需要跨范围修改先移交文件，禁止双方同时编辑；无需让队友维护渲染实现。

<a id="s13-5"></a>

### 合并与契约纪律

- 使用独立工作目录/分支；不要在共享目录同时切分支或修改同一文件。新分支可用 `codex/video-pipeline`、`codex/frontend`；已有 `kang` 可继续使用。
- A 负责集成 `main`，B 交前端变更及构建/操作证据；按功能小步合并。
- 当前 API 变更同步模型、OpenAPI 快照、测试和前端调用。旧契约只有实际变更时才更新 schema、样例、替身；不能静默宣称两套接口兼容。
- 前端锁文件由 B 更新，Python 锁文件由 A 更新。冲突由负责人解决并验证，避免整份覆盖。
- 主链路修改后用同一套真实素材跑上传到播放；provider 替身与真实 Gemini 结果分开记录。
- 发布记录提交与配置，先保留稳定版本；未经云端验收不能把本地成功升级为线上成功。

<a id="s13-6"></a>

### 启动、配置与完成定义

当前使用 `src/vlogii/`、`frontend/`、`tests/`；本地项目默认保存在 `projects/`。实际安装要求、命令和限制以 [指南](vlogii-guide.zh.md)为准：

```sh
uv sync --frozen --extra dev
npm --prefix frontend ci
npm --prefix frontend run build
uv run vlogii doctor
uv run vlogii serve
```

服务默认 `127.0.0.1:8000`，生产构建由 FastAPI 提供；前端开发使用 Vite 配置的代理，调用相对 `/api/vlogii`。A 管 `.env.example` 中的服务端配置，密钥不进入前端或 `VITE_` 变量。

每次交接提供：提交/文件范围、接口依据、启动或调用命令、可复现输入、实际结果与限制。前端构建通过不等于视频或浏览器全流程通过；本地 JSON 恢复不等于 App Storage/正式部署恢复。私人素材、转录、AI 原始记录、缓存、密钥和生成视频不提交 Git。

<a id="s14"></a>

## 比赛关卡的适用范围

原 36 小时方案是比赛验收目标，不再作为“当前从零开发”的进度表。当前实现已有原声字幕、竖屏等能力，仍缺卡点、杂志风、自然语言编辑、固定时长与 Replit 验证，详见 [覆盖对照](mvp-coverage.md)。

原比赛范围未在本次调整中改变；如继续按该范围参赛，依次验证：

1. [Replit 环境、正式闭环与实际负载](deployment.md#s18-2)。本地成功不能代替正式环境。
2. [AI 选片质量](ai-selection.md#s20-4)：关键瞬间、重复、范围与最终成片；已有 Gemini 接入不用从零重做，但仍需质量证据。
3. [整个 MVP 验收](acceptance.md#s15-1)：比赛成片、三类修改、失败保护/撤销、第二套素材、保存恢复/下载。
4. 通过后再决定新增范围，冻结稳定版本、彩排和准备备份；具体新增工作须明确授权。

## 编码助手如何参与

A/B 是人的职责划分，编码助手遵守同一文件归属和接口。每人可选择自己的工具；不要求统一个人 agent 配置，也不因旧角色模板把视频渲染派给前端负责人。状态和决定由 A 汇总维护。
