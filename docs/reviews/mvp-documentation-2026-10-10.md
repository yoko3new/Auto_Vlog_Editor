# MVP 文档与分工核对记录

**中文** · [English](mvp-documentation-2026-10-10.en.md)

日期：2026-10-10（America/New_York）。核对代码基线：`kang` / `ec21851`。

## 本次范围

- 读取已上传 Vlogii 的 API、模型、AI、时间线、流水线、渲染、前端及既有验证记录。
- A（杨康）负责视频生成全链路、后端、渲染、标题布局、资源、契约和集成；B（队友）负责前端。
- 新增 [MVP 功能对照](../mvp-coverage.md)，重写 [当前进度](../status.md)和 [协作手册](../collaboration.md)，同步入口、相关设计文档的适用范围与分工。
- 原比赛产品范围、JSON/OpenAPI 契约及应用代码未修改。当前 `/api/vlogii` 与原 `/api` 规划分别标明。

## 实际检查

| 命令 | 本轮结果 | 检查边界 |
| --- | --- | --- |
| `python3 tools/check_docs.py` | 通过 | 本地 Markdown 链接、稳定锚点、代码围栏与入口长度 |
| `PYTHONDONTWRITEBYTECODE=1 python3 contracts/validate_examples.py` | 通过：13 份样例、19 个反例 | 原契约数据，不涉及真实媒体/AI |
| `PYTHONDONTWRITEBYTECODE=1 python3 contracts/collaboration/validate_collaboration.py` | 通过：11 项 | 原合同/开发替身，内存 HTTP，不涉及浏览器/真实后端 |
| `git diff --check` | 通过 | 本次已跟踪文档的空白检查 |

本轮没有重新调用 Gemini、运行应用测试、构建前端、导出视频或执行 Replit 验收。[既有 Vlogii 记录](../vlogii-validation.zh.md)中的 29 个测试及两套真实素材结果作为已有证据引用，不记为本轮重验。

下一步：两人复现当前 MVP，再按明确授权的前端/视频任务推进；比赛差距与线上环境仍须实际验收。本记录只证明此次文档核对与修改检查。
