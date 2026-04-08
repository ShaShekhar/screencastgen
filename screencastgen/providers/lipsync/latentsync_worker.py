"""Standalone LatentSync worker for a dedicated Python environment."""

from __future__ import annotations

import argparse
import json
import os
import sys
from contextlib import redirect_stdout
from dataclasses import dataclass


def _emit(payload: dict) -> None:
    sys.stdout.write(json.dumps(payload) + "\n")
    sys.stdout.flush()


def _resolve_mask_path(root: str, mask_path: str) -> str:
    if os.path.isabs(mask_path):
        return mask_path
    return os.path.join(root, mask_path)


@dataclass
class LoadedPipeline:
    """Loaded LatentSync inference objects."""

    config: object
    pipeline: object
    dtype: object
    set_seed: object
    temp_dir: str
    guidance_scale: float
    inference_steps: int
    seed: int
    mask_image_path: str


def _load_pipeline(args) -> LoadedPipeline:
    with redirect_stdout(sys.stderr):
        import torch
        from accelerate.utils import set_seed
        from diffusers import AutoencoderKL, DDIMScheduler
        from omegaconf import OmegaConf

        from latentsync.models.unet import UNet3DConditionModel
        from latentsync.pipelines.lipsync_pipeline import LipsyncPipeline
        from latentsync.whisper.audio2feature import Audio2Feature

        if args.device != "cuda":
            raise RuntimeError("LatentSync inference requires CUDA.")

        config = OmegaConf.load(args.config_path)
        scheduler = DDIMScheduler.from_pretrained(os.path.join(args.root, "configs"))

        is_fp16_supported = torch.cuda.is_available() and torch.cuda.get_device_capability()[0] > 7
        dtype = torch.float16 if is_fp16_supported else torch.float32

        if config.model.cross_attention_dim == 768:
            whisper_model_path = os.path.join(args.root, "checkpoints", "whisper", "small.pt")
        elif config.model.cross_attention_dim == 384:
            whisper_model_path = os.path.join(args.root, "checkpoints", "whisper", "tiny.pt")
        else:
            raise NotImplementedError("LatentSync cross_attention_dim must be 768 or 384")

        audio_encoder = Audio2Feature(
            model_path=whisper_model_path,
            device=args.device,
            num_frames=config.data.num_frames,
            audio_feat_length=config.data.audio_feat_length,
        )

        vae = AutoencoderKL.from_pretrained("stabilityai/sd-vae-ft-mse", torch_dtype=dtype)
        vae.config.scaling_factor = 0.18215
        vae.config.shift_factor = 0

        unet, _ = UNet3DConditionModel.from_pretrained(
            OmegaConf.to_container(config.model, resolve=True),
            args.checkpoint_path,
            device="cpu",
        )
        unet = unet.to(dtype=dtype)

        pipeline = LipsyncPipeline(
            vae=vae,
            audio_encoder=audio_encoder,
            unet=unet,
            scheduler=scheduler,
        ).to(args.device)

        if args.enable_deepcache:
            try:
                from DeepCache import DeepCacheSDHelper
            except ImportError:
                pass
            else:
                helper = DeepCacheSDHelper(pipe=pipeline)
                helper.set_params(cache_interval=3, cache_branch_id=0)
                helper.enable()

    os.makedirs(args.temp_dir, exist_ok=True)
    return LoadedPipeline(
        config=config,
        pipeline=pipeline,
        dtype=dtype,
        set_seed=set_seed,
        temp_dir=args.temp_dir,
        guidance_scale=args.guidance_scale,
        inference_steps=args.inference_steps,
        seed=args.seed,
        mask_image_path=_resolve_mask_path(args.root, config.data.mask_image_path),
    )


def _run_inference(state: LoadedPipeline, request: dict) -> str:
    video_path = request["video_path"]
    audio_path = request["audio_path"]
    output_path = request["output_path"]

    if not os.path.isfile(video_path):
        raise FileNotFoundError(f"Input video not found at {video_path}")
    if not os.path.isfile(audio_path):
        raise FileNotFoundError(f"Input audio not found at {audio_path}")

    with redirect_stdout(sys.stderr):
        if state.set_seed is not None and state.seed != -1:
            state.set_seed(state.seed)

        state.pipeline(
            video_path=video_path,
            audio_path=audio_path,
            video_out_path=output_path,
            num_frames=state.config.data.num_frames,
            num_inference_steps=state.inference_steps,
            guidance_scale=state.guidance_scale,
            weight_dtype=state.dtype,
            width=state.config.data.resolution,
            height=state.config.data.resolution,
            mask_image_path=state.mask_image_path,
            temp_dir=state.temp_dir,
        )

    if not os.path.isfile(output_path):
        raise RuntimeError(f"LatentSync completed but output file not found at {output_path}")
    return output_path


def _serve(args) -> int:
    try:
        state = _load_pipeline(args)
    except Exception as exc:
        _emit({"ok": False, "phase": "startup", "error": str(exc)})
        return 1

    _emit({"ok": True, "event": "ready"})

    for raw_line in sys.stdin:
        line = raw_line.strip()
        if not line:
            continue

        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            _emit({"ok": False, "error": "Invalid JSON request"})
            continue

        cmd = request.get("cmd")
        if cmd == "shutdown":
            _emit({"ok": True, "event": "shutdown"})
            return 0
        if cmd != "run":
            _emit({"ok": False, "error": f"Unknown worker command: {cmd!r}"})
            continue

        try:
            output_path = _run_inference(state, request)
        except Exception as exc:
            _emit({"ok": False, "error": str(exc)})
            continue

        _emit({"ok": True, "output_path": output_path})

    return 0


def _download_checkpoints(args) -> int:
    from huggingface_hub import hf_hub_download

    os.makedirs(args.local_dir, exist_ok=True)
    for filename in (args.checkpoint_file, args.audio_checkpoint):
        path = hf_hub_download(
            repo_id=args.hf_repo,
            filename=filename,
            local_dir=args.local_dir,
        )
        print(f"Downloaded {filename} -> {path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="LatentSync sidecar worker")
    sub = parser.add_subparsers(dest="command", required=True)

    serve = sub.add_parser("serve", help="Start a persistent inference worker")
    serve.add_argument("--root", required=True)
    serve.add_argument("--config-path", required=True)
    serve.add_argument("--checkpoint-path", required=True)
    serve.add_argument("--temp-dir", required=True)
    serve.add_argument("--device", default="cuda")
    serve.add_argument("--inference-steps", type=int, required=True)
    serve.add_argument("--guidance-scale", type=float, required=True)
    serve.add_argument("--seed", type=int, default=1247)
    serve.add_argument("--enable-deepcache", action="store_true")

    dl = sub.add_parser("download-checkpoints", help="Download inference checkpoints")
    dl.add_argument("--hf-repo", default="ByteDance/LatentSync-1.6")
    dl.add_argument("--local-dir", required=True)
    dl.add_argument("--checkpoint-file", default="latentsync_unet.pt")
    dl.add_argument("--audio-checkpoint", default="whisper/tiny.pt")

    args = parser.parse_args()
    if args.command == "serve":
        return _serve(args)
    return _download_checkpoints(args)


if __name__ == "__main__":
    raise SystemExit(main())
