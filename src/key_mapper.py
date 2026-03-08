"""
Map horizontal pixel positions to piano key names.

Uses either:
1. Keyboard image analysis to identify actual key positions (preferred)
2. OCR'd labels from notes to build a position-to-key mapping
3. Interpolation based on standard piano layout (fallback)
"""
import numpy as np
from typing import List, Dict, Tuple, Optional
from .note_tracker import TrackedNote
from .calibrator import CalibrationResult
from .keyboard_analyzer import KeyInfo, map_x_to_key

# Standard piano: 88 keys, A0 to C8
# Key pattern repeats every octave: C C# D D# E F F# G G# A A# B
NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

# Full 88-key names
PIANO_KEYS = []
# Piano starts at A0
for octave in range(0, 9):
    for note in NOTE_NAMES:
        key_name = f"{note}{octave}"
        PIANO_KEYS.append(key_name)

# Trim to 88 keys: A0 to C8
# A0 is index 9 (A in octave 0), C8 is at the end
_start = NOTE_NAMES.index('A')  # 9
PIANO_88 = PIANO_KEYS[_start:_start + 88]


def build_key_map_from_ocr(notes: List[TrackedNote], 
                            frame_width: int) -> Dict[str, float]:
    """
    Build a mapping from note names to x-positions using OCR'd labels.
    
    Args:
        notes: Tracked notes with OCR text
        frame_width: Width of the video frame
    
    Returns:
        Dict mapping note_name -> center_x position
    """
    # Collect all OCR'd positions
    name_positions: Dict[str, List[float]] = {}
    
    for note in notes:
        if note.ocr_text and note.ocr_text != 'unknown':
            name = normalize_note_name(note.ocr_text)
            if name:
                if name not in name_positions:
                    name_positions[name] = []
                name_positions[name].append(note.center_x)
    
    # Average positions
    key_map = {}
    for name, positions in name_positions.items():
        key_map[name] = float(np.median(positions))
    
    return key_map


def normalize_note_name(text: str) -> Optional[str]:
    """
    Normalize OCR'd text to a standard note name.
    
    Handles common OCR errors and variations:
    - 'Cb' -> 'B' (enharmonic)
    - 'Db' -> 'C#'
    - Case variations
    - Number/letter confusion
    """
    text = text.strip().upper()
    
    # Common OCR corrections
    replacements = {
        'CB': 'B',
        'FB': 'E', 
        'DB': 'C#',
        'EB': 'D#',
        'GB': 'F#',
        'AB': 'G#',
        'BB': 'A#',
    }
    
    # Check for flat notation
    if len(text) >= 2 and text[-1] == 'B' and text[0] in 'CDEFGAB':
        # Could be a flat or a note name with octave
        if len(text) == 2 and text[0] in 'CDEFGA':
            # Likely a flat
            flat_name = text[:2]
            if flat_name in replacements:
                return replacements[flat_name]
    
    # Extract note letter, accidental, and octave
    if not text:
        return None
    
    note_letter = text[0]
    if note_letter not in 'ABCDEFG':
        return None
    
    rest = text[1:]
    accidental = ''
    octave = ''
    
    for ch in rest:
        if ch == '#' or ch == '♯':
            accidental = '#'
        elif ch == 'B' and not octave and accidental == '':
            # Could be flat
            accidental = 'b'
        elif ch.isdigit():
            octave += ch
    
    # Convert flats to sharps
    if accidental == 'b':
        flat_key = note_letter + 'B'
        if flat_key in replacements:
            base = replacements[flat_key]
            return base + octave if octave else base
    
    result = note_letter + accidental
    if octave:
        result += octave
    
    return result if result else None


def assign_keys_from_keyboard_map(notes: List[TrackedNote],
                                    keyboard_map: List[KeyInfo]) -> List[TrackedNote]:
    """
    Assign piano key names to notes using analyzed keyboard map.
    
    This is the preferred method - it uses actual detected key positions
    from the video's keyboard image rather than estimation.
    
    Args:
        notes: Tracked notes to assign keys to
        keyboard_map: List of KeyInfo from keyboard_analyzer
    
    Returns:
        Notes with key_index and note_name filled in
    """
    for note in notes:
        key = map_x_to_key(note.center_x, keyboard_map)
        if key:
            note.note_name = key.full_name
            note.key_index = key.midi_number
    
    return notes


