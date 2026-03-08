"""
Detect individual note rectangles in video frames.

Finds colored rectangular regions in the note area and extracts their
positions, dimensions, and color classification.

Key features:
- Per-frame precise box coordinates (x, y, w, h)
- Splits touching same-note boxes using vertical gap analysis
- Handles notes partially off-screen (clipped at y=0 or keyboard_y)
- Color-based hand classification (left/right)
"""
import cv2
import numpy as np
from dataclasses import dataclass
from typing import List, Optional, Tuple
from .calibrator import CalibrationResult, NoteColor, create_color_mask


@dataclass
class DetectedNote:
    """A note rectangle detected in a single frame."""
    x: int  # Left edge x
    y: int  # Top edge y
    width: int  # Width in pixels
    height: int  # Height in pixels
    center_x: int  # Center x position
    center_y: int  # Center y position
    color_idx: int  # Index into CalibrationResult.note_colors
    hand: str  # 'left_hand', 'right_hand', or 'unknown'
    area: int  # Area in pixels
    mean_hsv: Tuple[int, int, int]  # Mean HSV color of the note
    mean_bgr: Tuple[int, int, int]  # Mean BGR color
    ocr_text: str = ''  # OCR'd text label (if available)
    frame_index: int = -1  # Which frame this was detected in
    timestamp: float = 0.0  # Timestamp of the frame
    is_clipped_top: bool = False  # True if note extends above screen
    is_clipped_bottom: bool = False  # True if note touches keyboard


def classify_note_color(pixel_hsv: np.ndarray, note_colors: List[NoteColor]) -> Tuple[int, str]:
    """
    Classify a note's color to determine which hand it belongs to.

    Uses color distance in HSV space with hue wrapping.

    Args:
        pixel_hsv: Mean HSV values of the note [H, S, V]
        note_colors: List of reference note colors

    Returns:
        (color_index, hand_label)
    """
    if not note_colors:
        return 0, 'unknown'

    best_idx = 0
    best_dist = float('inf')

    for i, nc in enumerate(note_colors):
        # Hue distance with wrapping
        h_diff = abs(int(pixel_hsv[0]) - nc.center_hsv[0])
        h_diff = min(h_diff, 180 - h_diff)

        s_diff = abs(int(pixel_hsv[1]) - nc.center_hsv[1])
        v_diff = abs(int(pixel_hsv[2]) - nc.center_hsv[2])

        # Weighted distance — hue matters most
        dist = h_diff * 3 + s_diff * 1 + v_diff * 0.5

        if dist < best_dist:
            best_dist = dist
            best_idx = i

    return best_idx, note_colors[best_idx].label


def _split_contour_at_gaps(raw_mask: np.ndarray,
                           x: int, y: int, w: int, h: int,
                           min_gap_rows: int = 2,
                           min_section_height: int = 8) -> List[Tuple[int, int]]:
    """
    Split a bounding box at horizontal gap lines where NO pixels match any
    note color across the ENTIRE width.

    A row is a valid gap row only if EVERY pixel across the bounding box
    width is non-note-colored in the raw (pre-morphology) mask. This
    ensures that letter text printed on notes (which only covers part of
    the width) never causes false splits, while genuine gaps between notes
    (which span the full width) are always detected.

    Uses the raw mask (before morphological operations) so that gaps
    bridged by MORPH_CLOSE are still detectable.

    Args:
        raw_mask: Full-frame raw binary mask (before morph ops)
        x, y, w, h: Bounding box of the contour
        min_gap_rows: Minimum consecutive gap rows to count as a split
        min_section_height: Minimum height for a valid note section

    Returns:
        List of (y_start, y_end) tuples for each detected note section.
        Returns [(y, y+h)] if no splits found.
    """
    mask_roi = raw_mask[y:y + h, x:x + w]
    if mask_roi.size == 0:
        return [(y, y + h)]

    # Count note-colored pixels per row in the raw mask
    row_pixel_count = np.sum(mask_roi > 0, axis=1)

    # A gap row has ZERO note-colored pixels across the entire width.
    # If ANY pixel in the row matches a note color, it is NOT a valid
    # split line — this prevents false splits at letter text.
    is_gap = row_pixel_count == 0

    # Find contiguous non-gap sections separated by real gaps
    sections = []
    current_start = None
    row_idx = 0

    while row_idx < len(is_gap):
        if not is_gap[row_idx]:
            if current_start is None:
                current_start = row_idx
            row_idx += 1
        else:
            # Count consecutive gap rows
            gap_start = row_idx
            while row_idx < len(is_gap) and is_gap[row_idx]:
                row_idx += 1
            gap_width = row_idx - gap_start

            if gap_width >= min_gap_rows and current_start is not None:
                section_height = gap_start - current_start
                if section_height >= min_section_height:
                    sections.append((y + current_start, y + gap_start))
                current_start = None

    # Handle the last section
    if current_start is not None:
        section_height = len(is_gap) - current_start
        if section_height >= min_section_height:
            sections.append((y + current_start, y + len(is_gap)))

    if len(sections) < 2:
        return [(y, y + h)]

    return sections


