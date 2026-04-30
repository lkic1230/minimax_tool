"""全局常量定义。"""

# Chat 默认参数与取值范围
CHAT_MODEL_DEFAULT = "MiniMax-M2.7"
CHAT_MODELS = [
    "MiniMax-M2.7",
    "MiniMax-M2.7-highspeed",
    "MiniMax-M2.5",
    "MiniMax-M2.1",
]

CHAT_MAX_TOKENS_MIN = 1
CHAT_MAX_TOKENS_MAX = 8192
CHAT_MAX_TOKENS_DEFAULT = 4096

CHAT_TEMPERATURE_MIN = 0.01
CHAT_TEMPERATURE_MAX = 1.0
CHAT_TEMPERATURE_DEFAULT = 0.7

CHAT_TOP_P_MIN = 0.01
CHAT_TOP_P_MAX = 1.0
CHAT_TOP_P_DEFAULT = 0.95

# 采样风格预设（名称, temperature, top_p）
CHAT_SAMPLING_PRESETS = [
    ("平衡通用", 0.7, 0.95),
    ("严谨稳定", 0.3, 0.8),
    ("创意发散", 0.9, 0.98),
]
CHAT_SAMPLING_CUSTOM_LABEL = "自定义"

# Image 选项
IMAGE_MODELS = ["image-01", "image-01-live"]
IMAGE_MODEL_DEFAULT = IMAGE_MODELS[0]
IMAGE_COUNT_MIN = 1
IMAGE_COUNT_MAX = 9
IMAGE_COUNT_DEFAULT = 1
IMAGE_ASPECT_RATIOS = ["1:1", "16:9", "4:3", "3:2", "2:3", "3:4", "9:16", "21:9"]
IMAGE_ASPECT_RATIO_DEFAULT = IMAGE_ASPECT_RATIOS[0]
IMAGE_STYLES = ["无", "漫画", "元气", "中世纪", "水彩"]
IMAGE_STYLE_MODEL = "image-01-live"

# Music 选项
MUSIC_ORIGINAL_MODELS = ["music-2.6", "music-2.6-free"]
MUSIC_COVER_MODELS = ["music-cover", "music-cover-free"]
MUSIC_MODELS = MUSIC_ORIGINAL_MODELS + MUSIC_COVER_MODELS
MUSIC_MODEL_DEFAULT = MUSIC_ORIGINAL_MODELS[0]
MUSIC_COVER_MODEL_DEFAULT = MUSIC_COVER_MODELS[0]
MUSIC_ORIGINAL_MODES = ["歌曲（有歌词）", "纯音乐"]
MUSIC_LYRICS_MODES = ["完整歌曲", "编辑续写"]
MUSIC_LYRICS_MODE_DEFAULT = MUSIC_LYRICS_MODES[0]
MUSIC_LYRICS_MODE_EDIT = MUSIC_LYRICS_MODES[1]
MUSIC_LYRICS_API_MODES = ["write_full_song", "edit"]
MUSIC_LYRICS_API_MODE_DEFAULT = "write_full_song"
MUSIC_LYRICS_API_MODE_EDIT = "edit"
MUSIC_LYRICS_MODE_API_MAP = {
    "完整歌曲": "write_full_song",
    "编辑续写": "edit",
}

# Speech 选项
SPEECH_MODELS = [
    "speech-2.8-hd",
    "speech-2.8-turbo",
    "speech-2.6-hd",
    "speech-2.6-turbo",
]
SPEECH_MODEL_DEFAULT = SPEECH_MODELS[0]
SPEECH_VOICES = [
    "female-tianmei",
    "female-yuanzi",
    "female-susanna",
    "male-yuanbao",
    "male-hongren",
    "male-tianmei",
]
SPEECH_VOICE_DEFAULT = SPEECH_VOICES[0]
SPEECH_EMOTIONS = ["平静", "开心", "悲伤", "生气"]
SPEECH_EMOTION_API_MAP = {
    "平静": "neutral",
    "开心": "happy",
    "悲伤": "sad",
    "生气": "angry",
}
SPEECH_API_EMOTIONS = list(SPEECH_EMOTION_API_MAP.values())
SPEECH_EMOTION_DEFAULT = "neutral"
SPEECH_SPEED_MIN = 0.5
SPEECH_SPEED_MAX = 2.0
SPEECH_SPEED_DEFAULT = 1.0

# Video 选项
VIDEO_MODELS = [
    "MiniMax-Hailuo-2.3",
    "MiniMax-Hailuo-02",
    "MiniMax-Hailuo-2.3-Fast",
]
VIDEO_MODEL_DEFAULT = VIDEO_MODELS[0]
VIDEO_GENERATION_MODES = ["文生视频", "图生视频"]
VIDEO_DURATIONS = ["6", "10"]
VIDEO_DURATIONS_INT = [int(v) for v in VIDEO_DURATIONS]
VIDEO_DURATION_DEFAULT = VIDEO_DURATIONS_INT[0]
VIDEO_RESOLUTIONS = ["512P", "720P", "768P", "1080P"]
VIDEO_RESOLUTION_DEFAULT = "768P"
