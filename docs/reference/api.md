# HTTP 与模块交接

[返回项目总览](../../README.md)

何时读：前后端对接、任务状态或 A/B 模块调用时读；按具体端点/函数查阅。

<a id="s10"></a>

## 前后端怎么交互：从一次点击开始

<a id="s10-1"></a>

### 理解一次生成

用户点击“生成” → React 用 `fetch()` 发送项目 ID、请求编号和允许修改的设置 → FastAPI 返回 `202 Accepted` 与 `job_id` → 后台执行器处理任务 → React 每 1–2 秒查询状态 → 完成后拿到 `video_url`，交给 `<video>` 播放。

`job_id` 就像取餐号：先拿号码，处理期间可以查询进度，完成再取结果。生成和修改不能让浏览器一直等待一个很长的 HTTP 响应。

<a id="s10-2"></a>

### HTTP 接口约定：前后端按同一份样例开发

已附 [OpenAPI 3.1 接口定义](../../contracts/collaboration/api.openapi.json)和 [31 份请求／响应与状态样例](../../contracts/collaboration/api.examples.json)。这些定义补齐 HTTP 交接，原来的 `contracts.schema.json` 继续负责六类项目与剪辑数据。**现有样例和 mock 都是开发材料，不表示真实 API 已实现。** 整包已放入本仓库 `contracts/`，两人使用同一个提交版本。

所有 JSON 响应固定包含 `api_version: "1.0.0"` 和 `simulation: boolean`。样例与替身返回 `true`；实际后端只有使用真实实现才返回 `false`。成功响应按资源命名为 `project`、`clip`、`job` 或 `versions`，不再加另一个 `data` 外壳。定义为可空的字段仍必须出现，以 `null` 表示尚无值；集合没有内容时返回 `[]`。

| 接口 | 请求 | 成功响应 |
| --- | --- | --- |
| `GET /api/health` | 无 | 200；`status`、`execution_mode`、上传限制与模拟标记 |
| `POST /api/projects` | JSON：`request_id` | 201；`project`，包含 `project_id`、完整默认设置和空素材列表 |
| `POST /api/projects/{project_id}/clips` | multipart：`request_id` + **一个** `file` | 201；`project_id`、`clip`，其中有素材 ID、时长、方向、文件名和可空缩略图 URL |
| `GET /api/projects/{project_id}` | 无 | 200；`project`，恢复设置、素材、`current_version`、`active_job_id`、`pending_selection` |
| `POST /api/projects/{project_id}/generate` | JSON：`request_id`、`settings`；默认 `settings: {}` | 202；`project_id`、`job_id`，不等待渲染 |
| `POST /api/projects/{project_id}/edits` | JSON：`request_id`、`base_version_id`、`input` | 202；`project_id`、`job_id` |
| `GET /api/jobs/{job_id}` | 无 | 200；`job`，固定字段见下文；即使任务处理失败，这个查询仍可成功返回 200 |
| `GET /api/projects/{project_id}/versions` | 无 | 200；`project_id`、`current_version_id`、`versions`，最新创建的版本在前 |
| `POST /api/projects/{project_id}/current-version` | JSON：`request_id`、当前 `base_version_id`、目标 `version_id` | 200；更新后的 `project`；恢复目标版设置，不创建新版本 |
| `GET /api/projects/{project_id}/versions/{version_id}/video` | 可选 `Range` 请求头；下载用 `?download=true` | MP4 字节，200 或单段 Range 的 206；范围无效返回 416 |
| `GET /api/projects/{project_id}/clips/{clip_id}/thumbnail` | 无 | 实际 JPEG 字节；尚无缩略图时素材中的 `thumbnail_url=null`，前端显示占位图 |

上传由前端逐文件执行，一次只传一个文件，保留失败文件的重试入口。首版生成前可继续上传；生成中禁止上传、修改和切换版本；已有成功版本后素材集固定，新增素材通过新项目处理。`generate` 用于首次生成或首次失败后的重试，已有成片后走 `edits`，避免双方对“再次生成是否清空历史”理解不同。

HTTP `settings` 是初始设置的白名单，MVP 只接受可选的 `title_overrides` 和 `warmth_override`，不是整份 `config.settings`。固定风格、BGM、输出规格与排除列表由后端补齐。前端需要完整设置时读取 `project.settings` 或 `version.settings`，不要自己再维护另一套默认值。

