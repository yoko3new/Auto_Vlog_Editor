# 参考 reel 风格模板（feng-style 实验）

[返回项目总览](../README.md)

何时读：要把参考短视频的剪辑节奏、BGM 混音和画面风格做成可复用模板，或用模板给自己的素材出预览时读。

**状态：** `feng-style` 分支上的实验工具链，已在合成素材和两段真实音乐上验证（见[验证记录](#evidence)）；尚未用真实用户素材做观感验收，未接入产品 API、前端或 `contracts/`。它超出 MVP：9:16 属 V3-1，旁白字幕与音乐压低属 V2-3，更多风格属 V3-3/V3-5。是否纳入产品范围由 A 在[决策记录](decisions.md)中确认。

## 从三个参考 reel 学到了什么

| 模板 | 参考 | 节奏（实测） | 声音（实测） | 画面与文字 |
| --- | --- | --- | --- | --- |
| `ig_cozy_night_study` | [DNvYfcx5EBk](https://www.instagram.com/reel/DNvYfcx5EBk/) 15.3 秒 | 24 个镜头，中位 0.67 秒，从头到尾均匀，无快剪开头 | 纯音乐，−14.0 LUFS，LRA 1.7，真峰值 −1.2 dBTP，无淡入淡出，无人声 | 暖色台灯（暖度 0.22、饱和 0.46）；“cozy night / study / with me”三层标题，小字打字机效果，活动小标签 |
| `ig_city_day_in_life` | [DYui5l2x141](https://www.instagram.com/reel/DYui5l2x141/) 37.9 秒 | 前 3.77 秒 13 个镜头（中位 0.30 秒）快剪开头，之后中位 0.70 秒 | 纯音乐，−15.6 LUFS，真峰值 +3.0 dBTP（已削波），无人声 | 自然日光（饱和 0.30）；白色粗体 “day in my life”、时间范围、地点标签；正文数字时钟 + 小说明 |
| `ig_narrated_college_day` | [DWxtN9tCoc2](https://www.instagram.com/reel/DWxtN9tCoc2/) 64.9 秒 | 前 2.87 秒 21 个镜头（中位 0.13 秒）闪剪开头，正文中位 0.67 秒、跨度大，结尾 3.55 秒黑场 | 99% 时长检测到人声并有逐句字幕，判断为旁白；−14.1 LUFS，结尾 0.6 秒淡出 | 阴天冷调（暖度 0.06）；深红粗体标题配白色星星；中部数字时钟，62% 高度处小写字幕 |

测量值来自 `style/references/*.profile.json`；画面与文字一栏来自人工看帧。模板 JSON 的 `reference.learned` 逐条标明“measured”或“observed”。

### 关键发现：参考片的“卡点”不是锁拍

三个参考的切点与音乐节拍的吻合率都接近随机水平（拍点命中 0.13/0.31/0.29，随机期望 0.29/0.25/0.27）。另做了一个不依赖速度估计的检验：比较切点附近与随机位置的音乐起音强度，三个都不显著。它们的节奏感来自**稳定的镜头长度**，不是剪在拍子上；音乐可能是在 Instagram 里后加的，这一点只是推测。

因此模板学习的是**镜头长度（秒）和段落结构**，套用时再把每一刀对齐到**你自己那首音乐**的节拍网格：保留原片的节奏密度，同时真正卡在拍上。用两段真实音乐出的预览复测，切点 100% 落在半拍上，起音检验显著（参考原片不显著）。

## 工作方式

```text
参考 reel ─ analyze_reference.py → profile.json（只有测量值）＋ 人工看帧
                                  → style/templates/<id>.json（模板）
你的素材 + 音乐 + 模板 + manifest ─ plan_edit.py → plan.json（每一刀的帧位置、调色、文字、混音参数）
plan.json ─ render_preview.py → preview.mp4 + preview.report.json
```

分工沿用项目原则：AI 或用户只写 manifest，决定用哪些素材、顺序、每段标签和标题文字；节拍、帧位置和混音由代码计算；渲染器只执行 plan。

`plan_edit.py` 的步骤：

1. 检测音乐节拍，修正约 30 毫秒的检测延迟并平滑抖动；估计强拍位置，置信度低时给出警告。
2. 按模板选择起点：`first_downbeat` 从第一个强拍开始，`most_energetic` 选最响的一段。总时长取整到整小节，开头段和结尾黑场取整到两拍。
3. 每段先按参考的镜头秒数选拍数倍数，例如 0.5/1/1.5/2 拍，保证正好填满该段；再按素材长度比例把镜头分给各条素材，保持素材顺序，同一素材的多个镜头分散取用。开头快剪段从各素材靠后的位置取预览，参考片也重复使用当天的瞬间。
4. 每条素材按参考实测的亮度、饱和度和暖度，以模板 `strength` 的比例做部分校正。
5. 时钟只取 QuickTime `creationdate`（带时区）或 manifest 的 `clock`；没有可靠时间就不显示，不编造时间。

素材不足时自动缩短，低于模板最短时长就报错，不复制画面凑时长。音乐太短同样处理。

## 模板字段

结构见 [style_template.schema.json](../style/templates/style_template.schema.json)，校验器 `tools/style_lab/templates.py` 只用标准库。字段都已由 planner 与预览渲染器实现，不存在“能写但不会画”的合法配置。

| 字段 | 作用 |
| --- | --- |
| `sections` | `hook`（可选）与 `body`：段长、镜头秒数范围、随机变化、允许的拍数倍数 |
| `duration`、`end_card` | 目标/最短/最长时长；结尾黑场及文字 |
| `music` | 起点策略、淡入淡出、目标响度、真峰值上限 |
| `source_audio`、`voiceover` | 原声一律静音；旁白模板的旁白响度和压低量 |
| `grade` | 参考实测的目标亮度、饱和度、暖度及校正强度 |
| `text` | 文字角色（字体候选、字号、颜色、阴影、底框）、标题行与装饰、时间/标签戳、旁白字幕 |

## 混音规则

- 原素材声音静音，三个参考都是这样处理的。
- 整体响度 −14 LUFS，真峰值不超过 −1 dBTP。渲染器先限幅，AAC 编码后再测一次，超出就降低上限重编，所以最终 MP4 的测量值也满足要求。
- 旁白模板：旁白 −14 LUFS，有人声时音乐压低 12 dB（起 80 毫秒，回 300 毫秒）。参考片里无法分离出音乐电平，所以 −12 dB 是常用默认值，不是测量结果。
- 淡入淡出按参考设置（0 或 0.6 秒），另加 30 毫秒防爆音。

## 怎么用

```sh
python3 -m venv work/.venv && work/.venv/bin/pip install -r tools/style_lab/requirements.txt
python3 tools/style_lab/templates.py                      # 校验模板（标准库即可）
work/.venv/bin/python tools/style_lab/plan_edit.py --template ig_city_day_in_life \
  --music work/me/song.mp3 --manifest work/me/manifest.json --out work/me/plan.json
work/.venv/bin/python tools/style_lab/render_preview.py work/me/plan.json --out work/me/preview.mp4
```

manifest 写法见 `plan_edit.py` 开头说明；只想快速试一下可以用 `--clips 文件夹` 代替，按拍摄时间排序、不带标签。旁白模板另加 `--voiceover` 和 `--transcript`，后者使用契约里的 `transcript.json` 格式。

学习新的参考：先用 `yt-dlp` 下载到 `work/references/`，再运行 `analyze_reference.py <视频> --url <链接> --out-dir work/style_lab/<id>`；看 `contact_sheet.jpg` 后写模板 JSON，并把 profile 复制到 `style/references/`。

## 素材与许可

- 参考 reel 只下载到被 Git 忽略的 `work/`，不提交、不进入成片。仓库只保存测量值和公开链接。模板不复制原片的音乐、画面或字体；字体使用本机可用的替代：Caladea 代替 Playfair Display，DejaVu Sans Mono 代替 DSEG7 数字字体。实际用到的字体写在 report 里。
- 你上传的音乐需要有发布授权，并按[准备与 Demo](demo.md)记录许可。

<a id="evidence"></a>

## 验证记录

2026-10-10，云端容器，FFmpeg 6.1.1，Python 3.13，librosa 1.0.0。

| 检查 | 结果 |
| --- | --- |
| 模板校验 `templates.py` | 3/3 有效；8 种错误写法均被拒绝 |
| 节拍检测（合成 100 BPM 鼓点，真值已知） | 召回 0.994，精度 1.0，速度 99.83 BPM，平均误差约 −3 毫秒 |
| `selftest.py` 三个模板端到端 | 见下表，全部检查通过 |
| 真实音乐复测（两段参考原声，仅本地） | 切点 100% 落在半拍上，起音检验显著；−14.1 LUFS，真峰值 −1.3/−1.5 dBTP |
| 文字渲染 | 抽帧检查标题、打字机效果、标签、时钟、字幕、星星和结尾黑场；修正了片头字幕与副标题重叠 |

| 模板 | 镜头 | 时长（计划/成片） | 响度 / 真峰值 | 计划切点与真实节拍最大偏差 | 成片切点与计划一致 | 原声测试音 | 其他 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `ig_cozy_night_study` | 22 | 14.4 / 14.4 秒 | −14.3 LUFS / −1.5 dBTP | 2 毫秒 | 13/13 | 未检出 | 11 个活动标签 |
| `ig_city_day_in_life` | 59 | 38.4 / 38.4 秒 | −14.1 LUFS / −1.8 dBTP | 2 毫秒 | 25/25 | 未检出 | 28 个时钟/说明 |
| `ig_narrated_college_day` | 78 | 60.0 / 60.0 秒 | −14.1 LUFS / −1.5 dBTP | 18.7 毫秒 | 30/30 | 未检出 | 旁白下音乐降 11.6 dB；12 条字幕 |

合成素材是纯色画面，同一素材内的跳切看不出来，所以“成片切点”只统计换素材处的切点，三个模板换素材处的切点 100% 检出。三个模板的自测共耗时约 2.5 分钟，命令为 `work/.venv/bin/python tools/style_lab/selftest.py --work work/style_lab/selftest`。

未验证：真实用户素材的观感、真实旁白与 ASR、HEVC/HDR 素材、1080p 大素材的耗时、Replit 环境，以及合成素材之外的调色效果。

## 与产品契约的关系和下一步

本分支没有修改 `contracts/`，对现有契约无兼容影响。若要并入产品，需要 A/B 先确认：

- `config.settings.style_id` 是否可指向这些模板；竖屏需要 `portrait_v1`，旁白模板需要 `audio_envelopes_v1` 和 `subtitles_v1`。
- `plan.json` 编译成 `timeline.json`：帧位置可以直接对应，素材路径改为 `clip_id`，文字改为图层，压低改为音频包络。
- 上传音乐的节拍检测放进 `core/music.py`（A）。是否在 Replit 引入 librosa 由 A 决定。
- `render_preview.py` 是原型；产品渲染器（B）可以沿用 ASS 文字方案，也可以重写。

建议下一步：用你自己的 10–15 段素材和一首有授权的音乐，三个模板各出一次预览，看完反馈哪里不像。
