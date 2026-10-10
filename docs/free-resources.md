# 字体与 BGM 免费资源候选

**中文** · [English](free-resources.en.md)

[返回总览](../README.md) · [本轮修复](mvp-fixes.md) · [候选文件与校验值](../resources/candidates.json)

2026-10-10 调研并预下载。当前完成候选资源、授权来源与基本文件验证。自定义音乐上传、混音和节拍卡点已随[风格成片](style-templates.md)实现；内置曲库和资源选择仍未实现，候选曲目的风格效果、BPM 和卡点表现待试听/测量。本轮不改动现行 API 契约。

## 建议先内置的资源

| 资源 | 用途建议 | 授权和依据 | 本地检查 |
| --- | --- | --- | --- |
| Noto Sans CJK SC Regular | 中英字幕与默认标题；先用一套稳定字体减少缺字 | [官方字体](https://github.com/notofonts/noto-cjk/blob/main/Sans/OTF/SimplifiedChinese/NotoSansCJKsc-Regular.otf)，SIL OFL 1.1 | 约 16.4 MB；Pillow 成功读取，包含中英文字形；SHA-256 已记录 |
| Noto Serif CJK SC Regular | 后续书页/杂志感标题，作为可选预设 | [官方字体](https://github.com/notofonts/noto-cjk/blob/main/Serif/OTF/SimplifiedChinese/NotoSerifCJKsc-Regular.otf)，SIL OFL 1.1 | 约 24.5 MB；Pillow 成功读取中英文；SHA-256 已记录 |
| Dreams — Holizna | 轻音乐候选，306.636 秒 | [作者发布合集](https://opengameart.org/content/chillout-instrumentals-collection)标明 CC0 | MP3、48 kHz、双声道，完整解码通过 |
| Day Jobs — Holizna | 日常 vlog 候选，138.540 秒 | 同一作者合集、CC0 | MP3、48 kHz、双声道，完整解码通过 |
| Dancing — Holizna | 节奏型候选，135.708 秒；实际节拍待测 | 同一作者合集、CC0 | MP3、48 kHz、双声道，完整解码通过 |

用途建议是待试听的初选，不能仅凭曲名认定快慢或节拍。合集共六首，每首有 MP3/OGG 两种格式；先提取以上三首 MP3，避免立即引入大量预设。

OFL 允许字体随软件打包、嵌入和分发，需要保留版权与许可文件；不单独出售字体，改动字体时遵守保留名称要求。[Noto Sans 许可](https://github.com/notofonts/noto-cjk/blob/main/Sans/LICENSE)、[Noto Serif 许可](https://github.com/notofonts/noto-cjk/blob/main/Serif/LICENSE)。原始许可已保存于 [Sans OFL](../resources/licenses/NotoSans-OFL.txt)和 [Serif OFL](../resources/licenses/NotoSerif-OFL.txt)。

作者将音乐合集标为 CC0；[CC0 的官方说明](https://creativecommons.org/publicdomain/zero/1.0/)允许复制、改编、分发及商业用途。保留作者、作品名、来源、许可核对日期和下载文件散列，便于以后审计。未测试平台 Content ID，不把许可标签作为平台自动审核结果。

## 其他资源库如何使用

- [Kenney Music Jingles](https://kenney.nl/assets/music-jingles)：作者标为 CC0，85 个短音乐片段，更适合片头/片尾，暂未下载，不能当成长 BGM。
- Google Fonts / Noto 官方仓库：优先取发布的字体文件与同目录许可；当前静态 Regular 字体可以直接给 FFmpeg/Pillow 使用，不需全局安装。
- [Pixabay](https://pixabay.com/service/license-summary/)允许免费使用、改编，但限制原样素材的独立分发。可评估单支成片用途，暂不把下载来的原始音乐当作默认资源包公开分发。

## 默认资源与用户上传的下一步设计

首次生成不要求用户写字体名或上传音乐。字体默认用内置无衬线；BGM 采用“自动选择 / 不添加 / 指定内置曲 / 上传自己的”四种方式。自动选择只在经过试听、许可登记与预处理的有限库里选曲；口播期间自动压低 BGM。保留“不添加”供纯原声成片使用。

字体提供“默认 / 预设 / 上传字体”，先支持 TTF/OTF，再根据渲染器确认 TTC 的字体索引。音乐先支持 MP3/WAV/OGG，导入时探测音轨、时长、采样率并验证可解码；服务端保存副本，不依赖用户之后仍保留原文件。上传字体先检查中英字形，不完整时用内置字体回退并说明。

资源以 `asset_id` 关联到项目和成功版本，不把本机文件路径交给浏览器或 AI。生成记录保存实际使用的资源 ID、散列、音量和选段；字体或音乐变化只使相关渲染缓存失效，复用未变化的素材理解与转写。用户上传的资源仅保存在该项目，不自动成为全局默认库；界面提示只上传有使用权的文件。

A（杨康）负责资源登记、存储/版本、字体渲染、混音和节拍；B（队友）负责选择、试听、上传和失败反馈。实现时统一修改模型、OpenAPI、调用方和相关测试，再验证口播可懂、字幕无缺字、不同长度 BGM、Retry 和撤销。

## 下载与交付范围

完整下载位于忽略的 `local-evidence/free-resources-2026-10-10/`：两款字体、原许可、79.6 MB 合集 ZIP、作者页/CC0 页面快照、三首选取的 MP3、完整解码日志及下载散列。候选元数据和字体许可可提交；二进制资源尚未放入应用发行包，需按确定的默认库和打包方式接入。
