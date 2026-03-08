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
    
    # Step 5: Validate assignment against actual black key positions
    keys = _validate_with_black_keys(white_centers, black_centers, keys,
                                     gray, keyboard_y, keyboard_height)
    
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
        # Use the actual detected white key centers with default C assumption;
        # the downstream validation step will correct the starting note.
        return _build_from_reference_c(white_centers, 0,
                                        white_key_width, octave_offset)
    
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
    
    # Last resort: use detected positions with default C assumption
    return _build_from_reference_c(white_centers, 0,
                                    white_key_width, octave_offset)


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


# ────────────────────────────────────────────────────────────────────
#  Post-hoc validation using detected black-key positions
# ────────────────────────────────────────────────────────────────────

NO_BLACK_PAIRS = frozenset({('E', 'F'), ('B', 'C')})


def _detect_halftone_gaps_from_brightness(
    gray: np.ndarray,
    keyboard_y: int,
    keyboard_height: int,
    white_centers: List[int],
) -> Optional[List[bool]]:
    """
    Determine which white-key gaps have a black key by scanning the
    keyboard image brightness at multiple heights.

    In the region where black keys sit (roughly 50-70 % into the
    keyboard from the top), the midpoint between two white keys is
    dark if a black key is present and bright if not (E-F or B-C).

    Returns
    -------
    has_black : list of bool (one per gap), or ``None`` if the signal
        is too weak to be reliable.
    """
    n_gaps = len(white_centers) - 1
    if n_gaps < 4:
        return None

    h_img = gray.shape[0]
    best_separation = 0.0
    best_has_black: Optional[List[bool]] = None

    # Scan several heights inside the keyboard region
    for frac in (0.55, 0.60, 0.50, 0.65, 0.70, 0.45, 0.75):
        y = keyboard_y + int(keyboard_height * frac)
        if y < 0 or y >= h_img:
            continue

        y_lo = max(0, y - 4)
        y_hi = min(h_img, y + 5)
        row = np.mean(gray[y_lo:y_hi, :].astype(float), axis=0)

        mids = np.empty(n_gaps)
        for i in range(n_gaps):
            mid_x = (white_centers[i] + white_centers[i + 1]) // 2
            mid_x = max(0, min(mid_x, len(row) - 1))
            mids[i] = row[mid_x]

        # Need a bimodal split: some gaps bright, some dark.
        threshold = (np.max(mids) + np.min(mids)) / 2.0
        bright = mids > threshold
        dark = ~bright

        if bright.sum() == 0 or dark.sum() == 0:
            continue

        mean_bright = float(np.mean(mids[bright]))
        mean_dark = float(np.mean(mids[dark]))
        separation = mean_bright - mean_dark

        if separation <= best_separation:
            continue

        # Sanity: the bright (no-black-key) gaps should appear at
        # intervals of 3 or 4 (the two half-step positions inside one
        # octave are 3 and 4 white keys apart). Verify periodicity.
        bright_idxs = list(np.where(bright)[0])
        if len(bright_idxs) < 2:
            # Only one bright gap — borderline, but still useful
            # if the separation is dramatic.
            if separation > 15:
                best_separation = separation
                best_has_black = [not b for b in bright]
            continue

        # Check if the spacings between bright gaps are multiples of 7
        # (same junction type repeated), or a mix of 3/4 (alternating
        # E-F / B-C within one octave).
        spacings = np.diff(bright_idxs)
        valid = all(s % 7 == 0 or s in (3, 4) for s in spacings)
        if not valid:
            continue

        best_separation = separation
        best_has_black = [not b for b in bright]

    if best_separation < 15:
        return None

    return best_has_black


