# 双人协作包：不用等对方完成再开始

这个目录是开发用的接口约定和替身。**它不是已完成的 Auto Vlog 应用，也没有附带视频、音乐、字体或密钥。** [接口文档](../../docs/reference/api.md)定义交接，[协作手册](../../docs/collaboration.md)安排分工；真实出片和 Replit 验收仍按原来的关卡执行。

本包已经位于应用仓库的 `contracts/`。两人从同一个 Git 提交开始，不各自修改一份契约。

## 先看哪些文件

| 文件 | 用途 | 主要使用者 |
| --- | --- | --- |
| `api.openapi.json` | HTTP 请求、响应、状态和错误的字段定义 | A 实现 API，B 接页面 |
| `api.examples.json` | 31 份可直接查看的请求／响应与状态样例 | A、B |
| `mock_api.py` | 可运行的本地模拟 API | B，无需等待真实后端 |
| `runtime_contracts.py` | Renderer、标题布局、进度、错误类型；含 RenderStub | A、B |
| `smoke9.timeline.json` | 三段各三秒的固定时间线 | B，无需等待 AI 或 API |
| `asset-paths.example.json` | 资源 ID 到本地文件的映射示例 | B 渲染、A 准备文件 |
| `validate_collaboration.py` | 样例一致性和开发替身的检查 | 合并前运行 |
| `contract_utils.py` | 替身和检查脚本使用的有限 schema 检查器 | 工具内部使用 |

## B：现在就能连接的 mock API

在本目录运行，使用 Python 3.10 或更新版本，无需安装第三方包：

```sh
python3 mock_api.py --port 8000 --scenario success
```

访问 `http://127.0.0.1:8000/api/health` 检查服务。服务只监听本机；Vite 配置 `/api` 转发到 `http://127.0.0.1:8000`，React 始终调用相对路径。切换到 A 的真实服务时，停止 mock、启动真实服务，组件不改字段。

默认有一个 `project_demo`，包含十条虚拟素材记录，可以直接调用生成接口。`POST /api/projects` 创建空项目时会重置这个唯一的沙盒项目；这个限制只适用于 mock。上传通过 multipart 传 `request_id` 和一个 `file`，文件内容被丢弃，返回八秒等模拟元数据。

模拟视频播放需要额外提供本地 MP4，停止旧服务后运行：

```sh
python3 mock_api.py --port 8000 --scenario success --media /absolute/path/sample.mp4
```

所有版本播放同一个文件；mock 不检查它是否匹配时间线或声明的时长。未传 `--media` 时，视频接口明确返回 `FIXTURE_MEDIA_MISSING`，其他状态仍可开发。缩略图返回 `null`，页面使用占位图。媒体路由支持单段 Range、拖动所需的字节响应和下载参数；真实浏览器播放与真实成片仍要单独验收。

用以下参数启动不同场景；每次先停止占用 8000 端口的旧服务：

| `--scenario` | 能检查什么 |
| --- | --- |
| `success` | 生成、完成、版本列表、撤销、明确操作修改 |
| `failed` | 任务失败后的提示、重试入口和解除忙碌 |
| `interrupted` | 中断后的提示和重试入口；这是模拟状态，不是重启恢复测试 |
| `needs_selection` | 先生成首版，再提交自然语言编辑；出现候选，提交明确 `remove_clip` 后完成 |
| `rendering` | 一直停在处理中，检查禁用重复提交与保留旧预览 |

任务状态随轮询次数推进，通常第三次查询进入终态。分析／规划等静态状态可从 `api.examples.json` 取 fixture。自然语言在 mock 中不会真的理解或修改视频，只有明确操作会更新模拟设置。任务结束后重新读取项目；遇到歧义时读取 `pending_selection`，确认选择用新请求编号和原基准版本。

每个 JSON 响应都有 `simulation: true`，所有响应包含 `X-Auto-Vlog-Simulation: true`。前端持续显示“模拟数据 / 开发模式”。mock 的范围是表单、交互与状态；它不验证真实媒体、累计上传体积、AI 效果、持久保存、重启恢复或线上资源。不要用它的成功结果记录正式验收。

## A：用渲染替身测试自己的队列

