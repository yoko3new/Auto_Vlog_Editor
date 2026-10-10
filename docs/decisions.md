# 已确认决策与变更记录

**中文** · [English](decisions.en.md)

[返回项目总览](../README.md)

何时读：记录影响产品范围、架构和公共契约的决定；A 汇总维护。具体实现仍链接所属技术文档。

<a id="s19"></a>

## 已确认的方向与开工默认值

| 项目 | 当前决定 |
| --- | --- |
| 主赛道 | Adobe Creative；展示生活感受、审美和创作控制 |
| 开发环境 | 本地开发为主，通过 GitHub 同步到 Replit 验证与正式发布 |
| 前端 | React + Vite + Tailwind + shadcn/ui，单页编辑台 |
| 后端与渲染 | FastAPI + 单个任务执行器 + FFmpeg；AI 给计划，代码算时间线 |
| 存储 | 单实例 JSON 管理项目；线上持久媒体与 JSON 使用 App Storage |
| AI（原比赛评估安排） | 第 6–7 小时按[AI 素材理解与选片测试：第 6–7 小时首测，第 14 小时前验证成片](ai-selection.md#s20-4)用 10 段素材测试；先测一家，最多比较另一家，只锁定一个主供应商；当前 Vlogii 已使用 Gemini，比赛质量评估仍待完成 |
| 语音（原比赛目标） | 原方案 MVP 不转录、原声静音；V2-3 才加口播字幕。当前 Vlogii 保留原声/字幕，两者范围差异见功能对照；本次未修改比赛目标 |
| 可选赞助商 | Gemini、ElevenLabs 均不强求，不为兼报增加无用功能 |
| 阶段范围 | MVP 必达；V2 按情绪表达、缩短、口播顺序加入；V3 以赛后为主 |
| 交付关卡 | 第 2 小时环境预检，第 6 小时 Replit 验证通过，第 7 小时完成 AI 首轮选片测试，第 14 小时自动速剪及关键瞬间复核，第 24 小时验收 MVP，最后 6 小时冻结 |

先完成[开工验证：先确认 Replit 能跑通，再接 AI](deployment.md#s18-2)的 Replit 环境、正式闭环与实际负载验证，再完成 AI、固定风格和三类修改；口播属于 MVP 放行后的 V2-3。平台和模型的选择服务于这条闭环。

## 后续决定如何记录

由 A 保存影响范围、架构或公共契约的决定，可委托编码助手；保留日期、决定、原因、受影响文档与状态。已失效的决定注明被哪一项替代，不让历史结论继续充当当前规范。

| 日期 | 决定 | 原因 / 影响 | 状态 |
| --- | --- | --- | --- |
| 2026-10-10 | 支持 AI自动、开头快剪、保留大部分、完整保留；省略目标不再默认 30秒；加入可点击示例与成片时间删除 | 用户希望自由选择保留量和精华开头，后续精确删除；模式/默认兼容规则见[剪辑模式](editing-modes.md) | 随本批提交交付；95测试及真实长片/快剪/网页编辑撤销通过 |
| 2026-10-10 | 品牌采用 vlogii 的浅薄荷绿、粗圆小写字标与叠帧图标（v8） | 用户已确认最终设计；正式 PNG 与使用约定见[视觉规范](visual-design.md#brand-logo) | 已保存资源与文档；网页接入待 B 实现 |
| 2026-10-09 | 长文档拆成短总览、独立协作手册和按需参考 | 降低重复读取；旧全文归档，技术约定保留 | 已接受并实施 |
| 2026-10-09 | 共享项目文档、契约与通用 AGENTS.md；个人角色和调度设置留本地 | 两人可使用不同开发工具；共同遵守文件归属、接口和验收 | 已接受；共享内容以 GitHub 当前提交为准 |
| 2026-10-10 | A（杨康）负责视频生成全链路、后台/AI/渲染/标题/素材/存储/契约/集成；B（队友）负责前端 | 按用户明确调整替代旧“B 渲染+前端”；不改模块行为或 API | 已实施于共享分工文档 |
| 2026-10-10 | 当前基线采用 kang 的 Vlogii 本地网页 MVP，分别记录现行实现与原比赛目标 | 已上传 ec21851；使用 /api/vlogii、独立模型和本地文件保存；不把 BGM/杂志风/Replit 缺口记成完成 | 已核对代码及既有验证记录，未在本轮重跑应用 |

Vlogii 已使用 Gemini，模型由 `VLOGII_MODEL` 配置，既有环境记录见 [本地验证](vlogii-validation.zh.md)；具体比赛模型质量、正式运行环境与部署配置仍待验，不把小样本当作整体完成。


## Vlogii local web implementation — 2026-10-10

At the user's request, branch `kang` adds an independent local web MVP based on the
successfully exercised VX workflow. The core renderer is shared by FastAPI and a
small debugging CLI. New source and notes are English. No VX source is copied.
The user clarified that the product should be a website, so this release includes
React upload, real job status, playback, version edits, undo and download.

The existing competition product and public API contracts are preserved.
Vlogii's separately versioned `/api/vlogii` interface is documented by its own
OpenAPI snapshot. Replit, App Storage, BGM and magazine styling remain outside
this local release and are not marked accepted.

## 2026-10-10：生活 Shorts 与速度

用户确定产品聚焦生活类 Shorts：艺术字/贴画封面、开头几个闪切镜头、带简单字幕/少量词语和时间标注/轻特效的正文。保存[设计方向](shorts-direction.md)，完整封面和开头正文拼接尚未实现。

本地快剪默认改为约 5 秒、单镜头最多约 0.5 秒；镜头停留与视频倍速分别配置。整片与当前成片时间段支持绝对倍速，字幕/原声跟随时序，旧片可撤销。新 API 字段见[剪辑规则](editing-modes.md)，验证证据见[记录](vlogii-validation.zh.md)。本批提交包含实现、调用方与验收记录。

快剪默认静音：用户指出快速切点截断原声。计划持久化静音策略，渲染替换为静音音轨，调速/删除/重试维持该策略；正文模式继续保留原声。

用户认可 0.5 秒一镜、1 倍速、静音的对比版本，作为当前默认快剪节奏；目标时长仍可选，镜头停留和倍速独立可调。
