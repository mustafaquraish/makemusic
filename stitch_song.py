#!/usr/bin/env python3
"""
Stitch video frames into a single tall "piano roll" image.

Notes scroll downward at a constant speed.  Each frame reveals a thin
strip of new content at the top.  By extracting these strips and
stacking them we reconstruct the full song as one image.

Layout of the output (top → bottom):
    latest strip   — notes that play last
    …
    strip 1        — notes that play second
    initial area   — notes visible at the start (play first)
    keyboard       — the piano keys (optional)
"""
import os
import sys
import time as _time
from dataclasses import dataclass
from collections import deque
from threading import Thread

import cv2
import numpy as np

# Allow running from project root
sys.path.insert(0, os.path.dirname(__file__))

from src.frame_extractor import get_video_info, pipe_frames, iter_frames_pipe
from src.calibrator import (
    calibrate, CalibrationResult,
    detect_keyboard_region, detect_intro_end,
)
from src.keyboard_analyzer import build_keyboard_map
from src.stitch_detector import (
    detect_notes_on_stitched_image,
    StitchedNote,
    y_to_time,
)


@dataclass
class StitchResult:
    """All artefacts produced by the stitch-and-detect flow."""
    image: np.ndarray
    calibration: CalibrationResult
    keyboard_map: list
    notes: list            # List[StitchedNote]


def stitch_song(video_path: str,
                stitch_fps: float = 30.0,
                include_keyboard: bool = True,
                verbose: bool = True) -> StitchResult:
    """
    Stitch video frames into a single tall piano-roll image.

    Pipeline:
      1. Decode calibration frames (full-res, 2 fps, first 30 s)
      2. Quick-detect keyboard_y and intro_end from cal frames
      3. Start stitch decode (from intro_end) in a background thread
      4. While that decode runs, calibrate() + build_keyboard_map()
         on the main thread — the VP9 decode and calibration overlap
      5. Assemble strips from the decoded frames
      6. Detect notes on the assembled image
    """
    # ── 1. Video info ───────────────────────────────────────────────
    if verbose:
        print(f"[1/4] Getting video info …")
    info = get_video_info(video_path)
    width  = info['width']
    height = info['height']
    duration = info['duration']
    if verbose:
        print(f"       {width}×{height} @ {info['fps']} fps, "
              f"duration {duration:.1f} s")

    # ── 2. Calibration frames + quick pre-scan ─────────────────────
    if verbose:
        print(f"[2/4] Calibrating …")
    cal_end = min(30.0, duration or 30.0)
    cal_frames = pipe_frames(video_path, fps=2.0,
                             width=width, height=height,
                             end_time=cal_end)

    # Quick pre-scan: get keyboard_y and intro_end so we can start
    # the stitch decode immediately while calibrate() runs.
    mid_frame = cal_frames[len(cal_frames) * 2 // 3][1]
    pre_keyboard_y, _ = detect_keyboard_region(mid_frame)
    _, pre_intro_end = detect_intro_end(cal_frames, pre_keyboard_y)

    # ── 3. Start stitch decode in background ───────────────────────
    #
    # The ffmpeg subprocess decodes VP9 independently — no GIL
    # contention with the main thread's calibrate() CPU work.
    # Frames from the pipe are views into bytes objects that are
    # safe to hold without copying.
    #
    reader_buf: deque[tuple[float, np.ndarray]] = deque()
    reader_done = False

    def _reader():
        nonlocal reader_done
        for ts, frame in iter_frames_pipe(
            video_path, fps=stitch_fps,
            width=width, height=height,
            start_time=pre_intro_end, end_time=duration,
        ):
            # No .copy() — each frame's underlying bytes buffer is
            # a separate object from each read() call, so it stays
            # valid even after the generator advances.
            reader_buf.append((ts, frame))
        reader_done = True

    reader_thread = Thread(target=_reader, daemon=True)
    reader_thread.start()

    # ── 4. Full calibration (overlaps with decode above) ───────────
    cal = calibrate(cal_frames)

    keyboard_y      = cal.keyboard_y
    keyboard_height = cal.keyboard_height
    scroll_speed    = cal.scroll_speed
    intro_end       = cal.intro_end_time
    note_area_h     = keyboard_y

    kb_map = build_keyboard_map(cal_frames[-1][1], keyboard_y, keyboard_height)
    del cal_frames

    if verbose:
        strip_h = scroll_speed / stitch_fps
        print(f"       Keyboard Y: {keyboard_y}, height: {keyboard_height}")
        print(f"       Keyboard map: {len(kb_map)} keys")
        print(f"       Scroll speed: {scroll_speed:.1f} px/s")
        print(f"       Intro ends: {intro_end:.1f} s")
        print(f"       Strip height at {stitch_fps} fps: {strip_h:.1f} px")

    # ── 5. Stitch strips ──────────────────────────────────────────
    if verbose:
        print(f"[3/4] Stitching at {stitch_fps} fps …")

    initial_note_area = None
    keyboard_strip = None
    strips: list[np.ndarray] = []
    extracted_total = 0
    first_ts = None
    stitch_count = 0

    def _process_stitch_frame(ts: float, frame: np.ndarray):
        nonlocal initial_note_area, keyboard_strip, first_ts
        nonlocal extracted_total, stitch_count

        stitch_count += 1
        if first_ts is None:
            first_ts = ts
            initial_note_area = frame[0:keyboard_y, :].copy()
            if include_keyboard:
                kb_bottom = min(keyboard_y + keyboard_height, frame.shape[0])
                keyboard_strip = frame[keyboard_y:kb_bottom, :].copy()
            return

        elapsed        = ts - first_ts
        expected_total = scroll_speed * elapsed
        new_rows       = int(round(expected_total)) - extracted_total

        if new_rows > 0:
            new_rows = min(new_rows, note_area_h)
            strips.append(frame[0:new_rows, :].copy())
            extracted_total += new_rows

    # Drain frames from the background reader
    while True:
        while reader_buf:
            ts, frame = reader_buf.popleft()
            _process_stitch_frame(ts, frame)
        if reader_done:
            while reader_buf:
                ts, frame = reader_buf.popleft()
                _process_stitch_frame(ts, frame)
            break
        _time.sleep(0.001)

    reader_thread.join()

    if initial_note_area is None:
        raise RuntimeError("No frames extracted from video")

    if verbose:
        total_strip_h = sum(s.shape[0] for s in strips)
        print(f"       {stitch_count} frames → {len(strips)} strips, "
              f"total height: {total_strip_h} px")

    # ── Assemble the tall image ─────────────────────────────────────
    parts = list(reversed(strips))
    del strips
    parts.append(initial_note_area)
    if keyboard_strip is not None:
        parts.append(keyboard_strip)

    stitched = np.vstack(parts)
    del parts

    if verbose:
        print(f"       Stitched image: "
              f"{stitched.shape[1]} × {stitched.shape[0]} px")

    # ── 6. Detect notes ─────────────────────────────────────────────
    if verbose:
        print(f"[4/4] Detecting notes …")

    detected = detect_notes_on_stitched_image(stitched, cal, kb_map)

    if verbose:
        n_rh = sum(1 for n in detected if n.hand == 'right_hand')
        n_lh = sum(1 for n in detected if n.hand == 'left_hand')
        print(f"       {len(detected)} notes ({n_rh} RH, {n_lh} LH)")

    return StitchResult(
        image=stitched,
        calibration=cal,
        keyboard_map=kb_map,
        notes=detected,
    )
