"""Small shared translation layer for CLI and persistent job messages."""

import re

MESSAGES = {
    "Planning your film": "正在规划你的影片",
    "Joining segments": "正在合并视频片段",
    "Checking video and audio": "正在检查画面与音频",
    "Waiting to start.": "正在等待开始。",
    "Your film is ready.": "影片已生成。",
    "Resuming the saved plan": "正在从已保存的剪辑计划继续",
    "Interrupted by server restart. Retry generation.": "服务重启中断了任务，点击重试可继续。",
    "Generation failed. Previous films are preserved. Check the server terminal or retry.": "生成失败，之前的成片已保留。可点击重试继续。",
    "Set GEMINI_API_KEY in the server's .env file and restart.": "请在服务端 .env 中配置 GEMINI_API_KEY 后重启。",
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
        (r"Rendering (\d+)/(\d+): (.*)", "正在渲染 {0}/{1}：{2}"),
        (r"Rendering cached (\d+)/(\d+)", "使用已渲染片段 {0}/{1}"),
        (r"Complete: (.*)", "已完成：{0}"),
    )
    for pattern, template in patterns:
        if match := re.fullmatch(pattern, message):
            return template.format(*match.groups())
    return message
