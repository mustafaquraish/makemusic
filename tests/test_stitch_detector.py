"""
Comprehensive tests for stitch_detector — the per-key column scanner.

Testing strategy
────────────────
Generate synthetic stitched images with KNOWN note placements, run the
detector, and verify we get the same notes back.  Each test generator
aims to reproduce visual characteristics of real falling-notes videos:

• Rounded-rectangle notes with borders and optional glow
• Text labels printed INSIDE the note body
• Subtle gradients (some videos shade from bright top to dim bottom)
• Multiple colour themes (purple/green, blue/orange, pink/cyan)
• Realistic key widths and note widths
• Black-key notes that are narrower than white-key notes
"""

import sys, os, math
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import numpy as np
import cv2
import pytest
from dataclasses import dataclass

from src.calibrator import CalibrationResult, NoteColor
from src.keyboard_analyzer import KeyInfo
from src.stitch_detector import (
    detect_notes_on_stitched_image,
    StitchedNote,
    _find_vertical_runs,
    _compute_key_x_ranges,
)


# ═══════════════════════════════════════════════════════════════════
#  Test-image generation utilities
# ═══════════════════════════════════════════════════════════════════

# Reference key layout ── one octave of 7 white + 5 black keys.
WHITE_NOTES = ['C', 'D', 'E', 'F', 'G', 'A', 'B']
BLACK_NOTES = ['C#', 'D#', 'F#', 'G#', 'A#']

# Pairs of white keys that have a black key between them
BLACK_KEY_MAP = {
    ('C', 'D'): 'C#', ('D', 'E'): 'D#',
    ('F', 'G'): 'F#', ('G', 'A'): 'G#', ('A', 'B'): 'A#',
}


def _make_keyboard_map(
    octaves: int = 3,
    start_octave: int = 3,
    white_key_width: float = 40.0,
    x_offset: int = 50,
) -> list:
    """Build a simple KeyInfo list covering *octaves* octaves."""
    keys = []
    wx = x_offset + white_key_width / 2   # centre of first white key

    white_centers = []
    for oct in range(start_octave, start_octave + octaves):
        for name in WHITE_NOTES:
            keys.append(KeyInfo(center_x=int(round(wx)),
                                note_name=name, is_black=False, octave=oct))
            white_centers.append(wx)
            wx += white_key_width

    # Add black keys
    all_whites = [k for k in keys if not k.is_black]
    for i in range(len(all_whites) - 1):
        pair = (all_whites[i].note_name, all_whites[i + 1].note_name)
        if pair in BLACK_KEY_MAP:
            bname = BLACK_KEY_MAP[pair]
            bx = all_whites[i].center_x + 0.42 * (
                all_whites[i + 1].center_x - all_whites[i].center_x
            )
            keys.append(KeyInfo(center_x=int(round(bx)),
                                note_name=bname, is_black=True,
                                octave=all_whites[i].octave))

    keys.sort(key=lambda k: k.center_x)
    return keys


# ── Colour themes ────────────────────────────────────────────────
# Each theme: (RH NoteColor, LH NoteColor, BG colour BGR)

def _theme_purple_green():
    """Classic Synthesia-like theme: purple RH, green LH."""
    rh = NoteColor(
        center_hsv=(82, 175, 222), center_bgr=(195, 222, 75),
        label='right_hand',
        h_range=(52, 111), s_range=(81, 255), v_range=(73, 255),
    )
    lh = NoteColor(
        center_hsv=(146, 92, 193), center_bgr=(192, 123, 183),
        label='left_hand',
        h_range=(137, 154), s_range=(46, 137), v_range=(97, 255),
    )
    return rh, lh, (10, 10, 10)


def _theme_blue_orange():
    """Blue RH, orange LH on dark grey background."""
    rh = NoteColor(
        center_hsv=(110, 200, 220), center_bgr=(220, 120, 30),
        label='right_hand',
        h_range=(90, 130), s_range=(100, 255), v_range=(80, 255),
    )
    lh = NoteColor(
        center_hsv=(15, 200, 230), center_bgr=(40, 120, 230),
        label='left_hand',
        h_range=(5, 25), s_range=(100, 255), v_range=(100, 255),
    )
    return rh, lh, (20, 20, 25)


def _theme_pink_cyan():
    """Pink RH, cyan LH on black background."""
    rh = NoteColor(
        center_hsv=(170, 180, 230), center_bgr=(180, 80, 230),
        label='right_hand',
        h_range=(155, 180), s_range=(80, 255), v_range=(80, 255),
    )
    lh = NoteColor(
        center_hsv=(90, 180, 210), center_bgr=(210, 190, 50),
        label='left_hand',
        h_range=(75, 100), s_range=(80, 255), v_range=(80, 255),
    )
    return rh, lh, (5, 5, 5)


