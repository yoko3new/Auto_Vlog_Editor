"""Small shared translation layer for CLI and persistent job messages."""

import re

MESSAGES = {
    "Mixing background music": "正在混合背景音乐",
    "A bundled preset is missing or changed. Restore the application assets.": "内置资源缺失或已变化，请恢复应用资源文件。",
    "A caption contains unsupported font glyphs. Remove emoji or use supported text.": "字幕含字体不支持的字符，请移除表情符号或改用可显示的文字。",
    "Planning your film": "正在规划你的影片",
    "Joining segments": "正在合并视频片段",
    "Checking video and audio": "正在检查画面与音频",
    "Waiting to start.": "正在等待开始。",
    "Your film is ready.": "影片已生成。",
    "Resuming the saved plan": "正在从已保存的剪辑计划继续",
    "Interrupted by server restart. Retry generation.": "服务重启中断了任务，点击重试可继续。",
    "Generation failed. Previous films are preserved. Check the server terminal or retry.": "生成失败，之前的成片已保留。可点击重试继续。",
    "Set GEMINI_API_KEY in the server's .env file and restart.": "请在服务端 .env 中配置 GEMINI_API_KEY 后重启。",
    "Retention modes have no target duration. Clear the target or choose AI auto/highlights.": "保留模式不设目标时长，请清空目标秒数，或改选 AI自动/快剪。",
    "Nothing remains after removing black/no-speech ranges. Choose keep_all or AI auto.": "去黑场和无语音区间后没有内容可保留，请改选完整保留或 AI自动。",
    "Speed ranges must not overlap. Combine them or choose separate ranges.": "调速区间不能重叠，请合并或分开选择。",
    "Time edit is shorter than one source frame. Choose a wider range.": "该修改短于一个素材帧，请扩大时间范围。",
    "Speed edits need one time range and a rate, e.g. 00:12到00:18加速到2倍.": "请填写一个时间段和倍速，例如 00:12到00:18加速到2倍。",
    "Time edits support deletion ranges or explicit speeds only. Other requests need generation controls.": "当前时间修改支持删除或指定倍速，其他需求请使用生成控件。",
    "Use an ordered time range and a speed between 0.25 and 8.": "请使用结束大于开始的时间区间，速度范围为 0.25–8 倍。",
    "Time ranges need nonnegative start and end greater than start.": "时间区间须非负，且结束须大于开始。",
    "Choose a target between 1 and 1800 seconds.": "目标时长须在 1–1800 秒内。",
    "Choosing moments for the style": "正在为风格挑选片段",
    "No Gemini key: using every clip in import order": "未配置 Gemini 密钥：按导入顺序使用全部素材",
    "Finding the beat": "正在分析音乐节拍",
    "Setting the titles": "正在排版标题",
    "Mixing the music": "正在混音",
    "Finishing the film": "正在合成成片",
    "Add a music track before making a style film.": "请先添加音乐，再制作风格成片。",
    "Could not find a steady beat in the music.": "这首音乐找不到稳定的节拍，请换一首。",
    "Style films keep every cut on the beat: change the title, warmth or clips, or make a new version. Time-range and speed edits are not available.": "风格成片的每一刀都卡在节拍上：可以改标题、调暖、去掉素材或重新生成，不支持按时间段删除或调速。",
}


def translate(message: str, language: str) -> str:
    if language != "zh":
        return message
    if message in MESSAGES:
        return MESSAGES[message]
    patterns = (
        (r"Inspecting (\d+)/(\d+)", "正在检查素材 {0}/{1}"),
        (r"Preparing video (\d+)/(\d+)", "正在准备视频 {0}/{1}"),
        (r"AI analysis (\d+)/(\d+)", "正在分析画面 {0}/{1}"),
        (r"Analysis cached: (\d+)/(\d+)", "使用画面分析缓存 {0}/{1}"),
        (r"Speech recognition (\d+)/(\d+)", "正在识别语音 {0}/{1}"),
        (r"Speech cached: (\d+)/(\d+)", "使用语音识别缓存 {0}/{1}"),
        (r"Checking black frames (\d+)/(\d+)", "正在检查黑场 {0}/{1}"),
        (
            r"Time ranges must be within the current film \(0–([\d.]+)s\) and span at least one frame\.",
            "时间区间须在当前成片 0–{0} 秒内，且至少包含一帧。",
        ),
        (r"Rendering (\d+)/(\d+): style shot", "正在渲染风格镜头 {0}/{1}"),
        (
            r"Not enough footage: this style needs ([\d.]+)s, the selected clips give ([\d.]+)s\.",
            "素材不够：这个风格需要 {0} 秒，所选片段只有 {1} 秒。",
        ),
        (
            r"The music is ([\d.]+)s; this style needs at least ([\d.]+)s after the first downbeat\.",
            "音乐长 {0} 秒，这个风格从第一个强拍起至少需要 {1} 秒。",
        ),
        (r"Rendering (\d+)/(\d+): (.*)", "正在渲染 {0}/{1}：{2}"),
        (r"Rendering cached (\d+)/(\d+)", "使用已渲染片段 {0}/{1}"),
        (r"Complete: (.*)", "已完成：{0}"),
    )
    for pattern, template in patterns:
        if match := re.fullmatch(pattern, message):
            return template.format(*match.groups())
    return message
