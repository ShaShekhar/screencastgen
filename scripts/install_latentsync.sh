#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LATENTSYNC_ROOT="${PROJECT_ROOT}/external/LatentSync"
LATENTSYNC_ENV="${PROJECT_ROOT}/.venvs/latentsync"
HF_REPO="ByteDance/LatentSync-1.6"
CHECKPOINT_FILE="latentsync_unet.pt"
AUDIO_CHECKPOINT="whisper/tiny.pt"
SKIP_CHECKPOINTS=0

usage() {
  cat <<EOF
Usage: scripts/install_latentsync.sh [options]

Options:
  --root PATH                LatentSync repo clone directory
  --env PATH                 Dedicated LatentSync virtualenv directory
  --hf-repo REPO             Hugging Face repo for checkpoints
  --checkpoint-file FILE     Main checkpoint filename in the Hugging Face repo
  --audio-checkpoint FILE    Audio checkpoint filename in the Hugging Face repo
  --skip-checkpoints         Install LatentSync dependencies without downloading checkpoints
  -h, --help                 Show this help
EOF
}

require_command() {
  local cmd="$1"
  local install_hint="$2"
  if ! command -v "${cmd}" >/dev/null 2>&1; then
    echo "${cmd} is required but was not found in PATH." >&2
    if [[ -n "${install_hint}" ]]; then
      echo "${install_hint}" >&2
    fi
    exit 1
  fi
}

check_system_deps() {
  local missing=0

  if ! command -v gcc >/dev/null 2>&1; then
    echo "Missing required build tool: gcc" >&2
    missing=1
  fi
  if ! command -v g++ >/dev/null 2>&1; then
    echo "Missing required build tool: g++" >&2
    missing=1
  fi
  if ! command -v make >/dev/null 2>&1; then
    echo "Missing required build tool: make" >&2
    missing=1
  fi

  if [[ "${missing}" -ne 0 ]]; then
    cat >&2 <<EOF

Install the required system packages first, then rerun this script.
For Ubuntu/Debian:
  sudo apt-get update
  sudo apt-get install -y build-essential python3.10-dev ffmpeg libgl1 libglib2.0-0
EOF
    exit 1
  fi

  if ! command -v ffmpeg >/dev/null 2>&1; then
    echo "ffmpeg was not found in PATH. Install it before running lip-sync jobs." >&2
    echo "For Ubuntu/Debian: sudo apt-get install -y ffmpeg" >&2
  fi
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
    --skip-checkpoints)
      SKIP_CHECKPOINTS=1
      shift
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

require_command "uv" "Install uv first: https://docs.astral.sh/uv/getting-started/installation/"
require_command "git" "Install git first, then rerun this script."
check_system_deps

if [[ ! -d "${LATENTSYNC_ROOT}" ]]; then
  mkdir -p "$(dirname "${LATENTSYNC_ROOT}")"
  git clone https://github.com/bytedance/LatentSync.git "${LATENTSYNC_ROOT}"
else
  echo "Using existing LatentSync clone at ${LATENTSYNC_ROOT}"
fi

uv venv --python 3.10 "${LATENTSYNC_ENV}"

LATENTSYNC_PYTHON="${LATENTSYNC_ENV}/bin/python"
uv pip install --python "${LATENTSYNC_PYTHON}" -r "${LATENTSYNC_ROOT}/requirements.txt"

if [[ "${SKIP_CHECKPOINTS}" -eq 0 ]]; then
  "${LATENTSYNC_PYTHON}" \
    "${PROJECT_ROOT}/screencastgen/providers/lipsync/latentsync_worker.py" \
    download-checkpoints \
    --hf-repo "${HF_REPO}" \
    --local-dir "${LATENTSYNC_ROOT}/checkpoints" \
    --checkpoint-file "${CHECKPOINT_FILE}" \
    --audio-checkpoint "${AUDIO_CHECKPOINT}"
else
  echo "Skipping LatentSync checkpoint download."
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