def _split_contour_horizontally(raw_mask: np.ndarray,
                                x: int, y: int, w: int, h: int,
                                min_gap_cols: int = 2,
                                min_section_width: int = 10) -> List[Tuple[int, int]]:
    """
    Split a bounding box at vertical gap lines where NO pixels match any
    note color across the ENTIRE height.

    Same principle as _split_contour_at_gaps but for the x-axis.
    A column is a valid gap only if EVERY pixel in that column is zero
    in the raw mask. This handles adjacent notes on neighboring keys
    (e.g., A and G#) that form a single wide contour.

    Args:
        raw_mask: Full-frame raw binary mask (before morph ops)
        x, y, w, h: Bounding box of the region
        min_gap_cols: Minimum consecutive zero-fill columns for a split
        min_section_width: Minimum width for a valid note section

    Returns:
        List of (x_start, x_end) tuples for each section.
        Returns [(x, x+w)] if no splits found.
    """
    mask_roi = raw_mask[y:y + h, x:x + w]
    if mask_roi.size == 0:
        return [(x, x + w)]

    # Count note-colored pixels per column
    col_pixel_count = np.sum(mask_roi > 0, axis=0)

    # A gap column has ZERO note-colored pixels across the entire height
    is_gap = col_pixel_count == 0

    sections = []
    current_start = None
    col_idx = 0

    while col_idx < len(is_gap):
        if not is_gap[col_idx]:
            if current_start is None:
                current_start = col_idx
            col_idx += 1
        else:
            gap_start = col_idx
            while col_idx < len(is_gap) and is_gap[col_idx]:
                col_idx += 1
            gap_width = col_idx - gap_start

            if gap_width >= min_gap_cols and current_start is not None:
                section_width = gap_start - current_start
                if section_width >= min_section_width:
                    sections.append((x + current_start, x + gap_start))
                current_start = None

    if current_start is not None:
        section_width = len(is_gap) - current_start
        if section_width >= min_section_width:
            sections.append((x + current_start, x + len(is_gap)))

    if len(sections) < 2:
        return [(x, x + w)]

    return sections


