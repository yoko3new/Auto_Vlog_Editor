# Vlogii

[English](README.md) | **简体中文**

![Vlogii](frontend/public/brand/vlogii-logo.png)

**把日常素材剪成可编辑的短片。** Vlogii 是一个本地视频编辑器，使用 React 网页界面、FastAPI 后端、Gemini 分析和真实 FFmpeg 导出。网页与命令行均支持中文和英文。

当前版本是本地网页 MVP。

上传素材 → 分析画面与语音 → 校验按帧计算的时间线 → 渲染 → 精修、撤销和下载。

## 快速启动

需要 macOS 或 Linux，以及 **Python 3.11+、Node.js 20+、uv、FFmpeg 和 FFprobe**。FFmpeg 需要支持 `drawtext`、`zscale`、`tonemap`、`libx264` 和 AAC；风格标题需要 `libass`，HLG 导出还需要 `libx265`。

```sh
# macOS
brew install uv ffmpeg-full

# Ubuntu / Debian：先单独安装 uv，再安装视频工具
# sudo apt-get update
# sudo apt-get install -y ffmpeg fontconfig fonts-dejavu-core fonts-noto-cjk

git clone https://github.com/yoko3new/Auto_Vlog_Editor.git
cd Auto_Vlog_Editor
uv sync --frozen --extra dev
npm --prefix frontend ci
cp .env.example .env
```

在本地 `.env` 中填写 `GEMINI_API_KEY`，并选择你的账户可用的模型，然后执行：

```sh
npm --prefix frontend run build
uv run vlogii --language zh doctor
uv run vlogii --language zh serve
```

打开 **http://127.0.0.1:8000**。FastAPI 同时提供构建后的前端页面和接口。交互式接口文档位于 **http://127.0.0.1:8000/docs**。

服务仅绑定本机地址。只运行一个进程：渲染使用一个工作线程，最多允许八个待处理任务，每个项目只能有一个正在执行的任务。当前 MVP 没有身份认证，适用于本地使用。

开发前端时，保持后端运行并执行 `npm --prefix frontend run dev`；Vite 会将 `/api` 请求代理到 8000 端口。修改前端后，需要重新构建，FastAPI 提供的页面才会更新。

## 支持的功能

1. 创建项目并上传 MP4、MOV、M4V 或 MKV 素材；导入时读取元数据并去重。
2. 选择横竖屏、参与剪辑的素材、创作方向、字体、音乐、滤镜和剪辑模式。
3. 生成成片，查看实际的分析、规划和渲染阶段，然后预览或下载 MP4。
4. 精修章节、删除整章或时间区间、调整倍速、修改标题或外观，并批量应用修改。
5. 用成片中的一帧制作封面，设置标题、副标题、标签、字体和装饰；下载 PNG，或添加、替换一秒钟的封面开头。
6. 撤销到上一成功版本，或使用保存的请求和有效缓存重试失败任务；渲染失败时保留旧的成功成片。

| 模式 | 行为 |
| --- | --- |
| AI 自动（`auto`） | Gemini 根据创作方向和可选目标时长挑选、排列片段。 |
| 开头快剪（`highlights`） | 独立导出约五秒的快剪；默认每镜头最多约 0.5 秒、正常速度，原声静音且不叠语音字幕。 |
| 保留大部分（`keep_most`） | 按导入顺序保留素材，修剪黑场和口播长停顿；可选择删除没有识别到语音的区间。 |
| 完整保留（`keep_all`） | 按导入顺序保留全部勾选素材的区间；播放速度会改变成片长度。 |

保留模式可以添加约五秒的快剪开头。开头静音，正文保留所配置的原声和字幕。自动、快剪模式接受 1–1800 秒的近似目标时长；保留模式的长度由素材决定。程序不会重复素材来填满目标时长。

渲染支持源语言字幕、横竖屏排版、原始／明亮／温暖／冷白滤镜、**14 款内置字体和六首 CC0 纯音乐**，以及配乐循环和口播时压低配乐。章节标题和说明可以单独切换语言，不改变原始语音字幕。

三款参考风格支持按音乐节拍切镜、标题和时钟标签：`ig_city_day_in_life`、`ig_cozy_night_study`、`ig_narrated_college_day`。Python 计算节拍网格和切镜时间。风格成片将素材原声静音；满音量配乐目标为 −14 LUFS，真峰值上限为 −1 dBTP。未配置 Gemini 密钥时，风格模式按导入顺序使用素材和默认文字，不进行 AI 选片。