ALL_THEMES = [_theme_purple_green, _theme_blue_orange, _theme_pink_cyan]


# ── Note rendering helpers ───────────────────────────────────────

def _draw_note_rect(
    image: np.ndarray,
    x: int, y: int, w: int, h: int,
    color_bgr: tuple,
    *,
    label: str = '',
    border: bool = True,
    glow: bool = False,
    gradient: bool = False,
    rounded: bool = False,
):
    """
    Draw a single note rectangle, optionally with realistic effects.

    This tries to closely match how real falling-notes videos render:
    • Solid colour fill (or vertical gradient from bright to dimmer)
    • Thin darker border
    • Optional glow halo around the rectangle
    • Optional text label centred inside
    """
    x2, y2 = x + w, y + h
    if y2 <= 0 or y >= image.shape[0] or x2 <= 0 or x >= image.shape[1]:
        return

    # Clamp to image bounds
    x_c = max(0, x)
    y_c = max(0, y)
    x2_c = min(image.shape[1], x2)
    y2_c = min(image.shape[0], y2)

    if glow:
        # Draw a soft glow halo (~5px, half-bright)
        glow_col = tuple(c // 3 for c in color_bgr)
        pad = 5
        gx1, gy1 = max(0, x - pad), max(0, y - pad)
        gx2, gy2 = min(image.shape[1], x2 + pad), min(image.shape[0], y2 + pad)
        cv2.rectangle(image, (gx1, gy1), (gx2, gy2), glow_col, -1)

    if gradient:
        # Vertical gradient: top row = 100% brightness, bottom row = 60%
        for row in range(y_c, y2_c):
            frac = (row - y_c) / max(1, y2_c - y_c - 1)
            scale = 1.0 - 0.4 * frac
            row_col = tuple(int(c * scale) for c in color_bgr)
            cv2.line(image, (x_c, row), (x2_c - 1, row), row_col, 1)
    else:
        cv2.rectangle(image, (x_c, y_c), (x2_c - 1, y2_c - 1),
                      color_bgr, -1)

    if border:
        border_col = tuple(max(0, int(c * 0.6)) for c in color_bgr)
        cv2.rectangle(image, (x_c, y_c), (x2_c - 1, y2_c - 1),
                      border_col, 1)

    if label and w >= 10 and h >= 12:
        font = cv2.FONT_HERSHEY_SIMPLEX
        scale = min(w, h) / 55.0
        scale = max(0.3, min(scale, 1.2))
        thick = max(1, int(scale * 2))
        tsz = cv2.getTextSize(label, font, scale, thick)[0]
        tx = x_c + (x2_c - x_c - tsz[0]) // 2
        ty = y_c + (y2_c - y_c + tsz[1]) // 2
        if tx >= 0 and ty >= 0:
            cv2.putText(image, label, (tx, ty), font, scale,
                        (255, 255, 255), thick)


def _draw_keyboard_strip(
    image: np.ndarray,
    keyboard_map: list,
    keyboard_y: int,
    keyboard_height: int,
    white_key_width: float,
):
    """Draw a simplified keyboard into the image at the bottom."""
    h, w = image.shape[:2]
    # White keys
    for k in keyboard_map:
        if k.is_black:
            continue
        xl = int(k.center_x - white_key_width / 2)
        xr = int(k.center_x + white_key_width / 2)
        cv2.rectangle(image, (xl, keyboard_y), (xr, keyboard_y + keyboard_height),
                      (230, 230, 230), -1)
        cv2.rectangle(image, (xl, keyboard_y), (xr, keyboard_y + keyboard_height),
                      (100, 100, 100), 1)
    # Black keys
    bw = int(white_key_width * 0.58)
    bh = int(keyboard_height * 0.65)
    for k in keyboard_map:
        if not k.is_black:
            continue
        xl = int(k.center_x - bw / 2)
        xr = int(k.center_x + bw / 2)
        cv2.rectangle(image, (xl, keyboard_y), (xr, keyboard_y + bh),
                      (20, 20, 20), -1)


# ── High-level image builder ─────────────────────────────────────

@dataclass
class NoteSpec:
    """Specification for one note to place on the synthetic image."""
    key_name: str       # e.g. 'C4', 'F#5'
    y: int              # top edge in stitched image coords
    height: int
    hand: str           # 'right_hand' | 'left_hand'
    label: str = ''     # text to draw inside
    glow: bool = False
    gradient: bool = False


def build_synthetic_stitched_image(
    note_specs: list,
    *,
    theme_fn=None,
    octaves: int = 3,
    start_octave: int = 3,
    white_key_width: float = 40.0,
    x_offset: int = 50,
    note_area_height: int = 2000,
    keyboard_height: int = 120,
    bg_color: tuple = None,
) -> tuple:
    """
    Generate a synthetic stitched image with given notes.

    Returns:
        (image_bgr, calibration, keyboard_map, note_specs_placed)

    note_specs_placed is a list of NoteSpec with actual pixel coords.
    """
    if theme_fn is None:
        theme_fn = _theme_purple_green
    rh_color, lh_color, default_bg = theme_fn()
    if bg_color is None:
        bg_color = default_bg

    keyboard_map = _make_keyboard_map(octaves, start_octave,
                                       white_key_width, x_offset)

    frame_width = x_offset * 2 + int(white_key_width * octaves * 7)
    total_height = note_area_height + keyboard_height

    image = np.zeros((total_height, frame_width, 3), dtype=np.uint8)
    image[:] = bg_color

    # Draw keyboard at the bottom
    keyboard_y = note_area_height
    _draw_keyboard_strip(image, keyboard_map, keyboard_y, keyboard_height,
                         white_key_width)

    # Build lookup: key_name → (center_x, is_black)
    key_lookup = {k.full_name: k for k in keyboard_map}

    # Key width helpers
    white_centers = sorted(k.center_x for k in keyboard_map if not k.is_black)
    if len(white_centers) >= 2:
        wkw = float(np.median(np.diff(white_centers)))
    else:
        wkw = white_key_width
    bkw = wkw * 0.58

    # Determine colour mapping
    hand_colors = {
        'right_hand': rh_color.center_bgr,
        'left_hand': lh_color.center_bgr,
    }

    placed = []
    for spec in note_specs:
        kinfo = key_lookup.get(spec.key_name)
        if kinfo is None:
            continue

        note_w = int(bkw) if kinfo.is_black else int(wkw)
        note_x = int(kinfo.center_x - note_w / 2)
        color_bgr = hand_colors.get(spec.hand, rh_color.center_bgr)

        # Auto-label with key name when the note is tall enough to fit text,
        # unless an explicit label (or blank override) was provided.
        # Real videos always show the note name inside each box.
        auto_label = spec.label if spec.label != '' else (
            spec.key_name if spec.height >= 20 else ''
        )

        _draw_note_rect(
            image, note_x, spec.y, note_w, spec.height,
            color_bgr,
            label=auto_label,
            glow=spec.glow,
            gradient=spec.gradient,
        )
        placed.append(spec)

    # Calibration
    cal = CalibrationResult(
        keyboard_y=keyboard_y,
        keyboard_height=keyboard_height,
        note_area_top=0,
        note_area_bottom=keyboard_y,
        note_colors=[rh_color, lh_color],
        scroll_speed=242.0,
        frame_width=frame_width,
        frame_height=total_height,
    )

    return image, cal, keyboard_map, placed


# ═══════════════════════════════════════════════════════════════════
#  Helper: compare detected vs expected
# ═══════════════════════════════════════════════════════════════════

def _match_notes(detected: list, expected: list,
                 y_tolerance: int = 20,
                 height_tolerance_frac: float = 0.3) -> dict:
    """
    Match detected notes to expected notes.

    Returns dict with keys:
        matched    — list of (expected, detected) pairs
        missing    — list of expected specs not detected
        extra      — list of detected notes not matched
    """
    det_available = list(detected)
    matched = []
    missing = []

    for exp in expected:
        best = None
        best_dist = float('inf')
        for d in det_available:
            if d.key_name != exp.key_name:
                continue
            if d.hand != exp.hand:
                continue
            y_dist = abs(d.y - exp.y)
            h_diff = abs(d.height - exp.height) / max(1, exp.height)
            if y_dist <= y_tolerance and h_diff <= height_tolerance_frac:
                dist = y_dist + h_diff * 100
                if dist < best_dist:
                    best_dist = dist
                    best = d
        if best is not None:
            matched.append((exp, best))
            det_available.remove(best)
        else:
            missing.append(exp)

    return {'matched': matched, 'missing': missing, 'extra': det_available}


# ═══════════════════════════════════════════════════════════════════
#  Unit tests for internals
# ═══════════════════════════════════════════════════════════════════

class TestFindVerticalRuns:
    """Tests for _find_vertical_runs."""

    def test_single_run(self):
        col = np.zeros((100, 5), dtype=np.uint8)
        col[20:50, :] = 255
        runs = _find_vertical_runs(col, fill_threshold=0.3, min_height=5,
                                    min_gap=3)
        assert len(runs) == 1
        assert runs[0] == (20, 50)

    def test_two_runs_with_gap(self):
        col = np.zeros((200, 5), dtype=np.uint8)
        col[10:40, :] = 255
        col[80:110, :] = 255
        runs = _find_vertical_runs(col, fill_threshold=0.3, min_height=5,
                                    min_gap=3)
        assert len(runs) == 2

    def test_small_gap_bridged(self):
        """A 5px gap inside a note should be bridged if min_gap >= 5."""
        col = np.zeros((100, 5), dtype=np.uint8)
        col[10:30, :] = 255
        col[35:60, :] = 255   # 5px gap at rows 30-34
        runs = _find_vertical_runs(col, fill_threshold=0.3, min_height=5,
                                    min_gap=10)
        assert len(runs) == 1, f"Expected bridged run, got {runs}"

    def test_large_gap_not_bridged(self):
        col = np.zeros((200, 5), dtype=np.uint8)
        col[10:30, :] = 255
        col[60:90, :] = 255   # 30px gap
        runs = _find_vertical_runs(col, fill_threshold=0.3, min_height=5,
                                    min_gap=10)
        assert len(runs) == 2

    def test_below_fill_threshold(self):
        """Columns only partially filled shouldn't trigger a run."""
        col = np.zeros((100, 20), dtype=np.uint8)
        col[10:30, 0:1] = 255   # only 1/20 columns filled = 5%
        runs = _find_vertical_runs(col, fill_threshold=0.3, min_height=5,
                                    min_gap=3)
        assert len(runs) == 0

    def test_min_height_filters_short_runs(self):
        col = np.zeros((100, 5), dtype=np.uint8)
        col[10:14, :] = 255  # only 4 rows
        runs = _find_vertical_runs(col, fill_threshold=0.3, min_height=8,
                                    min_gap=3)
        assert len(runs) == 0


class TestComputeKeyXRanges:
    """Tests for _compute_key_x_ranges."""

    def test_basic_ranges(self):
        km = _make_keyboard_map(octaves=1, white_key_width=40.0, x_offset=0)
        ranges = _compute_key_x_ranges(km, 400)
        # Should have 7 white + 5 black = 12 keys
        assert len(ranges) == 12
        # All ranges should be non-empty
        for name, is_black, xl, xr in ranges:
            assert xr > xl, f"Empty range for {name}"

    def test_black_narrower_than_white(self):
        km = _make_keyboard_map(octaves=1, white_key_width=40.0, x_offset=0)
        ranges = _compute_key_x_ranges(km, 400)
        white_widths = [xr - xl for _, ib, xl, xr in ranges if not ib]
        black_widths = [xr - xl for _, ib, xl, xr in ranges if ib]
        assert all(bw < ww for bw in black_widths for ww in white_widths), \
            "Black keys should be narrower"


# ═══════════════════════════════════════════════════════════════════
#  Integration tests — synthetic image round-trips
# ═══════════════════════════════════════════════════════════════════

class TestBasicDetection:
    """Simple cases that must always pass."""

    def test_single_white_key_note(self):
        """A single note on a white key should be detected."""
        specs = [NoteSpec('C4', y=100, height=80, hand='right_hand')]
        img, cal, km, placed = build_synthetic_stitched_image(specs)
        detected = detect_notes_on_stitched_image(img, cal, km)

        result = _match_notes(detected, placed)
        assert len(result['matched']) == 1
        assert len(result['missing']) == 0

    def test_single_black_key_note(self):
        """A single note on a black key (F#4) should be detected."""
        specs = [NoteSpec('F#4', y=100, height=80, hand='right_hand')]
        img, cal, km, placed = build_synthetic_stitched_image(specs)
        detected = detect_notes_on_stitched_image(img, cal, km)

        result = _match_notes(detected, placed)
        assert len(result['matched']) == 1, \
            f"Missing: {result['missing']}, Extra: {[(n.key_name, n.y) for n in result['extra']]}"

    def test_two_notes_different_keys(self):
        specs = [
            NoteSpec('C4', y=100, height=60, hand='right_hand'),
            NoteSpec('G4', y=100, height=60, hand='right_hand'),
        ]
        img, cal, km, placed = build_synthetic_stitched_image(specs)
        detected = detect_notes_on_stitched_image(img, cal, km)

        result = _match_notes(detected, placed)
        assert len(result['matched']) == 2
        assert len(result['missing']) == 0

    def test_left_and_right_hand(self):
        """Notes of different hands (colours) should both be detected."""
        specs = [
            NoteSpec('C4', y=100, height=60, hand='right_hand'),
            NoteSpec('G3', y=100, height=60, hand='left_hand'),
        ]
        img, cal, km, placed = build_synthetic_stitched_image(specs)
        detected = detect_notes_on_stitched_image(img, cal, km)

        rh = [d for d in detected if d.hand == 'right_hand']
        lh = [d for d in detected if d.hand == 'left_hand']
        assert len(rh) >= 1
        assert len(lh) >= 1

    def test_note_with_text_label(self):
        """Text label inside a note should not cause false splits."""
        specs = [
            NoteSpec('E4', y=100, height=100, hand='right_hand', label='E4'),
        ]
        img, cal, km, placed = build_synthetic_stitched_image(specs)
        detected = detect_notes_on_stitched_image(img, cal, km)

        e_notes = [d for d in detected if d.key_name == 'E4']
        assert len(e_notes) == 1, \
            f"Expected 1 E4, got {len(e_notes)} — text caused false split?"


class TestThinnBlackKeyNotes:
    """
    Bug (1): Sharp/flat notes have thinner boxes.  Text labels can be
    as wide as the box itself, potentially punching a full-width hole
    in the colour mask and causing a false vertical split.
    """

    @pytest.mark.parametrize("key", ['C#4', 'D#4', 'F#4', 'G#4', 'A#4'])
    def test_black_key_with_label(self, key):
        """A black-key note with text should remain ONE detection."""
        specs = [NoteSpec(key, y=50, height=120, hand='right_hand', label=key)]
        img, cal, km, placed = build_synthetic_stitched_image(
            specs, white_key_width=40.0,
        )
        detected = detect_notes_on_stitched_image(img, cal, km)

        matching = [d for d in detected if d.key_name == key]
        assert len(matching) == 1, \
            f"Expected 1 {key}, got {len(matching)} — thin box text split?"

    @pytest.mark.parametrize("key", ['C#4', 'G#4'])
    def test_black_key_with_large_label(self, key):
        """Even a large bold label should not split a black-key note."""
        specs = [NoteSpec(key, y=30, height=150, hand='right_hand', label=key)]
        img, cal, km, placed = build_synthetic_stitched_image(
            specs, white_key_width=50.0,
        )
        detected = detect_notes_on_stitched_image(img, cal, km)

        matching = [d for d in detected if d.key_name == key]
        assert len(matching) == 1

    def test_multiple_black_keys_with_labels(self):
        """Several black-key notes, all with labels, all detected once."""
        specs = [
            NoteSpec('C#4', y=50, height=100, hand='right_hand', label='C#'),
            NoteSpec('F#4', y=50, height=100, hand='right_hand', label='F#'),
            NoteSpec('A#4', y=200, height=80, hand='left_hand', label='A#'),
        ]
        img, cal, km, placed = build_synthetic_stitched_image(specs)
        detected = detect_notes_on_stitched_image(img, cal, km)

        result = _match_notes(detected, placed)
        assert len(result['matched']) == 3, \
            f"Missing: {[s.key_name for s in result['missing']]}"


class TestAdjacentKeyOverlap:
    """
    Bug (2): C C# C C# patterns —- adjacent keys overlap slightly in X.
    The per-key column scanner should detect each as a separate note.
    """

    def test_c_and_csharp_simultaneous(self):
        """C and C# playing at the same time should be 2 separate notes."""
        specs = [
            NoteSpec('C4', y=100, height=80, hand='right_hand'),
            NoteSpec('C#4', y=100, height=80, hand='right_hand'),
        ]
        img, cal, km, placed = build_synthetic_stitched_image(specs)
        detected = detect_notes_on_stitched_image(img, cal, km)

        result = _match_notes(detected, placed)
        assert len(result['matched']) == 2, \
            f"Missing: {[s.key_name for s in result['missing']]}"

    def test_c_csharp_alternating_sequence(self):
        """C C# C C# C C# — 6 separate notes at different Y positions."""
        specs = []
        for i in range(6):
            key = 'C4' if i % 2 == 0 else 'C#4'
            specs.append(NoteSpec(key, y=50 + i * 100, height=60,
                                  hand='right_hand'))

        img, cal, km, placed = build_synthetic_stitched_image(
            specs, note_area_height=800,
        )
        detected = detect_notes_on_stitched_image(img, cal, km)

        c_notes = [d for d in detected if d.key_name == 'C4']
        cs_notes = [d for d in detected if d.key_name == 'C#4']
        assert len(c_notes) == 3, f"Expected 3 C4, got {len(c_notes)}"
        assert len(cs_notes) == 3, f"Expected 3 C#4, got {len(cs_notes)}"

    def test_chromatic_run(self):
        """C C# D D# E — 5 adjacent notes, all separate."""
        keys = ['C4', 'C#4', 'D4', 'D#4', 'E4']
        specs = [NoteSpec(k, y=100, height=60, hand='right_hand') for k in keys]
        img, cal, km, placed = build_synthetic_stitched_image(specs)
        detected = detect_notes_on_stitched_image(img, cal, km)

        result = _match_notes(detected, placed)
        assert len(result['matched']) == 5, \
            f"Missing: {[s.key_name for s in result['missing']]}"

    def test_g_gsharp_adjacent(self):
        """G and G# (the original bug from the screenshots)."""
        specs = [
            NoteSpec('G4', y=100, height=80, hand='right_hand'),
            NoteSpec('G#4', y=100, height=80, hand='right_hand'),
        ]
        img, cal, km, placed = build_synthetic_stitched_image(specs)
        detected = detect_notes_on_stitched_image(img, cal, km)

        result = _match_notes(detected, placed)
        assert len(result['matched']) == 2

    def test_three_adjacent_keys_staggered(self):
        """A A# B — three adjacent keys, played at different (non-overlapping)
        times so their note boxes are stacked vertically but never overlap in Y.
        The tricky part: A#4 is a black key whose column zone sits between A4
        and B4.  All three must be detected independently."""
        specs = [
            NoteSpec('A4',  y=100, height=80,  hand='right_hand'),
            NoteSpec('A#4', y=230, height=60,  hand='right_hand'),
            NoteSpec('B4',  y=350, height=100, hand='right_hand'),
        ]
        img, cal, km, placed = build_synthetic_stitched_image(specs)
        detected = detect_notes_on_stitched_image(img, cal, km)

        result = _match_notes(detected, placed)
        assert len(result['matched']) == 3


class TestSameKeyRepeatedNotes:
    """Multiple notes on the SAME key at different times (vertical stacking)."""

    def test_two_notes_same_key_with_gap(self):
        """Two C4 notes with a gap between them."""
        specs = [
            NoteSpec('C4', y=100, height=60, hand='right_hand'),
            NoteSpec('C4', y=250, height=60, hand='right_hand'),
        ]
        img, cal, km, placed = build_synthetic_stitched_image(specs)
        detected = detect_notes_on_stitched_image(img, cal, km)

        c_notes = [d for d in detected if d.key_name == 'C4']
        assert len(c_notes) == 2, f"Expected 2 C4, got {len(c_notes)}"

    def test_three_rapid_repeated_notes(self):
        """Three quick C4 taps with small gaps."""
        gap = 30  # pixels between notes
        specs = [
            NoteSpec('C4', y=100, height=40, hand='right_hand'),
            NoteSpec('C4', y=100 + 40 + gap, height=40, hand='right_hand'),
            NoteSpec('C4', y=100 + 2 * (40 + gap), height=40, hand='right_hand'),
        ]
        img, cal, km, placed = build_synthetic_stitched_image(specs)
        detected = detect_notes_on_stitched_image(img, cal, km)

        c_notes = [d for d in detected if d.key_name == 'C4']
        assert len(c_notes) == 3, f"Expected 3 C4, got {len(c_notes)}"


class TestVisualEffects:
    """
    Notes with various visual effects (glow, gradient, labels) should
    still be detected correctly.
    """

    def test_glow_effect(self):
        """Glow halo around a note should not create false detections."""
        specs = [
            NoteSpec('D4', y=100, height=80, hand='right_hand', glow=True),
            NoteSpec('A4', y=100, height=80, hand='right_hand', glow=True),
        ]
        img, cal, km, placed = build_synthetic_stitched_image(specs)
        detected = detect_notes_on_stitched_image(img, cal, km)

        result = _match_notes(detected, placed)
        assert len(result['matched']) == 2

    def test_gradient_note(self):
        """Gradient-shaded notes should still be detected."""
        specs = [
            NoteSpec('E4', y=100, height=120, hand='right_hand', gradient=True),
        ]
        img, cal, km, placed = build_synthetic_stitched_image(specs)
        detected = detect_notes_on_stitched_image(img, cal, km)

        result = _match_notes(detected, placed)
        assert len(result['matched']) == 1

    def test_glow_and_gradient_combined(self):
        specs = [
            NoteSpec('F4', y=100, height=100, hand='right_hand',
                     glow=True, gradient=True),
            NoteSpec('G4', y=100, height=100, hand='left_hand',
                     glow=True, gradient=True),
        ]
        img, cal, km, placed = build_synthetic_stitched_image(specs)
        detected = detect_notes_on_stitched_image(img, cal, km)

        result = _match_notes(detected, placed)
        assert len(result['matched']) == 2


class TestMultipleThemes:
    """
    Run the same test scenario across all colour themes to ensure the
    detector works with different video styles.
    """

    @pytest.mark.parametrize("theme_fn", ALL_THEMES,
                             ids=['purple_green', 'blue_orange', 'pink_cyan'])
    def test_basic_chord_all_themes(self, theme_fn):
        """A simple chord detected correctly across all colour themes."""
        specs = [
            NoteSpec('C4', y=100, height=80, hand='right_hand'),
            NoteSpec('E4', y=100, height=80, hand='right_hand'),
            NoteSpec('G4', y=100, height=80, hand='right_hand'),
        ]
        img, cal, km, placed = build_synthetic_stitched_image(
            specs, theme_fn=theme_fn,
        )
        detected = detect_notes_on_stitched_image(img, cal, km)

        result = _match_notes(detected, placed)
        assert len(result['matched']) == 3, \
            f"Theme {theme_fn.__name__}: missing {[s.key_name for s in result['missing']]}"

    @pytest.mark.parametrize("theme_fn", ALL_THEMES,
                             ids=['purple_green', 'blue_orange', 'pink_cyan'])
    def test_black_key_with_label_all_themes(self, theme_fn):
        """Black-key notes with labels across all themes."""
        specs = [
            NoteSpec('C#4', y=50, height=120, hand='right_hand', label='C#'),
            NoteSpec('G#4', y=50, height=120, hand='left_hand', label='G#'),
        ]
        img, cal, km, placed = build_synthetic_stitched_image(
            specs, theme_fn=theme_fn,
        )
        detected = detect_notes_on_stitched_image(img, cal, km)

        result = _match_notes(detected, placed)
        assert len(result['matched']) == 2

    @pytest.mark.parametrize("theme_fn", ALL_THEMES,
                             ids=['purple_green', 'blue_orange', 'pink_cyan'])
    def test_adjacent_c_csharp_all_themes(self, theme_fn):
        """C/C# overlap test across all themes."""
        specs = [
            NoteSpec('C4', y=100, height=80, hand='right_hand'),
            NoteSpec('C#4', y=100, height=80, hand='right_hand'),
        ]
        img, cal, km, placed = build_synthetic_stitched_image(
            specs, theme_fn=theme_fn,
        )
        detected = detect_notes_on_stitched_image(img, cal, km)

        result = _match_notes(detected, placed)
        assert len(result['matched']) == 2, \
            f"Theme {theme_fn.__name__}: missing {[s.key_name for s in result['missing']]}"


class TestDifferentKeyWidths:
    """
    Different videos have different keyboard sizes  (wider or narrower keys).
    Test detection with various key widths.
    """

    @pytest.mark.parametrize("wkw", [30, 40, 55, 70])
    def test_varying_key_widths(self, wkw):
        """Detection should work across a range of key widths."""
        specs = [
            NoteSpec('C4', y=100, height=80, hand='right_hand'),
            NoteSpec('F#4', y=100, height=80, hand='right_hand'),
            NoteSpec('A4', y=200, height=60, hand='left_hand'),
        ]
        img, cal, km, placed = build_synthetic_stitched_image(
            specs, white_key_width=float(wkw),
        )
        detected = detect_notes_on_stitched_image(img, cal, km)

        result = _match_notes(detected, placed)
        assert len(result['matched']) == 3, \
            f"key_width={wkw}: missing {[s.key_name for s in result['missing']]}"


class TestComplexScenarios:
    """Realistic multi-note patterns that exercise many edge cases at once."""

    def test_chord_with_bass(self):
        """RH chord (C E G) + LH bass (C3) — different hands."""
        specs = [
            NoteSpec('C4', y=100, height=60, hand='right_hand'),
            NoteSpec('E4', y=100, height=60, hand='right_hand'),
            NoteSpec('G4', y=100, height=60, hand='right_hand'),
            NoteSpec('C3', y=100, height=120, hand='left_hand'),
        ]
        img, cal, km, placed = build_synthetic_stitched_image(specs)
        detected = detect_notes_on_stitched_image(img, cal, km)

        result = _match_notes(detected, placed)
        assert len(result['matched']) == 4

    def test_melody_with_staccato(self):
        """Short notes in succession on different keys."""
        notes = ['C4', 'D4', 'E4', 'F4', 'G4', 'A4', 'B4', 'C5']
        specs = [
            NoteSpec(n, y=50 + i * 80, height=40, hand='right_hand')
            for i, n in enumerate(notes)
        ]
        img, cal, km, placed = build_synthetic_stitched_image(
            specs, note_area_height=800,
        )
        detected = detect_notes_on_stitched_image(img, cal, km)

        result = _match_notes(detected, placed)
        assert len(result['matched']) == 8, \
            f"Missing: {[s.key_name for s in result['missing']]}"

    def test_chromatic_scale_with_labels(self):
        """Full chromatic scale C4..B4 with text labels and glow."""
        keys = ['C4', 'C#4', 'D4', 'D#4', 'E4', 'F4', 'F#4', 'G4',
                'G#4', 'A4', 'A#4', 'B4']
        specs = [
            NoteSpec(k, y=50 + i * 100, height=60, hand='right_hand',
                     label=k, glow=(i % 3 == 0))
            for i, k in enumerate(keys)
        ]
        img, cal, km, placed = build_synthetic_stitched_image(
            specs, note_area_height=1500,
        )
        detected = detect_notes_on_stitched_image(img, cal, km)

        result = _match_notes(detected, placed)
        assert len(result['matched']) >= 11, \
            f"Detected {len(result['matched'])}/12, " \
            f"missing: {[s.key_name for s in result['missing']]}"

    def test_sustained_note_with_staccato_overlay(self):
        """A long LH sustained note with short RH notes on nearby keys."""
        specs = [
            NoteSpec('C3', y=50, height=500, hand='left_hand'),
            NoteSpec('G4', y=100, height=40, hand='right_hand'),
            NoteSpec('E4', y=200, height=40, hand='right_hand'),
            NoteSpec('C4', y=300, height=40, hand='right_hand'),
        ]
        img, cal, km, placed = build_synthetic_stitched_image(
            specs, note_area_height=700,
        )
        detected = detect_notes_on_stitched_image(img, cal, km)

        result = _match_notes(detected, placed)
        assert len(result['matched']) == 4

    def test_dense_pattern_both_hands(self):
        """Dense pattern: many notes, both hands, some adjacent keys."""
        specs = [
            # RH melody
            NoteSpec('G4', y=50, height=80, hand='right_hand'),
            NoteSpec('B4', y=50, height=80, hand='right_hand'),
            NoteSpec('A4', y=150, height=60, hand='right_hand'),
            NoteSpec('G4', y=230, height=60, hand='right_hand'),
            NoteSpec('F#4', y=230, height=60, hand='right_hand'),
            # LH chords
            NoteSpec('G3', y=50, height=200, hand='left_hand'),
            NoteSpec('D3', y=50, height=200, hand='left_hand'),
            NoteSpec('B3', y=50, height=200, hand='left_hand'),
        ]
        img, cal, km, placed = build_synthetic_stitched_image(
            specs, note_area_height=500,
        )
        detected = detect_notes_on_stitched_image(img, cal, km)

        result = _match_notes(detected, placed)
        assert len(result['matched']) >= 7, \
            f"Missing: {[s.key_name for s in result['missing']]}"

    def test_all_effects_combined(self):
        """Notes with mixed effects: glow, gradient, labels, thick keys."""
        specs = [
            NoteSpec('C4', y=100, height=100, hand='right_hand',
                     label='C4', glow=True, gradient=True),
            NoteSpec('F#4', y=100, height=100, hand='right_hand',
                     label='F#', glow=True),
            NoteSpec('A3', y=100, height=200, hand='left_hand',
                     label='A', gradient=True),
        ]
        img, cal, km, placed = build_synthetic_stitched_image(
            specs, white_key_width=50.0,
        )
        detected = detect_notes_on_stitched_image(img, cal, km)

        result = _match_notes(detected, placed)
        assert len(result['matched']) == 3

    def test_notes_near_top_and_bottom_of_image(self):
        """Notes very close to the edges of the note area."""
        specs = [
            NoteSpec('C4', y=2, height=40, hand='right_hand'),       # near top
            NoteSpec('E4', y=950, height=40, hand='right_hand'),     # near bottom
        ]
        img, cal, km, placed = build_synthetic_stitched_image(
            specs, note_area_height=1000,
        )
        detected = detect_notes_on_stitched_image(img, cal, km)

        result = _match_notes(detected, placed)
        assert len(result['matched']) == 2

    def test_very_short_note(self):
        """Very short note (staccato) should be detected if above min_height."""
        specs = [NoteSpec('D4', y=100, height=12, hand='right_hand')]
        img, cal, km, placed = build_synthetic_stitched_image(specs)
        detected = detect_notes_on_stitched_image(img, cal, km)

        d_notes = [d for d in detected if d.key_name == 'D4']
        assert len(d_notes) == 1

    def test_very_long_sustained_note(self):
        """A very long sustained note should be one detection, not split."""
        specs = [NoteSpec('G3', y=50, height=1500, hand='left_hand')]
        img, cal, km, placed = build_synthetic_stitched_image(
            specs, note_area_height=1800,
        )
        detected = detect_notes_on_stitched_image(img, cal, km)

        g_notes = [d for d in detected if d.key_name == 'G3'
                   and d.hand == 'left_hand']
        assert len(g_notes) == 1, \
            f"Expected 1 long G3, got {len(g_notes)} (was it split?)"


class TestDeduplication:
    """
    Deduplication edge cases.  NOTE: glow effects only appear at the bottom
    of the screen when a note physically hits the piano keyboard — they are
    NOT present in the stitched note-roll body.  Tests here therefore use
    plain (non-glowing) notes.
    """

    def test_pixel_spill_adjacent_black_key(self):
        """A wide white key note whose rendered box slightly overlaps the owned
        column of an adjacent black key should NOT produce a ghost black-key
        detection."""
        specs = [
            NoteSpec('D4', y=100, height=100, hand='right_hand'),
        ]
        img, cal, km, placed = build_synthetic_stitched_image(specs)
        detected = detect_notes_on_stitched_image(img, cal, km)

        d_notes  = [d for d in detected if d.key_name == 'D4']
        ghosts   = [d for d in detected if d.key_name in ('C#4', 'D#4')]
        assert len(d_notes) == 1, f"Expected D4, got {[d.key_name for d in detected]}"
        assert len(ghosts)  == 0, \
            f"Ghost black-key detections: {[d.key_name for d in ghosts]}"