def _try_split_by_edge_detection(frame_gray: np.ndarray,
                                  x: int, y: int, w: int, h: int,
                                  expected_height: float,
                                  min_section_height: int = 12) -> List[Tuple[int, int]]:
    """
    Try to split a tall contour using horizontal edge detection.
    Used when mask-gap splitting doesn't find anything but the contour
    is suspiciously tall (>1.5x expected note height).

    Args:
        frame_gray: Grayscale frame
        x, y, w, h: Bounding box
        expected_height: Expected single-note height in pixels
        min_section_height: Minimum height for valid section

    Returns:
        List of (y_start, y_end) tuples, or [(y, y+h)] if no splits found.
    """
    if expected_height <= 0 or h < expected_height * 1.5:
        return [(y, y + h)]

    roi = frame_gray[y:y + h, x:x + w]
    if roi.size == 0:
        return [(y, y + h)]

    # Compute horizontal Sobel (detects horizontal edges = note boundaries)
    sobel_h = cv2.Sobel(roi, cv2.CV_64F, 0, 1, ksize=3)
    abs_sobel = np.abs(sobel_h)

    # Average across width to get per-row edge strength
    row_edge_strength = np.mean(abs_sobel, axis=1)

    # Smooth to avoid noise
    if len(row_edge_strength) > 5:
        kernel_size = 3
        k = np.ones(kernel_size) / kernel_size
        row_edge_strength = np.convolve(row_edge_strength, k, mode='same')

    # Find peaks in edge strength (potential note boundaries)
    threshold = np.percentile(row_edge_strength, 90)
    if threshold < 10:
        return [(y, y + h)]

    # Find local maxima above threshold near expected split positions
    peaks = []
    for rid in range(min_section_height, len(row_edge_strength) - min_section_height):
        if row_edge_strength[rid] >= threshold:
            window = row_edge_strength[max(0, rid - 3):rid + 4]
            if row_edge_strength[rid] >= np.max(window) * 0.95:
                relative_pos = rid % expected_height
                if (relative_pos < expected_height * 0.15 or
                        relative_pos > expected_height * 0.85):
                    peaks.append(rid)

    if not peaks:
        return [(y, y + h)]

    # Deduplicate peaks that are too close
    deduped = [peaks[0]]
    for p in peaks[1:]:
        if p - deduped[-1] > min_section_height:
            deduped.append(p)
    peaks = deduped

    # Build sections from peaks
    sections = []
    prev = 0
    for p in peaks:
        if p - prev >= min_section_height:
            sections.append((y + prev, y + p))
        prev = p
    if h - prev >= min_section_height:
        sections.append((y + prev, y + h))

    if len(sections) < 2:
        return [(y, y + h)]

    return sections


def _trim_box_width(combined_mask: np.ndarray,
                    x: int, y: int, w: int, h: int,
                    min_col_fill: float = 0.20) -> Tuple[int, int]:
    """
    Trim bounding box horizontally by removing edge columns with low fill.
    This removes glow/impact effects that extend the box beyond the actual note.

    When a note hits the keyboard, the glow effect adds sparse pixels
    around the note that inflate the bounding box. By checking per-column
    fill density, we can find the actual note edges.

    Args:
        combined_mask: Full-frame binary mask
        x, y, w, h: Bounding box of the region to trim
        min_col_fill: Minimum column fill ratio to keep a column

    Returns:
        (new_x, new_w) trimmed coordinates
    """
    if w <= 0 or h <= 0:
        return x, w

    mask_roi = combined_mask[y:y + h, x:x + w]
    if mask_roi.size == 0:
        return x, w

    # Compute fill ratio per column (fraction of rows with mask pixels)
    col_fill = np.sum(mask_roi > 0, axis=0).astype(float) / max(1, h)

    nonzero_fills = col_fill[col_fill > 0]
    if len(nonzero_fills) < 3:
        return x, w

    # Adaptive threshold: use 35% of the median nonzero column fill,
    # but at least min_col_fill. This adapts to different note heights.
    adaptive_thresh = max(min_col_fill, np.median(nonzero_fills) * 0.35)

    filled_cols = np.where(col_fill >= adaptive_thresh)[0]
    if len(filled_cols) < 3:
        return x, w

    new_left = int(filled_cols[0])
    new_right = int(filled_cols[-1])
    new_x = x + new_left
    new_w = new_right - new_left + 1

    return new_x, max(new_w, 1)


