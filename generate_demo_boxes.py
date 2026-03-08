#!/usr/bin/env python3
"""
Generate a demo video showing detected note boxes overlaid on original frames.

For each video in music/:
  1. Calibrate (find keyboard_y, note colors, intro end)
  2. Extract 30s of frames (native fps) starting after the intro
  3. Run per-frame note detection and draw red boxes + labels
  4. Encode annotated frames into a video clip

Then stitch all clips into a single demo_box.mp4.

Also saves a few "tricky" frames as images for human inspection.
"""
import os
import sys
import glob
import subprocess
import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))

from src.frame_extractor import get_video_info, extract_frames_opencv
from src.calibrator import calibrate
from src.note_detector import detect_notes_in_frame
from src.keyboard_analyzer import build_keyboard_map, map_x_to_key

MUSIC_DIR = 'music'
OUTPUT_DIR = 'tmp/demo_boxes'
SEGMENT_DURATION = 30.0  # seconds per video
NATIVE_FPS = 30  # render at 30fps (good enough, faster than 60)

# Colors
RED = (0, 0, 255)
GREEN = (0, 255, 0)
YELLOW = (0, 255, 255)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)


def draw_boxes_on_frame(frame, detections, keyboard_map, keyboard_y, frame_idx, timestamp, song_name):
    """Draw red boxes and labels on a frame."""
    annotated = frame.copy()
    
    # Draw keyboard line
    h, w = annotated.shape[:2]
    cv2.line(annotated, (0, keyboard_y), (w, keyboard_y), YELLOW, 1)
    
    # Song name and timestamp overlay
    label = f"{song_name}  t={timestamp:.2f}s  frame={frame_idx}  notes={len(detections)}"
    cv2.putText(annotated, label, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, WHITE, 2)
    cv2.putText(annotated, label, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, BLACK, 1)
    
    for det in detections:
        # Box color: red for right hand, blue for left hand
        if det.hand == 'left_hand':
            box_color = (255, 100, 100)  # blue-ish
        else:
            box_color = RED
        
        # Draw rectangle
        cv2.rectangle(annotated,
                      (det.x, det.y),
                      (det.x + det.width, det.y + det.height),
                      box_color, 2)
        
        # Look up note name from keyboard map
        note_name = '?'
        if keyboard_map:
            key = map_x_to_key(det.center_x, keyboard_map)
            if key:
                note_name = key.full_name
        
        # Label: note name + hand indicator
        hand_label = 'R' if det.hand == 'right_hand' else 'L'
        text = f"{note_name} ({hand_label})"
        
        # Clipping indicators
        if det.is_clipped_top:
            text += " ^"
        if det.is_clipped_bottom:
            text += " v"
        
        # Draw label background
        (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.4, 1)
        label_y = max(det.y - 5, th + 5)
        cv2.rectangle(annotated,
                      (det.x, label_y - th - 2),
                      (det.x + tw + 4, label_y + 2),
                      BLACK, -1)
        cv2.putText(annotated, text, (det.x + 2, label_y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, WHITE, 1)
    
    return annotated


def process_video(video_path, song_name):
    """Process one video: calibrate, detect, draw boxes, save clip."""
    print(f"\n{'='*60}")
    print(f"  Processing: {song_name}")
    print(f"{'='*60}")
    
    info = get_video_info(video_path)
    print(f"  Resolution: {info['width']}x{info['height']}, FPS: {info['fps']}, Duration: {info['duration']:.1f}s")
    
    # Calibrate
    cal_end = min(30.0, info['duration'] or 30.0)
    cal_frames = extract_frames_opencv(video_path, fps=2.0, end_time=cal_end)
    calibration = calibrate(cal_frames)
    print(f"  Keyboard Y: {calibration.keyboard_y}, Colors: {len(calibration.note_colors)}, Intro: {calibration.intro_end_time:.1f}s")
    
    # Build keyboard map for note labeling
    keyboard_map = None
    try:
        mid_time = (info['duration'] or 60) / 2
        mid_frames = extract_frames_opencv(video_path, fps=1.0,
                                           start_time=mid_time,
                                           end_time=mid_time + 1)
        if mid_frames:
            _, mid_frame = mid_frames[0]
            keyboard_map = build_keyboard_map(
                mid_frame, calibration.keyboard_y,
                calibration.keyboard_height
            )
            if keyboard_map:
                print(f"  Keyboard map: {len(keyboard_map)} keys ({keyboard_map[0].full_name} to {keyboard_map[-1].full_name})")
    except Exception as e:
        print(f"  Keyboard map failed: {e}")
    
    # Extract 30s at 30fps starting after intro
    start_time = max(0, calibration.intro_end_time)
    end_time = start_time + SEGMENT_DURATION
    if end_time > (info['duration'] or 999):
        end_time = info['duration']
    
    print(f"  Extracting frames: {start_time:.1f}s - {end_time:.1f}s at {NATIVE_FPS} fps...")
    frames = extract_frames_opencv(video_path, fps=NATIVE_FPS,
                                   start_time=start_time, end_time=end_time)
    print(f"  Got {len(frames)} frames")
    
    expected_note_height = calibration.scroll_speed * 0.4 if calibration.scroll_speed > 0 else 100
    
    # Process frames and write annotated clip
    clip_dir = os.path.join(OUTPUT_DIR, song_name)
    os.makedirs(clip_dir, exist_ok=True)
    
    clip_path = os.path.join(OUTPUT_DIR, f'{song_name}.mp4')
    h, w = frames[0][1].shape[:2]
    
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    writer = cv2.VideoWriter(clip_path, fourcc, NATIVE_FPS, (w, h))
    
    # Track interesting frames for human inspection
    tricky_frames = []
    
    for i, (ts, frame) in enumerate(frames):
        detections = detect_notes_in_frame(
            frame, calibration,
            frame_index=i, timestamp=ts,
            expected_note_height=expected_note_height,
        )
        
        annotated = draw_boxes_on_frame(
            frame, detections, keyboard_map,
            calibration.keyboard_y, i, ts, song_name
        )
        writer.write(annotated)
        
        # Save tricky frames: many detections, or clipped notes, or first few
        if i < 3 or (detections and any(d.is_clipped_top or d.is_clipped_bottom for d in detections)):
            if len(tricky_frames) < 5:  # Limit per video
                tricky_frames.append((i, ts, frame, detections, annotated))
        
        if i % 100 == 0:
            print(f"    Frame {i}/{len(frames)} ({ts:.1f}s) - {len(detections)} notes detected")
    
    writer.release()
    print(f"  Saved clip: {clip_path}")
    
    # Save a few annotated frames as images for inspection
    for idx, (fi, ts, orig, dets, ann) in enumerate(tricky_frames):
        img_path = os.path.join(clip_dir, f'frame_{fi:04d}_t{ts:.1f}s.png')
        cv2.imwrite(img_path, ann)
    
    # Also save a "mid-segment" frame for inspection
    mid_idx = len(frames) // 2
    if mid_idx < len(frames):
        ts_mid, frame_mid = frames[mid_idx]
        dets_mid = detect_notes_in_frame(
            frame_mid, calibration, frame_index=mid_idx, timestamp=ts_mid,
            expected_note_height=expected_note_height,
        )
        ann_mid = draw_boxes_on_frame(
            frame_mid, dets_mid, keyboard_map,
            calibration.keyboard_y, mid_idx, ts_mid, song_name
        )
        img_path = os.path.join(clip_dir, f'frame_mid_{mid_idx:04d}_t{ts_mid:.1f}s.png')
        cv2.imwrite(img_path, ann_mid)
        print(f"  Saved mid-frame: {img_path}")
    
    return clip_path


def stitch_clips(clip_paths, output_path):
    """Concatenate video clips into one using ffmpeg."""
    # Create concat list file
    list_path = os.path.join(OUTPUT_DIR, 'concat_list.txt')
    with open(list_path, 'w') as f:
        for p in clip_paths:
            f.write(f"file '{os.path.abspath(p)}'\n")
    
    cmd = [
        'ffmpeg', '-y', '-f', 'concat', '-safe', '0',
        '-i', list_path,
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
        '-pix_fmt', 'yuv420p',
        output_path
    ]
    print(f"\nStitching {len(clip_paths)} clips into {output_path}...")
    subprocess.run(cmd, check=True, capture_output=True)
    print(f"Done! Output: {output_path}")


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    videos = sorted(glob.glob(os.path.join(MUSIC_DIR, '*/video.webm')))
    print(f"Found {len(videos)} videos")
    
    clip_paths = []
    for vp in videos:
        song_name = os.path.basename(os.path.dirname(vp))
        clip_path = process_video(vp, song_name)
        clip_paths.append(clip_path)
    
    # Stitch all clips
    final_path = os.path.join(OUTPUT_DIR, 'demo_box.mp4')
    stitch_clips(clip_paths, final_path)
    
    # Summary of saved inspection frames
    print(f"\n{'='*60}")
    print(f"  Inspection frames saved in {OUTPUT_DIR}/*/")
    print(f"{'='*60}")
    for vp in videos:
        song_name = os.path.basename(os.path.dirname(vp))
        clip_dir = os.path.join(OUTPUT_DIR, song_name)
        if os.path.isdir(clip_dir):
            pngs = sorted(glob.glob(os.path.join(clip_dir, '*.png')))
            print(f"  {song_name}: {len(pngs)} frames")
            for p in pngs:
                print(f"    {p}")


if __name__ == '__main__':
    main()
