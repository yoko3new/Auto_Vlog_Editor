# 内置字体与免费纯音乐

**中文** · [English](free-resources.en.md)

[返回总览](../README.md) · [使用指南](vlogii-guide.zh.md) · [运行时资源清单](../src/vlogii/assets/manifest.json)

2026-10-10：集成分支已接入 6 款字体和 6 首纯音乐，包含网页选择/试听、真实 MP4 字体渲染与 BGM 混音。资源随应用读取，不需要用户安装字体、上传预设文件或在运行时访问第三方网站。自定义上传、BPM/节拍测量和自动卡点尚未实现。

## 字体

| 字体 | 建议用途 | 文字覆盖与来源 |
| --- | --- | --- |
| Noto Sans CJK SC / 思源黑体 | 默认字幕、清晰标题 | 中英文；[Noto 官方](https://github.com/notofonts/noto-cjk/tree/main/Sans) |
| Noto Serif CJK SC / 思源宋体 | 书页、杂志感文字 | 中英文；[Noto 官方](https://github.com/notofonts/noto-cjk/tree/main/Serif) |
| Ma Shan Zheng / 马善政 | 毛笔手写、短标题 | 中英文小样通过；[Google Fonts](https://github.com/google/fonts/tree/main/ofl/mashanzheng) |
| ZCOOL XiaoWei / 站酷小薇 | 文艺标题 | 中英文小样通过；[Google Fonts](https://github.com/google/fonts/tree/main/ofl/zcoolxiaowei) |
| Caveat | 英文手写 | 英文；中文回退；[Google Fonts](https://github.com/google/fonts/tree/main/ofl/caveat) |
| Playfair Display | 英文杂志标题 | 英文；中文回退；[Google Fonts](https://github.com/google/fonts/tree/main/ofl/playfairdisplay) |

字体均按原始 SIL OFL 1.1 分发，完整版权与许可保留在 [资源许可目录](../src/vlogii/assets/licenses)。没有修改或单独出售字体。标题与字幕共用所选字体；先按实际字形测量、换行与缩字号。检测到缺字时整条文字回退到思源黑体；回退字体仍缺字时报告错误，不静默输出方块。英文专用字体不会成为中文字幕的唯一字体。网页示例不是最终视频版式；默认字体示例显示思源黑体，已有本地字体配置可使实际导出不同。

## 免费纯音乐

以下六首来自 [Holizna 发布的 Chillout Instrumentals 合集](https://opengameart.org/content/chillout-instrumentals-collection)，作者标为 CC0。用途和节奏仍由用户试听决定，不从曲名推断 BPM。

| 曲名 | 时长（秒） | 格式 |
| --- | --- | --- |
| Dreams | 306.636 | MP3 / 48 kHz / 双声道 |
| Day Jobs | 138.540 | MP3 / 48 kHz / 双声道 |
| Dancing | 135.708 | MP3 / 48 kHz / 双声道 |
| Deja Vu | 124.764 | MP3 / 48 kHz / 双声道 |
| Childhood | 133.284 | MP3 / 48 kHz / 双声道 |
| Advertisements | 183.204 | MP3 / 48 kHz / 双声道 |

[CC0 官方说明](https://creativecommons.org/publicdomain/zero/1.0/)及[作者和来源记录](../src/vlogii/assets/licenses/Holizna-CC0.txt)随清单保留。原曲未修改，记录下载来源、许可核对日期、文件大小与 SHA-256。未验证各发布平台 Content ID。

## 默认行为与编辑

- 网页新生成默认字体为思源黑体，配乐为“自动”。自动是固定规则：快剪用 Dancing，其余模式用 Day Jobs；不是 AI 情绪匹配或卡点。用户可选“不添加”或六首中的任意一首。
- 试听为原曲播放；导出默认配乐音量 16%，支持 0–100% 调整。音乐按最终成片长度裁切或循环、首尾最多 0.5 秒淡入淡出；循环接点未做节拍对齐。
- 口播压低默认开启：使用已识别的语音区间，映射删除与倍速后的时间，在这些区间把配乐降至设定音量的约 30%，带短渐变。识别漏掉的口播不会触发压低。快剪原声仍静音，不对 BGM 加速或截成每镜头一段。
- 已有成片可在修改章节换字体、音乐、音量或压低开关，然后点击“应用修改”。复用原计划和分析；只改变音乐时复用视频片段缓存，在合并后连续混音。撤销恢复旧版原有设置和音轨。
- 兼容旧调用方：省略新增外观字段不自动给旧请求添加音乐；旧版本缺少设置时按“默认字体、不添加音乐”读取。

## 存储与接口

资源位于 `src/vlogii/assets/`，随 Python 安装包分发，总资源约 94.8 MB。网页从 `GET /api/vlogii/presets` 读取清单，资源 URL 使用登记 ID；不能请求任意磁盘路径。音乐支持字节范围试听，字体按需加载。生成和编辑使用可选 `appearance`，包含 `font`、`music`、`music_volume`、`duck_music`；实际模型和接口见 [OpenAPI](vlogii.openapi.json)。

成功版本保存 `project.json` 中的设置，以及 `assets.json` 中的实际资源 ID、散列、回退标记和口播压低区间。重试保留原请求；混音或字形检查失败不覆盖旧成功版。内置公开资源可随 Git 提交；私人素材、缓存、密钥、自定义上传的资源不提交。

```sh
uv run vlogii run my-day --music auto --font noto-sans
uv run vlogii edit my-day --music holizna-dreams --music-volume 0.2 --font caveat
uv run vlogii edit my-day --music none
```

现有本地字体覆盖仍可通过 `VLOGII_FONT` 配置，选择明确预设时优先使用该预设。

## 检查与后续

六首音乐完整解码通过；六款字体的英文及四款中文小样字形检查通过。[回归测试](../tests/test_presets.py)覆盖输出时长、短曲循环、淡入淡出、口播压低、字体回退、资源接口白名单/HTTP 206、换曲/移除/撤销、失败恢复、请求设置持久化和片段缓存复用。私人日志位于 `local-evidence/presets-20261010/`。自动检查不代替用户对选曲和口播清晰度的主观试听。

后续再加入项目内自定义 TTF/OTF 和 MP3/WAV/OGG 上传、分开的标题/字幕字体、更广的音乐类型及节拍卡点。A（杨康）负责资源、渲染、混音、存储和接口；B（队友）继续维护选择/试听页面。本轮已同步对应控件。
