"""
==========================================
📋 全局配置文件 v3.0
==========================================
"""

import os

# ==========================================
# 🍌 MetaChat Gemini API（文本分析 + 图片生成）
# ==========================================
METACHAT_API_KEY = "sk-live-eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJNZXRhQ2hhdCIsInN1YiI6IjY5OTQ0MThhZTkyMzEyZDZiZDY0YTJjYyIsImNsaWVudF9pZCI6IjVmYjFmZGQ5NmUyMGYyNzMzOTM3OWU4MDFlNjFkYTJmIiwiaWF0IjoxNzcyMzMxMTg3fQ.byc6bNzH-iQa8_CQM7PQG7RfqEQRgm--k96TBk3v0Vg"
GEMINI_BASE_URL = "https://llm-api.mmchat.xyz/gemini"
GEMINI_TEXT_MODEL = "gemini-2.5-flash"                    # 文本分析/剧本生成（最划算）
GEMINI_IMAGE_MODEL = "gemini-3.1-flash-image-preview"     # Nano Banana 2 图片生成

# ==========================================
# 🔥 火山引擎 AK/SK（即梦AI + TTS共用）
# ==========================================
VOLC_ACCESS_KEY = "AKLTMjA1NmQyZjZjMDk5NDQwOTk0NGFiNzNiYjQ5MzY3ZTU"
VOLC_SECRET_KEY = "WTJWbFpUUmlObVJpTVdOak5EUTRZMkZrWXpRelpURTVZVFpqT1dRMVptVQ=="

# ==========================================
# 🔊 火山引擎TTS配置
# ==========================================
VOLC_TTS_APP_ID = "8641701220"
VOLC_TTS_CLUSTER = "volcano_tts"
VOLC_TTS_TOKEN = "kShhbFfob3Q1INoNRC1CEjUb_yxAHH0d"
# 音色列表: https://www.volcengine.com/docs/6561/97465
# 推荐音色（有感情的大模型音色）
VOLC_TTS_VOICE_MAP = {
    # 男声
    "旁白男":   "zh_male_dayi_uranus_bigtts",          # 阳光男声-有声书
    "硬汉":     "zh_male_dayi_uranus_bigtts",            # 淳厚男声-大模型（适合警察/军人）
    "少年":     "zh_male_shaonianzixin_uranus_bigtts",     # 少年旅行-大模型
    "霸总":     "zh_male_ruyayichen_uranus_bigtts",         # 温暖阿虎-大模型
    "反派":     "zh_male_sunwukong_uranus_bigtts",    # 呆萌传媒-大模型
    "沉稳男":   "zh_male_dayi_uranus_bigtts",           # 阳光男声-有声书
    # 女声
    "旁白女":   "zh_female_shuangkuaisisi_uranus_bigtts",   # 爽快思思-大模型
    "干练女":   "zh_female_shuangkuaisisi_uranus_bigtts",   # 爽快思思-大模型（适合女警/女强人）
    "少女":     "zh_female_tianmeixiaoyuan_uranus_bigtts",   # 甜美小源-大模型
    "御姐":     "zh_female_shuangkuaisisi_uranus_bigtts",   # 爽快思思-大模型
    # 通用
    "旁白":     "zh_male_dayi_uranus_bigtts",           # 默认旁白
}
DEFAULT_TTS_VOICE = "旁白男"

# ==========================================
# 🎬 即梦AI（仅视频生成）
# ==========================================
# 图片生成已改用 Nano Banana 2，即梦只保留视频
JIMENG_VIDEO_REQ_KEY = "jimeng_ti2v_v30_pro"
JIMENG_UPSCALE_REQ_KEY = "jimeng_i2i_seed3_tilesr_cvtob"

# ==========================================
# 📹 视频参数
# ==========================================
VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
FPS = 30