## 配置与数据

从 [.env.example](.env.example) 开始配置。密钥只保存在后端。

| 配置项 | 用途 |
| --- | --- |
| `GEMINI_API_KEY` | Gemini 凭据，用于画面分析、规划、语音识别和章节文字翻译。 |
| `VLOGII_MODEL` | 画面分析和规划模型；示例默认值为 `gemini-3.8-flash`。 |
| `VLOGII_SPEECH_MODEL` | 单独处理原始音频的语音识别模型；示例默认值为 `gemini-3.5-transcribe`。 |
| `VLOGII_SPEECH_LANGUAGE` | 语音识别的语言提示，默认 `auto`。 |
| `VLOGII_THINKING` | 画面分析和规划请求的思考级别。 |
| `VLOGII_LANGUAGE` | 命令行默认语言；可用 `--language en` 或 `--language zh` 覆盖。 |
| `VLOGII_FFMPEG`、`VLOGII_FFPROBE` | 可选的可执行文件绝对路径；macOS 自动优先使用 Homebrew 的 `ffmpeg-full`。 |
| `VLOGII_FONT` | 可选的字幕字体覆盖。 |

模型访问权限、接口费用和识别质量取决于你的提供方账户。`doctor` 检查本地配置和视频工具能力，不能证明模型可用或 AI 质量达标。启用相应分析时，视频代理和原始音频会发送给 Gemini。

项目文件保存在已被 Git 忽略的 `projects/` 中，包括导入素材、分析和转录缓存、计划、任务状态、版本历史、日志和导出文件。执行 `uv run vlogii --projects /absolute/path/to/projects serve` 可指定其他目录。重启或备份时，请保留项目目录。

网页上传限制为 **50 段素材、单段 512 MiB、单次上传 2 GiB、原素材总长 30 分钟**。风格配乐支持 MP3/M4A/AAC/WAV/FLAC/OGG，最大 200 MiB，长度为 10 秒至 15 分钟。

## 命令行示例

```sh
uv run vlogii --language zh                           # 交互式会话
uv run vlogii --language zh init my-day /absolute/path/to/footage --color sdr
uv run vlogii --language zh run my-day --mode keep_all
uv run vlogii --language zh run my-day --mode highlights --shot-seconds 0.5 --speed 1
uv run vlogii --language zh run my-day --style ig_city_day_in_life --music /absolute/path/to/song.mp3
uv run vlogii --language zh edit my-day --instruction "00:12到00:18加速到2倍"
uv run vlogii --language zh retry my-day
uv run vlogii --language zh undo my-day
uv run vlogii --language zh styles
```

时间修改以**当前成功成片的时间戳**为准，包含封面开头。支持中文和英文的明确时间区间删除、调速指令；任意语义修改尚未实现。风格成片目前不支持章节时间或速度精修。

## 当前限制

- 仅支持本地文件存储；身份认证、云端存储、公开部署和多个工作进程尚未实现。
- 网页默认输出为 1080×1920、30 帧／秒、SDR/H.264/AAC。全部素材为 HLG 时可以使用 10-bit HEVC；混合素材使用 SDR。HEVC 播放取决于浏览器和设备；要求 SDR 的滤镜会拒绝不兼容的 HLG 设置。
- 尚不支持人物自动抠图、自定义贴纸或字体上传、任意语义编辑，也不保证精确目标时长。
- 自动检查不能证明真实素材的观感、转录准确率、原生 Safari／移动端兼容性或生产负载能力。需要使用自己的素材，另行验证真实 Gemini 和人工浏览器操作。

## 内置素材

运行时字体、音乐的来源、哈希和许可标识记录在 [assets/manifest.json](src/vlogii/assets/manifest.json) 中。完整许可声明保留在 [assets/licenses/](src/vlogii/assets/licenses/)、[style/fonts/](src/vlogii/style/fonts/)、[frontend/public/fonts/](frontend/public/fonts/) 和 [frontend/public/font-licenses/](frontend/public/font-licenses/) 中。分发内置素材时，请保留这些声明。仓库目前没有声明项目整体代码许可证。

凭据、上传素材、生成视频、缓存和私人验证记录不提交 Git。
