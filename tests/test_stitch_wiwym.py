"""
Tests for stitch_song end-to-end correctness using
music/when_i_was_your_man/video.webm.

These tests verify that the stitching pipeline produces deterministic,
correct results for a second video, including proper black-key note
detection.  They require the real video file to be present.
"""
import hashlib
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from stitch_song import stitch_song, StitchResult

WIWYM_VIDEO = os.path.join(
    os.path.dirname(__file__), "..", "music", "when_i_was_your_man", "video.webm"
)

needs_video = pytest.mark.skipif(
    not os.path.isfile(WIWYM_VIDEO),
    reason="music/when_i_was_your_man/video.webm not present",
)


@pytest.fixture(scope="module")
def wiwym_result() -> StitchResult:
    """Run stitch_song once for all tests in this module."""
    return stitch_song(WIWYM_VIDEO, stitch_fps=10, verbose=False)


# ── Image shape & basic properties ─────────────────────────────────


@needs_video
def test_stitched_image_shape(wiwym_result: StitchResult):
    """Stitched image must have the expected dimensions."""
    h, w, c = wiwym_result.image.shape
    assert w == 1920, f"Expected width 1920, got {w}"
    assert c == 3, f"Expected 3 channels, got {c}"
    assert 70000 < h < 76000, f"Height {h} outside expected range"


@needs_video
def test_stitched_image_exact_height(wiwym_result: StitchResult):
    """Height must be exactly 72604 at 10 fps."""
    assert wiwym_result.image.shape[0] == 72604


@needs_video
def test_image_dtype(wiwym_result: StitchResult):
    assert wiwym_result.image.dtype == np.uint8


# ── Calibration ────────────────────────────────────────────────────


@needs_video
def test_calibration_keyboard_y(wiwym_result: StitchResult):
    assert wiwym_result.calibration.keyboard_y == 406


@needs_video
def test_calibration_keyboard_height(wiwym_result: StitchResult):
    assert wiwym_result.calibration.keyboard_height == 672


@needs_video
def test_calibration_scroll_speed(wiwym_result: StitchResult):
    assert abs(wiwym_result.calibration.scroll_speed - 258.0) < 1.0


@needs_video
def test_calibration_intro_end(wiwym_result: StitchResult):
    assert abs(wiwym_result.calibration.intro_end_time - 5.5) < 0.5


# ── Keyboard map ───────────────────────────────────────────────────


@needs_video
def test_keyboard_map_count(wiwym_result: StitchResult):
    """Keyboard map should find 37 keys for this video."""
    assert len(wiwym_result.keyboard_map) == 37


@needs_video
def test_keyboard_map_ordering(wiwym_result: StitchResult):
    """Keys should be ordered left-to-right by x position."""
    xs = [k.center_x for k in wiwym_result.keyboard_map]
    assert xs == sorted(xs), "Keyboard keys not in left-to-right order"


# ── Note detection ─────────────────────────────────────────────────


@needs_video
def test_note_count_range(wiwym_result: StitchResult):
    """Should detect a reasonable number of notes."""
    n = len(wiwym_result.notes)
    assert 550 < n < 750, f"Note count {n} outside expected range"


@needs_video
def test_note_count_exact(wiwym_result: StitchResult):
    """Exact note count at 10 fps."""
    assert len(wiwym_result.notes) == 632


@needs_video
def test_notes_have_hands(wiwym_result: StitchResult):
    hands = {n.hand for n in wiwym_result.notes}
    assert 'right_hand' in hands
    assert 'left_hand' in hands


@needs_video
def test_note_hand_split(wiwym_result: StitchResult):
    rh = sum(1 for n in wiwym_result.notes if n.hand == 'right_hand')
    lh = sum(1 for n in wiwym_result.notes if n.hand == 'left_hand')
    assert rh == 542
    assert lh == 90


@needs_video
def test_black_key_notes_detected(wiwym_result: StitchResult):
    """Black key notes must be detected (regression test for fix)."""
    bk = sum(1 for n in wiwym_result.notes if n.is_black)
    assert bk == 213


@needs_video
def test_black_key_pitches(wiwym_result: StitchResult):
    """Should detect notes on the expected black keys."""
    bk_pitches = sorted({n.key_name for n in wiwym_result.notes if n.is_black})
    expected = ['A#4', 'A#5', 'C#5', 'C#6', 'D#5', 'F#4', 'F#5', 'G#4', 'G#5']
    assert bk_pitches == expected


@needs_video
def test_notes_have_valid_keys(wiwym_result: StitchResult):
    """All notes should map to known key names."""
    valid_notes = {'C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'}
    for note in wiwym_result.notes:
        pitch = note.key_name[:-1] if note.key_name[-1].isdigit() else note.key_name
        assert pitch in valid_notes, f"Invalid note name: {note.key_name}"


@needs_video
def test_notes_unique_pitches(wiwym_result: StitchResult):
    """Should detect the expected set of unique pitches."""
    unique = sorted({n.key_name for n in wiwym_result.notes})
    expected = [
        'A#4', 'A#5', 'A3', 'A4', 'A5', 'B3', 'B4', 'B5',
        'C#5', 'C#6', 'C4', 'C5', 'C6', 'D#5', 'D4', 'D5',
        'E4', 'E5', 'F#4', 'F#5', 'F3', 'F4', 'F5',
        'G#4', 'G#5', 'G3', 'G4', 'G5',
    ]
    assert unique == expected


# ── Pixel-level determinism ────────────────────────────────────────


@needs_video
def test_deterministic_output():
    """Running stitch_song twice must produce identical results."""
    r1 = stitch_song(WIWYM_VIDEO, stitch_fps=10, verbose=False)
    r2 = stitch_song(WIWYM_VIDEO, stitch_fps=10, verbose=False)

    assert r1.image.shape == r2.image.shape
    assert np.array_equal(r1.image, r2.image), "Stitched images differ between runs"
    assert len(r1.notes) == len(r2.notes), (
        f"Note count changed: {len(r1.notes)} vs {len(r2.notes)}"
    )


# ── Pixel content checks ──────────────────────────────────────────


@needs_video
def test_keyboard_region_is_bright(wiwym_result: StitchResult):
    """Bottom of the image (keyboard) should contain bright (white key) pixels."""
    img = wiwym_result.image
    kb_h = wiwym_result.calibration.keyboard_height
    kb_region = img[-kb_h:, :, :]
    mean_val = kb_region.mean()
    assert mean_val > 30, f"Keyboard region too dark: mean={mean_val:.1f}"


@needs_video
def test_top_region_has_content(wiwym_result: StitchResult):
    """Top of the image should have some note content (not all black)."""
    img = wiwym_result.image
    top_region = img[:500, :, :]
    mean_val = top_region.mean()
    assert mean_val > 5, f"Top region suspiciously dark: mean={mean_val:.1f}"


@needs_video
def test_image_hash_stable(wiwym_result: StitchResult):
    """Record the image hash so we detect any future regressions."""
    h = hashlib.sha256(wiwym_result.image.tobytes()).hexdigest()
    expected = "7c441bf88d7bd1541037b42f06e8b719b6fc6f1163bd1936969d164e3c1f4d8a"
    assert h == expected, f"Image hash changed: {h}"
