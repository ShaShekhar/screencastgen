#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LATENTSYNC_ROOT="${PROJECT_ROOT}/external/LatentSync"
LATENTSYNC_ENV="${PROJECT_ROOT}/.venvs/latentsync"
HF_REPO="ByteDance/LatentSync-1.6"
CHECKPOINT_FILE="latentsync_unet.pt"
AUDIO_CHECKPOINT="whisper/tiny.pt"

usage() {
  cat <<EOF
Usage: scripts/install_latentsync.sh [options]

Options:
  --root PATH                LatentSync repo clone directory
  --env PATH                 Dedicated LatentSync virtualenv directory
  --hf-repo REPO             Hugging Face repo for checkpoints
  --checkpoint-file FILE     Main checkpoint filename in the Hugging Face repo
  --audio-checkpoint FILE    Audio checkpoint filename in the Hugging Face repo
  -h, --help                 Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --root)
      LATENTSYNC_ROOT="$2"
      shift 2
      ;;
    --env)
      LATENTSYNC_ENV="$2"
      shift 2
      ;;
    --hf-repo)
      HF_REPO="$2"
      shift 2
      ;;
    --checkpoint-file)
      CHECKPOINT_FILE="$2"
      shift 2
      ;;
    --audio-checkpoint)
      AUDIO_CHECKPOINT="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required but was not found in PATH." >&2
  exit 1
fi

if ! command -v git >/dev/null 2>&1; then
  echo "git is required but was not found in PATH." >&2
  exit 1
fi

if [[ ! -d "${LATENTSYNC_ROOT}" ]]; then
  mkdir -p "$(dirname "${LATENTSYNC_ROOT}")"
  git clone https://github.com/bytedance/LatentSync.git "${LATENTSYNC_ROOT}"
else
  echo "Using existing LatentSync clone at ${LATENTSYNC_ROOT}"
fi

uv venv --python 3.10 "${LATENTSYNC_ENV}"

LATENTSYNC_PYTHON="${LATENTSYNC_ENV}/bin/python"
uv pip install --python "${LATENTSYNC_PYTHON}" -r "${LATENTSYNC_ROOT}/requirements.txt"

"${LATENTSYNC_PYTHON}" \
  "${PROJECT_ROOT}/screencastgen/providers/lipsync/latentsync_worker.py" \
  download-checkpoints \
  --hf-repo "${HF_REPO}" \
  --local-dir "${LATENTSYNC_ROOT}/checkpoints" \
  --checkpoint-file "${CHECKPOINT_FILE}" \
  --audio-checkpoint "${AUDIO_CHECKPOINT}"

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "ffmpeg was not found in PATH. Install it before running lip-sync jobs." >&2
fi

cat <<EOF

LatentSync installation complete.

Default runtime paths:
  LATENTSYNC_ROOT=${LATENTSYNC_ROOT}
  LATENTSYNC_PYTHON=${LATENTSYNC_PYTHON}

Export these variables if you are using non-default paths:
  export LATENTSYNC_ROOT="${LATENTSYNC_ROOT}"
  export LATENTSYNC_PYTHON="${LATENTSYNC_PYTHON}"
EOF
