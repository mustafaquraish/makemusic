#!/usr/bin/env python3
"""
Stitch video frames into a single tall "piano roll" image.

Instead of detecting boxes per-frame and tracking them, this approach
stitches together thin horizontal strips from consecutive frames to
create a single tall image of the entire song.  Box detection can then
be performed on this single static image.

The key insight: notes scroll downward at a constant speed.  Each frame
reveals a thin strip of new content at the top.  By extracting these
strips and stacking them, we reconstruct the full song as one image.

Layout of the output (top → bottom):
    latest strip   — notes that play last
    ...
    strip 1        — notes that play second
    initial area   — notes visible at the start (play first)
    keyboard       — the piano keys (optional)
"""
import os
import sys
import argparse
from dataclasses import dataclass, field

import cv2
import numpy as np

# Allow running from project root
sys.path.insert(0, os.path.dirname(__file__))

from src.frame_extractor import extract_frames_opencv, get_video_info
from src.calibrator import calibrate, CalibrationResult
from src.keyboard_analyzer import build_keyboard_map
from src.stitch_detector import (
    detect_notes_on_stitched_image,
    StitchedNote,
    y_to_time,
)


@dataclass
class StitchResult:
    """All artefacts produced by the stitch-and-detect flow."""
    image_path: str
    image: np.ndarray
    calibration: CalibrationResult
    keyboard_map: list
    notes: list            # List[StitchedNote]  — empty until detect() runs


def stitch_song(video_path: str,
                output_path: str = None,
                stitch_fps: float = 30.0,
                include_keyboard: bool = True,
                verbose: bool = True) -> StitchResult:
    """
    Stitch video frames into a single tall piano-roll image.

    Args:
        video_path:       Path to the video file.
        output_path:      Where to save the stitched image
                          (default: tmp/stitched_<song>.png).
        stitch_fps:       FPS to sample frames at.  Higher → finer strips,
                          better quality.  30 fps with 240 px/s scroll gives
                          8 px strips.
        include_keyboard: Include the keyboard region at the bottom.
        verbose:          Print progress info.

    Returns:
        StitchResult containing image path, calibration, and keyboard map.
    """
    # ── 1. Video info ───────────────────────────────────────────────
    if verbose:
        print(f"[1/5] Getting video info …")
    info = get_video_info(video_path)
    duration = info['duration']
    if verbose:
        print(f"       {info['width']}×{info['height']} @ {info['fps']} fps, "
              f"duration {duration:.1f} s")

    # ── 2. Calibrate & keyboard map ───────────────────────────────
    if verbose:
        print(f"[2/5] Calibrating …")
    cal_end = min(30.0, duration or 30.0)
    cal_frames = extract_frames_opencv(video_path, fps=2.0, end_time=cal_end)
    cal = calibrate(cal_frames)

    keyboard_y      = cal.keyboard_y
    keyboard_height = cal.keyboard_height
    scroll_speed    = cal.scroll_speed
    intro_end       = cal.intro_end_time
    note_area_h     = keyboard_y          # notes fall from y=0 → y=keyboard_y

    # Build keyboard map from a frame that has the keyboard visible
    kb_frame = cal_frames[-1][1]    # last calibration frame
    kb_map = build_keyboard_map(kb_frame, keyboard_y, keyboard_height)

    if verbose:
        strip_h = scroll_speed / stitch_fps
        print(f"       Keyboard Y: {keyboard_y}, height: {keyboard_height}")
        print(f"       Keyboard map: {len(kb_map)} keys")
        print(f"       Scroll speed: {scroll_speed:.1f} px/s")
        print(f"       Intro ends: {intro_end:.1f} s")
        print(f"       Strip height at {stitch_fps} fps: {strip_h:.1f} px")

    # ── 3. Extract frames & stitch ─────────────────────────────────
    if verbose:
        print(f"[3/5] Extracting frames at {stitch_fps} fps …")

    frames_data = extract_frames_opencv(
        video_path,
        fps=stitch_fps,
        start_time=intro_end,
        end_time=duration,
    )
    if not frames_data:
        raise RuntimeError("No frames extracted")
    if verbose:
        print(f"       Extracted {len(frames_data)} frames")

    # First frame: capture the full note area (everything above the keyboard)
    first_ts, first_frame = frames_data[0]
    initial_note_area = first_frame[0:keyboard_y, :].copy()

    # Optional keyboard strip from the first frame
    keyboard_strip = None
    if include_keyboard:
        kb_bottom = min(keyboard_y + keyboard_height, first_frame.shape[0])
        keyboard_strip = first_frame[keyboard_y:kb_bottom, :].copy()

    # Collect thin strips of new content from each subsequent frame.
    # Use integrated offset (not accumulated dt) to avoid drift.
    strips = []
    extracted_total = 0          # total integer rows extracted so far

    try:
        from tqdm import tqdm
        frame_iter = (tqdm(range(1, len(frames_data)), desc="       Stitching")
                      if verbose else range(1, len(frames_data)))
    except ImportError:
        frame_iter = range(1, len(frames_data))

    for i in frame_iter:
        ts_curr = frames_data[i][0]
        frame   = frames_data[i][1]

        elapsed        = ts_curr - first_ts
        expected_total = scroll_speed * elapsed      # ideal total rows by now
        new_rows       = int(round(expected_total)) - extracted_total

        if new_rows > 0:
            new_rows = min(new_rows, note_area_h)    # never exceed visible area
            strip = frame[0:new_rows, :].copy()
            strips.append(strip)
            extracted_total += new_rows

    if verbose:
        total_strip_h = sum(s.shape[0] for s in strips)
        print(f"       Collected {len(strips)} strips, "
              f"total height: {total_strip_h} px")

    # ── Assemble the tall image ─────────────────────────────────────
    #   top    → latest strip  (plays last)
    #   …
    #   strip1 → first new strip
    #   initial_note_area      (plays first)
    #   keyboard               (optional, at very bottom)
    parts = list(reversed(strips))
    parts.append(initial_note_area)
    if keyboard_strip is not None:
        parts.append(keyboard_strip)

    stitched = np.vstack(parts)

    if verbose:
        print(f"       Stitched image: "
              f"{stitched.shape[1]} × {stitched.shape[0]} px")

    # ── 4. Save ─────────────────────────────────────────────────────
    if output_path is None:
        song_name = os.path.basename(os.path.dirname(video_path))
        output_path = f"tmp/stitched_{song_name}.png"

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    cv2.imwrite(output_path, stitched)

    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    if verbose:
        print(f"[4/5] Saved: {output_path} ({size_mb:.1f} MB)")
        print(f"       Final size: {stitched.shape[1]} × {stitched.shape[0]}")

    # ── 5. Detect notes ─────────────────────────────────────────────
    if verbose:
        print(f"[5/5] Detecting notes on stitched image …")

    detected = detect_notes_on_stitched_image(
        stitched, cal, kb_map,
    )

    if verbose:
        note_area_bottom = stitched.shape[0] - cal.keyboard_height
        n_rh = sum(1 for n in detected if n.hand == 'right_hand')
        n_lh = sum(1 for n in detected if n.hand == 'left_hand')
        print(f"       Detected {len(detected)} notes "
              f"({n_rh} RH, {n_lh} LH)")
        # Show first few notes with times
        for n in detected[:10]:
            t = y_to_time(n.y, note_area_bottom,
                          cal.scroll_speed, cal.intro_end_time)
            print(f"         {n.key_name:5s}  {n.hand:12s}  "
                  f"t={t:6.1f}s  h={n.height}px")
        if len(detected) > 10:
            print(f"         … and {len(detected) - 10} more")

    return StitchResult(
        image_path=output_path,
        image=stitched,
        calibration=cal,
        keyboard_map=kb_map,
        notes=detected,
    )


