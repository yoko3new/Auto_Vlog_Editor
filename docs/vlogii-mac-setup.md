# 在 Mac 上使用 Vlogii

**中文** · [English](vlogii-mac-setup.en.md)

[返回总览](../README.md) · [使用指南](vlogii-guide.zh.md)

本教程使用集成分支 `codex/integrate-feng-ui`，在终端安装并用 Safari 运行本地网页。

## 1. 安装环境

```sh
# Install developer tools if needed.
xcode-select --install
# Install Homebrew if needed.
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
brew install ffmpeg-full uv node
```

需要 Node.js 20+；用 `node -v` 检查。uv 会准备 Python 3.11+。完整版 FFmpeg 提供字幕、色彩转换和编码，应用会自动优先找到 Homebrew 的完整版。

## 2. 下载与构建

```sh
cd ~/Desktop
git clone --branch codex/integrate-feng-ui https://github.com/yoko3new/Auto_Vlog_Editor.git vlogii
cd vlogii
uv sync --frozen --extra dev
cp .env.example .env
npm --prefix frontend ci
npm --prefix frontend run build
```

已有仓库可继续使用，先切换到集成分支并更新；有本地修改时先保留自己的工作。私有仓库需要 GitHub 登录权限。

## 3. 配置 Gemini

在 [Google AI Studio](https://aistudio.google.com/apikey) 获取密钥，用 `open -e .env` 打开配置并保存。将占位内容替换为本地密钥：

```text
GEMINI_API_KEY=YOUR_LOCAL_KEY
VLOGII_MODEL=gemini-3.8-flash
VLOGII_SPEECH_MODEL=gemini-3.5-transcribe
```

画面与规划模型、语音模型分别配置，共用密钥；若账号不可用，请选用账号可访问的兼容模型。`.env` 已被 Git 忽略，不提交密钥。改配置后重启服务。没有密钥可以浏览页面、播放与修改已有成功成片；新素材分析、转录和 AI 选片需要密钥。手写计划的 CLI 路径见 [使用指南](vlogii-guide.zh.md)。

## 4. 启动

```sh
uv run vlogii doctor
uv run vlogii serve
```

打开 **http://127.0.0.1:8000**，保持终端运行；按 `Ctrl+C` 停止。下次进入项目目录运行 `uv run vlogii serve`。端口占用可使用 `uv run vlogii serve --port 8010` 并打开 http://127.0.0.1:8010。服务仅监听本机，运行一个进程。

## 5. 跑通一段影片

1. 顶栏切换中文或英文。在素材章节填写项目名，支持中英文字母、数字、下划线和连字符，开头须为字母或数字；如 `my-sunday`。拖入或选择 MP4/MOV/M4V/MKV，选择横竖屏后导入。
2. 在创作章节选择 AI 自动、开头快剪、保留大部分或完整保留。描述可留空；点击示例会填入文本并选择对应模式，确认后才提交。
3. AI 自动/快剪可填写 1–1800 秒近似目标；保留模式没有目标秒数。快剪默认每镜头最多 0.5 秒、1 倍速、静音，独立导出；尚不自动接正文。节奏与视频速度均可选。
4. 生成期间会显示进度；失败时点击 Retry，保留原请求和缓存，无需重新导入。旧成功成片仍可播放。
5. 完成后点击视频中的圆形播放按钮；下载 MP4。默认 SDR/H.264 兼容性较好；保留 HLG 的 HEVC 播放取决于设备。
6. 修改章节支持标题、暖度、素材排除、整片速度，以及当前成片时间区间删除/调速。点击示例后检查时间，再提交。撤销恢复上一成功版本。

时间修改以当前成片为坐标，规则和限制见 [剪辑规则](editing-modes.md)。字幕发布前需人工校对。

## 6. 更新与本地数据

先停止服务，再执行：

```sh
cd ~/Desktop/vlogii
git pull --ff-only
uv sync --frozen --extra dev
npm --prefix frontend ci
npm --prefix frontend run build
uv run vlogii serve
```

素材、缓存、计划和成片存于 `projects/`，不提交 Git。分析会把画面代理与原声发送给 Google Gemini；原片与导出留在本机。网页字体随应用打包，不需要远程字体请求。若页面仍显示旧样式，Safari 按 Option+Command+R 强制刷新。
