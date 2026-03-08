"""
Detect note rectangles on a stitched piano-roll image.

Instead of the per-frame contour approach (which requires tracking and
is vulnerable to merging adjacent keys), this module scans *per-key
columns* through the stitched image.

Algorithm
─────────
1.  Build a colour mask for each hand (same HSV ranges as calibrator).
2.  Determine each key's X-range from the keyboard map.
3.  For every (key, colour), sweep vertically through the column strip
    and find contiguous runs of "on" pixels  →  one run = one note.
4.  Return a flat list of detected note boxes.

This approach inherently solves two hard problems:
  • C / C# overlap – each key is scanned independently so slight pixel
    overlap between adjacent keys is irrelevant.
  • Thin sharp/flat splitting – text printed on a narrow note never
    causes a false split because we don't rely on zero-fill gaps to
    separate horizontally-adjacent keys.
"""

from __future__ import annotations

import cv2
import numpy as np
from dataclasses import dataclass, field
from typing import List, Tuple, Optional

from .calibrator import CalibrationResult, NoteColor


# ────────────────────────────────────────────────────────────────────
#  Data structures
# ────────────────────────────────────────────────────────────────────

@dataclass
class StitchedNote:
    """A note detected on the stitched image."""
    key_name: str          # e.g. 'C4',  'F#5'
    is_black: bool
    hand: str              # 'left_hand' | 'right_hand' | 'unknown'
    x: int                 # left edge (px)
    y: int                 # top edge  (px, 0 = top of stitched image)
    width: int
    height: int
    color_idx: int         # index into CalibrationResult.note_colors
    pixel_count: int = 0   # number of mask-positive pixels inside the box


# ────────────────────────────────────────────────────────────────────
#  Colour mask helpers
# ────────────────────────────────────────────────────────────────────

def _build_color_mask(hsv: np.ndarray,
                      nc: NoteColor,
                      note_area_bottom: int,
                      v_low_override: int | None = None) -> np.ndarray:
    """Create a binary mask for pixels matching *nc* above *note_area_bottom*.

    *hsv* must be the pre-converted HSV image (cv2.COLOR_BGR2HSV).
    If *v_low_override* is given, use that as the lower V bound instead
    of nc.v_range[0].  This is used to build a more permissive mask for
    black-key columns where note brightness can be lower.
    """
    h_lo, h_hi = nc.h_range
    v_lo = v_low_override if v_low_override is not None else nc.v_range[0]
    lower = np.array([h_lo, nc.s_range[0], v_lo])
    upper = np.array([h_hi, nc.s_range[1], nc.v_range[1]])

    if h_lo > h_hi:                       # hue wraps around 180
        m1 = cv2.inRange(hsv,
                         np.array([h_lo, nc.s_range[0], v_lo]),
                         np.array([180, nc.s_range[1], nc.v_range[1]]))
        m2 = cv2.inRange(hsv,
                         np.array([0, nc.s_range[0], v_lo]),
                         np.array([h_hi, nc.s_range[1], nc.v_range[1]]))
        mask = m1 | m2
    else:
        mask = cv2.inRange(hsv, lower, upper)

    # zero out keyboard region
    mask[note_area_bottom:, :] = 0
    return mask


# ────────────────────────────────────────────────────────────────────
#  Per-key vertical scanning
# ────────────────────────────────────────────────────────────────────

def _find_vertical_runs(column_mask: np.ndarray,
                        fill_threshold: float,
                        min_height: int,
                        min_gap: int) -> List[Tuple[int, int]]:
    """
    Find contiguous vertical "on" runs in a (H, W) column mask.

    A row is "on" when at least *fill_threshold* fraction of its
    columns are white.

    Returns list of (y_start, y_end) tuples (end is exclusive).
    """
    if column_mask.size == 0:
        return []

    col_width = column_mask.shape[1] if column_mask.ndim == 2 else 1
    if col_width == 0:
        return []

    # row-wise fill: fraction of columns that are nonzero
    if column_mask.ndim == 2:
        row_fill = np.mean(column_mask > 0, axis=1)
    else:
        row_fill = (column_mask > 0).astype(float)

    is_on = row_fill >= fill_threshold

    # Bridge small gaps using numpy edge detection
    if min_gap > 0:
        padded = np.empty(len(is_on) + 2, dtype=np.bool_)
        padded[0] = False
        padded[-1] = False
        padded[1:-1] = is_on
        edges = np.diff(padded.view(np.uint8).astype(np.int8))
        starts = np.where(edges == 1)[0]
        ends = np.where(edges == -1)[0]

        if len(starts) > 1:
            gaps = starts[1:] - ends[:-1]
            for i in np.where(gaps <= min_gap)[0]:
                is_on[ends[i]:starts[i + 1]] = True

    # Extract runs using vectorized edge detection
    padded = np.empty(len(is_on) + 2, dtype=np.bool_)
    padded[0] = False
    padded[-1] = False
    padded[1:-1] = is_on
    edges = np.diff(padded.view(np.uint8).astype(np.int8))
    starts = np.where(edges == 1)[0]
    ends = np.where(edges == -1)[0]

    # Filter by minimum height
    lengths = ends - starts
    valid = lengths >= min_height

    return [(int(s), int(e)) for s, e in zip(starts[valid], ends[valid])]


