"""Languages exposed by the web UI's language picker.

This is the curated list of languages Qwen3-TTS supports out of the
box (mirrors ``screencastgen/providers/tts/qwen_backend.py``'s
``_LANG_MAP`` keys, surfaced here as user-visible labels).
"""

from typing import List, TypedDict


class LanguageOption(TypedDict):
    code: str
    name: str


SUPPORTED_LANGUAGES: List[LanguageOption] = [
    {"code": "en-US", "name": "English (US)"},
    {"code": "en-GB", "name": "English (UK)"},
    {"code": "zh-CN", "name": "Chinese (Mandarin)"},
    {"code": "ja", "name": "Japanese"},
    {"code": "ko", "name": "Korean"},
    {"code": "de", "name": "German"},
    {"code": "fr", "name": "French"},
    {"code": "ru", "name": "Russian"},
    {"code": "pt", "name": "Portuguese"},
    {"code": "es", "name": "Spanish"},
    {"code": "it", "name": "Italian"},
]