`input` 只取一种形式：自然语言为 `{"kind":"instruction","text":"暖一点"}`；固定按钮或歧义确认用 `{"kind":"operations","operations":[{"type":"set_warmth","value":0.25}]}`。确认删除时提交明确 `remove_clip` 和新的 `request_id`，仍检查原来的 `base_version_id`。取消选择只收起界面，不提交编辑请求。重新打开项目时，后端通过 `pending_selection` 恢复尚未确认的候选；这不占用执行器。

**任务查询字段固定：** `job_id`、`project_id`、`request_id`、`kind`、`base_version_id`、`status`、`message`、`progress`、`version_id`、`video_url`、`summary`、`resolution`、`error`、`created_at`、`updated_at`。时间为 UTC ISO 8601 字符串。`progress` 为 `null` 或 `{completed,total,unit}`，只用于有真实总量的阶段，不是假总进度。

- 活动任务：`version_id/video_url/summary/resolution/error` 均为 `null`。
- `done`：填入成功版本、媒体 URL 和实际修改摘要；`resolution/error=null`。前端随后重新读取项目，更新当前版本和设置。
- `needs_selection`：只填[`edit_request.json`：修改是受控操作，不是任意 JSON 补丁](timeline.md#s6-8)的选择结构，候选缩略图按 `clip_id` 从项目素材列表查找；不产生成功版本。
- `failed/interrupted`：填 `error: {code,message,retryable}`；保留项目的旧成功版本。`retryable` 表示可以由用户发起新请求重试，不要求前端自动重试生成。

**接口请求失败统一返回：** `{"api_version":"1.0.0","simulation":false,"error":{"code":"STALE_VERSION","message":"请刷新项目后重试","retryable":false}}`。固定处理 400 请求格式、404 资源缺失、409 项目忙／版本过期／幂等冲突、413 体积超限、415 格式不支持、422 数据校验、429 队列满、500 内部异常；FastAPI 默认校验错误也转换为同一外壳。已受理任务的渲染失败则写入 `job.error`，不能让前端把两类错误混为一谈。

`request_id` 由前端生成，同一次网络重试沿用原值；用户修正内容或主动重试失败任务时生成新值。后端以项目、操作、`request_id` 为幂等键，先检查是否已有请求，再检查忙碌与版本条件；相同请求返回原结果，不重复入队，相同编号但内容不同返回 409。上传比较文件内容与有效表单字段，不以 multipart 随机 boundary 判定不同文件。

媒体 URL 使用相对同源地址，前端当作不透明值直接使用，不能自己拼磁盘路径或对象存储键。HTTP 200/206 播放返回字节，不套 JSON；版本下载设置附件文件名。媒体和版本路由由 A 实现，B 的渲染器只返回本地临时文件。

<a id="s10-3"></a>

### 页面和任务状态分开

页面主流程：`empty → ready → processing → done`；另有 `awaiting_selection` 和错误提示。后台主流程：`queued → analyzing → planning → rendering → done`；异常/不支持为 `failed`，中断为 `interrupted`，歧义为终止当前任务的 `needs_selection`。后者不占住执行器，也不创建成功视频版本；确认后创建新请求重新校验基准版本。

分析、规划、渲染是实际阶段，不假装知道整个流程精确完成了百分之多少。只有有明确总量的步骤才显示“已分析 8/15 段”这样的数字。

处理中禁用再次生成和修改，但保留上一版播放器。任务失败保留旧成片与原素材，显示可重试入口。轮询在完成、失败、中断、待选择或组件卸载后停止，临时断网恢复后继续查询同一个任务。

<a id="s10-4"></a>

### 一个共享队列，先保证稳定

原型采用一个 FastAPI 服务进程（Uvicorn `workers=1`），一个共享队列和一个后台执行线程。生成和修改都进入同一队列；执行线程调用同步 pipeline，并启动 FFmpeg 子进程。给队列设置较小上限，满时提示稍后重试，不无限积压。

API 在入队前原子检查项目忙碌状态、重复请求和基准版本；处理完成后再次确认提交结果的版本关系。不要只靠前端禁用按钮，后端仍需拒绝过期的 `base_version_id`。

不要在 `async` 路由里直接运行阻塞转码，也不要误以为 FastAPI 的 `BackgroundTasks` 自动提供可靠队列。官方对重型后台计算建议考虑独立任务系统；本次单实例方案是受控演示的取舍，之后再加独立 worker 和持久队列。[FastAPI 文档](https://fastapi.tiangolo.com/tutorial/background-tasks/)

任务进度写入项目记录，页面从 API 读取。每个任务配置超时；异常或超时后清理子进程并释放忙碌状态，启动时把遗留任务标为已中断。

<a id="s10-5"></a>

### 双方独立开发与替身切换

B 开发前端时运行随附 [本地 mock API](../../contracts/collaboration/mock_api.py)，按 OpenAPI 和同一份样例实现页面，无需等 A 的 API。mock 默认监听 `127.0.0.1:8000`；Vite 将 `/api` 代理到该地址。切到真实后端时只更换服务，页面组件和字段不变。JSON 和媒体响应都标记模拟，前端读取健康检查后持续显示“模拟数据 / 开发模式”。

A 开发队列、版本与错误恢复时，用 [渲染替身与模块类型](../../contracts/collaboration/runtime_contracts.py)注入 `RenderStub`；成功模式复制显式提供的测试文件，失败模式抛出约定错误，不依赖 B 的 FFmpeg 实现。真实渲染器就绪后替换同一个接口。任何替身参与的结果保持 `simulation=true`，使用独立测试目录，不能提交为真实成功版本或用来通过 Replit 验收。

B 独立开发渲染时，读取 [九秒时间线](../../contracts/collaboration/smoke9.timeline.json)和 [素材路径映射示例](../../contracts/collaboration/asset-paths.example.json)，直接从本地文件输出 MP4，无需等待 API、存储或 AI。映射示例不包含真实媒体；首小时准备真实文件并按实际元数据更新映射与素材清单。

mock 是单项目、内存状态服务，支持成功、失败、中断、待选择、持续处理中场景；上传只做表单检查并返回模拟元数据，自然语言不调用模型，重启后数据重置。只有提供 `--media` 才有测试视频播放；未提供时返回 `FIXTURE_MEDIA_MISSING`，不会伪造文件。它支持前端交互开发，不替代真实上传、持久恢复、AI、视频质量与资源测试。

API key 只存在后端环境变量 / Replit Secrets 中，不写入前端或 `VITE_` 环境变量。初期手工计划模式可以配真实渲染做环境验证，此时健康检查为 `execution_mode=manual_plan`；只有完整模型链路可用后才标为 `ai`。使用 mock API 时为 `mock`。

<a id="s10-6"></a>

### Python 模块交接：A 调度，B 渲染

以随附 `runtime_contracts.py` 为签名依据；它提供可导入的类型、接口约定和一个模拟渲染器，真实渲染与标题布局仍待实现。

| 调用 | 谁实现 / 谁调用 | 固定边界 |
| --- | --- | --- |
| `render_timeline(request, on_progress) -> RenderResult` | B 实现，A 的后台执行线程调用 | 接收完整 `timeline.json`、资源 ID 到本地路径的映射、独立工作目录、输出位置、超时和取消检查；同步执行，返回本地输出及实际测量的宽高、fps、帧数 |
| `layout_title(request) -> list[Overlay]` | B 实现，A 在冻结时间线前调用 | 接收最终三层标题、风格 ID/版本、输出规格、展示帧数和字体路径；测量后返回符合现有 Overlay schema 的排版，不新造另一套坐标格式 |
| `on_progress(RenderProgress)` | A 实现，B 回调 | B 报告已处理帧数、总帧数和文字；A 统一落盘任务状态，B 不写 `jobs/` |
| `ModuleError(code,message,retryable)` | B 抛出，A 捕获 | 缺素材、缺字体、文字溢出、渲染失败、超时或取消均明确报错；B 终止子进程，A 释放队列并保留旧版本 |

资源 ID 由 A 登记，存储键由 A 解析并将所需文件准备到本地。B 只访问传入的路径，不拼云端地址、不创建项目或版本、不自行改变镜头时长。A 在渲染后核对返回文件与时间线、保存 App Storage、提交版本指针；不能仅凭渲染函数正常返回就宣布成功。

标题布局采用两步：B 的布局函数在编译前确定文字换行、字号、位置；A 将结果写入时间线；B 渲染时据同一结果绘制透明图层，不重新排版。布局函数尚未完成时，A 用随附固定时间线测试流水线，标题修改功能保留为待联调，不能假装完成真实字体测量。