# ────────────────────────────────────────────────────────────────────
#  Key range helpers
# ────────────────────────────────────────────────────────────────────

def _compute_key_x_ranges(
    keyboard_map: list,
    frame_width: int,
) -> List[Tuple[str, bool, int, int]]:
    """
    Determine the (x_left, x_right) pixel range for every key.

    Returns list of (key_full_name, is_black, x_left, x_right).
    """
    if not keyboard_map:
        return []

    # Compute white key width from the map
    white_centers = sorted(k.center_x for k in keyboard_map if not k.is_black)
    if len(white_centers) >= 2:
        spacings = np.diff(white_centers)
        white_key_w = float(np.median(spacings))
    else:
        white_key_w = frame_width / 52.0

    black_key_w = white_key_w * 0.58      # typical ratio

    result = []
    for k in keyboard_map:
        half = (black_key_w if k.is_black else white_key_w) / 2.0
        xl = max(0, int(round(k.center_x - half)))
        xr = min(frame_width, int(round(k.center_x + half)))
        result.append((k.full_name, k.is_black, xl, xr))

    return result


def _build_column_ownership(
    keyboard_map: list,
    frame_width: int,
) -> np.ndarray:
    """
    For every pixel column, assign it to the key whose *centre* is closest.

    Returns:
        int32 array of shape (frame_width,) where value = index into
        keyboard_map, or -1 for unassigned columns.
    """
    if not keyboard_map:
        return np.full(frame_width, -1, dtype=np.int32)

    centers = np.array([k.center_x for k in keyboard_map], dtype=np.float64)
    cols = np.arange(frame_width, dtype=np.float64)
    dists = np.abs(cols[:, None] - centers[None, :])
    ownership = np.argmin(dists, axis=1).astype(np.int32)
    return ownership


# ────────────────────────────────────────────────────────────────────
#  Main entry point
# ────────────────────────────────────────────────────────────────────

