# 参考片风格模板：BGM 混音与节拍卡点

**中文** · [English](style-templates.en.md)

[返回项目总览](../README.md)

何时读：想了解三个风格从参考片学到了什么、怎样卡点和混音，或要学习新的参考片时读。

**状态：** 已并入 `codex/integrate-feng-ui` 的 Vlogii 网页应用：在 *No. 2* 选风格和音乐即可出片，命令行用 `vlogii run --style`。已在合成素材、两段真实音乐和真实 HTTP 流程上验证（见[验证记录](#evidence)）；尚未用真实用户素材和真实 Gemini 做观感验收。团队 `contracts/` 未改，Vlogii 使用自己的 `/api/vlogii` 接口。范围决定见[决策记录](decisions.md)。

## 从三个参考片学到了什么

| 模板 | 参考 | 节奏（实测） | 声音（实测） | 画面与文字 |
| --- | --- | --- | --- | --- |
| `ig_cozy_night_study` | [DNvYfcx5EBk](https://www.instagram.com/reel/DNvYfcx5EBk/) 15.3 秒 | 24 个镜头，中位 0.67 秒，从头到尾均匀，无快剪开头 | 纯音乐，−14.0 LUFS，LRA 1.7，真峰值 −1.2 dBTP，无淡入淡出，无人声 | 暖色台灯（暖度 0.22、饱和 0.46）；“cozy night / study / with me”三层标题，小字打字机效果，活动小标签 |
| `ig_city_day_in_life` | [DYui5l2x141](https://www.instagram.com/reel/DYui5l2x141/) 37.9 秒 | 前 3.77 秒 13 个镜头（中位 0.30 秒）快剪开头，之后中位 0.70 秒 | 纯音乐，−15.6 LUFS，真峰值 +3.0 dBTP（已削波），无人声 | 自然日光（饱和 0.30）；白色粗体 “day in my life”、时间范围、地点标签；正文数字时钟加小说明 |
| `ig_narrated_college_day` | [DWxtN9tCoc2](https://www.instagram.com/reel/DWxtN9tCoc2/) 64.9 秒 | 前 2.87 秒 21 个镜头（中位 0.13 秒）闪剪开头，正文中位 0.67 秒、跨度大，结尾 3.55 秒黑场 | 99% 时长检测到人声并有逐句字幕，判断为旁白；−14.1 LUFS，结尾 0.6 秒淡出 | 阴天冷调（暖度 0.06）；深红粗体标题配白色星星；中部数字时钟，62% 高度处小写字幕 |

测量值来自 `style/references/*.profile.json`；画面与文字一栏来自人工看帧。模板 JSON 的 `reference.learned` 逐条标明是实测（measured）还是观察（observed）。

### 关键发现：参考片的“卡点”不是锁拍

三个参考片的切点与音乐节拍的吻合率都接近随机水平（拍点命中 0.13/0.31/0.29，随机期望 0.29/0.25/0.27）。另做了一个不依赖速度估计的检验：比较切点附近与随机位置的音乐起音强度，三个都不显著。它们的节奏感来自**稳定的镜头长度**，不是剪在拍子上；音乐可能是在 Instagram 里后加的，这一点只是推测。

因此模板学习的是**镜头长度（秒）和段落结构**，套用时再把每一刀对齐到**你自己那首音乐**的节拍网格：保留原片的节奏密度，同时真正卡在拍上。用两段真实音乐出的预览复测，切点 100% 落在半拍上，起音检验显著（参考原片不显著）。

## 工作方式

```text
参考 reel ─ tools/style_lab/analyze_reference.py → profile.json（只有测量值）＋ 人工看帧
                                                 → src/vlogii/style/templates/<id>.json（模板）
网页/CLI：素材 + 音乐 + 风格 ─ Gemini 选片段、标签、标题（无 key 时按导入顺序）
         ─ style/planner.py → style-plan.json（每一刀的帧位置、调色、文字、混音参数）
         ─ style/render.py → film.mp4（Vlogii 的一个新版本，可撤销、可下载）
```

分工沿用项目原则：AI 只决定用哪些片段、顺序、标签和标题文字；节拍、帧位置和混音由代码计算；渲染器只执行计划。

`style/planner.py` 的步骤：

1. 检测音乐节拍，修正约 30 毫秒的检测延迟并平滑抖动；估计强拍位置，置信度低时给出警告。
2. 按模板选择起点：`first_downbeat` 从第一个强拍开始，`most_energetic` 选最响的一段。总时长取整到整小节，开头段和结尾黑场取整到两拍。
3. 每段先按参考片的镜头秒数选拍数倍数（如 0.5/1/1.5/2 拍），保证正好填满该段；再按素材长度比例把镜头分给各片段，保持顺序，同一片段的多个镜头分散取用。开头快剪从各片段靠后的位置取预览，参考片也重复使用当天的瞬间。
4. 每段素材按参考片实测的亮度、饱和度和暖度，以模板的校正强度部分靠拢。
5. 时钟只取带时区的 QuickTime 拍摄时间或手写清单里的时钟；没有可靠时间就不显示，不编造。

素材不足时自动缩短，低于模板最短时长就报错，不复制画面凑时长；音乐太短同样处理。

## 模板字段

结构见 [style_template.schema.json](../src/vlogii/style/templates/style_template.schema.json)，校验器 `src/vlogii/style/templates.py` 只用标准库，`tests/test_style.py` 校验全部模板和错误写法。字段都已由规划器与渲染器实现，不存在“能写但不会画”的合法配置。

| 字段 | 作用 |
| --- | --- |
| `sections` | `hook`（可选）与 `body`：段长、镜头秒数范围、随机变化、允许的拍数倍数 |
| `duration`、`end_card` | 目标/最短/最长时长；结尾黑场及文字 |
| `music` | 起点策略、淡入淡出、目标响度、真峰值上限 |
| `source_audio`、`voiceover` | 原声一律静音；旁白模板的旁白响度和音乐压低量 |
| `grade` | 参考片实测的目标亮度、饱和度、暖度及校正强度 |
| `text` | 文字角色（字体候选、字号、颜色、阴影、底框）、标题行与装饰、时间/标签戳、旁白字幕 |

## 混音规则

- 原素材声音静音，三个参考片都是这样处理的。
- 整体响度 −14 LUFS，真峰值不超过 −1 dBTP。渲染器先限幅，AAC 编码后再测一次，超出就降低上限重编，所以最终 MP4 的测量值也满足要求。
- 旁白模板：旁白 −14 LUFS，有人声时音乐压低 12 dB（起 80 毫秒，回 300 毫秒）。参考片无法分离出音乐电平，−12 dB 是常用默认值，不是测量结果。
- 淡入淡出按参考片设置（0 或 0.6 秒），另加 30 毫秒防爆音。

## 怎么用

网页：导入竖屏素材后，在 *No. 2* 选风格和音乐，点生成。风格成片支持改标题、调暖和去掉素材，会按节拍重新剪；不支持调速和按时间段修改。步骤和常见问题见 [Mac 入门](vlogii-mac-setup.md)。

命令行：

```sh
uv run vlogii --language zh styles
uv run vlogii --language zh music my-day ~/Music/song.mp3
uv run vlogii --language zh run my-day --style ig_city_day_in_life
uv run vlogii --language zh style-preview ig_cozy_night_study --music song.mp3 --manifest work/me/manifest.json --out work/me/preview.mp4
```

清单写法见 `src/vlogii/style/planner.py` 开头说明；也可以用 `--clips` 指定文件夹，按拍摄时间排序、不带标签。旁白模板可加 `--voiceover` 和 `--transcript`，后者使用契约里的 `transcript.json` 格式；网页暂不支持上传旁白。

学习新的参考片：先运行 `uv sync --extra dev --extra style-lab`，用 `yt-dlp` 下载到 `work/references/`，再用 `uv run python tools/style_lab/analyze_reference.py` 分析（参数为视频、`--url` 和 `--out-dir`）。看 `contact_sheet.jpg` 后写模板 JSON，并把测量结果复制到 `style/references/`。完整自测用 `uv run python tools/style_lab/selftest.py --work work/style_lab/selftest`。

## 素材与许可

- 参考片只下载到被 Git 忽略的 `work/`，不提交、不进入成片。仓库只保存测量值和公开链接；模板不复制原片的音乐、画面或字体。
- 成片文字使用随程序附带的 OFL 开源字体：Poppins、DM Serif Display、Share Tech Mono，许可证在 `src/vlogii/style/fonts/`。Mac 和 Linux 出片字体一致，实际用到的字体记在每个版本的 `verification.json` 里。
- 你上传的音乐需要有发布授权，并按[准备与 Demo](demo.md)记录许可。

<a id="evidence"></a>

## 验证记录

2026-10-10，Linux 容器，FFmpeg 6.1.1，Python 3.13，librosa 1.0.0。

| 检查 | 结果 |
| --- | --- |
| 节拍检测（合成 100 BPM 鼓点，真值已知） | 召回 0.994，精度 1.0，速度 99.83 BPM，平均误差约 −3 毫秒 |
| 完整自测，三个模板端到端 | 全部通过；计划切点与真实节拍最大偏差 2/2/18.7 毫秒，成片切点与计划一致，换素材处的切点全部检出，原声测试音未检出；响度 −14.3/−14.1/−14.1 LUFS，真峰值 −1.5 至 −1.8 dBTP；旁白模板中音乐在人声下降低 11.6 dB，生成 12 条字幕 |
| 真实音乐复测（两段参考原声，仅本地） | 切点 100% 落在半拍上，起音检验显著；−14.1 LUFS，真峰值 −1.3/−1.5 dBTP |
| 应用测试 | 新增 19 项风格测试全部通过：模板与错误写法、已知节拍网格、镜头填满整段、AI 返回值校验、API 检查，以及一次真实出片（卡在半拍上、−14 LUFS ±1、真峰值 ≤ −1 dBTP、改标题/去素材/调暖后重剪、拒绝调速、撤销） |
| 真实 HTTP 流程（无 Gemini key） | 上传 14 段素材和一首 MP3，城市风格出片 38.4 秒，1080×1920 H.264/AAC，−14.1 LUFS，99 BPM；改标题并去掉一段后生成第 2 版；下载为附件；撤销回到第 1 版 |
| 网页与文字渲染 | 浏览器截图检查风格与音乐区域、成片说明；抽帧检查标题、打字效果、标签、时钟、字幕、星星和结尾黑场 |

合成素材是纯色画面，同一片段内的跳切看不出来，所以只统计换素材处的切点。

未验证：真实用户素材的观感、真实 Gemini 风格选片、真实旁白与语音转写、HEVC/HDR 素材、1080p 大素材的耗时、macOS 实机与 Safari、Replit 环境，以及合成素材之外的调色效果。

## 与团队契约的关系和下一步

风格功能使用 Vlogii 的 `/api/vlogii` 接口（`GET /styles`、`POST /projects/{name}/music`，以及 `generate` 的 `style_id`），没有修改团队 `contracts/`，对其无兼容影响。若以后迁回团队契约：`config.settings.style_id` 指向模板；`style-plan.json` 的帧位置可直接编译成 `timeline.json`，需要 `portrait_v1`，旁白模板还需要 `audio_envelopes_v1` 和 `subtitles_v1`。

建议下一步：用你自己的 10–15 段素材、一首有授权的音乐和 Gemini key，三个风格各出一次，看完反馈哪里不像。
