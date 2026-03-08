"""Tests for JSON export and validation."""
import json
import pytest
import os
from src.json_exporter import notes_to_dict, export_json, validate_json
from src.note_tracker import TrackedNote
from src.calibrator import CalibrationResult, NoteColor


def make_test_data():
    """Create test notes and calibration."""
    notes = [
        TrackedNote(id=1, note_name='C4', hand='right_hand', color_idx=0,
                   start_time=5.0, duration=0.5, center_x=500, key_index=39,
                   mean_bgr=(200, 130, 190)),
        TrackedNote(id=2, note_name='E4', hand='right_hand', color_idx=0,
                   start_time=5.5, duration=0.3, center_x=600, key_index=43,
                   mean_bgr=(200, 130, 190)),
        TrackedNote(id=3, note_name='G3', hand='left_hand', color_idx=1,
                   start_time=5.0, duration=1.0, center_x=400, key_index=34,
                   mean_bgr=(60, 200, 220)),
    ]
    
    calibration = CalibrationResult(
        keyboard_y=700,
        keyboard_height=380,
        note_area_top=0,
        note_area_bottom=700,
        note_colors=[
            NoteColor(center_hsv=(146, 84, 200), center_bgr=(200, 130, 190),
                     label='right_hand'),
            NoteColor(center_hsv=(25, 120, 240), center_bgr=(60, 200, 220),
                     label='left_hand'),
        ],
        scroll_speed=100.0,
        frame_width=1920,
        frame_height=1080,
    )
    
    return notes, calibration


class TestNotesToDict:
    """Tests for JSON serialization."""
    
    def test_basic_structure(self):
        """Output should have metadata, notes, and summary."""
        notes, cal = make_test_data()
        data = notes_to_dict(notes, cal)
        
        assert 'metadata' in data
        assert 'notes' in data
        assert 'summary' in data
    
    def test_metadata_fields(self):
        """Metadata should contain all required fields."""
        notes, cal = make_test_data()
        data = notes_to_dict(notes, cal, video_path='test.webm',
                            video_duration=260.0, video_fps=60.0)
        
        meta = data['metadata']
        assert meta['source_video'] == 'test.webm'
        assert meta['duration_seconds'] == 260.0
        assert meta['fps'] == 60.0
        assert meta['resolution'] == [1920, 1080]
        assert meta['keyboard_y'] == 700
        assert meta['scroll_speed'] == 100.0
    
    def test_notes_structure(self):
        """Each note should have all required fields."""
        notes, cal = make_test_data()
        data = notes_to_dict(notes, cal)
        
        for note in data['notes']:
            assert 'id' in note
            assert 'note_name' in note
            assert 'start_time' in note
            assert 'duration' in note
            assert 'hand' in note
            assert 'key_index' in note
            assert 'center_x' in note
            assert 'color_rgb' in note
    
    def test_summary(self):
        """Summary should have correct counts."""
        notes, cal = make_test_data()
        data = notes_to_dict(notes, cal)
        
        summary = data['summary']
        assert summary['total_notes'] == 3
        assert summary['right_hand_notes'] == 2
        assert summary['left_hand_notes'] == 1
    
    def test_json_serializable(self):
        """Output should be JSON serializable."""
        notes, cal = make_test_data()
        data = notes_to_dict(notes, cal)
        
        # Should not raise
        json_str = json.dumps(data)
        assert len(json_str) > 0
        
        # Should round-trip
        parsed = json.loads(json_str)
        assert parsed['summary']['total_notes'] == 3


class TestExportJson:
    """Tests for file export."""
    
    def test_export_creates_file(self, tmp_path):
        """Should create a valid JSON file."""
        notes, cal = make_test_data()
        output_path = str(tmp_path / 'test_notes.json')
        
        data = export_json(notes, cal, output_path)
        
        assert os.path.exists(output_path)
        
        with open(output_path) as f:
            loaded = json.load(f)
        
        assert loaded['summary']['total_notes'] == 3


class TestValidateJson:
    """Tests for JSON validation."""
    
    def test_valid_data_passes(self):
        """Valid data should produce no errors."""
        notes, cal = make_test_data()
        data = notes_to_dict(notes, cal)
        
        issues = validate_json(data)
        errors = [i for i in issues if i.startswith('ERROR')]
        assert len(errors) == 0, f"Unexpected errors: {errors}"
    
    def test_missing_metadata(self):
        """Should flag missing metadata."""
        issues = validate_json({'notes': []})
        assert any('metadata' in i for i in issues)
    
    def test_missing_notes(self):
        """Should flag missing notes field."""
        issues = validate_json({'metadata': {}})
        assert any('notes' in i for i in issues)
    
    def test_negative_start_time(self):
        """Should flag negative start times."""
        data = {
            'metadata': {},
            'notes': [
                {'id': 1, 'start_time': -1.0, 'duration': 0.5, 'key_index': 39}
            ]
        }
        issues = validate_json(data)
        assert any('negative' in i.lower() for i in issues)
    
    def test_zero_duration(self):
        """Should flag non-positive durations."""
        data = {
            'metadata': {},
            'notes': [
                {'id': 1, 'start_time': 1.0, 'duration': 0, 'key_index': 39}
            ]
        }
        issues = validate_json(data)
        assert any('duration' in i.lower() for i in issues)
