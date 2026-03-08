"""
Analyze the piano keyboard visible in video frames to determine 
the position and name of each key.

Approach:
1. Detect white key positions from bottom-of-keyboard intensity profile
2. Detect black key positions from top-of-keyboard dark regions
3. Use the 2-3 black key grouping pattern to assign note names
4. Fall back to position extrapolation from the best complete octave
5. Determine absolute octave offset using heuristics
"""
import cv2
import numpy as np
import logging
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, field

try:
    from scipy.ndimage import uniform_filter1d
except ImportError:
    def uniform_filter1d(x, size):
        """Simple moving average fallback."""
        kernel = np.ones(size) / size
        return np.convolve(x, kernel, mode='same')

logger = logging.getLogger(__name__)

NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
WHITE_NOTES = ['C', 'D', 'E', 'F', 'G', 'A', 'B']
BLACK_NOTES = ['C#', 'D#', 'F#', 'G#', 'A#']

# Black keys that exist between adjacent white keys
BLACK_KEY_MAP = {
    ('C', 'D'): 'C#',
    ('D', 'E'): 'D#',
    ('F', 'G'): 'F#',
    ('G', 'A'): 'G#',
    ('A', 'B'): 'A#',
}


@dataclass
class KeyInfo:
    """Information about a single piano key."""
    center_x: int
    note_name: str  # e.g. 'C', 'F#'
    is_black: bool
    octave: int  # absolute octave (e.g. 4 for middle C)
    full_name: str = ''  # e.g. 'C4'

    def __post_init__(self):
        if not self.full_name:
            self.full_name = f"{self.note_name}{self.octave}"

    @property
    def midi_number(self) -> int:
        """MIDI note number (C4 = 60)."""
        note_idx = NOTE_NAMES.index(self.note_name)
        return (self.octave + 1) * 12 + note_idx

    def to_dict(self) -> dict:
        return {
            'center_x': self.center_x,
            'note_name': self.note_name,
            'is_black': self.is_black,
            'octave': self.octave,
            'full_name': self.full_name,
            'midi': self.midi_number,
        }