def _validate_with_black_keys(
    white_centers: List[int],
    black_centers: List[int],
    keys: List[KeyInfo],
    gray: Optional[np.ndarray] = None,
    keyboard_y: int = 0,
    keyboard_height: int = 0,
) -> List[KeyInfo]:
    """
    Validate the current note name assignment by checking each
    adjacent white-key gap against the detected black key positions.

    The piano has a fixed rule: there is NO black key between E-F and
    B-C, and there IS a black key between all other adjacent white key
    pairs.  We score all 7 possible white-key-name rotations and apply
    a correction if a different rotation matches the physical layout
    better than the current one.

    When ``black_centers`` has too few entries (standard detection
    failed), falls back to brightness-based gap analysis if a
    grayscale frame is provided.

    Returns the (possibly corrected) key list.
    """
    if len(white_centers) < 4:
        return keys

    has_black: Optional[List[bool]] = None

    if len(black_centers) >= 2:
        # ── Strategy A: use detected black-key centres ────────────
        has_black = []
        for i in range(len(white_centers) - 1):
            mid = (white_centers[i] + white_centers[i + 1]) / 2.0
            threshold = (white_centers[i + 1] - white_centers[i]) * 0.4
            found = any(abs(bc - mid) < threshold for bc in black_centers)
            has_black.append(found)

    if has_black is None or sum(has_black) < 2:
        # ── Strategy B: brightness-based gap analysis ─────────────
        if gray is not None and keyboard_height > 0:
            has_black = _detect_halftone_gaps_from_brightness(
                gray, keyboard_y, keyboard_height, white_centers)

    if has_black is None:
        return keys

    # ── Determine the current first-white-key note name ───────────
    white_keys_sorted = sorted(
        [k for k in keys if not k.is_black],
        key=lambda k: k.center_x,
    )
    if not white_keys_sorted:
        return keys
    current_offset = WHITE_NOTES.index(white_keys_sorted[0].note_name)

    # ── Score all 7 possible starting offsets ─────────────────────
    #
    # When brightness detection can only find one junction type (e.g.
    # E-F shows as bright but B-C looks dark), two offsets will tie
    # because the bright gaps match both E-F and B-C predictions
    # equally.  We break ties using WHITE KEY GAP WIDTHS: gaps at
    # half-step junctions (E-F, B-C) tend to be slightly narrower
    # because the adjacent keys meet flush (no black key between them).
    gap_widths = [white_centers[i + 1] - white_centers[i]
                  for i in range(len(white_centers) - 1)]
    median_gap = float(np.median(gap_widths)) if gap_widths else 1.0

    best_offset = current_offset
    best_score = -9999
    best_width_score = 0.0

    for offset in range(7):
        score = 0
        width_score = 0.0
        for i in range(len(has_black)):
            name_i = WHITE_NOTES[(i + offset) % 7]
            name_next = WHITE_NOTES[(i + offset + 1) % 7]
            expect_black = (name_i, name_next) not in NO_BLACK_PAIRS
            if has_black[i] == expect_black:
                score += 1
            else:
                score -= 1

            # Width tiebreaker: narrower-than-median gaps at predicted
            # half-step junctions support this offset.
            if not expect_black and i < len(gap_widths):
                # bonus if this predicted half-step gap IS narrow
                width_score += (median_gap - gap_widths[i]) / median_gap

        if (score > best_score or
                (score == best_score and width_score > best_width_score)):
            best_score = score
            best_offset = offset
            best_width_score = width_score

    shift = (best_offset - current_offset) % 7
    if shift > 3:
        shift -= 7
    if shift == 0:
        return keys

    logger.info("Black-key validation: correcting white-key shift by %+d", shift)
    return _apply_white_key_shift(keys, shift)


def _apply_white_key_shift(keys: List[KeyInfo], shift: int) -> List[KeyInfo]:
    """
    Shift all white-key names by *shift* positions in the C-D-E-F-G-A-B
    cycle, then re-derive black keys from the corrected white keys.

    Physical x-positions are preserved; only names and octaves change.
    """
    white_keys = sorted(
        [k for k in keys if not k.is_black],
        key=lambda k: k.center_x,
    )
    if not white_keys:
        return list(keys)

    new_keys: List[KeyInfo] = []
    for wk in white_keys:
        old_idx = WHITE_NOTES.index(wk.note_name)
        new_idx = (old_idx + shift) % 7
        octave_delta = (old_idx + shift) // 7
        new_keys.append(KeyInfo(
            center_x=wk.center_x,
            note_name=WHITE_NOTES[new_idx],
            is_black=False,
            octave=wk.octave + octave_delta,
        ))

    # Re-derive black keys between appropriate white-key pairs.
    for i in range(len(new_keys) - 1):
        low, high = new_keys[i], new_keys[i + 1]
        pair = (low.note_name, high.note_name)
        if pair in BLACK_KEY_MAP:
            bx = low.center_x + 0.42 * (high.center_x - low.center_x)
            new_keys.append(KeyInfo(
                center_x=int(round(bx)),
                note_name=BLACK_KEY_MAP[pair],
                is_black=True,
                octave=low.octave,
            ))

    new_keys.sort(key=lambda k: k.center_x)
    return new_keys


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
