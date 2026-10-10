# Vlogii

A local web app that turns real footage into a small, editable vlog.

**Upload → Gemini video analysis → validated plan → FFmpeg export → preview, edit, undo and download.**

This is an independent implementation informed by a working VX workflow and its failure cases. It does not copy or import VX. Code and implementation notes are in English; the Mac setup guide is in Chinese.

## 在 Mac 上部署和使用（Safari）

一步一步的说明、没有 API key 时的演示和常见问题见 **[Mac 部署教程](docs/vlogii-mac-setup.md)**。

1. 安装环境（只需一次；需要先装好 [Homebrew](https://brew.sh)）：

   ```sh
   xcode-select --install
   brew install ffmpeg-full uv node
   ```

2. 下载代码、安装依赖并构建网页：

   ```sh
   git clone --branch feng-emergence https://github.com/yoko3new/Auto_Vlog_Editor.git vlogii
   cd vlogii
   uv sync --frozen --extra dev
   cp .env.example .env
   cd frontend && npm ci && npm run build && cd ..
   ```

3. 用 `open -e .env` 填写 `GEMINI_API_KEY`（在 [Google AI Studio](https://aistudio.google.com/apikey) 获取）。没有 key 时可先做教程第 6 步的无 key 演示。
4. 启动服务，然后用 Safari 打开 **http://127.0.0.1:8000**（在终端按 `Ctrl + C` 停止）：

   ```sh
   uv run vlogii doctor
   uv run vlogii serve
   ```

5. 使用：在 *No. 1* 导入 10–15 段视频 → 在 *No. 2* 写一句想留下的感觉并点 **Make my film** → 点圆形 **Play** 观看 → 在 *No. 3* 改标题、调暖或去掉素材后点 **Apply changes** → **Undo last version** 撤销 → **Download MP4** 下载。

素材、成片和 `.env` 只保存在本机（`projects/` 与 `.env` 已被 Git 忽略），AI 分析时只把低分辨率副本发给 Gemini。服务只监听本机：保持单进程运行，不要暴露到公网。Linux 安装见 [实现说明](docs/vlogii-guide.md)。

## Included

- Upload real footage, inspect metadata and deduplicate identical files.
- Gemini video understanding, source-language speech transcription and structured planning.
- Strict validation and deterministic frame-based timing before rendering.
- Original audio, speech captions, occasional text, portrait or landscape exports.
- Browser-friendly SDR/H.264 by default; optional all-HLG 10-bit HEVC preservation.
- Title changes, controlled warmth and clip exclusion without another AI call.
- Successful versions, undo, persistent actual progress, restart recovery and download.
- An editorial web UI after Emergence Magazine’s long-form features, with the vlogii fresh palette and approved logo.
- Full FFmpeg logs and output verification; failures preserve previous successful films.

Limits: 50 clips, 512 MB per clip, 2 GB per upload, 30 minutes of source footage. Target duration guides the AI; it is not guaranteed or padded with repeated footage. Warmth edits use SDR. HEVC playback depends on the browser and display. AI captions and editorial choices require human review.

## Verify

```sh
uv run pytest -q
uv run ruff check src/vlogii tests
uv run ruff format --check src/vlogii tests
cd frontend && npm run build
```

Tests include real FFmpeg exports. Provider test doubles verify failure handling, not live AI performance. Actual results and limitations are recorded in [local validation](docs/vlogii-validation.md).

## Documentation and scope

- [Mac 部署教程](docs/vlogii-mac-setup.md) (Chinese, step by step)
- [Setup, modules, CLI, supported formats, web design and limitations](docs/vlogii-guide.md)
- [Local API specification](docs/vlogii.openapi.json); interactive docs at `/docs`
- [Implementation and validation status](docs/status.md)
- [Existing team product plan](docs/product.md) and [contracts](docs/contracts.md)

This branch implements the local vlog web MVP requested after VX validation. Existing team documents, schemas and substitutes are preserved as planning material. The application uses a separate `/api/vlogii` namespace; it does not claim compatibility with the older `/api` contract.

BGM, beat matching, magazine decorations, arbitrary natural-language editing, authentication, cloud storage, Replit deployment and NLE exports are outside this release. The original competition MVP is not presented as fully delivered.

Only source, dependency locks, English documentation and non-sensitive verification summaries are published. Footage, transcripts, AI caches, generated videos and keys are excluded.
