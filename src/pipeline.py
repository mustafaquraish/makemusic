"""
Main pipeline orchestrating the full video analysis process.
"""
import os
import time
import logging
from typing import Optional

from tqdm import tqdm

from .frame_extractor import get_video_info, extract_frames_opencv, extract_frames
from .calibrator import calibrate, CalibrationResult
from .note_detector import detect_notes_in_frame
from .note_tracker import NoteTracker, TrackedNote
from .key_mapper import (build_key_map_from_ocr, assign_keys_from_positions,
                         assign_keys_from_keyboard_map)
from .keyboard_analyzer import build_keyboard_map, keyboard_map_to_list
from .ocr_reader import read_note_label
from .json_exporter import export_json, validate_json

logger = logging.getLogger(__name__)


def analyze_video(video_path: str, output_dir: str,
                  analysis_fps: float = 10.0,
                  ocr_enabled: bool = True,
                  ocr_sample_rate: int = 5,
                  keyboard_map_json: Optional[str] = None,
                  octave_offset: Optional[int] = None,
                  verbose: bool = True) -> dict:
    """
    Full pipeline: analyze a falling notes video and export JSON.
    
    Args:
        video_path: Path to the video file
        output_dir: Directory for output files
        analysis_fps: FPS for frame extraction (lower = faster, higher = more accurate)
        ocr_enabled: Whether to run OCR on note labels
        ocr_sample_rate: Run OCR every N frames (to save time)
        verbose: Print progress messages
    
    Returns:
        The exported JSON data dict
    """
    os.makedirs(output_dir, exist_ok=True)
    song_name = os.path.basename(os.path.dirname(video_path) if os.path.basename(video_path) == 'video.webm' else video_path)
    
    # Step 1: Get video info
    if verbose:
        print(f"\n{'='*60}")
        print(f"  Analyzing: {song_name}")
        print(f"{'='*60}")
        print(f"[1/7] Getting video info...")
    info = get_video_info(video_path)
    if verbose:
        print(f"       Resolution: {info['width']}x{info['height']}")
        print(f"       FPS: {info['fps']}, Duration: {info['duration']:.1f}s")
    
    # Step 2: Extract calibration frames (first 30 seconds at 2fps)
    if verbose:
        print(f"[2/7] Extracting calibration frames...")
    cal_end = min(30.0, info['duration'] or 30.0)
    cal_frames = extract_frames_opencv(video_path, fps=2.0, end_time=cal_end)
    if verbose:
        print(f"       Extracted {len(cal_frames)} calibration frames")
    
    # Step 3: Calibrate
    if verbose:
        print(f"[3/7] Calibrating...")
    calibration = calibrate(cal_frames)
    if verbose:
        print(f"       Keyboard Y: {calibration.keyboard_y}")
        print(f"       Note colors: {len(calibration.note_colors)}")
        for nc in calibration.note_colors:
            print(f"         - {nc.label}: HSV={nc.center_hsv}, BGR={nc.center_bgr}")
        print(f"       Scroll speed: {calibration.scroll_speed:.1f} px/s")
        print(f"       Intro ends at: {calibration.intro_end_time:.1f}s (frame {calibration.intro_end_frame})")
    
    # Step 4: Extract analysis frames (full video, at analysis_fps)
    if verbose:
        print(f"[4/7] Extracting analysis frames at {analysis_fps} fps...")
    start_time_offset = max(0, calibration.intro_end_time - 2.0)
    analysis_frames = extract_frames_opencv(
        video_path, fps=analysis_fps,
        start_time=start_time_offset
    )
    if verbose:
        print(f"       Extracted {len(analysis_frames)} frames for analysis")
    
    # Estimate expected note height from scroll speed and typical note duration
    # A quarter note at 120bpm = 0.5s, so expected height ~ 0.5 * scroll_speed
    expected_note_height = calibration.scroll_speed * 0.4 if calibration.scroll_speed > 0 else 100

    # Step 5: Detect and track notes
    if verbose:
        print(f"[5/7] Detecting and tracking notes...")
    
    tracker = NoteTracker(calibration, max_gap_frames=int(analysis_fps * 0.5))
    
    ocr_frame_count = 0
    total_detections = 0
    
    pbar = tqdm(analysis_frames, desc="Detecting", unit="frame",
                disable=not verbose, leave=False)
    
    for i, (ts, frame) in enumerate(pbar):
        # Detect notes in this frame
        detections = detect_notes_in_frame(
            frame, calibration,
            frame_index=i, timestamp=ts,
            expected_note_height=expected_note_height,
        )
        
        # Optionally run OCR on some frames
        if ocr_enabled and detections and i % ocr_sample_rate == 0:
            for det in detections:
                ocr_result = read_note_label(
                    frame, det.x, det.y, det.width, det.height
                )
                if ocr_result and ocr_result.confidence > 0.3:
                    det.ocr_text = ocr_result.text
            ocr_frame_count += 1
        
        # Feed to tracker
        tracker.process_frame(detections, i, ts)
        total_detections += len(detections)
        
        pbar.set_postfix(notes=total_detections, tracks=len(tracker.active_tracks))
    
    pbar.close()
    
    # Finalize tracking
    tracked_notes = tracker.finalize()
    if verbose:
        print(f"       Total tracked notes: {len(tracked_notes)}")
        print(f"       Measured scroll speed: {tracker.scroll_speed:.1f} px/s")
        print(f"       OCR ran on {ocr_frame_count} frames")
    
    # Step 6: Map keys
    if verbose:
        print(f"[6/7] Mapping notes to piano keys...")
    
    # Try keyboard image analysis first (most accurate)
    keyboard_map = None
    
    if keyboard_map_json:
        # Use pre-built keyboard map
        import json
        from .keyboard_analyzer import keyboard_map_from_list
        with open(keyboard_map_json) as f:
            keyboard_map = keyboard_map_from_list(json.load(f))
        if verbose:
            print(f"       Loaded keyboard map from {keyboard_map_json} ({len(keyboard_map)} keys)")
    else:
        # Analyze keyboard from a frame
        try:
            # Get a frame showing the keyboard clearly (middle of video)
            mid_time = (info['duration'] or 60) / 2
            mid_frames = extract_frames_opencv(video_path, fps=1.0,
                                                start_time=mid_time,
                                                end_time=mid_time + 1)
            if mid_frames:
                _, mid_frame = mid_frames[0]
                keyboard_map = build_keyboard_map(
                    mid_frame, calibration.keyboard_y, 
                    calibration.keyboard_height,
                    octave_offset=octave_offset
                )
                if verbose:
                    print(f"       Keyboard analysis: {len(keyboard_map)} keys detected")
                    if keyboard_map:
                        first = keyboard_map[0]
                        last = keyboard_map[-1]
                        print(f"       Range: {first.full_name} to {last.full_name}")
        except Exception as e:
            if verbose:
                print(f"       Keyboard analysis failed: {e}")
            keyboard_map = None
    
    if keyboard_map:
        tracked_notes = assign_keys_from_keyboard_map(tracked_notes, keyboard_map)
        
        import json
        kbd_path = os.path.join(output_dir, 'keyboard_map.json')
        with open(kbd_path, 'w') as f:
            json.dump(keyboard_map_to_list(keyboard_map), f, indent=2)
        if verbose:
            print(f"       Saved keyboard map to {kbd_path}")
    else:
        key_map = build_key_map_from_ocr(tracked_notes, calibration.frame_width)
        if verbose:
            print(f"       OCR reference points: {len(key_map)} (fallback mode)")
        tracked_notes = assign_keys_from_positions(tracked_notes, key_map, calibration)
    
    # Step 7: Export
    if verbose:
        print(f"[7/7] Exporting JSON...")
    
    output_path = os.path.join(output_dir, 'notes.json')
    data = export_json(
        tracked_notes, calibration, output_path,
        video_path=video_path,
        video_duration=info['duration'] or 0,
        video_fps=info['fps'],
    )
    
    # Validate
    issues = validate_json(data)
    if verbose:
        if issues:
            print(f"\nValidation issues:")
            for issue in issues:
                print(f"  {issue}")
        else:
            print(f"\nValidation passed!")
        
        print(f"\nSummary:")
        print(f"  Total notes: {data['summary']['total_notes']}")
        print(f"  Left hand: {data['summary']['left_hand_notes']}")
        print(f"  Right hand: {data['summary']['right_hand_notes']}")
        if data['summary']['duration_range'][0] is not None:
            print(f"  Time range: {data['summary']['duration_range'][0]:.1f}s - {data['summary']['duration_range'][1]:.1f}s")
        print(f"\nOutput: {output_path}")
    
    return data
