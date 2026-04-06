"""Model download and cache management."""

import os


def _get_cache_dir() -> str:
    cache = os.environ.get("SCREENCASTGEN_MODEL_CACHE", "~/.cache/screencastgen/models")
    path = os.path.expanduser(cache)
    os.makedirs(path, exist_ok=True)
    return path


def download_models(
    whisperx: bool = False,
    f5_tts: bool = False,
    latentsync: bool = False,
    qwen: bool = False,
    qwen_1_7b: bool = False,
) -> None:
    """Download model weights for the specified backends."""
    if not any([whisperx, f5_tts, latentsync, qwen, qwen_1_7b]):
        print("No models specified. Use --whisperx, --f5-tts, --latentsync, --qwen, or --all")
        return

    cache_dir = _get_cache_dir()
    print(f"Model cache directory: {cache_dir}")

    if whisperx:
        print("\n--- Downloading WhisperX models ---")
        try:
            import whisperx as wx
            print("Loading Whisper base model...")
            wx.load_model("base", "cpu", compute_type="float32")
            print("Loading alignment model...")
            wx.load_align_model(language_code="en", device="cpu")
            print("WhisperX models ready.")
        except ImportError:
            print("ERROR: whisperx not installed. Run: pip install whisperx")
        except Exception as e:
            print(f"ERROR downloading WhisperX models: {e}")

    if f5_tts:
        print("\n--- Downloading F5-TTS models ---")
        try:
            from f5_tts.api import F5TTS
            print("Loading F5-TTS model...")
            F5TTS(device="cpu")
            print("F5-TTS model ready.")
        except ImportError:
            print("ERROR: f5-tts not installed. Run: pip install f5-tts")
        except Exception as e:
            print(f"ERROR downloading F5-TTS models: {e}")

    if latentsync:
        print("\n--- Downloading LatentSync models ---")
        try:
            import latentsync
            print("LatentSync package found. Models will be downloaded on first use.")
        except ImportError:
            print(
                "ERROR: latentsync not installed.\n"
                "See: https://github.com/bytedance/LatentSync for installation instructions."
            )

    if qwen or qwen_1_7b:
        model_name = (
            "Qwen/Qwen3-TTS-12Hz-1.7B-Base" if qwen_1_7b
            else "Qwen/Qwen3-TTS-12Hz-0.6B-Base"
        )
        print(f"\n--- Downloading Qwen3-TTS model: {model_name} ---")
        try:
            from qwen_tts import Qwen3TTSModel
            import torch
            print(f"Loading {model_name}...")
            Qwen3TTSModel.from_pretrained(
                model_name,
                device_map="cpu",
                dtype=torch.float32,
            )
            print("Qwen3-TTS model ready.")
        except ImportError:
            print("ERROR: qwen-tts not installed. Run: pip install 'screencastgen[qwen]'")
        except Exception as e:
            print(f"ERROR downloading Qwen3-TTS model: {e}")

    print("\nDone.")
