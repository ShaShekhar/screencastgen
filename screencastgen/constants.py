"""Default constants and magic numbers for screencastgen."""

# TTS limits (conservative defaults; backends override via max_chunk_bytes)
MAX_CHUNK_BYTES = 4900
MAX_TTS_BYTES = 5000
MAX_SENTENCE_BYTES = 850
SENTENCE_WARN_BYTES = 900

# Splitting
LONG_SENTENCE_THRESHOLD = 850

# Defaults
DEFAULT_LANGUAGE = "en-US"
DEFAULT_OUTPUT_DIR = "audio"
DEFAULT_STATUS_FILE = "processing_status.json"

# Chunk file pattern
CHUNK_FILE_PATTERN = "audio_chunk_{num:03d}.{ext}"
VIDEO_CHUNK_FILE_PATTERN = "video_chunk_{num:03d}.mp4"

# Video defaults
DEFAULT_VIDEO_WIDTH = 1280
DEFAULT_VIDEO_HEIGHT = 720
DEFAULT_VIDEO_FPS = 24
DEFAULT_FONT_SIZE = 32
DEFAULT_HIGHLIGHT_COLOR = (255, 255, 0)  # yellow
DEFAULT_TEXT_COLOR = (255, 255, 255)  # white
DEFAULT_BG_COLOR = (30, 30, 30)  # dark gray

# Model cache
DEFAULT_MODEL_CACHE = "~/.cache/screencastgen/models"

# EPUB defaults
EPUB_AUDIO_FORMAT = "mp3"
EPUB_CHAPTER_DIR = "chapters"
EPUB_AUDIO_DIR = "audio"
EPUB_VIDEO_DIR = "video"
EPUB_SMIL_DIR = "smil"
MEDIA_OVERLAY_ACTIVE_CLASS = "-epub-media-overlay-active"