def detect_white_key_positions(gray_frame: np.ndarray,
                                keyboard_y: int,
                                keyboard_height: int) -> List[int]:
    """
    Detect white key center positions from the bottom portion of the keyboard
    where only white keys are visible.
    
    Returns sorted list of x-coordinates for white key centers.
    """
    h, w = gray_frame.shape[:2]
    
    # Use bottom 20% of keyboard (white key only region)
    white_row_start = keyboard_y + int(keyboard_height * 0.80)
    white_row_end = min(keyboard_y + keyboard_height - 3, h - 1)
    
    if white_row_end <= white_row_start:
        white_row_start = keyboard_y + int(keyboard_height * 0.6)
    
    white_region = gray_frame[white_row_start:white_row_end, :]
    
    # Average vertically to get 1D profile
    profile = np.mean(white_region.astype(float), axis=0)
    profile_smooth = uniform_filter1d(profile, 3)
    
    # Find local minima (gaps between white keys)
    threshold = (np.max(profile_smooth) + np.min(profile_smooth)) / 2
    
    boundaries = []
    for x in range(5, len(profile_smooth) - 5):
        window = profile_smooth[x - 3:x + 4]
        if profile_smooth[x] == np.min(window) and profile_smooth[x] < threshold:
            boundaries.append(x)
    
    # Remove boundaries too close together
    filtered = []
    for b in boundaries:
        if not filtered or b - filtered[-1] > 15:
            filtered.append(b)
    boundaries = filtered
    
    # Compute centers between boundaries
    edges = [0] + boundaries + [w]
    centers = [(edges[i] + edges[i + 1]) // 2 for i in range(len(edges) - 1)]
    
    # Filter out very narrow keys at edges (less than half the median width)
    if len(centers) > 3:
        widths = [edges[i + 1] - edges[i] for i in range(len(edges) - 1)]
        median_width = np.median(widths)
        min_width = median_width * 0.4
        valid_centers = []
        for i, c in enumerate(centers):
            if widths[i] >= min_width:
                valid_centers.append(c)
        centers = valid_centers
    
    return centers


def detect_black_key_positions(gray_frame: np.ndarray,
                                keyboard_y: int,
                                keyboard_height: int) -> List[int]:
    """
    Detect black key center positions from the top portion of the keyboard.
    
    Returns sorted list of x-coordinates for black key centers.
    """
    h, w = gray_frame.shape[:2]
    
    # Use top 40% of keyboard
    black_row_start = keyboard_y + 5
    black_row_end = keyboard_y + int(keyboard_height * 0.4)
    
    black_region = gray_frame[black_row_start:black_row_end, :]
    profile = np.mean(black_region.astype(float), axis=0)
    profile_smooth = uniform_filter1d(profile, 5)
    
    # Find contiguous dark regions
    black_threshold = 80
    centers = []
    in_dark = False
    dark_start = 0
    
    for x in range(len(profile_smooth)):
        if profile_smooth[x] < black_threshold and not in_dark:
            in_dark = True
            dark_start = x
        elif (profile_smooth[x] >= black_threshold or x == len(profile_smooth) - 1) and in_dark:
            in_dark = False
            dark_width = x - dark_start
            if dark_width > 15:  # Minimum black key width
                centers.append((dark_start + x) // 2)
    
    return centers


def group_black_keys(black_centers: List[int],
                     white_key_width: float) -> List[List[int]]:
    """
    Group black keys into the standard piano 2-3 pattern.
    
    Returns list of groups (each group is a list of x-positions).
    """
    if len(black_centers) < 2:
        return [[c] for c in black_centers]
    
    gap_threshold = white_key_width * 1.5
    
    groups = [[black_centers[0]]]
    for i in range(1, len(black_centers)):
        gap = black_centers[i] - black_centers[i - 1]
        if gap < gap_threshold:
            groups[-1].append(black_centers[i])
        else:
            groups.append([black_centers[i]])
    
    return groups


def find_best_complete_octave(white_centers: List[int],
                               black_centers: List[int],
                               black_groups: List[List[int]],
                               white_key_width: float) -> Optional[int]:
    """
    Find the index (in white_centers) of the C that starts the most
    complete and reliable octave.
    
    Returns the index into white_centers of the best C, or None.
    """
    group_sizes = [len(g) for g in black_groups]
    
    # Find groups of exactly 2 followed by groups of exactly 3
    best_c_idx = None
    best_score = -1
    
    for i in range(len(group_sizes) - 1):
        if group_sizes[i] == 2 and group_sizes[i + 1] == 3:
            # This is a C#/D# group followed by F#/G#/A# group
            # The C is just to the left of the first key in the group of 2
            first_csharp = black_groups[i][0]
            
            # Find the white key just to the left of C#
            c_candidates = [j for j, wc in enumerate(white_centers) 
                           if wc < first_csharp and first_csharp - wc < white_key_width]
            
            if c_candidates:
                c_idx = c_candidates[-1]  # closest white key to the left
                
                # Score: prefer complete octaves (C through B = 7 white keys after c_idx)
                remaining_whites = len(white_centers) - c_idx
                remaining_blacks = sum(group_sizes[i:])
                score = min(remaining_whites, 7) + min(remaining_blacks, 5)
                
                # Also prefer octaves in the middle of the keyboard
                mid_x = (white_centers[0] + white_centers[-1]) / 2
                dist_from_mid = abs(white_centers[c_idx] - mid_x)
                mid_bonus = 1.0 / (1.0 + dist_from_mid / 500)
                score += mid_bonus
                
                if score > best_score:
                    best_score = score
                    best_c_idx = c_idx
    
    return best_c_idx


def build_keyboard_map(frame_bgr: np.ndarray,
                        keyboard_y: int,
                        keyboard_height: int,
                        octave_offset: Optional[int] = None) -> List[KeyInfo]:
    """
    Build a complete keyboard map from a video frame.
    
    Args:
        frame_bgr: BGR video frame
        keyboard_y: Top y-coordinate of keyboard region
        keyboard_height: Height of keyboard region
        octave_offset: Absolute octave number for the first visible C.
                       If None, uses heuristic (first C = C3).
    
    Returns:
        List of KeyInfo objects sorted by x-position
    """
    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape[:2]
    
    # Step 1: Detect key positions
    white_centers = detect_white_key_positions(gray, keyboard_y, keyboard_height)
    black_centers = detect_black_key_positions(gray, keyboard_y, keyboard_height)
    
    if len(white_centers) < 3:
        logger.warning("Too few white keys detected (%d), falling back to estimate", 
                       len(white_centers))
        return _estimate_keyboard(w, octave_offset)
    
    white_key_width = float(np.median(np.diff(white_centers)))
    
    logger.info("Detected %d white keys, %d black keys (key width: %.1f px)",
                len(white_centers), len(black_centers), white_key_width)
    
    # Step 2: Group black keys
    black_groups = group_black_keys(black_centers, white_key_width)
    group_sizes = [len(g) for g in black_groups]
    
    logger.info("Black key groups: %s", group_sizes)
    
    # Step 3: Find the best reference octave
    best_c_idx = find_best_complete_octave(white_centers, black_centers, 
                                            black_groups, white_key_width)
    
    if best_c_idx is not None:
        # Step 4a: Build from reference C using known white key pattern
        keys = _build_from_reference_c(white_centers, best_c_idx, 
                                        white_key_width, octave_offset)
    else:
        # Step 4b: Try to assign from black key pattern analysis
        logger.warning("No complete 2-3 pattern found, attempting fallback")
        keys = _build_from_black_key_pattern(white_centers, black_groups, 
                                              white_key_width, octave_offset)
    
    return keys


def _build_from_reference_c(white_centers: List[int],
                             c_idx: int,
                             white_key_width: float,
                             octave_offset: Optional[int]) -> List[KeyInfo]:
    """
    Build keyboard map using a known C position and the repeating 
    C-D-E-F-G-A-B pattern.
    """
    # Determine absolute octave
    if octave_offset is not None:
        # User specified the octave for some reference
        ref_octave = octave_offset
    else:
        # Heuristic: first visible C = C3
        # Count how many octaves the reference C is from the first C
        # (which is at index c_idx % 7, or equivalently c_idx - 7*(c_idx//7))
        octaves_from_first_c = c_idx // 7
        ref_octave = 3 + octaves_from_first_c
    
    # Assign note names to all white keys relative to the reference C
    keys = []
    for i, x in enumerate(white_centers):
        offset = i - c_idx
        note_idx = offset % 7
        octave_delta = offset // 7
        
        note_name = WHITE_NOTES[note_idx]
        octave = ref_octave + octave_delta
        
        keys.append(KeyInfo(
            center_x=int(round(x)),
            note_name=note_name,
            is_black=False,
            octave=octave,
        ))
    
    # Add black keys between appropriate white keys
    for i in range(len(keys) - 1):
        low = keys[i]
        high = keys[i + 1]
        pair = (low.note_name, high.note_name)
        
        if pair in BLACK_KEY_MAP:
            black_name = BLACK_KEY_MAP[pair]
            # Position black key between the two white keys
            bx = low.center_x + 0.42 * (high.center_x - low.center_x)
            keys.append(KeyInfo(
                center_x=int(round(bx)),
                note_name=black_name,
                is_black=True,
                octave=low.octave,
            ))
    
    # Sort by position
    keys.sort(key=lambda k: k.center_x)
    return keys


def _build_from_black_key_pattern(white_centers: List[int],
                                    black_groups: List[List[int]],
                                    white_key_width: float,
                                    octave_offset: Optional[int]) -> List[KeyInfo]:
    """
    Fallback: try to assign note names using any identifiable black key groups.
    """
    group_sizes = [len(g) for g in black_groups]
    
    # Find ANY group of 2 or 3 to use as a reference
    ref_group_idx = None
    ref_type = None  # 'cd' for group of 2 (C#/D#) or 'fga' for group of 3 (F#/G#/A#)
    
    for i, size in enumerate(group_sizes):
        if size == 3:
            ref_group_idx = i
            ref_type = 'fga'
            break
        elif size == 2 and ref_group_idx is None:
            ref_group_idx = i
            ref_type = 'cd'
    
    if ref_group_idx is None:
        logger.warning("No identifiable black key groups, using position-only estimation")
        return _estimate_keyboard(white_centers[-1] if white_centers else 1920, octave_offset)
    
    # Use the reference group to find a C
    grp = black_groups[ref_group_idx]
    
    if ref_type == 'cd':
        # Group of 2 = [C#, D#]
        # C is the white key just left of C#
        first_black = grp[0]
        c_candidates = [i for i, wc in enumerate(white_centers)
                       if wc < first_black and first_black - wc < white_key_width]
        if c_candidates:
            return _build_from_reference_c(white_centers, c_candidates[-1],
                                            white_key_width, octave_offset)
    elif ref_type == 'fga':
        # Group of 3 = [F#, G#, A#]
        # F is the white key just left of F#
        first_black = grp[0]
        f_candidates = [i for i, wc in enumerate(white_centers)
                       if wc < first_black and first_black - wc < white_key_width]
        if f_candidates:
            f_idx = f_candidates[-1]
            # C is 3 white keys to the left of F (F=3, E=2, D=1, C=0)
            c_idx = f_idx - 3
            if c_idx >= 0:
                return _build_from_reference_c(white_centers, c_idx,
                                                white_key_width, octave_offset)
            else:
                # C is off-screen, compute its would-be position
                # Still assign from f_idx knowing it's F
                return _build_from_reference_f(white_centers, f_idx,
                                                white_key_width, octave_offset)
    
    return _estimate_keyboard(white_centers[-1] if white_centers else 1920, octave_offset)


def _build_from_reference_f(white_centers: List[int],
                             f_idx: int,
                             white_key_width: float,
                             octave_offset: Optional[int]) -> List[KeyInfo]:
    """Build keyboard from a known F position."""
    # F is the 4th white key in an octave (index 3)
    # So the C for this octave would be at f_idx - 3
    virtual_c_idx = f_idx - 3
    
    # Determine octave
    ref_octave = octave_offset if octave_offset is not None else 3
    
    keys = []
    for i, x in enumerate(white_centers):
        offset = i - virtual_c_idx
        note_idx = offset % 7
        octave_delta = offset // 7
        
        note_name = WHITE_NOTES[note_idx]
        octave = ref_octave + octave_delta
        
        keys.append(KeyInfo(
            center_x=int(round(x)),
            note_name=note_name,
            is_black=False,
            octave=octave,
        ))
    
    # Add black keys
    for i in range(len(keys) - 1):
        low = keys[i]
        high = keys[i + 1]
        pair = (low.note_name, high.note_name)
        if pair in BLACK_KEY_MAP:
            black_name = BLACK_KEY_MAP[pair]
            bx = low.center_x + 0.42 * (high.center_x - low.center_x)
            keys.append(KeyInfo(
                center_x=int(round(bx)),
                note_name=black_name,
                is_black=True,
                octave=low.octave,
            ))
    
    keys.sort(key=lambda k: k.center_x)
    return keys


def _estimate_keyboard(frame_width: int,
                        octave_offset: Optional[int]) -> List[KeyInfo]:
    """
    Last-resort fallback: estimate keyboard assuming 3 octaves
    centered in the frame starting from C3.
    """
    octave = octave_offset if octave_offset is not None else 3
    num_octaves = 3
    total_white = num_octaves * 7 + 1  # 22 white keys
    white_key_width = frame_width / total_white
    
    keys = []
    for i in range(total_white):
        note_name = WHITE_NOTES[i % 7]
        oct = octave + i // 7
        x = int((i + 0.5) * white_key_width)
        keys.append(KeyInfo(center_x=x, note_name=note_name, is_black=False, octave=oct))
    
    # Add black keys
    for i in range(len(keys) - 1):
        low = keys[i]
        high = keys[i + 1]
        pair = (low.note_name, high.note_name)
        if pair in BLACK_KEY_MAP:
            bx = low.center_x + int(0.42 * (high.center_x - low.center_x))
            keys.append(KeyInfo(
                center_x=bx,
                note_name=BLACK_KEY_MAP[pair],
                is_black=True,
                octave=low.octave,
            ))
    
    keys.sort(key=lambda k: k.center_x)
    return keys


def map_x_to_key(center_x: float, keyboard_map: List[KeyInfo]) -> Optional[KeyInfo]:
    """Find the closest keyboard key for a given x position."""
    if not keyboard_map:
        return None
    
    best_key = None
    best_dist = float('inf')
    for key in keyboard_map:
        dist = abs(key.center_x - center_x)
        if dist < best_dist:
            best_dist = dist
            best_key = key
    
    return best_key


def keyboard_map_to_list(keyboard_map: List[KeyInfo]) -> List[dict]:
    """Convert keyboard map to JSON-serializable list."""
    return [k.to_dict() for k in keyboard_map]


def keyboard_map_from_list(data: List[dict]) -> List[KeyInfo]:
    """Load keyboard map from JSON data."""
    keys = []
    for d in data:
        keys.append(KeyInfo(
            center_x=d['center_x'],
            note_name=d['note_name'],
            is_black=d['is_black'],
            octave=d['octave'],
        ))
    return keys
