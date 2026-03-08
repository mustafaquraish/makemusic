"""Tests for the note tracker module."""
import numpy as np
import pytest
from tests.conftest import make_scrolling_sequence, SAMPLE_WIDTH, SAMPLE_HEIGHT
from src.note_tracker import NoteTracker, TrackedNote, ActiveTrack
from src.note_detector import DetectedNote, detect_notes_in_frame
from src.calibrator import CalibrationResult, NoteColor


def make_test_calibration(keyboard_y=700, scroll_speed=100.0):
    """Create a CalibrationResult for testing."""
    return CalibrationResult(
        keyboard_y=keyboard_y,
        keyboard_height=SAMPLE_HEIGHT - keyboard_y,
        note_area_top=0,
        note_area_bottom=keyboard_y,
        note_colors=[
            NoteColor(
                center_hsv=(146, 84, 200),
                center_bgr=(200, 130, 190),
                label='right_hand',
                h_range=(120, 175),
                s_range=(30, 255),
                v_range=(80, 255),
            ),
        ],
        scroll_speed=scroll_speed,
        frame_width=SAMPLE_WIDTH,
        frame_height=SAMPLE_HEIGHT,
    )


def make_detection(x, y, w=60, h=120, color_idx=0, hand='right_hand',
                   frame_index=0, timestamp=0.0):
    """Create a test DetectedNote."""
    return DetectedNote(
        x=x, y=y, width=w, height=h,
        center_x=x + w // 2,
        center_y=y + h // 2,
        color_idx=color_idx,
        hand=hand,
        area=w * h,
        mean_hsv=(146, 84, 200),
        mean_bgr=(200, 130, 190),
        frame_index=frame_index,
        timestamp=timestamp,
    )


class TestNoteTracker:
    """Tests for the NoteTracker class."""
    
    def test_single_note_tracking(self):
        """Should track a single note moving across frames."""
        cal = make_test_calibration(scroll_speed=100.0)
        tracker = NoteTracker(cal, max_gap_frames=3)
        
        # Simulate a note falling from y=100 to y=600 over 10 frames
        for i in range(10):
            y = 100 + i * 50
            det = make_detection(500, y, frame_index=i, timestamp=i * 0.1)
            tracker.process_frame([det], i, i * 0.1)
        
        notes = tracker.finalize()
        
        assert len(notes) == 1, f"Expected 1 tracked note, got {len(notes)}"
        assert notes[0].hand == 'right_hand'
        assert notes[0].detection_count == 10
    
    def test_two_notes_same_time(self):
        """Should track two notes that appear at the same time."""
        cal = make_test_calibration(scroll_speed=100.0)
        tracker = NoteTracker(cal, max_gap_frames=3)
        
        for i in range(10):
            y = 100 + i * 50
            det1 = make_detection(300, y, frame_index=i, timestamp=i * 0.1)
            det2 = make_detection(800, y, frame_index=i, timestamp=i * 0.1)
            tracker.process_frame([det1, det2], i, i * 0.1)
        
        notes = tracker.finalize()
        
        assert len(notes) == 2, f"Expected 2 tracked notes, got {len(notes)}"
    
    def test_sequential_notes_same_key(self):
        """Should track two notes on the same key that appear at different times."""
        cal = make_test_calibration(scroll_speed=100.0)
        tracker = NoteTracker(cal, max_gap_frames=2)
        
        # First note: frames 0-4
        for i in range(5):
            y = 100 + i * 50
            det = make_detection(500, y, frame_index=i, timestamp=i * 0.1)
            tracker.process_frame([det], i, i * 0.1)
        
        # Gap: frames 5-7 (no note on this key)
        for i in range(5, 8):
            tracker.process_frame([], i, i * 0.1)
        
        # Second note: frames 8-12
        for i in range(8, 13):
            y = 100 + (i - 8) * 50
            det = make_detection(500, y, frame_index=i, timestamp=i * 0.1)
            tracker.process_frame([det], i, i * 0.1)
        
        notes = tracker.finalize()
        
        assert len(notes) == 2, f"Expected 2 tracked notes, got {len(notes)}"
    
    def test_note_timing(self):
        """Tracked note start_time should reflect when it reaches the play line."""
        cal = make_test_calibration(keyboard_y=700, scroll_speed=100.0)
        tracker = NoteTracker(cal, max_gap_frames=3)
        
        # Note starts at y=200, keyboard at y=700
        for i in range(10):
            y = 200 + i * 50
            det = make_detection(500, y, frame_index=i, timestamp=i * 0.1)
            tracker.process_frame([det], i, i * 0.1)
        
        notes = tracker.finalize()
        
        assert len(notes) >= 1, "Should track at least 1 note"
        # Start time should be positive
        assert notes[0].start_time >= 0, "Start time should be non-negative"
        # Duration should be positive
        assert notes[0].duration > 0, "Duration should be positive"
    
    def test_empty_frames_dont_crash(self):
        """Processing frames with no detections should work fine."""
        cal = make_test_calibration()
        tracker = NoteTracker(cal)
        
        for i in range(10):
            tracker.process_frame([], i, i * 0.1)
        
        notes = tracker.finalize()
        assert len(notes) == 0
    
    def test_different_color_notes_tracked_separately(self):
        """Notes with different colors should be tracked as separate tracks."""
        cal = make_test_calibration(scroll_speed=100.0)
        # Add second color
        cal.note_colors.append(
            NoteColor(
                center_hsv=(25, 120, 240),
                center_bgr=(128, 229, 246),
                label='left_hand',
                h_range=(10, 40),
                s_range=(60, 255),
                v_range=(150, 255),
            )
        )
        
        tracker = NoteTracker(cal, max_gap_frames=3)
        
        # Two notes at same x but different colors
        for i in range(10):
            y = 100 + i * 50
            det1 = make_detection(500, y, color_idx=0, hand='right_hand',
                                  frame_index=i, timestamp=i * 0.1)
            det2 = make_detection(500, y + 20, color_idx=1, hand='left_hand',
                                  frame_index=i, timestamp=i * 0.1)
            tracker.process_frame([det1, det2], i, i * 0.1)
        
        notes = tracker.finalize()
        
        assert len(notes) == 2, f"Expected 2 tracks (different colors), got {len(notes)}"


class TestTrackedNote:
    """Tests for TrackedNote properties."""
    
    def test_note_has_required_fields(self):
        """TrackedNote should have all required fields."""
        note = TrackedNote(
            id=1, note_name='C4', hand='right_hand', color_idx=0,
            start_time=5.0, duration=0.5, center_x=500.0
        )
        
        assert note.id == 1
        assert note.note_name == 'C4'
        assert note.hand == 'right_hand'
        assert note.start_time == 5.0
        assert note.duration == 0.5
        assert note.center_x == 500.0