def assign_keys_from_positions(notes: List[TrackedNote],
                                key_map: Dict[str, float],
                                calibration: CalibrationResult) -> List[TrackedNote]:
    """
    Assign piano key names to notes based on x-positions.
    
    If we have OCR data, use it to build a reference map.
    Otherwise, estimate from the frame width assuming the keyboard
    spans the full width with 88 keys.
    
    Args:
        notes: Tracked notes to assign keys to
        key_map: Known note_name -> x_position mappings (from OCR)
        calibration: Calibration data
    
    Returns:
        Notes with key_index and note_name filled in
    """
    frame_width = calibration.frame_width
    
    if len(key_map) >= 3:
        # Use OCR reference points to build the full mapping
        return _assign_keys_interpolated(notes, key_map, frame_width)
    else:
        # Estimate from frame width
        return _assign_keys_estimated(notes, frame_width)


def _assign_keys_interpolated(notes: List[TrackedNote],
                                key_map: Dict[str, float],
                                frame_width: int) -> List[TrackedNote]:
    """Assign keys using OCR reference points and interpolation."""
    
    # Build reference points: (x_position, key_index)
    ref_points = []
    for name, x_pos in key_map.items():
        if name in PIANO_88:
            idx = PIANO_88.index(name)
            ref_points.append((x_pos, idx))
    
    if len(ref_points) < 2:
        return _assign_keys_estimated(notes, frame_width)
    
    # Sort by x position
    ref_points.sort(key=lambda p: p[0])
    
    # Linear interpolation/extrapolation
    xs = np.array([p[0] for p in ref_points])
    idxs = np.array([p[1] for p in ref_points])
    
    # Fit linear relationship: key_index = a * x + b
    coeffs = np.polyfit(xs, idxs, 1)
    
    for note in notes:
        estimated_idx = int(round(coeffs[0] * note.center_x + coeffs[1]))
        estimated_idx = max(0, min(87, estimated_idx))
        note.key_index = estimated_idx + 21  # Convert to MIDI number (A0=21)
        if note.note_name == 'unknown' or not note.note_name:
            note.note_name = PIANO_88[estimated_idx]
    
    return notes


def _assign_keys_estimated(notes: List[TrackedNote], 
                            frame_width: int) -> List[TrackedNote]:
    """
    Assign keys based on estimated keyboard span.
    
    Assumes the visible keyboard spans a portion of the 88 keys
    centered roughly in the frame.
    """
    if not notes:
        return notes
    
    # Find the x-range of all notes
    x_positions = [n.center_x for n in notes]
    min_x = min(x_positions)
    max_x = max(x_positions)
    
    # Estimate how many keys are visible
    # A standard piano key (white) is about 23.5mm, visible range depends on zoom
    # Most videos show 3-5 octaves (36-60 keys)
    # Estimate based on frame width and typical note width
    
    # Get typical note widths from detections
    note_widths = [n.note_height_px for n in notes if n.note_height_px > 0]
    # Actually note_height_px is vertical height, not width. Use center_x spread.
    
    # Simple approach: assume keys are evenly spaced across the visible area
    # and estimate the octave range
    
    # Most falling notes videos show about 4 octaves centered around C4
    # That's 48 keys (4 octaves * 12 semitones)
    estimated_keys = 52  # ~4.3 octaves
    start_key = 20  # Starting around G#2
    
    # Map x to key index
    x_range = max_x - min_x
    if x_range < 10:
        x_range = frame_width
        min_x = 0
    
    pixels_per_key = x_range / estimated_keys
    
    for note in notes:
        key_offset = (note.center_x - min_x) / pixels_per_key
        estimated_idx = start_key + int(round(key_offset))
        estimated_idx = max(0, min(87, estimated_idx))
        note.key_index = estimated_idx + 21  # Convert to MIDI number (A0=21)
        if note.note_name == 'unknown' or not note.note_name:
            note.note_name = PIANO_88[estimated_idx]
    
    return notes


def get_key_boundaries(frame_width: int, num_visible_keys: int = 52,
                       start_key: int = 20) -> List[Tuple[str, int, int]]:
    """
    Get pixel boundaries for each visible piano key.
    
    Returns:
        List of (key_name, x_start, x_end) tuples
    """
    pixels_per_key = frame_width / num_visible_keys
    
    boundaries = []
    for i in range(num_visible_keys):
        key_idx = start_key + i
        if key_idx < len(PIANO_88):
            x_start = int(i * pixels_per_key)
            x_end = int((i + 1) * pixels_per_key)
            boundaries.append((PIANO_88[key_idx], x_start, x_end))
    
    return boundaries
