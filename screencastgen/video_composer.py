"""Video composition using MoviePy — assembles highlight frames + audio into video."""

from typing import List

import numpy as np

from .types import AlignedChunk


def _get_audio_duration(audio_path: str) -> float:
    """Get audio duration in seconds using pydub or ffprobe."""
    try:
        from pydub import AudioSegment
        audio = AudioSegment.from_file(audio_path)
        return len(audio) / 1000.0
    except ImportError:
        pass

    import subprocess
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "csv=p=0", audio_path],
        capture_output=True, text=True,
    )
    return float(result.stdout.strip())


def compose_highlight_video(
    aligned_chunks: List[AlignedChunk],
    renderer,
    output_path: str,
    fps: int = 24,
) -> str:
    """Create a video with highlighted text synced to audio.

    Each chunk becomes a clip; all clips are concatenated into the final video.
    """
    from moviepy import AudioFileClip, VideoClip, concatenate_videoclips

    clips = []

    for ac in aligned_chunks:
        duration = _get_audio_duration(ac.audio_path)
        word_texts = [w.word for w in ac.words]
        layout = renderer.layout_words(word_texts)

        def make_frame(t, _ac=ac, _layout=layout):
            active_idx = renderer.get_active_word_index(_ac.words, t)
            scroll = renderer.compute_scroll_offset(_layout, active_idx)
            img = renderer.render_frame(_layout, active_idx, scroll)
            return np.array(img)

        video_clip = VideoClip(make_frame, duration=duration).with_fps(fps)
        audio_clip = AudioFileClip(ac.audio_path)
        video_clip = video_clip.with_audio(audio_clip)
        clips.append(video_clip)

    if not clips:
        raise ValueError("No clips to compose")

    final = concatenate_videoclips(clips, method="compose")
    final.write_videofile(output_path, fps=fps, codec="libx264", audio_codec="aac")

    # Clean up
    for clip in clips:
        clip.close()
    final.close()

    return output_path


def compose_lipsync_video(
    aligned_chunks: List[AlignedChunk],
    lipsync_clips: List[str],
    renderer,
    output_path: str,
    fps: int = 24,
    face_position: str = "left",
) -> str:
    """Create a composite video with lip-synced face + highlighted text.

    Layout depends on face_position:
    - left: face on left half, text on right half
    - right: text on left half, face on right half
    - center: face centered top, text below
    """
    from moviepy import (
        AudioFileClip,
        CompositeVideoClip,
        VideoClip,
        VideoFileClip,
        concatenate_videoclips,
    )

    frame_w, frame_h = renderer.width, renderer.height
    clips = []

    for ac, lipsync_path in zip(aligned_chunks, lipsync_clips):
        duration = _get_audio_duration(ac.audio_path)
        word_texts = [w.word for w in ac.words]

        # Text area is half the frame for left/right layouts
        if face_position in ("left", "right"):
            text_w = frame_w // 2
            face_w = frame_w // 2
            face_h = frame_h
            text_renderer_width = text_w
        else:  # center
            text_w = frame_w
            face_w = frame_w // 2
            face_h = frame_h // 2
            text_renderer_width = text_w

        # Adjust renderer width for text area
        orig_width = renderer.width
        renderer.width = text_renderer_width
        layout = renderer.layout_words(word_texts)
        renderer.width = orig_width

        def make_text_frame(t, _ac=ac, _layout=layout, _tw=text_renderer_width):
            active_idx = renderer.get_active_word_index(_ac.words, t)
            scroll = renderer.compute_scroll_offset(_layout, active_idx)
            orig_w = renderer.width
            renderer.width = _tw
            img = renderer.render_frame(_layout, active_idx, scroll)
            renderer.width = orig_w
            return np.array(img)

        text_clip = VideoClip(make_text_frame, duration=duration).with_fps(fps)

        # Load lip-sync face video
        face_clip = VideoFileClip(lipsync_path).resized((face_w, face_h))
        if face_clip.duration < duration:
            face_clip = face_clip.loop(duration=duration)
        else:
            face_clip = face_clip.subclipped(0, duration)

        # Position clips
        if face_position == "left":
            face_clip = face_clip.with_position((0, 0))
            text_clip = text_clip.with_position((face_w, 0))
        elif face_position == "right":
            text_clip = text_clip.with_position((0, 0))
            face_clip = face_clip.with_position((text_w, 0))
        else:  # center
            face_clip = face_clip.with_position(((frame_w - face_w) // 2, 0))
            text_clip = text_clip.with_position((0, face_h))

        composite = CompositeVideoClip(
            [face_clip, text_clip],
            size=(frame_w, frame_h),
        ).with_duration(duration)

        audio_clip = AudioFileClip(ac.audio_path)
        composite = composite.with_audio(audio_clip)
        clips.append(composite)

    if not clips:
        raise ValueError("No clips to compose")

    final = concatenate_videoclips(clips, method="compose")
    final.write_videofile(output_path, fps=fps, codec="libx264", audio_codec="aac")

    for clip in clips:
        clip.close()
    final.close()

    return output_path