def _merge_overlapping_notes(notes: List['DetectedNote'],
                             overlap_threshold: float = 0.5) -> List['DetectedNote']:
    """
    Merge detected notes that significantly overlap within the same frame.
    Handles cases where the same note produces multiple detections (e.g.,
    from fragmented contours or split artifacts).

    Two notes are merged if their intersection area exceeds overlap_threshold
    of the smaller note's area, AND they are the same hand (color).

    Args:
        notes: List of detected notes
        overlap_threshold: Minimum intersection/smaller_area ratio to merge

    Returns:
        Filtered list with duplicates removed (keeps larger note)
    """
    if len(notes) <= 1:
        return notes

    # Sort by area descending (keep larger notes)
    sorted_notes = sorted(notes, key=lambda n: n.area, reverse=True)
    keep = []

    for note in sorted_notes:
        is_duplicate = False
        for kept in keep:
            # Only merge notes of the same hand
            if note.hand != kept.hand:
                continue

            # Compute intersection
            ix1 = max(note.x, kept.x)
            iy1 = max(note.y, kept.y)
            ix2 = min(note.x + note.width, kept.x + kept.width)
            iy2 = min(note.y + note.height, kept.y + kept.height)

            if ix1 < ix2 and iy1 < iy2:
                intersection = (ix2 - ix1) * (iy2 - iy1)
                smaller_area = min(note.area, kept.area)
                if smaller_area > 0 and intersection / smaller_area > overlap_threshold:
                    is_duplicate = True
                    break

        if not is_duplicate:
            keep.append(note)

    return keep


