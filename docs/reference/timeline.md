# 项目 JSON 与时间线语义

[返回项目总览](../../README.md)

何时读：修改 JSON、编译时间线或渲染时读相关小节；机器结构以 contracts/contracts.schema.json 为准。

<a id="s6"></a>

## JSON 数据契约：MVP 可用，V2/V3 可扩展

<a id="s6-1"></a>

### 谁生成什么：先分清计划、设置与执行结果

**AI 生成剪辑建议，后端编译成最终时间线，渲染器只执行时间线。** 用户设置和修改约束由后端保存，AI 不能覆盖它们。

```text
原素材 → assets.json + 内容分析
                    ↓
             AI → edit_plan.json
                    ↓
config.json → 后端编译与校验 → timeline.json → FFmpeg → MP4
                    ↑
用户修改 → edit_request.json → 更新设置/计划，形成新版本
```

| 文件 | 谁写 | 用途 | 阶段 |
| --- | --- | --- | --- |
| `assets.json` | 后端素材登记模块 | 稳定 ID 对应哪个视频、音乐、字体、图片；只在后端解析真实文件 | MVP |
| `config.json` | 后端，根据界面输入或已确认的修改更新 | 用户想要什么；保存每个版本的设置和排除素材 | MVP |
| `edit_plan.json` | AI 输出 `plan`，后端补外层标识 | 选片、顺序、建议范围、标题；不负责最后一帧的位置 | MVP |
| `timeline.json` | 后端编译器 | 已确定的画面、音轨、图层、字幕与精确时长 | MVP |
| `edit_request.json` | AI 或固定按钮解析，后端校验并补标识 | 允许的修改操作；也可表达需要用户选择或暂不支持 | MVP |
| `transcript.json` | ASR + 后端句子整理 | 原素材中的句子和词时间；字幕由此生成 | V2-3 |

`analysis.json` 继续作为分析缓存，不直接交给渲染器；本节的机器可校验契约集中在上面六种文档。前端 HTTP 请求可以更小，由后端补齐默认值后存成这些文件。

已提供 [机器可读 JSON Schema](../../contracts/contracts.schema.json)、[MVP 完整时间线](../../contracts/examples/mvp.timeline.json)、[MVP 计划](../../contracts/examples/mvp.edit_plan.json)和[校验脚本](../../contracts/validate_examples.py)。示例中的媒体、字体、图片 ID 和路径是设计用占位引用，尚无对应资产，不能据此宣称已渲染成功。

<a id="s6-2"></a>

### 统一约定：字段、时间、版本和能力

| 约定 | 固定含义 |
| --- | --- |
| `schema_version` | 本契约为 `"1.0.0"`；与产品阶段 MVP/V2/V3 无关 |
| `document_type` | 区分 `assets`、`project_config`、`edit_plan`、`timeline`、`edit_request`、`transcript` |
| `project_id` | 项目标识；来自后端，不由模型猜测 |
| `version_id` / `parent_version_id` | 每次生成/修改保留独立版本，首版父版本为 `null`；撤销后分支也使用新 ID |
| 原素材时间 | `*_seconds`，单位为秒，相对解码后媒体的零起点 |
| 成片时间 | `*_frame` / `*_frames`，单位为输出帧；三个阶段均先固定 30 fps |
| 时间区间 | 左闭右开，如 `[0, 90)` 为第 0–89 帧，共 3 秒 |
| 坐标 | 图层 `rect` 为最终画布像素，左上角为原点；不是百分比或视频原始尺寸 |
| 空值 | 未启用的集合使用 `[]`；有明确可空类型的标识使用 `null`；不混用空字符串 |
| 文件引用 | 时间线只保存 `asset_id` / `clip_id`，不保存本机绝对路径或会过期的访问 URL |
| 未知字段 | 拒绝拼错或未声明字段；不能将未知字段默默忽略后继续渲染 |

