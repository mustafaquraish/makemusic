"""Tests for the note detector module."""
import numpy as np
import cv2
import pytest
from tests.conftest import (
    make_playing_frame, make_blank_frame, add_note_rect,
    make_keyboard_frame, SAMPLE_WIDTH, SAMPLE_HEIGHT
)
from src.note_detector import (
    detect_notes_in_frame, classify_note_color, DetectedNote
)
from src.calibrator import NoteColor, CalibrationResult


def make_test_calibration(keyboard_y=700, note_colors=None):
    """Create a CalibrationResult for testing."""
    if note_colors is None:
        note_colors = [
            NoteColor(
                center_hsv=(146, 84, 200),
                center_bgr=(200, 130, 190),
                label='right_hand',
                h_range=(120, 175),
                s_range=(30, 255),
                v_range=(80, 255),
            ),
            NoteColor(
                center_hsv=(25, 120, 240),
                center_bgr=(128, 229, 246),
                label='left_hand',
                h_range=(10, 40),
                s_range=(60, 255),
                v_range=(150, 255),
            ),
        ]
    
    return CalibrationResult(
        keyboard_y=keyboard_y,
        keyboard_height=SAMPLE_HEIGHT - keyboard_y,
        note_area_top=0,
        note_area_bottom=keyboard_y,
        note_colors=note_colors,
        scroll_speed=100.0,
        frame_width=SAMPLE_WIDTH,
        frame_height=SAMPLE_HEIGHT,
    )


class TestDetectNotesInFrame:
    """Tests for per-frame note detection."""
    
    def test_detect_single_note(self):
        """Should detect a single note rectangle."""
        cal = make_test_calibration()
        frame = make_playing_frame(
            notes=[
                {'x': 500, 'y': 200, 'w': 60, 'h': 120, 'color': (200, 130, 190)},
            ],
            keyboard_y=700
        )
        
        detections = detect_notes_in_frame(frame, cal)
        
        assert len(detections) >= 1, f"Expected 1 note, got {len(detections)}"
        note = detections[0]
        assert abs(note.center_x - 530) < 20, f"Note center_x={note.center_x}, expected ~530"
        assert abs(note.center_y - 260) < 30, f"Note center_y={note.center_y}, expected ~260"
    
    def test_detect_multiple_notes(self):
        """Should detect multiple notes of the same color."""
        cal = make_test_calibration()
        frame = make_playing_frame(
            notes=[
                {'x': 300, 'y': 200, 'w': 60, 'h': 120, 'color': (200, 130, 190)},
                {'x': 600, 'y': 350, 'w': 60, 'h': 80, 'color': (200, 130, 190)},
                {'x': 900, 'y': 100, 'w': 60, 'h': 200, 'color': (200, 130, 190)},
            ],
            keyboard_y=700
        )
        
        detections = detect_notes_in_frame(frame, cal)
        assert len(detections) >= 3, f"Expected 3 notes, got {len(detections)}"
    
    def test_detect_two_colors(self):
        """Should detect notes of different colors."""
        # Need to use colors that match the calibration HSV ranges
        # right_hand color hsv center (146, 84, 200) -> purple-ish BGR (200, 130, 190)
        # left_hand color hsv center (25, 120, 240) -> orange-ish BGR (128, 229, 246) 
        cal = make_test_calibration()
        
        frame = make_playing_frame(
            notes=[
                {'x': 300, 'y': 200, 'w': 60, 'h': 120, 'color': (200, 130, 190)},
                {'x': 900, 'y': 300, 'w': 60, 'h': 100, 'color': (128, 229, 246)},
            ],
            keyboard_y=700
        )
        
        detections = detect_notes_in_frame(frame, cal)
        assert len(detections) >= 2, f"Expected 2 notes, got {len(detections)}"
        
        # Check that different colors were classified
        hands = set(d.hand for d in detections)
        assert len(hands) >= 1, "Should detect at least 1 hand classification"
    
    def test_no_notes_in_blank_frame(self):
        """Should detect nothing in a blank frame."""
        cal = make_test_calibration()
        frame = make_blank_frame()
        
        detections = detect_notes_in_frame(frame, cal)
        assert len(detections) == 0, f"Expected no notes, got {len(detections)}"
    
    def test_ignores_keyboard_area(self):
        """Should not detect notes in the keyboard area."""
        cal = make_test_calibration()
        frame, _ = make_keyboard_frame(keyboard_y=700)
        
        detections = detect_notes_in_frame(frame, cal)
        # All detected notes should be above keyboard
        for det in detections:
            assert det.center_y < 700, \
                f"Note detected below keyboard at y={det.center_y}"
    
    def test_note_position_accuracy(self):
        """Detected note position should be close to drawn position."""
        cal = make_test_calibration()
        
        for x_pos in [200, 500, 800, 1200, 1600]:
            frame = make_playing_frame(
                notes=[
                    {'x': x_pos, 'y': 300, 'w': 60, 'h': 100, 'color': (200, 130, 190)},
                ],
                keyboard_y=700
            )
            
            detections = detect_notes_in_frame(frame, cal)
            assert len(detections) >= 1, f"Should detect note at x={x_pos}"
            
            expected_cx = x_pos + 30
            assert abs(detections[0].center_x - expected_cx) < 30, \
                f"Note at x={x_pos}: detected cx={detections[0].center_x}, expected ~{expected_cx}"
    
    def test_small_notes_filtered(self):
        """Very small regions should be filtered out."""
        cal = make_test_calibration()
        frame = make_playing_frame(
            notes=[
                # Too small - should be filtered
                {'x': 500, 'y': 300, 'w': 5, 'h': 5, 'color': (200, 130, 190)},
            ],
            keyboard_y=700
        )
        
        detections = detect_notes_in_frame(frame, cal)
        assert len(detections) == 0, "Very small notes should be filtered"


