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


def _renderer_layout(renderer, words, width: int, height: int) -> list:
    """Lay out words with a temporary renderer size."""
    orig_width = renderer.width
    orig_height = renderer.height
    renderer.width = width
    renderer.height = height
    try:
        return renderer.layout_words(words)
    finally:
        renderer.width = orig_width
        renderer.height = orig_height


def _render_renderer_frame(renderer, words, layout, active_time: float, width: int, height: int):
    """Render one frame with a temporary renderer size."""
    orig_width = renderer.width
    orig_height = renderer.height
    renderer.width = width
    renderer.height = height
    try:
        active_idx = renderer.get_active_word_index(words, active_time)
        scroll = renderer.compute_scroll_offset(layout, active_idx)
        return renderer.render_frame(layout, active_idx, scroll)
    finally:
        renderer.width = orig_width
        renderer.height = orig_height


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
        layout = _renderer_layout(renderer, ac.words, renderer.width, renderer.height)

        def make_frame(t, _ac=ac, _layout=layout):
            img = _render_renderer_frame(
                renderer,
                _ac.words,
                _layout,
                t,
                renderer.width,
                renderer.height,
            )
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
    face_position: str = "bottom-right",
    face_scale: float = 0.22,
) -> str:
    """Create a composite video with lip-synced face + highlighted text.

    Layout depends on face_position:
    - left: face on left half, text on right half
    - right: text on left half, face on right half
    - center: face centered top, text below
    - top-left/top-right/bottom-left/bottom-right: presenter docked in corner
      with the text/page rendered in the remaining reading pane
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
    overlay_positions = {"top-left", "top-right", "bottom-left", "bottom-right"}
    overlay_margin = max(16, int(min(frame_w, frame_h) * 0.03))
    overlay_scale = min(max(face_scale, 0.1), 0.9)

    for ac, lipsync_path in zip(aligned_chunks, lipsync_clips):
        duration = _get_audio_duration(ac.audio_path)

        # Load lip-sync face video
        face_clip = VideoFileClip(lipsync_path)
        if face_clip.duration < duration:
            face_clip = face_clip.loop(duration=duration)
        else:
            face_clip = face_clip.subclipped(0, duration)

        src_face_w, src_face_h = face_clip.size
        if face_position in overlay_positions:
            face_w = max(1, int(frame_w * overlay_scale))
            face_h = max(1, int(src_face_h * face_w / max(src_face_w, 1)))
            if face_h > frame_h - (overlay_margin * 2):
                face_h = max(1, frame_h - (overlay_margin * 2))
                face_w = max(1, int(src_face_w * face_h / max(src_face_h, 1)))
        elif face_position in ("left", "right"):
            face_w = frame_w // 2
            face_h = frame_h
        else:
            face_w = frame_w // 2
            face_h = frame_h // 2
        face_clip = face_clip.resized((face_w, face_h))

        if face_position in overlay_positions:
            # Corner presenters are docked into a side rail.  The reading pane
            # takes the rest of the frame so the presenter never hides text.
            rail_w = min(frame_w - 1, face_w + (overlay_margin * 2))
            text_w = max(1, frame_w - rail_w)
            text_h = frame_h
        elif face_position in ("left", "right"):
            text_w = frame_w // 2
            text_h = frame_h
        else:  # center
            text_w = frame_w
            text_h = max(1, frame_h - face_h)

        layout = _renderer_layout(renderer, ac.words, text_w, text_h)

        def make_text_frame(t, _ac=ac, _layout=layout, _tw=text_w, _th=text_h):
            img = _render_renderer_frame(renderer, _ac.words, _layout, t, _tw, _th)
            return np.array(img)

        text_clip = VideoClip(make_text_frame, duration=duration).with_fps(fps)

        # Position clips
        if face_position == "left":
            face_clip = face_clip.with_position((0, 0))
            text_clip = text_clip.with_position((face_w, 0))
        elif face_position == "right":
            text_clip = text_clip.with_position((0, 0))
            face_clip = face_clip.with_position((text_w, 0))
        elif face_position == "center":
            face_clip = face_clip.with_position(((frame_w - face_w) // 2, 0))
            text_clip = text_clip.with_position((0, face_h))
        else:
            x = overlay_margin if face_position.endswith("left") else frame_w - face_w - overlay_margin
            y = overlay_margin if face_position.startswith("top") else frame_h - face_h - overlay_margin
            text_x = frame_w - text_w if face_position.endswith("left") else 0
            text_clip = text_clip.with_position((text_x, 0))
            face_clip = face_clip.with_position((x, y))

        layers = [face_clip, text_clip] if face_position == "left" else [text_clip, face_clip]

        composite = CompositeVideoClip(
            layers,
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