def detect_notes_on_stitched_image(
    image_bgr: np.ndarray,
    calibration: CalibrationResult,
    keyboard_map: list,
    *,
    fill_threshold: float = 0.15,
    min_note_height: int = 8,
    min_gap_bridge: int = 15,
    min_pixel_count: int = 50,
    min_white_density: float = 0.40,
    min_black_density: float = 0.45,
    phantom_density_cap: float = 0.65,
) -> List[StitchedNote]:
    """
    Detect all note rectangles in a stitched piano-roll image.

    Uses a **single-pass** approach where every key (black and white)
    is scanned using its nearest-centre *owned columns*.  Column
    ownership is non-overlapping, so no two keys see the same pixel.

    Phantom detections (caused by adjacent note pixels spilling into a
    neighbouring key's column zone) are eliminated with three filters:

      1. **White-key density filter** — phantom white-key detections
         from black-key note spill have density 0.19–0.29; real white
         notes are ≥ 0.79.  Threshold *min_white_density* (default 0.40)
         removes them.

      2. **Black-key density filter** — initial threshold
         *min_black_density* (default 0.45) removes the worst phantoms
         while preserving genuine notes as low as ~0.47 density.

      3. **Adjacency phantom check** — a black-key detection with
         density < *phantom_density_cap* (default 0.65) is discarded
         if **both** of its adjacent white keys have detected notes
         with overlapping Y ranges.  Additionally, if density < 0.60
         and **at least one** adjacent white key has overlapping notes,
         the detection is also discarded (single-adjacent phantom).
         This catches phantoms caused by white-key notes whose edges
         spill into the black key's column zone.

    Returns:
        Sorted list of StitchedNote (by y-position, then x).
    """
    img_h, img_w = image_bgr.shape[:2]
    note_area_bottom = img_h - calibration.keyboard_height

    # 1.  Key X ranges (only used for initial bounds)
    key_ranges = _compute_key_x_ranges(keyboard_map, img_w)
    if not key_ranges:
        return []

    # 1b. Column-ownership map (nearest-centre, non-overlapping)
    col_owner = _build_column_ownership(keyboard_map, img_w)

    # 2.  Per-colour masks (one per NoteColor)
    #     Convert BGR→HSV once (saves ~3 redundant conversions on
    #     a ~360 MB image).
    #     Standard masks use the calibrated V range.
    #     Extended masks lower V_LOW by ~30% for black-key columns
    #     where note brightness is inherently lower.
    hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)
    colour_masks: List[np.ndarray] = []
    colour_masks_bk: List[np.ndarray] = []   # extended V for black keys
    for nc in calibration.note_colors:
        colour_masks.append(_build_color_mask(hsv, nc, note_area_bottom))
        v_lo_ext = max(50, int(nc.v_range[0] * 0.65))
        colour_masks_bk.append(
            _build_color_mask(hsv, nc, note_area_bottom,
                              v_low_override=v_lo_ext))
    del hsv  # free ~360 MB

    # Light morphology to remove single-pixel noise
    # Standard masks (white keys): 3×3 opening
    # Extended masks (black keys): 1×3 vertical opening only, to preserve
    # sparse pixels at the edges of dimmer black-key notes
    open_kern = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    open_kern_v = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 3))
    for i in range(len(colour_masks)):
        colour_masks[i] = cv2.morphologyEx(
            colour_masks[i], cv2.MORPH_OPEN, open_kern, iterations=1)
        colour_masks_bk[i] = cv2.morphologyEx(
            colour_masks_bk[i], cv2.MORPH_OPEN, open_kern_v, iterations=1)

    # ── Build adjacency map: black-key index → (left white, right white) ──
    #    Maps each black-key key_ranges index to the indices of the two
    #    adjacent white keys (if they exist).
    black_adj: dict[int, tuple[int, int]] = {}
    for ki, (kn, is_black, xl, xr) in enumerate(key_ranges):
        if not is_black:
            continue
        left_white = right_white = -1
        # Search left for nearest white key
        for j in range(ki - 1, -1, -1):
            if not key_ranges[j][1]:  # is_black == False
                left_white = j
                break
        # Search right for nearest white key
        for j in range(ki + 1, len(key_ranges)):
            if not key_ranges[j][1]:
                right_white = j
                break
        black_adj[ki] = (left_white, right_white)

    # ── Single pass: ALL keys via owned columns ───────────────────
    all_notes: List[StitchedNote] = []

    for ki, (key_name, is_black, xl, xr) in enumerate(key_ranges):
        owned_cols = np.where(col_owner[xl:xr] == ki)[0]
        if len(owned_cols) < 2:
            continue

        col_start = xl + int(owned_cols[0])
        col_end = xl + int(owned_cols[-1]) + 1
        col_w = col_end - col_start

        for ci, nc in enumerate(calibration.note_colors):
            # Black keys use the extended-V mask for better sensitivity
            masks = colour_masks_bk if is_black else colour_masks
            raw_strip = masks[ci][0:note_area_bottom, col_start:col_end].copy()

            # Zero non-owned columns within the strip
            for local_col in range(raw_strip.shape[1]):
                abs_col = col_start + local_col
                if col_owner[abs_col] != ki:
                    raw_strip[:, local_col] = 0

            runs = _find_vertical_runs(
                raw_strip,
                fill_threshold=fill_threshold,
                min_height=min_note_height,
                min_gap=min_gap_bridge,
            )

            for y_start, y_end in runs:
                box_mask = raw_strip[y_start:y_end, :]
                px_count = int(np.sum(box_mask > 0))
                if px_count < min_pixel_count:
                    continue

                note_h = y_end - y_start
                area = col_w * note_h
                density = px_count / area if area > 0 else 0.0

                # Density filters (white and black)
                if is_black and density < min_black_density:
                    continue
                if not is_black and density < min_white_density:
                    continue

                all_notes.append(StitchedNote(
                    key_name=key_name,
                    is_black=is_black,
                    hand=nc.label,
                    x=col_start,
                    y=y_start,
                    width=col_w,
                    height=note_h,
                    color_idx=ci,
                    pixel_count=px_count,
                ))

    # ── Adjacency phantom check for black keys ────────────────────
    #    Discard a black-key note if its density is below
    #    phantom_density_cap AND both of its adjacent white keys have
    #    detected notes with overlapping Y ranges (same hand).
    #    This targets phantoms created when two white-key note edges
    #    both spill into the black key's column zone (e.g. D4+E4
    #    spilling into D#4).
    def _y_overlap(n1: StitchedNote, n2: StitchedNote) -> float:
        """Fraction of the shorter note's height that overlaps."""
        ys = max(n1.y, n2.y)
        ye = min(n1.y + n1.height, n2.y + n2.height)
        if ye <= ys:
            return 0.0
        return (ye - ys) / min(n1.height, n2.height)

    # Index detected notes by their key_ranges index for fast lookup
    notes_by_ki: dict[int, list[StitchedNote]] = {}
    for n in all_notes:
        # Find the key_ranges index for this note
        for ki2, (kn2, _, xl2, xr2) in enumerate(key_ranges):
            if kn2 == n.key_name:
                notes_by_ki.setdefault(ki2, []).append(n)
                break

    filtered: List[StitchedNote] = []
    for n in all_notes:
        if not n.is_black:
            filtered.append(n)
            continue

        area = n.width * n.height
        density = n.pixel_count / area if area > 0 else 0.0
        if density >= phantom_density_cap:
            # High-density black-key note — always keep
            filtered.append(n)
            continue

        # Find this note's key_ranges index
        ki_self = -1
        for ki2, (kn2, _, _, _) in enumerate(key_ranges):
            if kn2 == n.key_name:
                ki_self = ki2
                break

        if ki_self < 0 or ki_self not in black_adj:
            filtered.append(n)
            continue

        lw, rw = black_adj[ki_self]
        has_left_overlap = False
        has_right_overlap = False

        if lw >= 0:
            for wn in notes_by_ki.get(lw, []):
                if wn.hand == n.hand and _y_overlap(n, wn) > 0.3:
                    has_left_overlap = True
                    break

        if rw >= 0:
            for wn in notes_by_ki.get(rw, []):
                if wn.hand == n.hand and _y_overlap(n, wn) > 0.3:
                    has_right_overlap = True
                    break

        if has_left_overlap and has_right_overlap:
            # Phantom — both adjacent white keys have overlapping notes
            continue

        # Single-adjacent phantom: lower density + strong overlap on
        # one side (common for LH bass notes that spill one direction)
        if (has_left_overlap or has_right_overlap) and density < 0.60:
            continue

        filtered.append(n)

    # ── De-duplicate, sort ────────────────────────────────────────
    filtered = _deduplicate_notes(filtered)
    filtered.sort(key=lambda n: (n.y, n.x))
    return filtered


