"""Tests for the key mapper module."""
import pytest
from src.key_mapper import (
    normalize_note_name, build_key_map_from_ocr,
    assign_keys_from_positions, PIANO_88, NOTE_NAMES,
    _assign_keys_estimated, _assign_keys_interpolated,
)
from src.note_tracker import TrackedNote
from src.calibrator import CalibrationResult


class TestNormalizeNoteName:
    """Tests for note name normalization."""
    
    def test_basic_notes(self):
        assert normalize_note_name('C') == 'C'
        assert normalize_note_name('D') == 'D'
        assert normalize_note_name('E') == 'E'
        assert normalize_note_name('F') == 'F'
        assert normalize_note_name('G') == 'G'
        assert normalize_note_name('A') == 'A'
        assert normalize_note_name('B') == 'B'
    
    def test_with_octave(self):
        assert normalize_note_name('C4') == 'C4'
        assert normalize_note_name('A0') == 'A0'
        assert normalize_note_name('C8') == 'C8'
    
    def test_sharps(self):
        assert normalize_note_name('C#') == 'C#'
        assert normalize_note_name('F#4') == 'F#4'
        assert normalize_note_name('G#3') == 'G#3'
    
    def test_case_insensitive(self):
        assert normalize_note_name('c') == 'C'
        assert normalize_note_name('c#4') == 'C#4'
        assert normalize_note_name('f') == 'F'
    
    def test_invalid_input(self):
        assert normalize_note_name('') is None
        assert normalize_note_name('X') is None
        assert normalize_note_name('123') is None
    
    def test_whitespace_handling(self):
        assert normalize_note_name('  C4  ') == 'C4'
        assert normalize_note_name(' F# ') == 'F#'


class TestPiano88:
    """Tests for the PIANO_88 key list."""
    
    def test_length(self):
        assert len(PIANO_88) == 88
    
    def test_first_key(self):
        assert PIANO_88[0] == 'A0'
    
    def test_last_key(self):
        assert PIANO_88[87] == 'C8'
    
    def test_middle_c(self):
        """C4 (middle C) should be at index 39."""
        assert 'C4' in PIANO_88
        idx = PIANO_88.index('C4')
        assert idx == 39
    
    def test_a440(self):
        """A4 (440 Hz) should be in the list."""
        assert 'A4' in PIANO_88


class TestAssignKeysEstimated:
    """Tests for estimated key assignment."""
    
    def test_assigns_key_indices(self):
        """Notes should get key index assignments."""
        notes = [
            TrackedNote(id=1, note_name='unknown', hand='right_hand',
                       color_idx=0, start_time=1.0, duration=0.5, center_x=500),
            TrackedNote(id=2, note_name='unknown', hand='right_hand',
                       color_idx=0, start_time=2.0, duration=0.5, center_x=800),
        ]
        
        result = _assign_keys_estimated(notes, frame_width=1920)
        
        for note in result:
            assert 21 <= note.key_index <= 108  # MIDI number range
            assert note.note_name != 'unknown'
            assert note.note_name in PIANO_88
    
    def test_left_notes_get_lower_keys(self):
        """Notes further left should get lower key indices."""
        notes = [
            TrackedNote(id=1, note_name='unknown', hand='right_hand',
                       color_idx=0, start_time=1.0, duration=0.5, center_x=200),
            TrackedNote(id=2, note_name='unknown', hand='right_hand',
                       color_idx=0, start_time=1.0, duration=0.5, center_x=1600),
        ]
        
        result = _assign_keys_estimated(notes, frame_width=1920)
        
        assert result[0].key_index < result[1].key_index, \
            "Leftmost note should have lower key index"


class TestBuildKeyMapFromOCR:
    """Tests for building key maps from OCR data."""
    
    def test_builds_map_from_ocr(self):
        """Should build position map from OCR'd notes."""
        notes = [
            TrackedNote(id=1, note_name='C4', hand='right_hand',
                       color_idx=0, start_time=1.0, duration=0.5, center_x=500,
                       ocr_text='C4'),
            TrackedNote(id=2, note_name='E4', hand='right_hand',
                       color_idx=0, start_time=2.0, duration=0.5, center_x=600,
                       ocr_text='E4'),
        ]
        
        key_map = build_key_map_from_ocr(notes, frame_width=1920)
        
        assert 'C4' in key_map
        assert 'E4' in key_map
        assert key_map['C4'] < key_map['E4']
    
    def test_empty_ocr(self):
        """Should return empty map when no OCR data."""
        notes = [
            TrackedNote(id=1, note_name='unknown', hand='right_hand',
                       color_idx=0, start_time=1.0, duration=0.5, center_x=500),
        ]
        
        key_map = build_key_map_from_ocr(notes, frame_width=1920)
        assert len(key_map) == 0
