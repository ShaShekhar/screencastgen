"""Wav2Lip lip-sync provider."""


def run_wav2lip(video_path: str, audio_path: str, output_path: str):
    """Run Wav2Lip lip-sync generation."""
    from wav2lip import inference as wav2lip_infer

    wav2lip_infer.run(
        face=video_path,
        audio=audio_path,
        outfile=output_path,
    )
