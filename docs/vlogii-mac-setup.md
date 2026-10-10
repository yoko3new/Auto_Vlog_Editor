# 在 Mac 上部署和使用 Vlogii

[返回项目总览](../README.md) · [实现说明（英文）](vlogii-guide.md)

这份教程面向第一次在自己 Mac 上运行 Vlogii 的人：从安装环境、下载代码、配置 Gemini，到在 Safari 里跑通一个完整 demo。所有命令都在「终端」(Terminal) 里执行。

## 1. 安装环境（只需一次）

```sh
# 苹果命令行工具（含 git）；已安装会提示 already installed
xcode-select --install

# Homebrew；已安装可跳过
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# 视频处理、Python 包管理器和 Node.js
brew install ffmpeg-full uv node
```

- `ffmpeg-full` 是完整版 FFmpeg，提供字幕、HDR 转换和 H.264/HEVC 编码。程序会自动找到它，不需要手动设置 PATH。
- Python 不需要单独安装：下一步的 `uv` 会自动准备 3.11 以上的版本。
- 用 `node -v` 检查 Node.js 版本，需要 v20 或更高。

## 2. 下载代码并安装依赖

```sh
cd ~/Desktop
git clone --branch feng-emergence https://github.com/yoko3new/Auto_Vlog_Editor.git vlogii
cd vlogii

uv sync --frozen --extra dev          # 后端依赖
cp .env.example .env                  # 本地配置文件
cd frontend && npm ci && npm run build && cd ..   # 构建网页
```

如果仓库是私有的，`git clone` 会要求登录 GitHub。可以先 `brew install gh`，再运行 `gh auth login` 按提示登录，然后重新 clone。

## 3. 配置 Gemini（需要 AI 自动选片时）