从本目录可以导入 `runtime_contracts`。在应用中使用时，由 A 确认唯一的导入路径，两人不要各建一份类型定义。

```python
import json
from pathlib import Path
from runtime_contracts import RenderRequest, RenderStub

request = RenderRequest(
    timeline_document=json.loads(Path("smoke9.timeline.json").read_text()),
    asset_paths={},  # 替身不读取资源；真实渲染必须提供完整映射。
    work_dir=Path("/tmp/auto-vlog-stub/job-001"),
    output_path=Path("/tmp/auto-vlog-stub/job-001/preview.mp4"),
    timeout_seconds=120,
    is_cancelled=lambda: False,
)
result = RenderStub(Path("/absolute/path/sample.mp4")).render_timeline(
    request, lambda progress: print(progress)
)
assert result.simulation is True
```

成功模式只复制指定文件，尺寸和帧数来自请求，未实际测量。重复运行时换新的任务目录，已有输出会被拒绝覆盖。使用 `RenderStub(fail=True)` 检查失败是否释放队列、保留旧成功版本；`is_cancelled` 返回 `True` 可模拟调用前取消。它不实现真实子进程超时或运行中取消。

真实 Renderer 必须采用同一函数签名，测量实际输出并返回 `simulation=False`，在超时／取消时终止 FFmpeg。A 校验结果、写存储和提交版本；B 的渲染器不写项目记录。替身和真实任务使用不同测试目录；正式发布禁止 stub 模式。

## B：直接开发真实渲染

1. 读取 `smoke9.timeline.json`，三个镜头都从各自第零秒开始，共 270 帧，30 fps。
2. 把路径映射示例复制成自己的 `fixtures/local-paths.json`，提供三段至少三秒的真实素材，以及时间线引用的 BGM、字体、装饰文件。路径相对应用仓库根目录解析；A/B 共用资源 ID。
3. 根据实际视频更新素材清单中的时长、方向等元数据，不能把样例中的假定值当作探测结果。
4. 实现 `Renderer.render_timeline()` 和[协作手册](../../docs/collaboration.md#s13-6)约定的渲染 CLI。该 CLI **不包含在本包中**，由 B 在开工时创建。
5. 标题布局独立实现 `TitleLayouter.layout_title()`；A 在生成最终时间线前调用，B 渲染时严格按返回的 Overlay 绘制。

这条路径无需 A 的 API 或 AI。先交出可在干净环境重现的真实小 MP4、命令和依赖，再打磨页面。

## 合并前检查

从仓库根目录进入 `contracts/` 后运行：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 validate_examples.py
PYTHONDONTWRITEBYTECODE=1 python3 collaboration/validate_collaboration.py
```

第二条检查 HTTP 样例、OpenAPI 内复制的数据定义、九秒时间线，以及 mock 的请求去重、过期版本、失败、待选择、版本切换和媒体字节范围响应。默认把 HTTP 请求字节交给同一个处理器，通过内存读写响应，不启动端口；媒体测试使用临时字节文件，**不证明这些字节是有效视频**。

本次交付环境不允许监听本地端口，因此真实 HTTP 服务连通性尚未验证。开发电脑上可以补跑下面的命令；它临时启动本机随机端口并自动关闭，不访问外网：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 collaboration/validate_collaboration.py --http
```

两个检查器只覆盖本包用到的规则，不是完整的标准 OpenAPI / JSON Schema 验证器。真实应用仍需标准字段校验及[时间线文档](../../docs/reference/timeline.md)的语义检查；接入真实实现后，要用同一组请求验证响应契约，再做真实上传到播放、持久恢复与 Replit 负载测试。

本次交付检查：原有 13 份数据样例通过、19 个反例按预期被拒绝；新增 11 组协作检查通过，涵盖全部 31 份 HTTP 样例、复制定义一致性、九秒时间线与内存请求处理。尚未执行真实端口连接、浏览器播放、FFmpeg 或 Replit 测试。

## 开工时还需填写的四项

- A、B 的姓名和分支名。
- 共同验证过的 Python、Node、包管理器版本，以及后端配置负责人 A。
- 真实素材获取位置和文件散列；媒体、密钥和缓存不放 Git。
- 第一次真实对接时间：目标第 4 小时；遇到阻塞先用替身继续，真实验收仍由双方完成。
