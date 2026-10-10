# 团队共享工作指南

**中文** · [English](AGENTS.en.md)

`kang` 分支已有 Vlogii 本地网页 MVP；原比赛方案与契约保留为规划。接到明确开发任务后才实现相应代码；进度以真实证据为准。

本文件是团队共享规范，适用于成员选择的编码助手。个人角色模板、并发设置和调度流程不作为团队依赖。

## 按任务阅读

- 初次进入项目读 [README](README.md)；恢复未完成任务读 [当前进度](docs/status.md) 的相关行。
- 分工、文件归属和合并读 [协作手册](docs/collaboration.md)。
- 改服务边界/存储读 [架构](docs/architecture.md)；改接口/时间线按 [契约导航](docs/contracts.md) 定位小节与具体 schema。
- 前端/渲染视觉读 [视觉规范](docs/visual-design.md)；验收读 [验收标准](docs/acceptance.md)。
- 部署读 [Replit 验证](docs/deployment.md)；AI 接入/选片读 [AI 测试](docs/ai-selection.md)。
- 不递归读取全部链接；复用仍有效的已读信息，任务变化时再补读。

## 范围与归属

- 当前实现与缺口见 [MVP 功能对照](docs/mvp-coverage.md)；原比赛目标见 [产品定义](docs/product.md)。schema 能表达 V2/V3 不等于现在要实现。
- A（杨康）管视频生成全链路、后台/AI/素材/渲染/标题布局/契约/集成；B（队友）管前端页面、交互、样式与 API 调用。修改前确认本任务文件范围。
- 当前前端使用 `/api/vlogii` 和 [现行 OpenAPI](docs/vlogii.openapi.json)；旧 `/api` 契约及 mock 不可直接替换现行后端。
- 并行开发使用独立工作目录/worktree；共享目录不并行改同文件，也不同时切换 Git 分支。
- Review 默认只读；debug 默认复现诊断，接手修改需明确文件移交，避免原开发者同时写。
- status/decisions 由集成负责人 A 统一维护，可委托编码助手；其他成员提供证据与更新建议。
- 不要因待办存在就自行启动未授权开发。

## 交付

- 公共契约变更同时更新 schema、样例、替身和调用方；说明兼容影响，不能两边各猜一种字段。
- AI 给计划，代码计算时间线，渲染器执行；失败保留旧成功版本，mock 不计真实验收。
- 根据改动运行相关检查。文档链接检查：`python3 tools/check_docs.py`。
- 契约检查：`PYTHONDONTWRITEBYTECODE=1 python3 contracts/validate_examples.py` 和 `PYTHONDONTWRITEBYTECODE=1 python3 contracts/collaboration/validate_collaboration.py`。
- 交付说明目标、修改文件/提交、实际检查结果、未验项、下一步；日志存文件，仅回传摘要和证据路径。
- 只在相关代码/契约/流程变化时同步对应文档，不把每轮过程都追加到总览。
- 素材、缓存、密钥和私人评估记录不提交 Git；实际许可记录与非敏感验收证据应保留。
