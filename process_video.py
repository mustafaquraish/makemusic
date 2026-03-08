#!/usr/bin/env python3
"""
Process a falling-notes piano video into an interactive HTML viewer.

Usage:
    python process_video.py music/perfect/video.webm

    # With optional outputs:
    python process_video.py music/perfect/video.webm --stitched --boxes --json

Output goes to a folder next to the video (e.g. music/perfect/output/).
Override with -o OUTPUT_FOLDER.
"""

import os
import sys
import json
import time
import argparse
from pathlib import Path

import cv2
import numpy as np

# Allow running from project root
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from stitch_song import stitch_song, StitchResult, y_to_time


# ── Note name → 88-key index (A0=0, C8=87) ───────────────────────

_NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

def note_name_to_key_index(name: str) -> int:
    """Convert 'C4', 'A#3', 'G5' etc. to 88-key piano index (A0=0)."""
    # Parse note and octave
    if len(name) >= 2 and name[-1].isdigit():
        octave = int(name[-1])
        pitch = name[:-1]
    else:
        raise ValueError(f"Cannot parse note name: {name}")

    if pitch not in _NOTE_NAMES:
        raise ValueError(f"Unknown pitch: {pitch}")

    # MIDI note number: C4 = 60
    pitch_idx = _NOTE_NAMES.index(pitch)
    midi = (octave + 1) * 12 + pitch_idx  # C-1 = 0 in MIDI

    # 88-key index: A0 = MIDI 21
    return midi - 21


def build_notes_data(labelled_boxes, cal, note_area_bottom) -> dict:
    """Convert labelled bounding boxes into the EMBEDDED_NOTES_DATA format.

    Each box is (x1, y1, x2, y2, label, hand) where label is "KeyName Ts".
    Uses box coordinates directly for timing (bottom of box = start_time,
    height = duration).
    """
    notes = []
    # Sort by y descending (bottom of image = earliest time)
    sorted_boxes = sorted(labelled_boxes, key=lambda b: b[1], reverse=True)

    for i, (x1, y1, x2, y2, label, hand) in enumerate(sorted_boxes):
        # Parse key name from label ("G4 21.3s" → "G4")
        parts = label.split()
        key_name = parts[0] if parts else '?'

        try:
            key_idx = note_name_to_key_index(key_name)
        except ValueError:
            continue  # skip unparseable keys

        # Use the BOTTOM of the box (higher y = earlier time in bottom-up layout)
        # y2 = bottom of the note shape in image coords
        # start_time = when the note first appears (bottom edge)
        y2c = min(y2, note_area_bottom)
        start_time = y_to_time(y2c, note_area_bottom,
                               cal.scroll_speed, cal.intro_end_time)
        duration = (y2c - y1) / cal.scroll_speed

        if duration < 0.02:  # skip negligibly short fragments
            continue

        # Get the note color from hand assignment
        if hand == 'right_hand' and len(cal.note_colors) > 0:
            nc = cal.note_colors[0]
            color_rgb = [int(x) for x in reversed(nc.center_bgr)]
        elif hand == 'left_hand' and len(cal.note_colors) > 1:
            nc = cal.note_colors[1]
            color_rgb = [int(x) for x in reversed(nc.center_bgr)]
        else:
            color_rgb = [200, 200, 200]

        notes.append({
            'id': i + 1,
            'note_name': key_name,
            'start_time': round(start_time, 4),
            'duration': round(duration, 4),
            'hand': hand,
            'key_index': key_idx,
            'center_x': round((x1 + x2) / 2, 1),
            'color_rgb': color_rgb,
        })

    # Re-number IDs sequentially
    for i, n in enumerate(notes):
        n['id'] = i + 1

    # Build summary
    rh = sum(1 for n in notes if n['hand'] == 'right_hand')
    lh = sum(1 for n in notes if n['hand'] == 'left_hand')
    times = [n['start_time'] for n in notes]
    key_indices = [n['key_index'] for n in notes]

    summary = {
        'total_notes': len(notes),
        'right_hand_notes': rh,
        'left_hand_notes': lh,
        'duration_range': [round(min(times), 2), round(max(times), 2)] if times else [0, 0],
        'key_range': [min(key_indices), max(key_indices)] if key_indices else [0, 87],
    }

    metadata = {
        'keyboard_y': cal.keyboard_y,
        'keyboard_height': cal.keyboard_height,
        'scroll_speed': cal.scroll_speed,
        'intro_end_time': cal.intro_end_time,
    }

    return {
        'metadata': metadata,
        'notes': notes,
        'summary': summary,
    }


