"""
Export tracked notes to JSON format for the HTML viewer.
"""
import json
from typing import List, Dict, Any
from .note_tracker import TrackedNote
from .calibrator import CalibrationResult


def notes_to_dict(notes: List[TrackedNote], 
                  calibration: CalibrationResult,
                  video_path: str = '',
                  video_duration: float = 0.0,
                  video_fps: float = 60.0) -> Dict[str, Any]:
    """
    Convert tracked notes and calibration to a JSON-serializable dict.
    
    Args:
        notes: List of tracked notes
        calibration: Calibration results
        video_path: Source video path
        video_duration: Video duration in seconds
        video_fps: Video frame rate
    
    Returns:
        Dict ready for JSON serialization
    """
    # Build note color info
    color_info = {}
    for i, nc in enumerate(calibration.note_colors):
        color_info[nc.label] = {
            'rgb': [int(nc.center_bgr[2]), int(nc.center_bgr[1]), int(nc.center_bgr[0])],
            'hsv': [int(v) for v in nc.center_hsv],
            'index': i,
        }
    
    # Build note list
    note_list = []
    for note in notes:
        note_dict = {
            'id': note.id,
            'note_name': note.note_name,
            'start_time': round(note.start_time, 4),
            'duration': round(note.duration, 4),
            'hand': note.hand,
            'key_index': note.key_index,
            'center_x': round(note.center_x, 1),
            'color_rgb': [
                int(note.mean_bgr[2]),
                int(note.mean_bgr[1]),
                int(note.mean_bgr[0]),
            ],
        }
        if note.ocr_text:
            note_dict['ocr_text'] = note.ocr_text
        note_list.append(note_dict)
    
    return {
        'metadata': {
            'source_video': video_path,
            'duration_seconds': round(video_duration, 2),
            'fps': video_fps,
            'resolution': [calibration.frame_width, calibration.frame_height],
            'keyboard_y': calibration.keyboard_y,
            'scroll_speed': round(calibration.scroll_speed, 2),
            'intro_end_time': round(calibration.intro_end_time, 2),
            'note_colors': color_info,
        },
        'notes': note_list,
        'summary': {
            'total_notes': len(note_list),
            'left_hand_notes': sum(1 for n in note_list if n['hand'] == 'left_hand'),
            'right_hand_notes': sum(1 for n in note_list if n['hand'] == 'right_hand'),
            'duration_range': [
                round(min(n['start_time'] for n in note_list), 2) if note_list else 0,
                round(max(n['start_time'] + n['duration'] for n in note_list), 2) if note_list else 0,
            ],
            'key_range': [
                min(n['key_index'] for n in note_list) if note_list else 0,
                max(n['key_index'] for n in note_list) if note_list else 0,
            ],
        },
    }


def export_json(notes: List[TrackedNote],
                calibration: CalibrationResult,
                output_path: str,
                video_path: str = '',
                video_duration: float = 0.0,
                video_fps: float = 60.0):
    """
    Export notes to a JSON file.
    
    Args:
        notes: List of tracked notes
        calibration: Calibration results
        output_path: Path to write JSON file
        video_path: Source video path
        video_duration: Video duration
        video_fps: Video FPS
    """
    data = notes_to_dict(notes, calibration, video_path, video_duration, video_fps)
    
    with open(output_path, 'w') as f:
        json.dump(data, f, indent=2)
    
    return data


def validate_json(data: Dict[str, Any]) -> List[str]:
    """
    Validate a notes JSON structure for common issues.
    
    Returns:
        List of warning/error messages (empty if valid)
    """
    issues = []
    
    # Check required fields
    if 'metadata' not in data:
        issues.append("ERROR: Missing 'metadata' field")
    if 'notes' not in data:
        issues.append("ERROR: Missing 'notes' field")
        return issues
    
    notes = data['notes']
    
    if len(notes) == 0:
        issues.append("WARNING: No notes detected")
        return issues
    
    # Check timing
    for note in notes:
        if note.get('start_time', 0) < 0:
            issues.append(f"ERROR: Note {note.get('id')} has negative start_time")
        if note.get('duration', 0) <= 0:
            issues.append(f"ERROR: Note {note.get('id')} has non-positive duration")
        if note.get('key_index', -1) < 0 or note.get('key_index', 128) >= 128:
            issues.append(f"WARNING: Note {note.get('id')} has key_index out of range: {note.get('key_index')}")
    
    # Check for overlapping notes on the same key
    by_key = {}
    for note in notes:
        key = note.get('key_index', -1)
        if key not in by_key:
            by_key[key] = []
        by_key[key].append(note)
    
    for key, key_notes in by_key.items():
        key_notes.sort(key=lambda n: n['start_time'])
        for i in range(len(key_notes) - 1):
            end_time = key_notes[i]['start_time'] + key_notes[i]['duration']
            next_start = key_notes[i + 1]['start_time']
            if end_time > next_start + 0.01:  # Allow tiny overlap
                issues.append(
                    f"WARNING: Notes {key_notes[i]['id']} and {key_notes[i+1]['id']} "
                    f"overlap on key {key}"
                )
    
    # Sanity checks
    durations = [n['duration'] for n in notes]
    if max(durations) > 30:
        issues.append(f"WARNING: Unusually long note duration: {max(durations):.1f}s")
    if min(durations) < 0.01:
        issues.append(f"WARNING: Very short note duration: {min(durations):.4f}s")
    
    start_times = [n['start_time'] for n in notes]
    if max(start_times) < 1:
        issues.append("WARNING: All notes start within the first second")
    
    return issues