# ────────────────────────────────────────────────────────────────────
#  De-duplication
# ────────────────────────────────────────────────────────────────────

def _deduplicate_notes(notes: List[StitchedNote]) -> List[StitchedNote]:
    """
    Remove duplicate detections that arise when a note's pixels bleed
    into an adjacent key's column (glow, spill, etc.).

    Two notes are duplicates when:
      1. Same hand (colour channel)
      2. Their X ranges overlap (adjacent / overlapping keys)
      3. Significant Y overlap (>50 % of the shorter note)
      4. The weaker note has < 60 % of the stronger note's pixels
    """
    if len(notes) <= 1:
        return notes

    # Sort by pixel_count descending (keep the stronger detection)
    sorted_notes = sorted(notes, key=lambda n: n.pixel_count, reverse=True)
    keep: list[StitchedNote] = []

    for note in sorted_notes:
        is_dup = False
        for kept in keep:
            if note.hand != kept.hand:
                continue
            # Check X overlap (must be on adjacent / overlapping keys)
            x_overlap_start = max(note.x, kept.x)
            x_overlap_end = min(note.x + note.width, kept.x + kept.width)
            if x_overlap_end <= x_overlap_start:
                continue
            # Check Y overlap
            y_overlap_start = max(note.y, kept.y)
            y_overlap_end = min(note.y + note.height, kept.y + kept.height)
            if y_overlap_end <= y_overlap_start:
                continue
            y_overlap = y_overlap_end - y_overlap_start
            smaller_h = min(note.height, kept.height)
            if smaller_h > 0 and y_overlap / smaller_h > 0.5:
                # Significant Y overlap — check if the weaker one has
                # far fewer pixels (bleed artefact)
                if note.pixel_count < kept.pixel_count * 0.6:
                    is_dup = True
                    break

        if not is_dup:
            keep.append(note)

    return keep


# ────────────────────────────────────────────────────────────────────
#  High-level helper — stitch + detect in one call
# ────────────────────────────────────────────────────────────────────

def y_to_time(y: int, note_area_bottom: int,
              scroll_speed: float, intro_end_time: float) -> float:
    """
    Convert a Y coordinate on the stitched image to a playback time.

    The stitched image is laid out with the keyboard at the bottom and
    notes stacked above it.  Notes closer to the keyboard play earlier.
    """
    distance_from_keyboard = note_area_bottom - y
    return intro_end_time + distance_from_keyboard / scroll_speed