def detect_notes_in_frame(frame_bgr: np.ndarray,
                          calibration: CalibrationResult,
                          frame_index: int = -1,
                          timestamp: float = 0.0,
                          min_note_area: int = 500,
                          min_note_height: int = 10,
                          min_note_width: int = 15,
                          expected_note_height: float = 0.0) -> List[DetectedNote]:
    """
    Detect all note rectangles in a single frame.

    Includes splitting of tall contours (touching same-note boxes) via
    vertical gap analysis and edge detection.

    Args:
        frame_bgr: The frame to analyze (BGR format)
        calibration: Calibration results
        frame_index: Index of this frame
        timestamp: Timestamp of this frame
        min_note_area: Minimum area for a note contour
        min_note_height: Minimum height for a note
        min_note_width: Minimum width for a note
        expected_note_height: Expected single-note height (0 = auto)

    Returns:
        List of DetectedNote objects found in this frame
    """
    h, w = frame_bgr.shape[:2]
    hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    detected = []

    # Create combined mask for all note colors
    combined_mask = np.zeros((h, w), dtype=np.uint8)

    for nc in calibration.note_colors:
        mask = create_color_mask(frame_bgr, nc, calibration.keyboard_y)
        combined_mask = combined_mask | mask

    # Remove static elements
    if calibration.static_mask is not None:
        combined_mask = combined_mask & (~calibration.static_mask)

    # Save raw mask BEFORE morphological operations.
    # Used by _split_contour_at_gaps to detect gaps that MORPH_CLOSE
    # would bridge in the cleaned mask.
    raw_combined_mask = combined_mask.copy()

    # Morphological operations to clean up
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    combined_mask = cv2.morphologyEx(combined_mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    combined_mask = cv2.morphologyEx(combined_mask, cv2.MORPH_OPEN, kernel, iterations=1)

    # Find contours
    contours, _ = cv2.findContours(combined_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    for contour in contours:
        area = cv2.contourArea(contour)
        if area < min_note_area:
            continue

        cx_raw, cy_raw, cw, ch = cv2.boundingRect(contour)

        if ch < min_note_height or cw < min_note_width:
            continue

        # Skip if center is in keyboard area
        if cy_raw + ch // 2 > calibration.keyboard_y:
            continue

        # Try to split this contour into sub-notes using raw mask
        # (raw mask preserves gaps that MORPH_CLOSE may have bridged)
        # 1) Vertical splits (horizontal gap rows)
        y_sections = _split_contour_at_gaps(raw_combined_mask, cx_raw, cy_raw, cw, ch)

        # 2) For each y-section, also try horizontal splits (vertical gap cols)
        #    This separates adjacent notes on neighboring keys (e.g., A and G#)
        sub_boxes = []
        for (sy_start, sy_end) in y_sections:
            sub_h = sy_end - sy_start
            x_sections = _split_contour_horizontally(
                raw_combined_mask, cx_raw, sy_start, cw, sub_h
            )
            for (sx_start, sx_end) in x_sections:
                sub_boxes.append((sx_start, sy_start, sx_end - sx_start, sub_h))

        # Create a DetectedNote for each sub-box
        for (sx, sy_start, sw, sub_h) in sub_boxes:
            sy_end = sy_start + sub_h
            if sub_h < min_note_height or sw < min_note_width:
                continue

            # Trim box width to remove glow/impact effects
            trimmed_x, trimmed_w = _trim_box_width(
                combined_mask, sx, sy_start, sw, sub_h
            )
            if trimmed_w < min_note_width:
                continue

            sub_area = trimmed_w * sub_h
            if sub_area < min_note_area:
                continue

            # Skip if center is in keyboard area
            sub_cy = (sy_start + sy_end) // 2
            if sub_cy > calibration.keyboard_y:
                continue

            # Get mean color of this sub-box region (using trimmed x/w)
            sub_mask = np.zeros((h, w), dtype=np.uint8)
            sub_mask[sy_start:sy_end, trimmed_x:trimmed_x + trimmed_w] = \
                combined_mask[sy_start:sy_end, trimmed_x:trimmed_x + trimmed_w]

            pixel_count = np.sum(sub_mask > 0)
            if pixel_count < min_note_area * 0.3:
                continue

            mean_hsv_val = cv2.mean(hsv, mask=sub_mask)[:3]
            mean_bgr_val = cv2.mean(frame_bgr, mask=sub_mask)[:3]

            # Classify color
            color_idx, hand = classify_note_color(
                np.array(mean_hsv_val),
                calibration.note_colors
            )

            # Detect clipping
            is_clipped_top = sy_start <= 2
            is_clipped_bottom = sy_end >= calibration.keyboard_y - 5

            # Use trimmed center_x for key mapping (each sub-box has its own x)
            note_center_x = trimmed_x + trimmed_w // 2

            note = DetectedNote(
                x=trimmed_x, y=sy_start, width=trimmed_w, height=sub_h,
                center_x=note_center_x,
                center_y=sub_cy,
                color_idx=color_idx,
                hand=hand,
                area=sub_area,
                mean_hsv=tuple(int(v) for v in mean_hsv_val),
                mean_bgr=tuple(int(v) for v in mean_bgr_val),
                frame_index=frame_index,
                timestamp=timestamp,
                is_clipped_top=is_clipped_top,
                is_clipped_bottom=is_clipped_bottom,
            )
            detected.append(note)

    # Remove overlapping duplicate detections
    detected = _merge_overlapping_notes(detected)

    # Sort by x position (left to right, like piano keys)
    detected.sort(key=lambda n: n.center_x)

    return detected


def detect_notes_batch(frames_data: List[Tuple[float, np.ndarray]],
                       calibration: CalibrationResult,
                       start_index: int = 0) -> List[List[DetectedNote]]:
    """
    Detect notes across multiple frames.

    Args:
        frames_data: List of (timestamp, frame_bgr) tuples
        calibration: Calibration results
        start_index: Starting frame index for numbering

    Returns:
        List of lists — notes detected per frame
    """
    all_detections = []

    for i, (ts, frame) in enumerate(frames_data):
        notes = detect_notes_in_frame(
            frame, calibration,
            frame_index=start_index + i,
            timestamp=ts
        )
        all_detections.append(notes)

    return all_detections
