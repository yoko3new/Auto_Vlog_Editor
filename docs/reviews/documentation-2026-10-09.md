# 文档拆分与契约迁移检查

日期：2026-10-09，America/New_York。范围为本次文档和契约准备，没有应用代码提交。

## 执行检查

| 命令 / 检查 | 实际结果 |
| --- | --- |
| `python3 tools/check_docs.py` | 本地链接、稳定章节锚点、代码块和简短入口限制通过 |
| `PYTHONDONTWRITEBYTECODE=1 python3 contracts/validate_examples.py` | 13 份数据样例通过；19 个错误样例按预期被拒绝 |
| `PYTHONDONTWRITEBYTECODE=1 python3 contracts/collaboration/validate_collaboration.py` | 11 组检查通过，覆盖 31 份 HTTP 样例及内存请求处理；未启动真实端口 |
| 原文与拆分文档的章节锚点对照 | 原有 93 个编号章节/小节在当前主题文档中各保留一次 |
| 契约目录逐文件字节比对 | 仅 `collaboration/README.md` 更新了文档位置与链接；schema、样例、mock 和检查逻辑未改变 |

## 独立审阅

一个只读子 agent 先梳理原文关键要求，再检查 README、AGENTS、协作/契约/进度/维护/agent 工作流/决策文档，并按需对照技术参考。

结论：该范围内未发现实际影响的问题。阶段关卡、接口语义和 A/B 文件归属保留；按需读取入口明确；模拟与真实验收区分清楚；文档保留说明可以直接使用。

审阅后明确了产品运行时 AI 编排与开发工具的区别；随后重新运行文档检查。准备共享仓库时，个人角色/调度文档和历史归档留在本地，公共文档链接另按共享文件集核验。

## 未验证

真实 HTTP 连通、浏览器播放、字体排版、FFmpeg、AI 服务、持久恢复、Replit 正式部署与性能均未测试。个人开发工具不是共享资料的运行前提。

[返回当前进度](../status.md) · [文档保留说明](../maintenance.md)
