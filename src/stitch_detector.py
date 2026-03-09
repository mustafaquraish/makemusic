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
    center_density: float = 0.0  # density of center 1/3 columns (black keys)
    mean_saturation: float = 0.0  # mean HSV S of mask-positive pixels


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


def _split_runs_at_valleys(
    column_mask: np.ndarray,
    runs: List[Tuple[int, int]],
    valley_ratio: float = 0.50,
    max_valley_fill: float = 0.45,
    min_valley_width: int = 30,
    min_peak_fill: float = 0.80,
    min_valley_floor: float = 0.10,
    min_run_height: int = 8,
    min_sub_run: int = 30,
) -> List[Tuple[int, int]]:
    """Split runs where the fill profile shows deep *bleed* valleys.

    Prevents merging of separate notes when bleed from an adjacent key
    keeps the row fill just above *fill_threshold* across note
    boundaries.

    A valley is a contiguous band of ≥ *min_valley_width* rows where
    row fill is below the valley threshold (the lower of
    *valley_ratio* × peak_fill and *max_valley_fill*).

    Bleed valleys are distinguished from visual artifact valleys (text
    overlays, frame-stitching boundaries, etc.) by two criteria:

    * The run's 90th-percentile fill must be ≥ *min_peak_fill*.
      Sparse black-key notes with lower peak fill are skipped entirely.
    * Every row in the valley must have fill ≥ *min_valley_floor*.
      Bleed valleys have consistently moderate fill (all rows ~ 0.2-0.4)
      whereas artifact valleys contain zero-fill rows intermixed with
      higher-fill rows.
    """
    if not runs:
        return runs

    col_width = column_mask.shape[1] if column_mask.ndim == 2 else 1
    if col_width == 0:
        return runs

    refined: List[Tuple[int, int]] = []
    for y_start, y_end in runs:
        note_h = y_end - y_start
        if note_h < 3 * min_run_height:
            refined.append((y_start, y_end))
            continue

        strip = column_mask[y_start:y_end, :]
        if strip.ndim == 2:
            row_fill = np.mean(strip > 0, axis=1)
        else:
            row_fill = (strip > 0).astype(float)

        peak_fill = float(np.percentile(row_fill, 90))
        if peak_fill < 0.01:
            continue  # empty run

        # Skip sparse notes (black keys with inherently low fill)
        if peak_fill < min_peak_fill:
            refined.append((y_start, y_end))
            continue

        # Valley threshold: lower of relative and absolute
        valley_threshold = min(peak_fill * valley_ratio, max_valley_fill)
        is_peak = row_fill >= valley_threshold

        # Edge-detect to find sub-runs above the valley threshold
        padded = np.empty(len(is_peak) + 2, dtype=np.bool_)
        padded[0] = False
        padded[-1] = False
        padded[1:-1] = is_peak
        edges = np.diff(padded.view(np.uint8).astype(np.int8))
        sub_starts = np.where(edges == 1)[0]
        sub_ends = np.where(edges == -1)[0]

        if len(sub_starts) <= 1:
            # Single sub-run — check if leading/trailing bleed should
            # be trimmed.  If the sub-run is much smaller than the
            # whole run and both the leading and trailing margins are
            # mostly bleed (fill < valley_threshold), trim to the
            # sub-run so adjacent-key bleed doesn't inflate the note.
            if len(sub_starts) == 1:
                sr_s, sr_e = int(sub_starts[0]), int(sub_ends[0])
                sr_h = sr_e - sr_s
                lead = sr_s            # rows before sub-run
                trail = note_h - sr_e  # rows after sub-run
                # Trim if the sub-run occupies ≤ 70% of the run AND
                # leading or trailing bleed margin ≥ min_valley_width.
                if (sr_h <= note_h * 0.70
                        and sr_h >= min_sub_run
                        and (lead >= min_valley_width
                             or trail >= min_valley_width)):
                    refined.append((y_start + sr_s, y_start + sr_e))
                    continue
            refined.append((y_start, y_end))
            continue

        # Check each inter-sub-run gap.  Only split at gaps that are:
        #   1. Wide enough  (≥ min_valley_width)
        #   2. Consistently filled — bleed valleys have MOST rows at
        #      moderate fill (≥ min_valley_floor), whereas artifact
        #      valleys contain mostly zero-fill rows with only a few
        #      higher-fill rows sprinkled in.  We require ≥ 80% of
        #      valley rows to be above the floor.
        min_valley_frac = 0.90
        split_at: List[bool] = []
        for gi in range(len(sub_starts) - 1):
            gap_start = sub_ends[gi]
            gap_end = sub_starts[gi + 1]
            gap_width = gap_end - gap_start
            if gap_width < min_valley_width:
                split_at.append(False)
                continue
            valley_fills = row_fill[gap_start:gap_end]
            frac_above = float(np.mean(valley_fills >= min_valley_floor))
            if frac_above < min_valley_frac:
                split_at.append(False)  # artifact valley (mostly zero rows)
                continue
            split_at.append(True)

        if not any(split_at):
            refined.append((y_start, y_end))
            continue

        # Build merged segments: join sub-runs across non-split gaps
        segments: List[Tuple[int, int]] = []
        seg_start = int(sub_starts[0])
        for gi, do_split in enumerate(split_at):
            if do_split:
                seg_end = int(sub_ends[gi])
                if seg_end - seg_start >= min_sub_run:
                    segments.append((y_start + seg_start, y_start + seg_end))
                seg_start = int(sub_starts[gi + 1])
        # Last segment
        seg_end = int(sub_ends[-1])
        if seg_end - seg_start >= min_sub_run:
            segments.append((y_start + seg_start, y_start + seg_end))

        # Fallback: if splitting produces no viable segments, keep
        # the original run so we don't lose the note entirely.
        if segments:
            refined.extend(segments)
        else:
            refined.append((y_start, y_end))

    return refined


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
    min_black_density: float = 0.30,
    phantom_density_cap: float = 0.70,
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
         *min_black_density* (default 0.30) removes the worst phantoms
         while preserving genuine notes as low as ~0.33 density.

      3. **Adjacency phantom check** — a black-key detection with
         density < *phantom_density_cap* (default 0.70) is discarded
         if **both** of its adjacent white keys have detected notes
         with overlapping Y ranges.  Additionally, if **at least one**
         adjacent white key has overlapping notes, relative saturation
         is used to distinguish genuine notes from edge bleed — bleed
         phantoms have low relative saturation and are discarded.
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
    # Keep saturation channel for black-key bleed discrimination
    sat_channel = hsv[:, :, 1].copy()
    del hsv  # free ~360 MB (saturation copy is ~1/3 that)

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

            # Split runs that have deep fill-profile valleys
            # (prevents merging adjacent notes via low-level bleed)
            runs = _split_runs_at_valleys(
                raw_strip, runs,
                min_run_height=min_note_height,
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

                # Compute center density for black keys (middle 1/3)
                c_density = 0.0
                m_sat = 0.0
                if is_black and col_w >= 3:
                    c_lo = col_w // 3
                    c_hi = col_w - c_lo
                    center_strip = box_mask[:, c_lo:c_hi]
                    c_area = (c_hi - c_lo) * note_h
                    c_px = int(np.sum(center_strip > 0))
                    c_density = c_px / c_area if c_area > 0 else 0.0

                    # Mean saturation of mask-positive pixels
                    sat_strip = sat_channel[y_start:y_end,
                                            col_start:col_end]
                    sat_vals = sat_strip[box_mask > 0]
                    if len(sat_vals) > 0:
                        m_sat = float(np.mean(sat_vals))

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
                    center_density=c_density,
                    mean_saturation=m_sat,
                ))

    del sat_channel  # free saturation channel

    # ── Boundary artifact filter ──────────────────────────────────
    #    Remove tiny notes right at the keyboard boundary — these are
    #    usually keyboard-region colour bleeding into the note area.
    boundary_buffer = 20
    short_boundary = 20
    all_notes = [n for n in all_notes
                 if not (n.y + n.height > note_area_bottom - boundary_buffer
                         and n.height < short_boundary)]

    # ── Banner / overlay artifact filter ──────────────────────────
    #    When a video overlay (title card, banner, etc.) is present,
    #    every key column detects a note at the same Y position.
    #    Remove any group of notes that start at the same Y position
    #    (within tolerance) and span too many distinct keys.
    _BANNER_KEY_THRESHOLD = 15  # more than this many keys → banner
    _BANNER_Y_TOL = 5          # Y tolerance for grouping

    if all_notes:
        # Sort notes by y for efficient grouping
        y_sorted = sorted(all_notes, key=lambda n: n.y)
        banner_indices: set[int] = set()
        i0 = 0
        while i0 < len(y_sorted):
            y_ref = y_sorted[i0].y
            i1 = i0 + 1
            while i1 < len(y_sorted) and y_sorted[i1].y <= y_ref + _BANNER_Y_TOL:
                i1 += 1
            group_size = i1 - i0
            if group_size > _BANNER_KEY_THRESHOLD:
                for j in range(i0, i1):
                    banner_indices.add(id(y_sorted[j]))
            i0 = i1
        if banner_indices:
            all_notes = [n for n in all_notes if id(n) not in banner_indices]

    # ── Adjacency phantom check for black keys ────────────────────
    #    Discard a black-key note if its density is below
    #    phantom_density_cap AND both of its adjacent white keys have
    #    detected notes with overlapping Y ranges (same hand).
    #
    #    Single-adjacent phantom check uses *relative saturation* to
    #    distinguish genuine notes from edge bleed.  Genuine notes on
    #    black keys have vivid, highly saturated pixels (relative_sat
    #    near 1.0), while bleed from adjacent white keys produces
    #    washed-out pixels with moderate saturation (relative_sat
    #    around 0.5–0.65).  A relative_sat threshold of 0.75 cleanly
    #    separates them.
    RELATIVE_SAT_GENUINE = 0.80

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

    # Pre-compute per-color s_range for relative saturation
    s_ranges = [(float(nc.s_range[0]), float(nc.s_range[1]))
                for nc in calibration.note_colors]

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

        # Single-adjacent phantom: use relative saturation to decide.
        # Genuine notes have vivid pixels (high relative saturation).
        # Bleed phantoms have washed-out edge pixels (low relative sat).
        if has_left_overlap or has_right_overlap:
            s_lo, s_hi = s_ranges[n.color_idx]
            s_span = s_hi - s_lo
            if s_span > 0:
                relative_sat = (n.mean_saturation - s_lo) / s_span
            else:
                relative_sat = 0.0
            if relative_sat < RELATIVE_SAT_GENUINE:
                continue  # phantom — washed-out edge bleed

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