# ── Box drawing: connected-component based ────────────────────────

def _max_consecutive_true(arr) -> int:
    """Longest consecutive run of True values in a 1-D bool sequence."""
    best = cur = 0
    for v in arr:
        if v:
            cur += 1
            if cur > best:
                best = cur
        else:
            cur = 0
    return best


def _key_at_x(keyboard_map, x: int) -> str:
    """Look up the key name for a given x coordinate (nearest center)."""
    best_name = '?'
    best_dist = float('inf')
    for k in keyboard_map:
        d = abs(k.center_x - x)
        if d < best_dist:
            best_dist = d
            best_name = k.full_name
    return best_name


def _build_visual_mask(hsv: np.ndarray, nc, note_area_bottom: int) -> np.ndarray:
    """Build a relaxed colour mask for visual bounding-box purposes.

    Both S and V are relaxed so that black-key pixels (which tend to be
    more saturated than white-key pixels of the same hand colour) are
    captured.  A V floor of 55 is used to avoid picking up very dark
    background / glow bands.
    """
    h_lo, h_hi = nc.h_range
    s_lo, s_hi = nc.s_range
    s_hi = min(255, s_hi + 100)       # relax S ceiling for black keys
    v_lo = max(55, int(nc.v_range[0] * 0.50))
    v_hi = min(255, nc.v_range[1] + 20)

    if h_lo > h_hi:
        m1 = cv2.inRange(hsv, np.array([h_lo, s_lo, v_lo]),
                         np.array([180, s_hi, v_hi]))
        m2 = cv2.inRange(hsv, np.array([0, s_lo, v_lo]),
                         np.array([h_hi, s_hi, v_hi]))
        mask = m1 | m2
    else:
        mask = cv2.inRange(hsv, np.array([h_lo, s_lo, v_lo]),
                           np.array([h_hi, s_hi, v_hi]))
    mask[note_area_bottom:, :] = 0
    return mask


