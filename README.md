# Auto Vlog Editor

把手机里的校园生活碎片，剪成有个人风格的 vlog 开场速剪。

**36 小时 · 两人团队 · Adobe Creative 主赛道 · Replit 验证与展示。** Gemini、ElevenLabs 根据效果选用，不强求接入。

## 做什么

面向喜欢记录校园日常、但没有时间精剪的学生。用户上传零散视频，应用挑选有代表性的瞬间，配上音乐、标题和统一视觉，输出约 30 秒短片；用户可以用一句话修改。

当前交付的就是 vlog 开头的速剪成片。素材保留手机拍摄的自然感，展示重点是实际作品、审美和用户对表达的控制。

## 交付范围

| 阶段 | 内容 | 顺序 |
| --- | --- | --- |
| MVP，比赛必达 | 上传→AI 选片→约 30 秒速剪→改标题/暖度/删素材→撤销→下载 | 全部验收通过后再加功能 |
| V2，可选 | 第二种情绪表达；缩至 20 秒；短口播+字幕+BGM 压低 | 逐项实现并验收 |
| V3，主要赛后 | 竖屏、60 秒、更多风格/有限动画、抠图/旁白、参考图 | V2 稳定后推进 |

MVP 使用 10–15 段、总长≤3 分钟的已验证 1080p SDR 素材；固定杂志风、一首 BGM、硬切、原声静音。输出为 720p、16:9、30 fps MP4；首次目标 30±1 秒，删除素材后允许自然变短。90 秒出片是优化目标，尚无实测结论。

完整需求和排除项见 [产品与交付范围](docs/product.md)。

## 怎么实现

React + TypeScript + Vite 前端负责上传、状态、预览和编辑；FastAPI 后端负责 API、单个任务执行器和版本；FFmpeg 负责真实视频处理。本地开发，经 GitHub 同步到 Replit；前后端同仓库、同应用发布。

AI 生成剪辑计划 → 程序计算最终时间线 → 渲染器严格执行。MVP 暂不加 SQL 数据库；项目记录使用 JSON，线上素材和成片持久保存到 App Storage。

详见 [架构](docs/architecture.md)、[数据与接口导航](docs/contracts.md)。

## 从哪里开始读

你日常主要看总览、协作手册和进度表。技术文档保留在仓库，按任务读取，不需要每次全读。

| 现在要做什么 | 对应文档 |
| --- | --- |
| 确定 A/B 分工、开发节奏、交接与合并 | [两人协作手册](docs/collaboration.md) |
| 查看已完成、阻塞、下一步 | [当前进度](docs/status.md) |
| 查询编码助手的团队规范与阅读入口 | [AGENTS.md](AGENTS.md) |
| 写 API、时间线、渲染或修改功能 | [接口与数据导航](docs/contracts.md) |
| 调整网页和成片视觉 | [视觉规范](docs/visual-design.md) |
| 验收与排查失败 | [验收标准](docs/acceptance.md) |
| 验证 Replit 或处理部署问题 | [部署与平台验证](docs/deployment.md) |
| 选择模型、检查选片表现 | [模型与 AI 测试](docs/ai-selection.md) |
| 从参考 reel 学剪辑节奏/混音/风格，套用到自己的素材（实验） | [参考 reel 风格模板](docs/style-templates.md) |
| 确认已经作出的取舍 | [决策记录](docs/decisions.md) |
| 准备素材、录屏和比赛演示 | [准备与 Demo](docs/demo.md) |
| 知道什么必须保留、由谁维护 | [文档保留与维护](docs/maintenance.md) |

## 当前状态与第一步

已有方案、数据/API 契约、开发替身和检查脚本；真实应用、真实渲染、AI 接入和 Replit 验收尚未完成。这里不是已运行的产品，主题文档里的应用启动命令仍是开发约定。

第一步：两人确定 A/B、同步同一个仓库版本并准备三段真实素材。A 交 API/存储骨架，B 交九秒真实渲染；前端与后端分别用 mock 和 RenderStub 推进，目标第 4 小时接入真实实现，第 6 小时通过 Replit 关卡。详细任务见 [协作手册](docs/collaboration.md)。

契约检查可从仓库根目录运行：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 contracts/validate_examples.py
PYTHONDONTWRITEBYTECODE=1 python3 contracts/collaboration/validate_collaboration.py
python3 tools/check_docs.py
```

开发替身用法见 [契约工具说明](contracts/collaboration/README.md)。检查通过不代表真实视频或 Replit 验收通过。

共享仓库保留当前项目文档、契约和检查工具；个人 agent 角色、调度配置和历史长文档留在各自本地。