1. 在 [Google AI Studio](https://aistudio.google.com/apikey) 创建 API key。
2. 运行 `open -e .env`，填好后保存：

   ```text
   GEMINI_API_KEY=你的key
   VLOGII_MODEL=gemini-3-flash-preview
   ```

3. 如果之后提示模型不可用，把 `VLOGII_MODEL` 改成你账号可用的 Gemini 型号。

key 只保存在本机的 `.env` 里，`.env` 已被 Git 忽略，不要把它发给别人或提交到仓库。没有 key 也能先看效果，见第 6 步。

## 4. 启动并用 Safari 打开

```sh
uv run vlogii doctor    # 检查 FFmpeg、编码器和 Gemini key
uv run vlogii serve     # 启动服务，保持这个终端窗口打开
```

`doctor` 正常时会列出 FFmpeg 路径、SDR 编码器和 HLG 编码器；没填 key 时显示 `Gemini key: missing`，此时仍可使用第 6 步的无 key 演示。

用 Safari 打开 **http://127.0.0.1:8000**。

- 停止服务：在运行 `serve` 的终端按 `Ctrl + C`。
- 下次使用：`cd ~/Desktop/vlogii`，然后 `uv run vlogii serve`。
- 服务只监听本机地址，同一时间运行一个即可，不要暴露到公网。

## 5. 完整 demo（有 Gemini key）

1. **准备素材**：把 iPhone 上 10–15 段日常视频 AirDrop 到 Mac，总长 3 分钟以内效果最好。支持 MP4、MOV、M4V、MKV。
2. **导入（No. 1 Your Moments）**：项目名只用英文字母、数字、`-` 或 `_`，例如 `my-sunday`。把视频拖进浅绿色区域，或点 **Choose video clips**；选择竖屏或横屏后点 **Import my moments**。
3. **生成（No. 2 Your Direction）**：用一句话写下想留下的感觉，选择 30 / 60 / 150 秒，点 **Make my film**。右上角显示 *Working*，完成后变为 *Film ready*。
4. **播放**：在页面上方的大画面里点圆形 **Play**。
5. **修改（No. 3 Make It Yours）**：改标题、勾选 *A little warmer*、在 *Leave a clip out* 里去掉某段素材，点 **Apply changes**。修改会生成新版本，不再调用 AI。
6. **撤销与下载**：**Undo last version** 回到上一个成功版本；画面下方的 **Download MP4** 下载当前成片。

iPhone 的 HDR 视频不需要预先处理：默认的 *Standard* 设置会转成 Safari 和大多数播放器都能直接播放的 SDR/H.264。只有所有素材都是 HLG 时，才可以在 *Video compatibility* 里选择保留 HDR（HEVC）。

## 6. 没有 API key 时的演示

先用命令行导入素材，再写一个简单的剪辑计划代替 AI，即可渲染出真实成片；之后网页里的改标题、调暖、去掉素材、撤销和下载都能使用。若服务正在运行，先按 `Ctrl + C` 停止。

```sh
# 把 ~/Movies/demo-clips 换成你的素材文件夹；横屏素材在末尾加 --landscape
uv run vlogii init demo ~/Movies/demo-clips --color sdr

# 每段素材取前 3 秒（最多 12 段），第一段配标题 Slow Sunday
uv run python - <<'EOF'
import json, pathlib
d = pathlib.Path("projects/demo")
clips = json.loads((d / "project.json").read_text())["clips"]
segments = []
for i, c in enumerate(clips[:12]):
    end = round(min(c["duration"], 3.0), 2)
    seg = {"clip_id": c["id"], "in_sec": 0.0, "out_sec": end, "purpose": "scene", "overlays": []}
    if i == 0:
        seg["overlays"] = [{"start": 0.2, "end": min(2.2, end), "text": "Slow Sunday"}]
    segments.append(seg)
plan = {"schema_version": 1, "title": "Slow Sunday", "reasoning": "Hand-written demo plan", "segments": segments}
(d / "plan.json").write_text(json.dumps(plan, indent=1))
print(len(segments), "segments written")
EOF

uv run vlogii render demo     # 渲染第一版成片
uv run vlogii serve           # 重新启动网页
```

刷新 Safari，在 *Open a saved project* 里选择 `demo`。此时 **Make my film / Make a new version** 仍需要 Gemini key，其余功能都可使用。

## 7. 更新到最新版本

```sh
cd ~/Desktop/vlogii
git pull
uv sync --frozen --extra dev
cd frontend && npm ci && npm run build && cd ..
uv run vlogii serve
```

## 8. 数据保存在哪里

- 导入的素材、分析缓存、剪辑计划和每个版本的成片都保存在项目文件夹的 `projects/` 目录，已被 Git 忽略。
- 只有 AI 分析时会把低分辨率副本发送给 Google Gemini；原片和导出的视频留在本机。
- 删除某个项目：停止服务后删除 `projects/项目名` 文件夹。

## 9. 常见问题

| 现象 | 处理 |
| --- | --- |
| 页面只显示一段 JSON，提示 *Build the frontend* | 网页还没构建：`cd frontend && npm ci && npm run build` |
| 页面还是旧样式 | Safari 缓存：按 `Option + Command + R` 强制刷新 |
| 提示 *Set GEMINI_API_KEY* | `.env` 未填写 key，或填写后没有重启 `serve` |
| `doctor` 提示 FFmpeg 缺失 | `brew install ffmpeg-full`，然后重新打开终端 |
| 端口 8000 被占用 | `uv run vlogii serve --port 8010`，再打开 http://127.0.0.1:8010 |
| 导入按钮是灰色的 | 先选择视频，并确认项目名只含英文字母、数字、`-` 或 `_`，且以字母或数字开头 |
| 成片在其他浏览器无法播放 | 选择 *Standard* 颜色设置重新建项目，或点 **Download MP4** 用 QuickTime 播放 |

字幕和 AI 选片结果由模型生成，发布前请人工检查。更多实现细节、命令行调试和限制见 [实现说明](vlogii-guide.md)。