# ─────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Stitch falling-notes video into a tall piano-roll image",
    )
    parser.add_argument("video", help="Path to the video file")
    parser.add_argument("-o", "--output", help="Output image path")
    parser.add_argument(
        "--fps", type=float, default=30.0,
        help="Sampling FPS (default: 30).  Higher = finer strips.",
    )
    parser.add_argument(
        "--no-keyboard", action="store_true",
        help="Omit the keyboard region at the bottom of the image",
    )
    parser.add_argument("-q", "--quiet", action="store_true")
    args = parser.parse_args()

    result = stitch_song(
        video_path=args.video,
        output_path=args.output,
        stitch_fps=args.fps,
        include_keyboard=not args.no_keyboard,
        verbose=not args.quiet,
    )

    # Export detected notes to JSON
    song_name = os.path.basename(os.path.dirname(args.video))
    json_path = result.image_path.replace('.png', '_notes.json')
    import json
    note_area_bottom = result.image.shape[0] - result.calibration.keyboard_height

    notes_data = []
    for n in result.notes:
        t = y_to_time(n.y, note_area_bottom,
                      result.calibration.scroll_speed,
                      result.calibration.intro_end_time)
        dur = n.height / result.calibration.scroll_speed
        notes_data.append({
            'key': n.key_name,
            'hand': n.hand,
            'time': round(t, 3),
            'duration': round(dur, 3),
            'y': n.y,
            'height': n.height,
        })

    with open(json_path, 'w') as f:
        json.dump({'notes': notes_data, 'song': song_name}, f, indent=2)

    if not args.quiet:
        print(f"\nNotes JSON saved: {json_path}")


if __name__ == "__main__":
    main()