# ==========================================
# 📑 分集参数
# ==========================================
EPISODE_MIN_CHARS = 1500    # 每集最少字数
EPISODE_MAX_CHARS = 3000    # 每集最多字数
EPISODE_TARGET_DURATION = 90  # 每集目标时长(秒) 1.5分钟
SCENES_PER_EPISODE = 8       # 每集场景数

# ==========================================
# 🎞 剪映配置
# ==========================================
CAPCUT_DRAFT_DIR = r"C:\Users\五路\AppData\Local\JianyingPro\User Data\Projects\com.lveditor.draft"

# ==========================================
# 📁 输出路径
# ==========================================
OUTPUT_DIR = "./output"
SCRIPTS_DIR = os.path.join(OUTPUT_DIR, "scripts")
IMAGES_DIR = os.path.join(OUTPUT_DIR, "images")
VIDEOS_DIR = os.path.join(OUTPUT_DIR, "videos")
AUDIO_DIR = os.path.join(OUTPUT_DIR, "audio")
FINAL_DIR = os.path.join(OUTPUT_DIR, "final")
STATE_DIR = os.path.join(OUTPUT_DIR, "state")
PROFILE_DIR = os.path.join(OUTPUT_DIR, "profiles")

for _d in [SCRIPTS_DIR, IMAGES_DIR, VIDEOS_DIR, AUDIO_DIR, FINAL_DIR, STATE_DIR, PROFILE_DIR]:
    os.makedirs(_d, exist_ok=True)

# ==========================================
# 📖 小说文件
# ==========================================
NOVEL_FILE = "novel.txt"

# ============================================
# 输出画质配置
# ============================================
QUALITY_LEVEL = "hd"  # standard / hd / 4k

QUALITY_PRESETS = {
    "standard": {
        "width": 720,
        "height": 1280,
        "fps": 24,
        "video_bitrate": "2M",
        "audio_bitrate": "128k",
        "codec": "libx264",
    },
    "hd": {
        "width": 1080,
        "height": 1920,
        "fps": 30,
        "video_bitrate": "5M",
        "audio_bitrate": "192k",
        "codec": "libx264",
    },
    "4k": {
        "width": 2160,
        "height": 3840,
        "fps": 30,
        "video_bitrate": "15M",
        "audio_bitrate": "256k",
        "codec": "libx265",
    },
}

# 当前画质参数
CURRENT_QUALITY = QUALITY_PRESETS[QUALITY_LEVEL]

# 字幕样式标准化
SUBTITLE_STYLE = {
    "font": "Microsoft YaHei",
    "fontsize": 26,
    "fontcolor": "white",
    "borderw": 3,
    "bordercolor": "black",
    "margin_bottom": 130,  # 底部安全区距离
}

# 情绪风格配置（供tts_engine使用）
EMOTION_STYLE = {
    "amazed":   {"speed": 1.0, "volume": 1.2},
    "angry":    {"speed": 1.1, "volume": 1.3},
    "sad":      {"speed": 0.9, "volume": 0.8},
    "happy":    {"speed": 1.05, "volume": 1.1},
    "scared":   {"speed": 1.0, "volume": 0.9},
    "calm":     {"speed": 0.95, "volume": 0.9},
    "dramatic": {"speed": 1.0, "volume": 1.1},
    "epic":     {"speed": 1.0, "volume": 1.2},
    "cold":     {"speed": 0.95, "volume": 0.9},
    "whisper":  {"speed": 0.9, "volume": 0.7},
    "shout":    {"speed": 1.1, "volume": 1.3},
    "default":  {"speed": 1.0, "volume": 1.0},
}

JIMENG_VIDEO_FIRST_TAIL_REQ_KEY = "jimeng_i2v_first_tail_v30_1080"

# 角色/背景目录（由 gui.py 切换任务时动态覆盖）
CHARACTERS_DIR = os.path.join(IMAGES_DIR, "characters")
BACKGROUNDS_DIR = os.path.join(IMAGES_DIR, "backgrounds")
