# Vlogii

**中文** · [English](vlogii-guide.md)

一个适用于日常 Shorts 的本地 Web 应用，带有可编辑的导出功能。

**上传 → Gemini 视频分析 → 经过验证的剪辑计划 → 真实的 FFmpeg 导出 → 预览、编辑、撤销和下载。**

目前的实现是一个本地 MVP。下一个产品方向是风格化封面、开头快剪和带字幕的正文；封面和自动开头/正文拼接仍待实现。参见 [Shorts 产品方向](shorts-direction.md)。

## 本地运行

运行环境要求：macOS 或 Linux、Python 3.11+、Node.js 20+、[uv](https://docs.astral.sh/uv/)，以及支持 `drawtext`、`zscale`、`tonemap`、AAC、H.264 和 HEVC 的 FFmpeg。风格成片还需要 `ass` 滤镜（libass），`ffmpeg-full` 和 Ubuntu 的 `ffmpeg` 都已包含。

在 macOS 上：

```sh
brew install ffmpeg-full
```

在 Ubuntu 上：

```sh
sudo apt-get update
sudo apt-get install ffmpeg fontconfig fonts-dejavu-core fonts-noto-cjk
```

克隆实现分支并安装锁定的依赖项：

```sh
git clone --branch codex/integrate-feng-ui https://github.com/yoko3new/Auto_Vlog_Editor.git vlogii
cd vlogii
uv sync --frozen --extra dev
cp .env.example .env
```

将你的 Gemini API 密钥添加到 `.env`。保持 `.env` 仅在本地。默认情况下，`VLOGII_MODEL=gemini-3.8-flash` 用于视觉分析/规划，`VLOGII_SPEECH_MODEL=gemini-3.5-transcribe` 用于语音。两者使用相同的密钥。模型是可配置的，因为账户的可用性可能会发生变化。Gemini 接收低分辨率视频副本和单独提取的原始音频。当提供商支持删除时，远程上传的文件在识别后会被删除。新模型访问已通过单片段实测运行；准确性尚未进行基准测试；参见 [修复与模型选择](mvp-fixes.md)。

构建前端并启动服务器：

```sh
cd frontend
npm ci
npm run build
cd ..
uv run vlogii doctor
uv run vlogii serve
```

打开 **http://127.0.0.1:8000**。服务器特意绑定到 localhost。请运行单个服务器进程。不要使用多个 worker 或将此未认证的 MVP 作为公共服务暴露。

在 macOS 上，应用程序会自动优先使用 Homebrew 的 `ffmpeg-full`，因此不需要手动修改 `brew link` 或 PATH。必要时可使用 `VLOGII_FFMPEG` 和 `VLOGII_FFPROBE` 覆盖可执行文件路径。

## 功能特性

- 上传 MP4、MOV、M4V 或 MKV 素材，检查其实际元数据并对相同文件去重。
- 创作导向和目标时长为可选项。可选择 AI 自动、开头快剪、保留大部分或保留全部。如果没有目标时长，AI 自动会决定长度，快剪模式目标为 5 秒，而保留模式按保留规则决定时长。可点击示例直接填充输入和模式而无需立即提交。参见 [剪辑模式与时间修改](editing-modes.md)。
- Gemini 观看代理视频并描述可见事件。单独的 Gemini 语音请求处理提取为 PCM 的原始音频。字幕保留原语言。`VLOGII_SPEECH_LANGUAGE=auto` 支持混合语言；使用受支持的 BCP-47 代码进行明确提示。渲染器根据输出宽度和高度测量完整文本，并默认使用随程序附带的 Noto CJK；设置 `VLOGII_FONT` 可覆盖字体。语音转录需要人工审核。
- AI 选择源区间和少量事实性文字。Python 验证引用、范围和叠加文字，然后以整数帧计算所有输出时间。
- FFmpeg 在正常模式下保留原始音频，为无音频的剪辑添加静音，烧录文本和字幕，规范化片段并进行拼接。快剪模式默认对源音频静音并忽略语音字幕。
- 适合浏览器的 SDR/H.264 是网页默认格式。纯 HLG 项目可以使用 HEVC 保留 10 位 HDR；混合 HDR/SDR 素材会色调映射为 SDR。HEVC 播放取决于浏览器和显示器。
- 更改标题、应用受控的暖色调调整或移除选定的源剪辑。这些编辑会渲染一个新版本，而无需再次调用 AI。撤销操作会恢复上一个成功的版本且无需渲染。
- 失败的任务会保留之前成功的导出成果。进度基于实际阶段，而非模拟的百分比。服务器重启会将中断的作业标记为可重试的失败。
- 重试会保留失败任务的完整请求和类型，包括编辑操作。它会复用有效的视觉/语音缓存、保存的计划和已完成渲染的片段。具有不同导向的新生成将从最初导入的剪辑重新规划。
- 浏览器提供中英文切换，并在本地保存。支持 Unicode 项目名称和创作导向。界面语言不会强制指定语音语言。
- 本地项目记录、分析缓存、计划、时间线、完整的 FFmpeg 日志和成功的版本都存储在 `projects/` 下，并被 Git 忽略。

限制：50 个剪辑、每个剪辑 512 MB、每次上传 2 GB、30 分钟源素材，以及 AI 自动/快剪模式可选的 1–1800 秒目标时长。色调编辑使用 SDR 输出。重新生成 AI 计划会使用最初导入的剪辑集；移除剪辑是版本编辑，而不是永久删除源素材。

<a id="styles"></a>

## 风格：背景音乐、节拍卡点与参考片风格

风格是从参考片学到的模板：镜头长度与开头快剪、调色目标、标题与时间戳排版，以及混音规则。测量结果、参考片本身并未锁拍的发现，以及每个模板的由来见 [风格模板](style-templates.md)。

1. 网页里在 *No. 2* 选择风格、内置曲或上传音乐；命令行用 `vlogii music` 添加音乐，用 `vlogii run --style` 生成。
2. 有 Gemini 密钥时，已缓存的画面分析用于风格请求：Gemini 按时间顺序返回片段、简短活动标签和标题文字，Python 校验片段 ID、区间和总时长，不合格时带反馈重试一次。风格成片会静音原声，所以不做语音转写。没有密钥时按导入顺序使用全部素材和风格默认标题，页面会注明。重试复用已保存的选择。
3. `style/planner.py` 检测音乐节拍（librosa，修正起音延迟），从强拍开始，把成片取整到整小节，按参考片的镜头秒数选拍数倍数，并按顺序分配到各片段。每一刀与节拍网格的偏差都在半帧以内。不会重复画面凑时长；素材不足或音乐太短会明确提示。
4. `style/render.py` 修剪每个镜头并向参考片调色（HDR 转为 SDR），用随程序附带的 OFL 字体（Poppins、DM Serif Display、Share Tech Mono）通过 ASS 排版标题、时钟和标签，静音素材原声，并把音乐处理到 −14 LUFS、真峰值上限 −1 dBTP（在 AAC 编码后实测）。旁白风格还可以在旁白下压低音乐，并按转写稿出字幕（仅命令行）。
5. 结果是一个普通版本，包含 `style.json`、`style-plan.json`、日志和 `verification.json`。改标题、调暖和去掉素材会按节拍重新剪，不再调用 AI；调速和按时间段修改会破坏卡点，因此会被拒绝。撤销和下载照常可用。

音乐：MP3、M4A、AAC、WAV、FLAC 或 OGG，10 秒到 15 分钟，最大 200 MB，保存在项目中。请使用你有权发布的音乐。`GET /api/vlogii/styles` 列出风格，`POST /api/vlogii/projects/{name}/music` 添加音乐，生成请求接受 `style_id`。

```sh
uv run vlogii styles
uv run vlogii music my-day ~/Music/song.mp3
uv run vlogii run my-day --style ig_city_day_in_life
uv run vlogii style-preview ig_cozy_night_study --music song.mp3 --clips ~/Movies/day --out work/day.mp4
```

限制：风格成片为 SDR/H.264，按项目尺寸、30 fps 输出；三个风格都是竖屏。节拍检测听不见声音：没有清晰底鼓的音乐可能估错强拍，页面会显示这类警告。学习新风格使用 `tools/style_lab/`，需先运行 `uv sync --extra style-lab`。

## 范围与兼容性

此分支基于经过测试的 VX 工作流实现了一个**本地 vlog 网页 MVP**。这并非声称已交付原团队的完整竞赛 MVP。背景音乐和卡点通过[风格](#styles)提供。杂志风装饰、任意自然语言编辑、身份验证、云存储、Replit 部署、场景检测启发式算法和 NLE 导出均不包含在此版本中。

现有的 [团队产品定义](product.md)、[架构](architecture.md)、[契约](contracts.md)、schema、样例和开发替身均作为规划资料保留。Vlogii 使用明确且独立的 `/api/vlogii` 命名空间和本地模型；它并不假装实现了较旧的 `/api` 契约。实时 API 规范位于 `/openapi.json`，交互式文档位于 `/docs`；已签入的快照为 [vlogii.openapi.json](vlogii.openapi.json)。

## 代码结构

```text
src/vlogii/
  models.py       Strict local schemas
  storage.py      Atomic JSON writes and OS project locks
  media.py        FFmpeg discovery, probing, hashes and SDR proxies
  ai.py           Gemini video reviews and validated planning
  speech.py       Independent original-audio Gemini transcription
  i18n.py         Chinese CLI status messages
  editorial.py    Retention modes, black detection and time-range changes
  timeline.py     Deterministic frame timing and caption remapping
  render.py       Text, audio, HDR, encoding and output verification
  pipeline.py     Analysis caching, generation, edits and undo
  style/          Templates, beat detection, beat-locked planning, style rendering and fonts
  api.py          Uploads, persistent jobs, one worker and media delivery
  cli.py          Web startup and debugging commands
frontend/         React + TypeScript + Vite editor
tests/           Validation, failure recovery, API and real-media checks
```

## 验证

```sh
uv run pytest -q
uv run ruff check src/vlogii tests
uv run ruff format --check src/vlogii tests
cd frontend && npm run build
```

真实媒体测试会生成简短的合成片段并需要 FFmpeg。跳过的媒体测试不算作成功的视频验证。API 提供商测试替身仅检查失败行为；它们不能算作实测的 AI 验证。有关实际结果和遗留限制，请参见 [验证记录](vlogii-validation.zh.md)。

保留的团队基架仍可单独检查：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 contracts/validate_examples.py
PYTHONDONTWRITEBYTECODE=1 python3 contracts/collaboration/validate_collaboration.py
python3 tools/check_docs.py
```

## CLI 调试

Web 应用和 CLI 使用相同的模块：

```sh
uv run vlogii init my-day /absolute/path/to/footage --color sdr
uv run vlogii run my-day --mode keep_all
uv run vlogii run my-day --mode highlights --seconds 5 --shot-seconds 0.5 --speed 1
uv run vlogii run my-day --seconds 120 --direction "A chronological diary"
uv run vlogii retry my-day  # Resume the saved failed generation or edit
uv run vlogii edit my-day --title "Slow Sunday" --warmth 0.5
uv run vlogii status my-day
uv run vlogii render my-day   # Reuse a saved plan; no new AI request
uv run vlogii undo my-day
```

使用 `vlogii --projects /another/local/directory ...` 选择其他工作区。此版本支持 macOS 和 Linux；Windows 项目锁定尚未实现。

在终端中运行 `uv run vlogii` 选择中文/英文并停留在交互式生成/重试/编辑/撤销会话中。命令接受 `--language zh` 或 `--language en`；无论界面为何种语言，描述均可使用任一语言。例如：`uv run vlogii --language zh run 周末 --direction "保留早餐和散步"`。失败的交互命令无需退出即可提供重试；非交互式使用会打印明确的重试命令。1–1800 秒的约束仅适用于 AI 自动/快剪模式中的显式目标；保留模式不设置目标。

重试 API 为 `POST /api/vlogii/projects/{name}/retry`，且无需请求体。`JobState` 添加了 `retryable` 和 `kind`；生成/编辑接受可选的 `language`。现有请求依然有效。保存的请求在本地任务记录中保持私密。当前的重试没有旧契约的 `request_id` 幂等性保证；后端会阻止在同一项目上同时进行作业。前端控件和 [OpenAPI](vlogii.openapi.json) 使用相同的字段。

生成请求添加了 `mode`、`remove_no_speech`、`speed` 和 `shot_seconds`；`target_seconds` 现在是可选的（默认为 null）。编辑请求添加了以当前成片秒数计的 `remove_ranges` 和 `speed_ranges`、可空的 `speed`，以及用于受支持的删除/变速短语的 `instruction`。`ProjectView.selection` 描述了最新版本解析后的模式。这更改了省略目标时的行为；需要旧默认值的调用方必须显式发送 30。参见 [剪辑语义](editing-modes.md) 和更新后的 [OpenAPI](vlogii.openapi.json)。

## 数据与发布

仅源代码、依赖项锁定、双语文档、API schema和非敏感验证摘要归入 Git。API 密钥、素材、私有提示词、转录本、生成的视频、分析缓存或本地绝对路径均不属于已发布项目的一部分。

首个版本适用于本地测试和迭代。成功解码并不代表良好的剪辑选择、正确的转录、在所有输入上的性能表现或具备生产环境可用性。

### 快切与播放速度

`run/plan --speed 1 --shot-seconds 0.5` 更改导出速度以及快剪的单镜头播放上限。`edit --speed 1` 恢复源速度；`edit --instruction "00:12到00:18加速到2倍"` 仅更改当前成片中的该区间。速率是绝对的；字幕和音频遵循帧时间线。Web UI 为节奏和速度提供了单独的单选按钮组。参见 [剪辑规则](editing-modes.md) 和 [Shorts 产品方向](shorts-direction.md)；封面样式设计和自动开头/正文拼接仍待实现。

快剪导出现在默认静音源音频，并在编辑/重试中保留该选择。正常正文/保留模式保留源音频。静音 AAC 音轨使 MP4 适合未来的开头/正文串联；可在静音开头上混入可选的内置 BGM。

<a id="web-design"></a>

## 集成后的网页编辑器

`codex/integrate-feng-ui` 分支将 `feng-emergence` 的前端设计与当前 `kang` 功能结合。页面使用带阅读进度的白色细顶栏、单列阅读布局、宽幅视频区域、圆形播放按钮和编号章节。页面依次为创建项目/导入素材、生成设置、已有成片修改、底部预览；已导入素材清单可展开。“应用修改”在整片速度旁及修改表单底部均可点击，“查看成片”跳到最后的播放器。中英文切换、重试、生成模式、示例、镜头节奏、速度、时间区间编辑与撤销均保留。

清新配色以浅色背景和薄荷绿重点色为主。Newsreader、Libre Franklin 和 Courier Prime 通过 Fontsource 按 OFL 许可随应用打包，不需要外部字体请求；中文采用本机系统字体回退。网页字体仅改变编辑器，MP4 字幕字体和排版沿用现有渲染规则。品牌资源位于 `frontend/public/brand`。

首次在 macOS 和 Safari 上使用，见 [Mac 入门指南](vlogii-mac-setup.md)。

许可全文保留在 `frontend/public/fonts`，随前端一起提供。

时长输入支持秒数、“约2分钟”“约120秒”或“01:30”等常用写法，解析为近似秒数目标；不合法或超范围时提示纠正。示例按钮位于问题与输入框之间。生成章节的视频速度在点击“生成我的影片 / 生成一个新版本”后生效；修改章节的“整片速度”点击“应用修改”后复用当前计划调速。

顶栏不再显示完成标识。任务进行时显示视频解析、语音识别、画面分析、剪辑规划、视频制作及真实任务信息和片段计数。进度条反映当前批次，不估算整片百分比或剩余时间；分析阶段会按素材交替。没有计数的排队、规划、合并和校验阶段使用不定进度条。处理期间滚动页面仍可见，成功后收起。

字体与配乐：生成章节默认使用内置思源黑体和自动配乐；可预览字体、试听六首纯音乐、选“不添加”、调音量及口播压低。已有成片在修改章节更换后点击“应用修改”，保留旧版可撤销。资源随应用自动加载，详见[内置资源与许可](free-resources.md)。风格模式支持音乐上传和自动卡点；自定义字体上传仍待实现。
