# Vlogii

**中文** · [English](README.en.md)

![Vlogii logo](resources/branding/vlogii-logo.png)

将日常素材剪成可预览、修改和导出的生活类短视频。当前为本地网页 MVP，页面和 CLI 均支持中英文。

**上传 → Gemini 画面分析与语音转录 → 选片与帧时间线 → FFmpeg 导出 → 预览、修改、重试、撤销、下载。**

产品方向是「艺术字/贴画封面 → 开头快剪 → 字幕与少量标注正文」。目前快剪单独导出；封面和自动拼接正文仍待实现，详见 [Shorts 方向](docs/shorts-direction.md)。已确定的薄荷绿标识见 [品牌规范](docs/visual-design.md#brand-logo)。

集成分支 `codex/integrate-feng-ui` 将队友的杂志式前端与 `kang` 的生成、重试和编辑能力结合：薄荷绿页面、章节导航、宽幅播放器和内置网页字体。

## 本地启动

需要 macOS 或 Linux、Python 3.11+、Node.js 20+、[uv](https://docs.astral.sh/uv/) 和支持文字、音频、H.264/HEVC 的 FFmpeg。Ubuntu 安装见 [使用指南](docs/vlogii-guide.zh.md)。

```sh
# macOS
brew install ffmpeg-full
git clone --branch codex/integrate-feng-ui https://github.com/yoko3new/Auto_Vlog_Editor.git vlogii
cd vlogii
uv sync --frozen --extra dev
cp .env.example .env
```

在本地 `.env` 填写 `GEMINI_API_KEY`，然后构建并启动：

```sh
npm --prefix frontend ci
npm --prefix frontend run build
uv run vlogii doctor
uv run vlogii serve
```

打开 **http://127.0.0.1:8000**。macOS 自动优先使用 Homebrew 的 `ffmpeg-full`。只运行一个服务进程；当前没有认证，适用于本地使用。

## 当前功能

- 导入 MP4、MOV、M4V、MKV，读取元数据并去重；Gemini 分别处理画面代理和原声，字幕保留源语言并按输出尺寸排版。
- 中英文切换、可选创作描述、可点击输入示例；示例填入后由用户确认提交。
- 内置 6 款免费字体、6 首 CC0 纯音乐：自动加载、字体预览、音乐试听、配乐音量与口播压低；已有成片可更换并撤销。
- 横竖屏、原声字幕与少量文字；默认 SDR/H.264，可选全 HLG 素材的 10-bit HEVC 输出。
- 修改标题、暖度、排除素材、删除成片时间区间、整片或局部调速；字幕和原声跟随时间线。
- 成功版本、预览、撤销、下载；失败保留旧片，Retry 复用原请求、有效分析缓存和已完成渲染片段。
- 从 Instagram 参考片学到的风格成片：加入音乐、选择风格，每一刀都落在节拍上；100% 音量时音乐目标为 −14 LUFS，真峰值不超过 −1 dBTP，素材原声静音。Gemini 挑选片段、标签和标题，未配置密钥时按导入顺序使用素材。见 [风格模板](docs/style-templates.md)。

| 生成模式 | 默认行为 |
| --- | --- |
| AI 自动 | 根据素材与描述决定内容和时长，不再默认限制为 30 秒 |
| 开头快剪 | 约 5 秒的独立合集；默认每镜头最多约 **0.5 秒、1 倍速、静音**，不叠口播字幕 |
| 保留大部分 | 按导入顺序去黑场、修剪口播长停顿；默认保留无口播风景，可选择删除所有未识别到语音的区间 |
| 完整保留 | 按导入顺序保留全部已导入素材区间；倍速会改变成片长度 |

AI 自动/快剪可指定 1–1800 秒的近似目标；保留模式按内容决定时长，不重复素材凑时长。网页提供节奏和速度单选栏。时间修改以**当前成功成片**为坐标，如「删掉00:12到00:18」「00:12到00:18加速到2倍」，详见 [剪辑规则](docs/editing-modes.md)。

配置默认模型为 `gemini-3.8-flash`（画面/规划）和 `gemini-3.5-transcribe`（语音），共用 Gemini key，可在 `.env` 修改。真实小样已跑通，准确率仍需人工对照，见 [修复记录](docs/mvp-fixes.md)。Gemini 接收画面代理与音频；密钥、素材、转录、缓存、成片不提交 Git。

上传限制：50 段、单段 512 MB、单次 2 GB、原素材总长 30 分钟。暖度修改使用 SDR；HEVC 播放取决于浏览器与设备。

## CLI 与检查

```sh
uv run vlogii                          # Interactive language selection
uv run vlogii --language zh init my-day /absolute/path/to/footage --color sdr
uv run vlogii --language zh run my-day --mode keep_all
uv run vlogii --language zh run my-day --mode highlights --shot-seconds 0.5 --speed 1
uv run vlogii --language zh run my-day --style ig_city_day_in_life --music ~/Music/song.mp3
uv run vlogii --language zh edit my-day --instruction "00:12到00:18加速到2倍"
uv run vlogii --language zh retry my-day
```

```sh
uv run pytest -q
uv run ruff check src/vlogii tests
uv run ruff format --check src/vlogii tests
npm --prefix frontend run build
python3 tools/check_docs.py
```

最近代码验证记录为 **124 项 Python 测试通过**（含真实 FFmpeg 导出）、前端构建通过。提供方替身仅验证程序行为；AI 质量与未验项见 [验证记录](docs/vlogii-validation.zh.md)。

## 文档与分工

各文档页首提供中英文切换；代码、字段名与命令保持英文。

- [Mac / Safari 入门](docs/vlogii-mac-setup.md) · [使用指南](docs/vlogii-guide.zh.md) · [功能覆盖](docs/mvp-coverage.md) · [当前进度](docs/status.md)
- [剪辑规则](docs/editing-modes.md) · [风格模板](docs/style-templates.md) · [产品定义](docs/product.md) · [架构](docs/architecture.md)
- [免费字体/BGM 与许可](docs/free-resources.md)：已内置字体/纯音乐与混音，按需加载；风格模式支持上传音乐和节拍卡点。
- [协作交接](docs/collaboration.md)：杨康负责视频、AI、后端、渲染与集成；队友负责前端。
- [现行 OpenAPI](docs/vlogii.openapi.json)：`/api/vlogii`，运行时 `/docs`；[旧比赛契约](docs/contracts.md)作为规划参考。

待实现：艺术字/贴画封面、自动快剪接正文、任意语义自然语言修改、认证、云端存储与正式部署。原比赛完整验收尚未完成；现行实现与旧 `/api` 契约有独立边界。