Schema 使用 JSON Schema Draft 2020-12。结构校验与业务校验都需要：前者检查字段和类型，后者检查素材是否存在、时长是否对得上。[对象与必填字段](https://json-schema.org/understanding-json-schema/reference/object)、[不同对象结构的组合](https://json-schema.org/understanding-json-schema/reference/combining)

结构版本策略：发布新字段时同时发布新 schema；兼容新增提升次版本，改变时间含义等不兼容变更提升主版本。读端先按精确版本选择已安装的 schema，再校验；未知版本明确拒绝，或经显式迁移后写入新文件。旧文件和旧 MP4 不原地改写。

`timeline.required_capabilities` 用于判断当前渲染器能不能执行：

| 能力 | 含义 | 最早阶段 |
| --- | --- | --- |
| `core_v1` | 硬切、固定调色、文本/图片覆盖、音轨与首尾淡入淡出 | MVP |
| `audio_envelopes_v1` | 分时段压低音乐 | V2-3 |
| `subtitles_v1` | 已排好位置和时间的字幕 | V2-3 |
| `portrait_v1` | 720×1280 画布与对应构图 | V3-1 |
| `dissolve_v1` | 镜头交叠溶解 | V3-3 |
| `overlay_fade_v1` | 图层淡入淡出动画 | V3-3 |

MVP 渲染器只声明 `core_v1`。收到需要额外能力的文件必须报“当前版本不支持”，不能假装导出成功。情绪、时长和风格是编译器/产品能力，不必各造一种渲染类型；贴纸复用图片图层，旁白复用音轨。**有字段可以表示，不等于该阶段的产品功能已经实现。**

<a id="s6-3"></a>

### `assets.json`：把稳定 ID 和真实文件分开

共同字段为 `asset_id`、`kind`、`origin`、`storage_key`。`origin` 为 `upload`、`bundled` 或 `generated`；`storage_key` 是对象存储/工作区中的相对键，不能含绝对路径或 `..` 路径段。

| `kind` | 额外必填字段 | 示例用途 |
| --- | --- | --- |
| `video` | `duration_seconds`、`display_width`、`display_height`、`rotation_degrees`、`has_audio` | 用户素材；`clip_id` 引用这类资源 |
| `audio` | `duration_seconds` | BGM、V3 生成的旁白 |
| `image` | `width`、`height` | 固定装饰、抠图贴纸、参考图片 |
| `font` | 无 | 已安装并验证的字体文件 |

`display_width/height` 是应用旋转信息后的观看尺寸；`rotation_degrees` 记录解码原件时需要应用的旋转。规范化代理应记录已应用旋转，不能二次旋转。素材的秒时间仍对应原件内容，代理文件不得悄悄改变时间基准。

同一个资源 ID 指向不可变内容；替换音乐、字体或生成贴纸时分配新 ID。分析缓存仍按实际文件内容哈希和分析版本建立，不能仅用文件名。后端将 `storage_key` 下载/解析到临时路径，渲染器不依赖部署前的磁盘路径。目录中的 [assets 样例](../../contracts/examples/assets.json)同时为 MVP、V2、V3 样例提供引用。

<a id="s6-4"></a>

### `config.json`：保存用户意图和版本设置

外层包括项目/版本标识，实际设置放在 `settings`。后端在每个新版本中保存完整快照，不在旧配置上覆盖写入。

| `settings` 字段 | 类型 / MVP 默认 | 含义与后续用途 |
| --- | --- | --- |
| `output` | 对象：1280×720、30 fps、`mp4_h264_aac` | V3-1 可选 720×1280；编码规格保持一致 |
| `duration_policy` | `target`、30 秒、容差 30 帧 | 明确什么时候需要凑目标时长，见下文 |
| `style_id` / `style_revision` | `magazine_scrapbook` / `1` | 选择哪一个已验证的风格版本 |
| `mood_id` | `null` | V2-1 为 `cozy_memory` / `bright_diary` |
| `title_overrides` | `{}`，可包含三层标题中的任意已修改层 | 未覆盖部分使用已有 AI 标题；不是让 AI 每次重写用户标题 |
| `warmth_override` | `null`；显式值范围 −1…1 | `null` 用预设，0 中性，正值偏暖，负值偏冷 |
| `music_asset_id` | `bgm_lofi_01` | MVP 固定；V2-1 随情绪选择已准备曲目 |
| `voice_enabled` / `subtitles_enabled` | `false` / `false` | V2-3 才开放，关闭原声时同时关闭口播字幕 |
| `excluded_clip_ids` | `[]` | 持久记录用户排除的原素材，后续重新选片不得加回 |
| `creation_brief` | `text: null`、`reference_image_asset_ids: []` | V3-5 接收一句话或参考图；最后仍编译为已支持的风格参数 |

输出配置只接受 1280×720 或 720×1280，不接受两个宽高值随意组合。编码档 `mp4_h264_aac` 固定为 MP4、H.264、yuv420p、AAC 48 kHz；编码性能参数由经过验证的渲染器配置管理，不由 AI 生成。

**时长冲突用两种模式解决：**

- 首次生成或 V2 显式指定时长：`{"mode":"target","target_seconds":30,"tolerance_frames":30}`。素材不足时返回无法满足目标，不复制素材填满；20 秒从 V2-2 开放，60 秒从 V3-2 开放。
- 单纯删除素材：切换为 `{"mode":"natural","target_seconds":null,"tolerance_frames":0}`。27 秒结果就是合法的 27 秒，不继续用旧的 30 秒目标判失败。再次明确请求 20/30 秒时才切回目标模式。

仅改标题或暖度保留原时长模式和镜头安排。删除全部可用镜头时拒绝该修改并保留旧版，不生成空视频。

<a id="s6-5"></a>

### `edit_plan.json`：AI 输出什么

外层 `schema_version`、项目/版本 ID、`origin` 由后端写入；`origin` 标明 `ai`、`rules` 或设计样例的 `fixture`。**AI 实际只返回 `plan` 对象**，不承担版本分配、路径拼接和最终时间计算。

| `plan` 字段 | 类型 | 作用 |
| --- | --- | --- |
| `title` | `eyebrow`、`headline`、`tagline` 三个字符串 | 三层标题，字符上限分别 40、60、80；实际布局还需测量 |
| `shots` | 有序数组 | 数组顺序就是建议的成片顺序 |
| `sections` | `{section_id,label}` 数组，MVP 为 `[]` | V3-3 章节标签来源 |

每个 `plan.shots[]`：

| 字段 | 含义 |
| --- | --- |
| `shot_id` | 本计划中的唯一镜头 ID，编译后保留；同一原素材可被多个镜头引用 |
| `clip_id` | 引用 `assets.json` 中的 `video` |
| `source_window.in_seconds/out_seconds` | 允许截取的候选范围，必须在原素材内 |
| `preferred_duration_seconds` | 建议镜头时长，不超过候选范围；实际时长由后端确定 |
| `importance` | 1–5，越高越应该保留；用于缩短时的稳定排序，不是质量保证 |
| `section_id` | MVP 为 `null`；后续引用 `sections` |
| `speech_sentence_ids` | MVP 为 `[]`；V2-3 引用真实转录句子 |

完整 [MVP 计划样例](../../contracts/examples/mvp.edit_plan.json)有 10 个镜头，建议每个 3 秒。候选范围不是让模型猜出逐帧精确动作边界；它只能基于已提供的关键帧、时间信息和后续转录。

提供给模型服务的 schema 只抽取 `PlanPayload` 或 `EditPayload` 及所需定义，并按该服务支持的 schema 子集适配；不要把整个后端根 schema 原样提交给所有供应商。

<a id="s6-6"></a>

### `timeline.json`：最终执行说明

外层固定为 `schema_version`、`document_type`、`project_id`、`version_id`、`parent_version_id`、`timeline`。

| `timeline` 字段 | 作用 |
| --- | --- |
| `compiler_version` | 编译算法版本；当前契约样例为 `1.0.0` |
| `required_capabilities` | 渲染前检查的能力清单 |
| `output` | 最终宽高、帧率和编码档 |
| `duration_frames` | 成片实际总帧数；900 帧为 30 秒 |
| `duration_policy` | 从配置复制的校验策略，不由渲染器重新调整目标 |
| `excluded_clip_ids` | 从配置复制，最终再检查排除约束 |
| `style_snapshot` | 风格 ID、版本、情绪与实际 `grade` 参数 |
| `shots` | 最终视频轨，至少一个镜头 |
| `audio_tracks` | 显式音轨；MVP 只有一条 BGM |
| `overlays` | 已排版的标题和图片装饰；V3 扩展章节和贴纸 |
| `subtitles` | 已排好时间和位置的字幕；MVP 为 `[]` |

渲染器使用这里的实际参数，不再加载“当前最新版预设”覆盖快照。`grade` 包含 `warmth`（−1…1）、`saturation`（0…2，1 为原值）、`contrast`（0.5…1.5，1 为原值）、`brightness`（−0.2…0.2，0 为原值）。具体像素映射随渲染器实现固定并验证，不能交给模型临时选择滤镜。

**一段镜头的完整结构如下：**

```json
{
  "shot_id": "shot_01",
  "clip_id": "clip_01",
  "source_in_seconds": 1.0,
  "start_frame": 0,
  "duration_frames": 90,
  "framing": {
    "mode": "contain",
    "background_color": "#F6F3EE",
    "focus_x": 0.5,
    "focus_y": 0.5
  },
  "transition_in": {"type": "cut", "duration_frames": 0}
}
```

它表示：原素材第 1–4 秒，放在成片第 0–90 帧，以完整画面显示；空余区域使用暖白背景。

只存一个时长字段，避免 `source_out_seconds`、`end_frame`、时长三者互相矛盾。派生关系为：

- `end_frame = start_frame + duration_frames`。
- `source_out_seconds = source_in_seconds + duration_frames / fps`；MVP–V3 均不支持变速。
- 第一个镜头必须从 0 帧开始，且 `transition_in` 为硬切。
- 后续 `start_frame = 前一镜头 end_frame − 当前 transition_in.duration_frames`。
- 全片 `duration_frames = 最后镜头 end_frame`，不得有非预期空洞。

编译器先将候选范围向内量化到 30 fps 网格，最终视频截取起点也落在这个网格上；保存秒小数时至少保留 6 位有效小数，校验时允许浮点序列化微差。素材规范化后必须输出约定帧数，不能通过静默变速修正。

`framing.mode=contain` 为 MVP 默认，完整保留画面，不自动裁掉人物；`focus_x/y` 在此模式不参与计算。`cover` 按比例放大并裁切填满画布，以 0…1 的焦点坐标选择裁切中心，裁切框始终限制在素材范围内；V3-1 才在验证主体可见后使用。

`transition_in` 表示进入当前镜头的转场。MVP 固定 `cut/0`；V3-3 可选 `dissolve`，1–30 帧，默认 15 帧。前后转场长度之和须小于当前镜头长度，避免三个镜头同时重叠；口播镜头两侧仍使用硬切。

<a id="s6-7"></a>

### 音轨、字幕和图层如何扩展

**`audio_tracks[]`：所有可听声音都从这里产生。** 不能因为视频文件自带音轨就自动混入原声，也不再同时使用另一套 `keep_audio` 开关。

| 字段 | 含义 |
| --- | --- |
| `track_id` / `kind` / `asset_id` | 音轨 ID、`bgm/source_audio/narration`、资源 ID |
| `shot_id` | 只有 `source_audio` 绑定画面镜头；BGM 和旁白为 `null` |
| `source_in_seconds` | 从音频或视频原音轨哪里开始取 |
| `start_frame` / `duration_frames` | 在成片中的位置与长度 |
| `gain_db` | 固定增益，0 表示原音量；样例 BGM 为 −12 dB，仅是待试听初值 |
| `fade_in_frames` / `fade_out_frames` | 音轨首尾淡入淡出的帧数，之和不超过音轨长度 |
| `envelope` | MVP 为 `[]`；V2-3 的 `{offset_frame,delta_db}` 音量变化点 |

`envelope.offset_frame` 相对本音轨起点，按时间严格递增，非空时包含 0 和本音轨长度两个端点；`delta_db` 叠加到基础 `gain_db`，相邻点在 dB 值上做线性插值。首尾淡入淡出另按线性振幅叠加。编译器根据口播区间提前算好压低曲线，渲染时不再检测语音。

必须恰有一条 BGM 覆盖全片；素材长度不足时提前拒绝或选用足够长的已准备曲目，不隐式循环。原声的资源 ID 必须等于绑定镜头的 `clip_id`，起点与画面保持同一时间映射。原声/旁白之间不得相互覆盖；全片混音后使用固定限幅策略避免削波。

V3 旁白先生成音频、登记为 `audio` 资源并测实际时长，再安排轨道。文案、音色和生成设置属于生成请求/资源来源记录；时间线只引用已生成音频，不让渲染器临时调用 TTS。

**`overlays[]`：MVP 就支持文本与图片两种图层。**

| 字段 | 含义 |
| --- | --- |
| `overlay_id` / `kind` / `role` | 唯一 ID；`text/image`；区分三层标题、装饰及后续章节/贴纸 |
| `start_frame` / `end_frame` | 成片全局起止帧，不能超过全片 |
| `rect` | `x/y/width/height`，最终画布像素；全部在画布内 |
| `z_index` / `opacity` | 数值大的在上；同层按数组顺序绘制，后者在上；透明度 0…1 |
| `animation` | MVP 为 `none/0/0`；V3-3 才支持 `fade` 的入/出帧数 |
| 文本专有字段 | `text`、`text_style`：字体 ID、像素字号、颜色、对齐、描边宽度/颜色 |
| 图片专有字段 | `asset_id`、`fit=contain`；透明 PNG 直接保留透明度 |

图层矩形从左上角定位。文字换行、大小写与字号在最终时间线产生前确定；`text` 可带明确换行。编译/标题模块用实际字体测量，超框时先缩字号到已验证下限，仍超框则返回标题过长；不要静默改写用户指定文字。MVP 标题从第 0 帧显示到 `min(90, duration_frames)`，删除后成片不足 3 秒时也不会越界。渲染器据最终字体和布局生成 PNG 覆盖层，不重新设计布局。竖屏时重新计算这些像素坐标，不能只把横屏成片拉长。

**`subtitles[]`：V2-3 才填入。** 每项包含 `subtitle_id`、`source_audio_track_id`、`source_sentence_id`、`start_frame/end_frame`、`text`、`rect`、`text_style`。句子来自 `transcript.json`，不能由导演模型编造；起止帧必须位于对应原声/旁白范围内。可以把长句拆成多个字幕块，但其内容与范围必须可追溯到原转录，时间不能平均猜测。

`transcript.sentences[]` 定义 `sentence_id`、`asset_id`、原素材 `in_seconds/out_seconds`、`text` 与 `words[]`。每个词也有文字和原素材秒时间。只有句子时间时 `words=[]`；这时只做句级字幕，不宣称逐词高亮。无可靠句子时间时不能通过验收。

<a id="s6-8"></a>

### `edit_request.json`：修改是受控操作，不是任意 JSON 补丁

外层字段为 `request_id`、`project_id`、`base_version_id`、原始 `instruction` 和 `resolution`，外加通用 schema/type。版本 ID、请求 ID 均由调用方/后端提供，模型不能修改。

| 操作 | 参数 | 阶段 |
| --- | --- | --- |
| `set_title` | `field: eyebrow/headline/tagline`、`value: string` | MVP；“改标题”默认指 headline |
| `set_warmth` | `value: -1…1` 的绝对值 | MVP；“暖一点”按当前值 +0.1 后限幅 |
| `remove_clip` | `clip_id` | MVP；删除该原素材的全部成片引用，并记入排除列表 |
| `set_mood` | `mood_id: cozy_memory/bright_diary` | V2-1 |
| `set_target_length` | `seconds: 20/30/60` | 20/30 为 V2-2，60 为 V3-2 |
| `set_voice` / `set_subtitles` | `enabled: boolean` | V2-3 |
| `set_aspect_ratio` | `value: 16:9/9:16` | V3-1 |
| `set_style` | 已登记的 `style_id` | V3-3 |

单次多操作先整体校验，再按数组顺序应用到副本，全部成功后才创建可见成功版本；一项不支持就不局部执行。`set_title` 还需按对应层的 40/60/80 字符上限校验。`set_mood` 清除旧暖度覆盖，但保留用户标题和排除约束；若同条指令又明确设暖度，将 `set_warmth` 放在后面。切换完整风格清空旧 mood/暖度覆盖，保留用户标题、排除约束、画幅和时长意图。

阶段校验由后端执行：MVP 只接受前三种操作，不能因为总 schema 包含 V2/V3 操作就开放所有能力。V3 的贴纸/旁白生成和参考图输入由对应流程产生资源或设置，再使用已有时间线结构；不是让模型生成任意 shell 命令或任意图层类型。

`resolution` 为以下三种互斥结构：

- `ready`：包含非空 `operations`，可以继续校验和渲染。
- `needs_selection`：包含 `prompt` 和至少两个 `{clip_id,label}` 候选；此时没有可执行操作。任务返回此结果并释放执行器，前端展示后端解析出的缩略图；用户确认后用新 `request_id` 提交明确 `remove_clip`，再次检查 `base_version_id`。
- `unsupported`：包含 `reason`，不修改版本。例如 MVP 请求“只删这个视频里的半秒狗画面”，不能悄悄删整段原素材。

候选只能来自当前成功版本实际使用的素材；没有匹配时返回明确的不支持/无法定位原因。模型的解析结果不使用“已修改成功”摘要；只有渲染、保存成功后，后端根据实际操作生成 `result.summary`。

<a id="s6-9"></a>

### V2/V3 会改哪些字段

| 功能 | 使用或改变的字段 | 是否需要推翻镜头结构 |
| --- | --- | --- |
| V2-1 两种情绪 | config 的 mood/music；实际 grade、shots 时长和 BGM | 否，重新编译已有结构 |
| V2-2 缩短 | duration_policy、shots、受影响的音轨/图层时段 | 否，重新计算，不让渲染器临时删镜头 |
| V2-3 口播字幕 | plan 的句子引用；新增 source_audio、envelope 和 subtitles | 否 |
| V3-1 竖屏 | output 宽高、每段 framing、图层/字幕 rect 与字号 | 否 |
| V3-2 60 秒 | target_seconds、更多 shots、足够长的 BGM | 否，重新做资源与性能验收 |
| V3-3 风格/动画 | style_snapshot、sections、overlays、transition_in | 否 |
| V3-4 抠图/旁白 | assets 的新 image/audio；图片图层或 narration 音轨 | 否 |
| V3-5 文字/参考图 | creation_brief，映射到已有 style、mood、plan | 否，不直接将参考图内容当渲染命令 |

<a id="s6-10"></a>

### 编译和校验必须遵守的规则

1. **引用与阶段先校验。** 素材、字体、句子、风格 ID 存在且类型匹配；排除素材不能被选回；当前阶段与渲染器能力均支持。
2. **合法素材范围优先。** 候选区间量化后仍在素材内；实际时长不得超过可用区间。MVP 默认单镜头 45–90 帧。V2-3 所保留完整口播可突破这个普通镜头上限，仍需满足片源和整体时长。
3. **目标时长与自然时长分开。** target 模式检查 ±30 帧；natural 模式采用实际镜头总长。删除后不自动补片，后续改标题不能把旧目标重新激活。
4. **卡点是偏好。** 在合法范围内挑接近建议时长的可用节拍；遇到整体时长或完整口播冲突时让步。不为卡点切断一句话。节拍数组相对原音乐，先减去音乐截取起点并加成片起点，再换算帧。
5. **缩短顺序稳定。** V2-2 按 importance 从低到高依次缩短无口播镜头，同优先级从靠后镜头开始；每段最多缩到允许下限，一旦满足目标就停止。仍过长时按相同顺序尝试移除镜头，并重新检查目标容差。剩余素材无法满足时明确失败，保留旧版，不无限重新调用 AI。
6. **检查全部轨道。** 画面没有空洞，转场正确交叠；BGM 覆盖全片；原声与画面源时间一致；字幕和图层不越界；原声与旁白不重叠。
7. **检查实际画面与声音。** 字体存在且文字可排入，原始音轨没有被默认混入，最终编码/分辨率/帧数符合预期。结构合法不代表审美或播放质量合格。
8. **成功后发布版本。** 校验或渲染失败不移动当前版本指针；撤销只是切换已成功版本。配置、计划、时间线应具有一致的项目/版本身份。

一条编译路径足够：校验输入 → 应用排除与覆盖设置 → 选定合法截取长度 → 算硬切/后续转场的位置 → 排音乐/口播 → 排标题/字幕 → 完整校验。计划修复调用最多 2 次，总超时按任务配置限制；无法满足时返回原因。

<a id="s6-11"></a>

### 完整样例与明确预期

| 样例 | 应当得到的时间关系 | 用途 |
| --- | --- | --- |
| [MVP config](../../contracts/examples/mvp.config.json) + [计划](../../contracts/examples/mvp.edit_plan.json) + [时间线](../../contracts/examples/mvp.timeline.json) | 10 个镜头，各 90 帧，共 900 帧；标题前三秒；仅 BGM | 两人联调基线 |
| [删除请求](../../contracts/examples/mvp.edit_request.json) + [删除后的配置](../../contracts/examples/mvp.after-delete.config.json) + [删除后的时间线](../../contracts/examples/mvp.after-delete.timeline.json) | 删除 clip_07 后 9 个镜头，共 810 帧/27 秒；自然时长模式，旧版保留 | 验证删除与目标时长冲突已经分开 |
| [需要选择的修改](../../contracts/examples/selection.edit_request.json) | 不生成新视频，返回两个候选 | 避免错误删除 |
| [V2 时间线](../../contracts/examples/v2.timeline.json) + [转录](../../contracts/examples/v2.transcript.json) | 仍为 900 帧；6.1–8.7 秒放带余量的原声，6.2–8.6 秒显示句子字幕，BGM 同步压低 | 验证音画时间映射 |
| [V3 时间线](../../contracts/examples/v3.timeline.json) | 720×1280；一次 15 帧溶解后共 885 帧/29.5 秒；另有贴纸、淡入淡出和旁白 | 验证结构可扩展；不代表 V3 功能已实现 |

V2/V3 样例演示字段容量，镜头素材沿用同一组占位引用；并非审美比较结果。MVP 样例的 3 秒切点可用 100 BPM、每 5 拍切换的音乐片段验证，但示例并未附真实音乐或节拍文件。

<a id="s6-12"></a>

### 验证方法与交付边界

从仓库根目录进入 `contracts/`运行 `python3 validate_examples.py`，会检查 JSON 结构、引用、镜头时长、音轨、字幕映射和错误样例。协作接口与开发替身另运行 `python3 collaboration/validate_collaboration.py`，完整使用方式见 [协作包说明](../../contracts/collaboration/README.md)。

脚本不依赖额外安装，结构检查仅覆盖本 schema 使用的关键字，不是通用 JSON Schema 标准实现。真正应用开发时使用标准 JSON Schema 校验器或 Pydantic，并保留跨字段业务校验。当前检查没有读取真实素材或字体、没有调用模型，也没有运行 FFmpeg/Replit；实际渲染与 UI 仍按项目关卡验收。
