"""
Tests for stitch_song end-to-end correctness using
music/river_flows_in_you/video.webm.

These tests verify correct detection of the A-G#-A alternation
pattern (no merging of adjacent notes) and absence of boundary
artifacts.
"""
import hashlib
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from stitch_song import stitch_song, StitchResult

RIVER_VIDEO = os.path.join(
    os.path.dirname(__file__), "..", "music", "river_flows_in_you", "video.webm"
)

needs_video = pytest.mark.skipif(
    not os.path.isfile(RIVER_VIDEO),
    reason="music/river_flows_in_you/video.webm not present",
)


@pytest.fixture(scope="module")
def river_result() -> StitchResult:
    """Run stitch_song once for all tests in this module."""
    return stitch_song(RIVER_VIDEO, stitch_fps=10, verbose=False)


# ── Image shape & basic properties ─────────────────────────────────


@needs_video
def test_stitched_image_shape(river_result: StitchResult):
    h, w, c = river_result.image.shape
    assert w == 1920
    assert c == 3
    assert 60000 < h < 67000


@needs_video
def test_stitched_image_exact_height(river_result: StitchResult):
    assert river_result.image.shape[0] == 63441


@needs_video
def test_image_dtype(river_result: StitchResult):
    assert river_result.image.dtype == np.uint8


# ── Calibration ────────────────────────────────────────────────────


@needs_video
def test_calibration_keyboard_y(river_result: StitchResult):
    assert river_result.calibration.keyboard_y == 763


@needs_video
def test_calibration_keyboard_height(river_result: StitchResult):
    assert river_result.calibration.keyboard_height == 316


@needs_video
def test_calibration_scroll_speed(river_result: StitchResult):
    assert abs(river_result.calibration.scroll_speed - 224.0) < 1.0


@needs_video
def test_calibration_intro_end(river_result: StitchResult):
    assert abs(river_result.calibration.intro_end_time - 6.0) < 0.5


# ── Keyboard map ───────────────────────────────────────────────────


@needs_video
def test_keyboard_map_count(river_result: StitchResult):
    assert len(river_result.keyboard_map) == 54


@needs_video
def test_keyboard_map_ordering(river_result: StitchResult):
    xs = [k.center_x for k in river_result.keyboard_map]
    assert xs == sorted(xs)


# ── Note detection ─────────────────────────────────────────────────


@needs_video
def test_note_count_exact(river_result: StitchResult):
    assert len(river_result.notes) == 530


@needs_video
def test_notes_have_hands(river_result: StitchResult):
    hands = {n.hand for n in river_result.notes}
    assert 'right_hand' in hands
    assert 'left_hand' in hands


@needs_video
def test_note_hand_split(river_result: StitchResult):
    rh = sum(1 for n in river_result.notes if n.hand == 'right_hand')
    lh = sum(1 for n in river_result.notes if n.hand == 'left_hand')
    assert rh == 437
    assert lh == 93


@needs_video
def test_black_key_notes_detected(river_result: StitchResult):
    bk = sum(1 for n in river_result.notes if n.is_black)
    assert bk == 151


# ── A-G# merging regression test ──────────────────────────────────
#    River Flows in You has rapid A-G#-A alternation.  Previously
#    these were merged into giant 3+ second notes.  This must not
#    happen.


@needs_video
def test_no_merged_a5_notes(river_result: StitchResult):
    """A5 notes must not be merged across G# transitions (regression)."""
    cal = river_result.calibration
    a5_notes = [n for n in river_result.notes if n.key_name == 'A5']
    for n in a5_notes:
        dur = n.height / cal.scroll_speed
        assert dur < 3.0, (
            f"A5 note at y={n.y} has duration {dur:.2f}s — likely a "
            f"merged A-G#-A sequence"
        )


@needs_video
def test_separate_gsharp5_notes(river_result: StitchResult):
    """G#5 notes should exist as separate individual detections."""
    gs5 = [n for n in river_result.notes if n.key_name == 'G#5']
    assert len(gs5) >= 10, (
        f"Only {len(gs5)} G#5 notes detected — expected many more "
        f"individual G#5 notes in the A-G#-A pattern"
    )


@needs_video
def test_gsharp_notes_reasonable_duration(river_result: StitchResult):
    """G#5 notes should not be unreasonably long (merged)."""
    cal = river_result.calibration
    gs5 = [n for n in river_result.notes if n.key_name == 'G#5']
    for n in gs5:
        dur = n.height / cal.scroll_speed
        assert dur < 3.0, (
            f"G#5 note at y={n.y} has duration {dur:.2f}s — likely merged"
        )


# ── Boundary artifact filter ──────────────────────────────────────


@needs_video
def test_no_boundary_artifacts(river_result: StitchResult):
    """No tiny notes should appear right at the keyboard boundary."""
    note_area_bottom = (river_result.image.shape[0]
                        - river_result.calibration.keyboard_height)
    boundary_buffer = 20
    short_threshold = 20
    boundary_notes = [
        n for n in river_result.notes
        if n.y + n.height > note_area_bottom - boundary_buffer
        and n.height < short_threshold
    ]
    assert len(boundary_notes) == 0, (
        f"Found {len(boundary_notes)} tiny notes near keyboard boundary"
    )


@needs_video
def test_notes_have_valid_keys(river_result: StitchResult):
    valid = {'C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'}
    for note in river_result.notes:
        pitch = note.key_name[:-1] if note.key_name[-1].isdigit() else note.key_name
        assert pitch in valid, f"Invalid note name: {note.key_name}"


# ── Pixel-level determinism ────────────────────────────────────────


@needs_video
def test_image_hash_stable(river_result: StitchResult):
    h = hashlib.sha256(river_result.image.tobytes()).hexdigest()
    expected = "15c79f3533f1fbecc0f931b9a9728fde1cef85a92801279a135f4db354af6ef2"
    assert h == expected, f"Image hash changed: {h}"