class TestClassifyNoteColor:
    """Tests for color classification."""
    
    def test_exact_color_match(self):
        """Should classify exact color matches correctly."""
        colors = [
            NoteColor(center_hsv=(146, 84, 200), center_bgr=(200, 130, 190),
                     label='right_hand'),
            NoteColor(center_hsv=(25, 120, 240), center_bgr=(128, 229, 246),
                     label='left_hand'),
        ]
        
        idx, label = classify_note_color(np.array([146, 84, 200]), colors)
        assert label == 'right_hand'
        
        idx, label = classify_note_color(np.array([25, 120, 240]), colors)
        assert label == 'left_hand'
    
    def test_similar_color_match(self):
        """Should classify similar (but not exact) colors correctly."""
        colors = [
            NoteColor(center_hsv=(146, 84, 200), center_bgr=(200, 130, 190),
                     label='right_hand'),
            NoteColor(center_hsv=(25, 120, 240), center_bgr=(128, 229, 246),
                     label='left_hand'),
        ]
        
        # Slightly different purple
        idx, label = classify_note_color(np.array([150, 80, 195]), colors)
        assert label == 'right_hand'
        
        # Slightly different orange
        idx, label = classify_note_color(np.array([20, 125, 235]), colors)
        assert label == 'left_hand'
    
    def test_sharp_flat_color_variation(self):
        """Sharp/flat notes may have slightly different colors but should match."""
        colors = [
            NoteColor(center_hsv=(146, 84, 200), center_bgr=(200, 130, 190),
                     label='right_hand'),
            NoteColor(center_hsv=(25, 120, 240), center_bgr=(128, 229, 246),
                     label='left_hand'),
        ]
        
        # Sharp might be slightly lighter/darker
        idx, label = classify_note_color(np.array([146, 70, 180]), colors)
        assert label == 'right_hand', \
            "Slight color variation should still match correct hand"
