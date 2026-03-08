#!/usr/bin/env python3
"""
Save specific frames from Perfect at timestamps where the detector has issues,
so we can get human input on what the correct detection should be.

Based on the sequence alignment, the problematic areas are:
- t~17.5-20.7s: Missing standalone G before (B+G) chord
- t~20.7-22.0s: Missing B in "A B B A" sequence  
- t~22.0-24.5s: Missing a G note
- t~26.5-29.5s: Missing A from (A+F#) chord
- t~32.5-34.5s: Missing B and G notes
"""
import os, sys, cv2, numpy as np
sys.path.insert(0, os.path.dirname(__file__))

from src.frame_extractor import get_video_info, extract_frames_opencv
from src.calibrator import calibrate
from src.note_detector import detect_notes_in_frame
from src.keyboard_analyzer import build_keyboard_map, map_x_to_key

VIDEO = 'music/perfect/video.webm'
OUTPUT_DIR = 'tmp/human_review_perfect'
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Timestamps where we suspect detection problems
PROBLEM_TIMES = [
    (17.0, 21.0, "Missing_G_before_BG_chord"),
    (20.5, 22.5, "Missing_B_in_ABBA_sequence"),
    (22.0, 25.0, "Missing_G_note"),
    (26.0, 30.0, "Missing_A_from_AF_sharp_chord"),
    (32.0, 35.0, "Missing_B_and_G_notes"),
    (39.0, 42.0, "Extra_notes_region"),
]

info = get_video_info(VIDEO)
print(f"Video: {info['width']}x{info['height']}, {info['fps']}fps, {info['duration']:.1f}s")

# Calibrate
cal_frames = extract_frames_opencv(VIDEO, fps=2.0, end_time=30.0)
calibration = calibrate(cal_frames)
print(f"Keyboard Y: {calibration.keyboard_y}")

# Build keyboard map
mid_time = info['duration'] / 2
mid_frames = extract_frames_opencv(VIDEO, fps=1.0, start_time=mid_time, end_time=mid_time+1)
_, mid_frame = mid_frames[0]
keyboard_map = build_keyboard_map(mid_frame, calibration.keyboard_y, calibration.keyboard_height)
print(f"Keyboard: {len(keyboard_map)} keys ({keyboard_map[0].full_name} to {keyboard_map[-1].full_name})")

expected_note_height = calibration.scroll_speed * 0.4

YELLOW = (0, 255, 255)
RED = (0, 0, 255)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)

for start_t, end_t, label in PROBLEM_TIMES:
    print(f"\nExtracting: {label} ({start_t:.1f}s - {end_t:.1f}s)")
    
    # Extract at 5 fps for review (not too many frames)
    frames = extract_frames_opencv(VIDEO, fps=5.0, start_time=start_t, end_time=end_t)
    
    for i, (ts, frame) in enumerate(frames):
        detections = detect_notes_in_frame(
            frame, calibration, frame_index=i, timestamp=ts,
            expected_note_height=expected_note_height,
        )
        
        annotated = frame.copy()
        h, w = annotated.shape[:2]
        
        # Draw keyboard line
        cv2.line(annotated, (0, calibration.keyboard_y), (w, calibration.keyboard_y), YELLOW, 1)
        
        # Header
        header = f"Perfect RH - {label} - t={ts:.2f}s - {len(detections)} notes"
        cv2.putText(annotated, header, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, WHITE, 2)
        cv2.putText(annotated, header, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, BLACK, 1)
        
        for det in detections:
            color = (255, 100, 100) if det.hand == 'left_hand' else RED
            cv2.rectangle(annotated, (det.x, det.y), (det.x+det.width, det.y+det.height), color, 2)
            
            note_name = '?'
            if keyboard_map:
                key = map_x_to_key(det.center_x, keyboard_map)
                if key:
                    note_name = key.full_name
            
            hand_char = 'R' if det.hand == 'right_hand' else 'L'
            clip = ""
            if det.is_clipped_top: clip += "^"
            if det.is_clipped_bottom: clip += "v"
            text = f"{note_name}({hand_char}){clip}"
            
            (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
            label_y = max(det.y - 5, th + 5)
            cv2.rectangle(annotated, (det.x, label_y-th-2), (det.x+tw+4, label_y+2), BLACK, -1)
            cv2.putText(annotated, text, (det.x+2, label_y), cv2.FONT_HERSHEY_SIMPLEX, 0.45, WHITE, 1)
        
        fname = f"{label}_t{ts:.2f}s.png"
        cv2.imwrite(os.path.join(OUTPUT_DIR, fname), annotated)
    
    print(f"  Saved {len(frames)} frames")

print(f"\nAll review frames saved to: {OUTPUT_DIR}/")
print(f"Total files: {len(os.listdir(OUTPUT_DIR))}")
