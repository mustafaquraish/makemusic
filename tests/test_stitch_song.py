"""
Tests for stitch_song end-to-end correctness using music/perfect/video.webm.

These tests verify that the stitching pipeline produces deterministic,
correct results.  They require the real video file to be present.
"""
import hashlib
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from stitch_song import stitch_song, StitchResult

PERFECT_VIDEO = os.path.join(
    os.path.dirname(__file__), "..", "music", "perfect", "video.webm"
)

needs_video = pytest.mark.skipif(
    not os.path.isfile(PERFECT_VIDEO),
    reason="music/perfect/video.webm not present",
)


@pytest.fixture(scope="module")
def perfect_result() -> StitchResult:
    """Run stitch_song once for all tests in this module."""
    return stitch_song(PERFECT_VIDEO, stitch_fps=10, verbose=False)


# ── Image shape & basic properties ─────────────────────────────────


@needs_video
def test_stitched_image_shape(perfect_result: StitchResult):
    """Stitched image must have the expected dimensions."""
    h, w, c = perfect_result.image.shape
    assert w == 1920, f"Expected width 1920, got {w}"
    assert c == 3, f"Expected 3 channels, got {c}"
    # Height should be ~62k pixels (initial_area + strips + keyboard)
    assert 60000 < h < 65000, f"Height {h} outside expected range"


@needs_video
def test_stitched_image_exact_height(perfect_result: StitchResult):
    """Height must be exactly 62375 at 10 fps."""
    assert perfect_result.image.shape[0] == 62375


@needs_video
def test_image_dtype(perfect_result: StitchResult):
    assert perfect_result.image.dtype == np.uint8


# ── Calibration ────────────────────────────────────────────────────


@needs_video
def test_calibration_keyboard_y(perfect_result: StitchResult):
    assert perfect_result.calibration.keyboard_y == 653


@needs_video
def test_calibration_keyboard_height(perfect_result: StitchResult):
    assert perfect_result.calibration.keyboard_height == 423


@needs_video
def test_calibration_scroll_speed(perfect_result: StitchResult):
    assert abs(perfect_result.calibration.scroll_speed - 242.0) < 1.0


@needs_video
def test_calibration_intro_end(perfect_result: StitchResult):
    assert abs(perfect_result.calibration.intro_end_time - 7.0) < 0.5


# ── Keyboard map ───────────────────────────────────────────────────


@needs_video
def test_keyboard_map_count(perfect_result: StitchResult):
    """Keyboard map should find 37 keys for this video."""
    assert len(perfect_result.keyboard_map) == 37


@needs_video
def test_keyboard_map_ordering(perfect_result: StitchResult):
    """Keys should be ordered left-to-right by x position."""
    xs = [k.center_x for k in perfect_result.keyboard_map]
    assert xs == sorted(xs), "Keyboard keys not in left-to-right order"


# ── Note detection ─────────────────────────────────────────────────


@needs_video
def test_note_count_range(perfect_result: StitchResult):
    """Should detect a reasonable number of notes."""
    n = len(perfect_result.notes)
    assert 350 < n < 500, f"Note count {n} outside expected range"


@needs_video
def test_note_count_exact(perfect_result: StitchResult):
    """Exact note count at 10 fps."""
    assert len(perfect_result.notes) == 412


@needs_video
def test_notes_have_hands(perfect_result: StitchResult):
    hands = {n.hand for n in perfect_result.notes}
    assert 'right_hand' in hands
    assert 'left_hand' in hands


@needs_video
def test_note_hand_split(perfect_result: StitchResult):
    rh = sum(1 for n in perfect_result.notes if n.hand == 'right_hand')
    lh = sum(1 for n in perfect_result.notes if n.hand == 'left_hand')
    assert rh == 312
    assert lh == 100


@needs_video
def test_notes_have_valid_keys(perfect_result: StitchResult):
    """All notes should map to known key names."""
    valid_notes = {'C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'}
    for note in perfect_result.notes:
        # key_name is like "G4", "F#3" etc.
        pitch = note.key_name[:-1] if note.key_name[-1].isdigit() else note.key_name
        assert pitch in valid_notes, f"Invalid note name: {note.key_name}"


@needs_video
def test_notes_unique_pitches(perfect_result: StitchResult):
    """Should detect the expected set of unique pitches."""
    unique = sorted({n.key_name for n in perfect_result.notes})
    expected = ['A3', 'A4', 'B4', 'C3', 'C5', 'D3', 'D4', 'D5',
                'E3', 'E4', 'E5', 'F#4', 'F#5', 'G3', 'G4', 'G5']
    assert unique == expected


# ── Pixel-level determinism ────────────────────────────────────────


@needs_video
def test_deterministic_output():
    """Running stitch_song twice must produce identical results."""
    r1 = stitch_song(PERFECT_VIDEO, stitch_fps=10, verbose=False)
    r2 = stitch_song(PERFECT_VIDEO, stitch_fps=10, verbose=False)

    assert r1.image.shape == r2.image.shape
    assert np.array_equal(r1.image, r2.image), "Stitched images differ between runs"
    assert len(r1.notes) == len(r2.notes), f"Note count changed: {len(r1.notes)} vs {len(r2.notes)}"


# ── Pixel content checks ──────────────────────────────────────────


@needs_video
def test_keyboard_region_is_bright(perfect_result: StitchResult):
    """Bottom of the image (keyboard) should contain bright (white key) pixels."""
    img = perfect_result.image
    kb_h = perfect_result.calibration.keyboard_height
    kb_region = img[-kb_h:, :, :]
    mean_val = kb_region.mean()
    # Keyboard has white keys → should be reasonably bright
    assert mean_val > 80, f"Keyboard region too dark: mean={mean_val:.1f}"


@needs_video
def test_top_region_has_content(perfect_result: StitchResult):
    """Top of the image should have some note content (not all black)."""
    img = perfect_result.image
    top_region = img[:500, :, :]
    mean_val = top_region.mean()
    assert mean_val > 5, f"Top region suspiciously dark: mean={mean_val:.1f}"


@needs_video
def test_image_hash_stable(perfect_result: StitchResult):
    """Record the image hash so we detect any future regressions."""
    h = hashlib.sha256(perfect_result.image.tobytes()).hexdigest()
    # This value was recorded from a known-good run at 10 fps.
    # If this test fails, the stitching algorithm has changed its output.
    # Update the hash after verifying the new output is correct.
    expected = "1615c120485fc2973002212ddc6c03e2c183a11a736dd876244a56bef5f2b36c"
    assert h == expected, f"Image hash changed: {h}"