def _should_merge(a, b, source_bgr, mask) -> bool:
    """Decide whether two components should be merged.

    They're fragments of the same note if:
    - same colour index
    - X-ranges overlap by ≥ 40 %
    - vertical gap ≤ 25 px
    - the gap region's INTERIOR is bright (text label), NOT dark (background)
    """
    if a[4] != b[4]:
        return False
    # X overlap fraction
    ol = max(0, min(a[2], b[2]) - max(a[0], b[0]))
    min_w = min(a[2] - a[0], b[2] - b[0])
    if min_w <= 0 or ol / min_w < 0.4:
        return False
    # Vertical gap (a is earlier in y, but handle either order)
    gap_y1 = min(a[3], b[3])
    gap_y2 = max(a[1], b[1])
    if gap_y2 <= gap_y1:
        return True                   # overlapping → merge
    if gap_y2 - gap_y1 > 25:
        return False                  # too far apart
    # Brightness test on INNER columns (skip 3px edge borders)
    # Text labels between fragments are bright; dark background = separate notes
    gap_x1 = max(a[0], b[0])
    gap_x2 = min(a[2], b[2])
    # Use inner region to avoid note shape border pixels
    border_skip = min(3, (gap_x2 - gap_x1) // 4)
    inner_x1 = gap_x1 + border_skip
    inner_x2 = gap_x2 - border_skip
    if inner_x2 <= inner_x1:
        # Very narrow — fall back to full width
        inner_x1, inner_x2 = gap_x1, gap_x2
    if inner_x2 <= inner_x1:
        return False
    gap_region = source_bgr[gap_y1:gap_y2, inner_x1:inner_x2]
    if gap_region.size == 0:
        return False
    gray = cv2.cvtColor(gap_region, cv2.COLOR_BGR2GRAY)
    bright_frac = float(np.mean(gray > 60))
    return bright_frac > 0.3


def _trim_box(x1, y1, x2, y2, mask, note_area_bottom, img_w, pad=2):
    """Shrink a box so every boundary row/column contains mask pixels."""
    while y1 < y2 - 1 and np.sum(mask[y1, x1:x2]) == 0:
        y1 += 1
    while y2 > y1 + 1 and np.sum(mask[y2 - 1, x1:x2]) == 0:
        y2 -= 1
    while x1 < x2 - 1 and np.sum(mask[y1:y2, x1]) == 0:
        x1 += 1
    while x2 > x1 + 1 and np.sum(mask[y1:y2, x2 - 1]) == 0:
        x2 -= 1
    return (max(0, x1 - pad), max(0, y1 - pad),
            min(img_w, x2 + pad), min(note_area_bottom, y2 + pad))


def _verify_boxes(boxes, combined_mask, source_gray, note_area_bottom):
    """Run quality checks — coverage, fill, and SOURCE-PIXEL dark-band detection.

    For every box, scan every interior row and column of the SOURCE image.
    A row/column is "dark" if its mean brightness (inner pixels, skip 3px
    border) is below 45 % of the note's typical brightness.  Flag any box
    with ≥ 2 consecutive dark rows/columns as a possible merge.

    Returns a dict with stats.  Prints a human-readable report.
    """
    img_w = combined_mask.shape[1]
    mask = combined_mask[:note_area_bottom, :img_w]
    total_px = int(np.sum(mask > 0))

    # Build a "covered" map
    covered = np.zeros_like(mask, dtype=np.uint8)
    for b in boxes:
        x1, y1, x2, y2 = b[:4]
        y2c = min(y2, note_area_bottom)
        covered[y1:y2c, x1:x2] = 255

    covered_px = int(np.sum((mask > 0) & (covered > 0)))
    cov_pct = 100.0 * covered_px / max(1, total_px)

    # Significant uncovered regions
    uncov_mask = ((mask > 0) & (covered == 0)).astype(np.uint8)
    n_labels, _, stats, _ = cv2.connectedComponentsWithStats(uncov_mask, 8)
    big_uncov = []
    for lbl in range(1, n_labels):
        area = stats[lbl, cv2.CC_STAT_AREA]
        if area >= 200:
            big_uncov.append((
                stats[lbl, cv2.CC_STAT_LEFT],
                stats[lbl, cv2.CC_STAT_TOP],
                stats[lbl, cv2.CC_STAT_WIDTH],
                stats[lbl, cv2.CC_STAT_HEIGHT],
                area,
            ))

    # Per-box checks using SOURCE PIXELS
    issues = []
    for i, b in enumerate(boxes):
        x1, y1, x2, y2 = b[:4]
        label = b[4] if len(b) > 4 else '?'
        y2c = min(y2, note_area_bottom)
        bh = y2c - y1
        bw = x2 - x1
        if bh <= 10 or bw <= 8:
            continue

        # Fill check (mask-based)
        bm = mask[y1:y2c, x1:x2]
        fill = float(np.sum(bm > 0)) / (bw * bh)
        if fill < 0.12:
            issues.append(f"Box {i} ({label}): very low fill {fill:.2f}")

        # ── Horizontal dark band check (source pixels) ────────────
        # Use mask content to determine where the actual note lives.
        # This avoids false positives from stray edge pixels that
        # extend the bounding box beyond the real note.
        mask_row_fill = np.mean(bm > 0, axis=1)
        filled_rows = np.where(mask_row_fill > 0.3)[0]
        if len(filled_rows) >= 10:
            note_y_start = filled_rows[0]
            note_y_end = filled_rows[-1] + 1
            note_h = note_y_end - note_y_start
            bskip_h = min(10, bw // 4)
            inner_h = source_gray[y1 + note_y_start:y1 + note_y_end,
                                  x1 + bskip_h:x2 - bskip_h]
            if inner_h.size > 0:
                row_means = np.mean(inner_h, axis=1)
                note_bright = float(np.percentile(row_means, 75))
                if note_bright > 50:
                    dark_thresh = note_bright * 0.35
                    vedge = min(5, note_h // 8)
                    dark_rows = row_means[vedge:note_h - vedge] < dark_thresh
                    max_run = _max_consecutive_true(dark_rows)
                    if max_run >= 2:
                        issues.append(
                            f"Box {i} ({label}): H dark band {max_run}px "
                            f"(bright={note_bright:.0f}, thresh={dark_thresh:.0f})")

        # ── Vertical dark band check (source pixels) ──────────────
        mask_col_fill = np.mean(bm > 0, axis=0)
        filled_cols = np.where(mask_col_fill > 0.3)[0]
        if len(filled_cols) >= 6:
            note_x_start = filled_cols[0]
            note_x_end = filled_cols[-1] + 1
            note_w = note_x_end - note_x_start
            bskip_v = min(10, bh // 4)
            inner_v = source_gray[y1 + bskip_v:y2c - bskip_v,
                                  x1 + note_x_start:x1 + note_x_end]
            if inner_v.size > 0:
                col_means = np.mean(inner_v, axis=0)
                note_bright_v = float(np.percentile(col_means, 75))
                if note_bright_v > 50:
                    dark_thresh_v = note_bright_v * 0.35
                    hedge = min(5, note_w // 8)
                    dark_cols = col_means[hedge:note_w - hedge] < dark_thresh_v
                    max_run_v = _max_consecutive_true(dark_cols)
                    if max_run_v >= 4:
                        issues.append(
                            f"Box {i} ({label}): V dark band {max_run_v}px "
                            f"(bright={note_bright_v:.0f}, thresh={dark_thresh_v:.0f})")

    # ── Print report ──────────────────────────────────────────────
    print(f"\n  Box verification (source-pixel based):")
    print(f"    Boxes drawn  : {len(boxes)}")
    print(f"    Mask coverage: {cov_pct:.1f}%  "
          f"({covered_px}/{total_px} mask px)")
    if big_uncov:
        print(f"    ⚠  {len(big_uncov)} uncovered region(s) ≥200 px "
              f"({sum(r[4] for r in big_uncov)} total px)")
        for r in big_uncov[:10]:
            print(f"       region at x={r[0]} y={r[1]} "
                  f"({r[2]}×{r[3]}, {r[4]} px)")
    if issues:
        print(f"    ⚠  {len(issues)} issue(s) found:")
        for iss in issues:
            print(f"    ⚠  {iss}")
    if not big_uncov and not issues:
        print(f"    ✓  All checks passed")

    return {
        'total_px': total_px,
        'covered_px': covered_px,
        'coverage_pct': cov_pct,
        'big_uncovered': big_uncov,
        'issues': issues,
    }


def _analyze_boxes(result, verbose=False):
    """Run CC analysis and labelling on the stitched image.

    Sets result._labelled_boxes and result._note_area_bottom
    as side-effects (used by build_notes_data).
    Does NOT create a drawn image — much faster.

    Algorithm
    ---------
    1. Build per-colour masks (relaxed V for full visual coverage).
    2. Connected-component analysis on the raw mask (no morphology)
       to find individual note blobs.
    3. Merge vertically-adjacent fragments of the same note that were
       split by text labels (same key column, gap contains bright pixels).
    4. Trim each box to the tightest fit on the original mask.
    5. Label each box by matching to the nearest detector note, with
       keyboard-map fallback for unmatched blobs.
    6. Optionally verify coverage and quality.
    """
    cal = result.calibration
    source = result.image
    img_h, img_w = source.shape[:2]
    note_area_bottom = img_h - cal.keyboard_height
    keyboard_map = result.keyboard_map

    # ── 1. Build per-colour masks ─────────────────────────────────
    hsv = cv2.cvtColor(source, cv2.COLOR_BGR2HSV)
    masks: list[np.ndarray] = []
    for nc in cal.note_colors:
        masks.append(_build_visual_mask(hsv, nc, note_area_bottom))
    del hsv

    combined = np.zeros((img_h, img_w), dtype=np.uint8)
    for m in masks:
        combined = cv2.bitwise_or(combined, m)

    # ── 2. Connected components (raw — no morphology) ─────────────
    # Compute the maximum plausible note width (≈ 3× white key width).
    # This rejects full-width glow bands that would produce phantom notes.
    _wc = sorted(k.center_x for k in keyboard_map if not k.is_black)
    _max_note_w = int(np.median(np.diff(_wc)) * 3) if len(_wc) >= 2 else 120

    raw_comps: list[list] = []          # [x1, y1, x2, y2, ci]
    for ci, mask in enumerate(masks):
        n_labels, _labels, stats, _cents = \
            cv2.connectedComponentsWithStats(mask, connectivity=8)
        for lbl in range(1, n_labels):
            area = stats[lbl, cv2.CC_STAT_AREA]
            if area < 100:
                continue
            x = stats[lbl, cv2.CC_STAT_LEFT]
            y = stats[lbl, cv2.CC_STAT_TOP]
            w = stats[lbl, cv2.CC_STAT_WIDTH]
            h = stats[lbl, cv2.CC_STAT_HEIGHT]
            if h < 8 or w < 4:
                continue
            if w > _max_note_w:
                continue              # reject glow bands / full-width artefacts
            raw_comps.append([x, y, x + w, y + h, ci])

    # ── 3. Merge text-split fragments ─────────────────────────────
    raw_comps.sort(key=lambda c: c[1])       # sort by y_top
    changed = True
    while changed:
        changed = False
        new_comps: list[list] = []
        used = [False] * len(raw_comps)
        for i in range(len(raw_comps)):
            if used[i]:
                continue
            box = list(raw_comps[i])
            for j in range(i + 1, len(raw_comps)):
                if used[j]:
                    continue
                if _should_merge(box, raw_comps[j], source, masks[box[4]]):
                    box[0] = min(box[0], raw_comps[j][0])
                    box[1] = min(box[1], raw_comps[j][1])
                    box[2] = max(box[2], raw_comps[j][2])
                    box[3] = max(box[3], raw_comps[j][3])
                    used[j] = True
                    changed = True
            new_comps.append(box)
        raw_comps = new_comps

    # ── 4. Trim boxes to tight fit ────────────────────────────────
    for b in raw_comps:
        b[0], b[1], b[2], b[3] = _trim_box(
            b[0], b[1], b[2], b[3],
            masks[b[4]], note_area_bottom, img_w)

    # ── 4b. Split boxes at internal dark bands (SOURCE pixels) ────
    #   Use source-image brightness (not mask) to find dark horizontal/
    #   vertical bands that indicate merged notes or adjacent-key bleed.
    #   Recursively split until no more dark bands are found.
    gray = cv2.cvtColor(source, cv2.COLOR_BGR2GRAY)

    def _find_h_dark_bands(x1, y1, x2, y2c, ci):
        """Find horizontal dark bands using source pixels (inner cols).

        Uses a generous border skip to avoid false positives from
        the rounded corners of note shapes.
        """
        bw = x2 - x1
        bh = y2c - y1
        if bw < 12 or bh < 20:
            return []
        # Skip enough border pixels to clear rounded corners
        bskip = min(10, bw // 4)
        inner = gray[y1:y2c, x1 + bskip:x2 - bskip]
        if inner.size == 0:
            return []
        row_means = np.mean(inner, axis=1)
        # Note brightness = 75th percentile of row means
        note_bright = float(np.percentile(row_means, 75))
        if note_bright < 50:
            return []
        dark_thresh = note_bright * 0.35
        # Scan for dark runs (skip edge at top/bottom)
        vedge = min(3, bh // 6)
        bands = []
        in_dark, ds = False, 0
        for r in range(vedge, bh - vedge):
            if row_means[r] < dark_thresh:
                if not in_dark:
                    ds = r
                    in_dark = True
            else:
                if in_dark:
                    bands.append((ds, r - ds))
                    in_dark = False
        if in_dark:
            bands.append((ds, bh - vedge - ds))
        # Only keep bands >= 2 px
        return [(s, l) for s, l in bands if l >= 2]

    def _find_v_dark_bands(x1, y1, x2, y2c, ci):
        """Find vertical dark bands using source pixels (inner rows)."""
        bw = x2 - x1
        bh = y2c - y1
        if bw < 20 or bh < 12:
            return []
        bskip = min(10, bh // 4)
        inner = gray[y1 + bskip:y2c - bskip, x1:x2]
        if inner.size == 0:
            return []
        col_means = np.mean(inner, axis=0)
        note_bright = float(np.percentile(col_means, 75))
        if note_bright < 50:
            return []
        dark_thresh = note_bright * 0.35
        hedge = min(3, bw // 6)
        bands = []
        in_dark, ds = False, 0
        for c in range(hedge, bw - hedge):
            if col_means[c] < dark_thresh:
                if not in_dark:
                    ds = c
                    in_dark = True
            else:
                if in_dark:
                    bands.append((ds, c - ds))
                    in_dark = False
        if in_dark:
            bands.append((ds, bw - hedge - ds))
        return [(s, l) for s, l in bands if l >= 2]

    def _recursive_split(x1, y1, x2, y2, ci, depth=0):
        """Recursively split a box at dark bands."""
        if depth > 20:
            return [[x1, y1, x2, y2, ci]]
        y2c = min(y2, note_area_bottom)
        bw = x2 - x1
        bh = y2c - y1
        if bw < 12 or bh < 15:
            return [[x1, y1, x2, y2, ci]]

        # Check vertical dark bands first (adjacent-key merge)
        v_bands = _find_v_dark_bands(x1, y1, x2, y2c, ci)
        if v_bands:
            # Split at the widest band
            best = max(v_bands, key=lambda b: b[1])
            if best[1] >= 4:
                split_x = x1 + best[0] + best[1] // 2
                parts = []
                left = _trim_box(x1, y1, split_x, y2,
                                 masks[ci], note_area_bottom, img_w)
                right = _trim_box(split_x, y1, x2, y2,
                                  masks[ci], note_area_bottom, img_w)
                if left[2] - left[0] > 4 and left[3] - left[1] > 8:
                    parts.extend(_recursive_split(
                        left[0], left[1], left[2], left[3], ci, depth + 1))
                if right[2] - right[0] > 4 and right[3] - right[1] > 8:
                    parts.extend(_recursive_split(
                        right[0], right[1], right[2], right[3], ci, depth + 1))
                if parts:
                    return parts

        # Check horizontal dark bands (merged consecutive notes)
        h_bands = _find_h_dark_bands(x1, y1, x2, y2c, ci)
        if h_bands:
            # Split at ALL dark bands (not just the biggest)
            # Sort by position to split top-to-bottom
            h_bands.sort(key=lambda b: b[0])
            split_ys = [y1 + s + l // 2 for s, l in h_bands if l >= 2]
            if split_ys:
                # Add start and end boundaries
                boundaries = [y1] + split_ys + [y2]
                parts = []
                for k in range(len(boundaries) - 1):
                    seg_y1 = boundaries[k]
                    seg_y2 = boundaries[k + 1]
                    trimmed = _trim_box(x1, seg_y1, x2, seg_y2,
                                        masks[ci], note_area_bottom, img_w)
                    if (trimmed[2] - trimmed[0] > 4 and
                            trimmed[3] - trimmed[1] > 8):
                        parts.append([trimmed[0], trimmed[1],
                                      trimmed[2], trimmed[3], ci])
                if len(parts) > 1:
                    return parts

        return [[x1, y1, x2, y2, ci]]

    split_comps: list[list] = []
    for b in raw_comps:
        split_comps.extend(_recursive_split(b[0], b[1], b[2], b[3], b[4]))

    # ── 4c. Re-merge tiny split fragments ─────────────────────────
    #   Black key notes are narrow, so their text labels ("F#", "C#", etc.)
    #   can create false dark bands that incorrectly split one note into
    #   two tiny pieces. Merge back any vertically adjacent pieces on the
    #   same key column where one piece is very short (< 30px ≈ 0.12s).
    MIN_NOTE_HEIGHT = 30  # px — below this, try to merge back
    split_comps.sort(key=lambda c: (c[0], c[1]))  # sort by x, then y
    merged_back: list[list] = []
    used = [False] * len(split_comps)
    for i in range(len(split_comps)):
        if used[i]:
            continue
        box = list(split_comps[i])
        bh = box[3] - box[1]
        if bh < MIN_NOTE_HEIGHT:
            # Try to merge with adjacent box on same key
            for j in range(len(split_comps)):
                if i == j or used[j]:
                    continue
                other = split_comps[j]
                if other[4] != box[4]:
                    continue
                # Check x overlap
                ol = max(0, min(box[2], other[2]) - max(box[0], other[0]))
                min_w = min(box[2] - box[0], other[2] - other[0])
                if min_w <= 0 or ol / min_w < 0.4:
                    continue
                # Check vertical adjacency (gap ≤ 15px)
                gap_y1 = min(box[3], other[3])
                gap_y2 = max(box[1], other[1])
                if gap_y2 - gap_y1 > 15:
                    continue
                # Merge the tiny piece into the larger one
                box[0] = min(box[0], other[0])
                box[1] = min(box[1], other[1])
                box[2] = max(box[2], other[2])
                box[3] = max(box[3], other[3])
                used[j] = True
        merged_back.append(box)
    raw_comps = merged_back

    # ── 5. Label: match to detector notes ─────────────────────────
    labelled: list[tuple] = []
    det_used = [False] * len(result.notes)

    for b in raw_comps:
        x1, y1, x2, y2, ci = b
        # Best overlapping detector note (same colour)
        best_idx = -1
        best_score = 0
        for ni, n in enumerate(result.notes):
            if n.color_idx != ci:
                continue
            v_ol = max(0, min(y2, n.y + n.height) - max(y1, n.y))
            h_ol = max(0, min(x2, n.x + n.width) - max(x1, n.x))
            score = v_ol * h_ol
            if score > best_score:
                best_score = score
                best_idx = ni

        if best_idx >= 0:
            n = result.notes[best_idx]
            det_used[best_idx] = True
            t = y_to_time(n.y, note_area_bottom,
                          cal.scroll_speed, cal.intro_end_time)
            label = f"{n.key_name} {t:.1f}s"
            hand = n.hand
        else:
            cx = (x1 + x2) // 2
            key_name = _key_at_x(keyboard_map, cx)
            t = y_to_time(y1, note_area_bottom,
                          cal.scroll_speed, cal.intro_end_time)
            label = f"{key_name} {t:.1f}s"
            hand = cal.note_colors[ci].label if ci < len(cal.note_colors) \
                else 'unknown'

        labelled.append((x1, y1, x2, y2, label, hand))

    # ── 6. Verify ─────────────────────────────────────────────────
    if verbose:
        _verify_boxes(labelled, combined, gray, note_area_bottom)

    # ── 7. Store labelled boxes ─────────────────────────────────
    result._labelled_boxes = labelled
    result._note_area_bottom = note_area_bottom


def draw_boxes_on_stitched(result, verbose=False) -> np.ndarray:
    """Run analysis and render labelled bounding boxes on a copy.

    Calls _analyze_boxes() if not already done, then draws.
    """
    if not hasattr(result, '_labelled_boxes'):
        _analyze_boxes(result, verbose=verbose)

    source = result.image
    img_h, img_w = source.shape[:2]
    labelled = result._labelled_boxes

    img = source.copy()
    BOX_RH  = (0, 220, 120)      # green
    BOX_LH  = (120, 160, 255)    # blue
    TEXT_BG = (30, 30, 30)
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.5
    thickness = 1

    for (x1, y1, x2, y2, label, hand) in labelled:
        colour = BOX_LH if hand == 'left_hand' else BOX_RH
        cv2.rectangle(img, (x1, y1), (x2, y2), colour, 2)

        (tw, th), baseline = cv2.getTextSize(label, font, font_scale,
                                             thickness)
        margin = 4
        lx = x2 + margin
        if lx + tw + margin > img_w:
            lx = x1 - tw - margin
        ly = y1 + th + margin

        cv2.rectangle(img,
                      (lx - 1, ly - th - margin),
                      (lx + tw + 1, ly + baseline + 1),
                      TEXT_BG, -1)
        cv2.putText(img, label, (lx, ly),
                    font, font_scale, colour, thickness, cv2.LINE_AA)

    return img


def label_notes(result, verbose=False):
    """Run CC analysis and labelling WITHOUT drawing.

    Sets result._labelled_boxes and result._note_area_bottom,
    needed by build_notes_data().  Much faster than
    draw_boxes_on_stitched() since it skips the image copy and
    rendering.
    """
    _analyze_boxes(result, verbose=verbose)


def build_standalone_html(notes_data: dict, title: str = 'MakeMusic') -> str:
    """Build a self-contained HTML viewer with the notes data embedded."""
    # Read the viewer template
    viewer_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'viewer')
    template_path = os.path.join(viewer_dir, 'index.html')

    with open(template_path, 'r') as f:
        html = f.read()

    # Update the title
    html = html.replace('<title>MakeMusic - Piano Roll Viewer</title>',
                        f'<title>{title} - MakeMusic</title>')

    # Inject EMBEDDED_NOTES_DATA before the main script block
    # Find the last </script> before </body>
    embed_script = (
        '\n<script>\n'
        'const EMBEDDED_NOTES_DATA = '
        + json.dumps(notes_data, separators=(',', ':'))
        + ';\n</script>\n'
    )

    # Insert just before the main <script> block (which contains the
    # EMBEDDED_NOTES_DATA check).  We find the pattern:
    #   <script src="...tone..."></script>\n    <script>
    # and insert our block between them.
    #
    # Alternative: just insert before the closing </body>
    # Since the check is:  if (typeof EMBEDDED_NOTES_DATA !== 'undefined')
    # our script tag must run BEFORE that check.
    # The simplest approach: insert right after </style> and before the
    # existing <script> tags.
    insert_marker = '</style>\n'
    if insert_marker in html:
        idx = html.index(insert_marker) + len(insert_marker)
        html = html[:idx] + embed_script + html[idx:]
    else:
        # Fallback: insert before </body>
        html = html.replace('</body>', embed_script + '</body>')

    return html


def main():
    parser = argparse.ArgumentParser(
        description='Process a falling-notes piano video into an '
                    'interactive HTML viewer.',
    )
    parser.add_argument('video', help='Path to the input video file')
    parser.add_argument('-o', '--output', default=None,
                        help='Output folder (default: <video_dir>/output)')
    parser.add_argument('--fps', type=float, default=10.0,
                        help='Sampling FPS for stitching (default: 10). '
                             'Higher = better quality but slower.')
    parser.add_argument('--title', default=None,
                        help='Title for the HTML page '
                             '(default: derived from folder name)')
    parser.add_argument('-q', '--quiet', action='store_true',
                        help='Suppress progress output')

    # Optional output flags (HTML is always produced)
    parser.add_argument('--stitched', action='store_true',
                        help='Also save stitched.png')
    parser.add_argument('--boxes', action='store_true',
                        help='Also save stitched_boxes.png (implies --stitched)')
    parser.add_argument('--json', action='store_true',
                        help='Also save notes.json')
    parser.add_argument('--all', action='store_true',
                        help='Enable all optional outputs')
    args = parser.parse_args()

    if args.all:
        args.stitched = args.boxes = args.json = True
    if args.boxes:
        args.stitched = True

    t_start = time.perf_counter()

    # Derive output folder
    if args.output is None:
        args.output = os.path.join(
            os.path.dirname(os.path.abspath(args.video)), 'output')

    # Derive title from video path if not given
    if args.title is None:
        song_name = os.path.basename(
            os.path.dirname(os.path.abspath(args.video)))
        args.title = song_name.replace('_', ' ').title()

    os.makedirs(args.output, exist_ok=True)

    # ── 1. Run stitch + detect pipeline ───────────────────────────
    if not args.quiet:
        print(f'Processing: {args.video}')
        print(f'Output:     {args.output}/')
        print()

    result = stitch_song(
        video_path=args.video,
        stitch_fps=args.fps,
        verbose=not args.quiet,
    )

    # ── 2. Analyse notes (CC labelling) ─────────────────────────
    if args.boxes:
        # Full draw — also produces labelled_boxes as side-effect
        boxes_img = draw_boxes_on_stitched(result, verbose=not args.quiet)
    else:
        # Label-only — skips the expensive image copy + rendering
        label_notes(result, verbose=not args.quiet)
        boxes_img = None

    # ── 3. Generate notes data from boxes ─────────────────────────
    notes_data = build_notes_data(
        result._labelled_boxes,
        result.calibration,
        result._note_area_bottom,
    )

    if not args.quiet:
        s = notes_data['summary']
        print(f'\nNotes: {s["total_notes"]} total '
              f'({s["right_hand_notes"]} RH, {s["left_hand_notes"]} LH)')
        print(f'Duration: {s["duration_range"][0]:.1f}s – '
              f'{s["duration_range"][1]:.1f}s')

    # ── 4. Build and save HTML (always) ───────────────────────────
    html = build_standalone_html(notes_data, title=args.title)
    html_path = os.path.join(args.output, 'output.html')
    with open(html_path, 'w') as f:
        f.write(html)

    # ── 5. Optional outputs ───────────────────────────────────────
    saved = [html_path]

    if args.stitched:
        stitched_path = os.path.join(args.output, 'stitched.png')
        cv2.imwrite(stitched_path, result.image)
        saved.append(stitched_path)

    if args.boxes:
        boxes_path = os.path.join(args.output, 'stitched_boxes.png')
        cv2.imwrite(boxes_path, boxes_img)
        saved.append(boxes_path)
        del boxes_img

    if args.json:
        json_path = os.path.join(args.output, 'notes.json')
        with open(json_path, 'w') as f:
            json.dump(notes_data, f, indent=2)
        saved.append(json_path)

    elapsed = time.perf_counter() - t_start

    if not args.quiet:
        print(f'\nSaved:')
        for p in saved:
            sz = os.path.getsize(p)
            if sz > 1024 * 1024:
                print(f'  {p} ({sz / 1024 / 1024:.1f} MB)')
            else:
                print(f'  {p} ({sz / 1024:.0f} KB)')
        print(f'\nDone in {elapsed:.1f}s')


if __name__ == '__main__':
    main()
