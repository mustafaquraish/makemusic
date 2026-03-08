"""Tests for the MP3 generator module."""
import pytest
import os
import json
import tempfile
import numpy as np
from src.mp3_generator import (
    note_name_to_midi,
    create_midi,
    synthesize_audio,
    save_wav,
    generate_from_json,
)


class TestNoteNameToMidi:
    """Tests for note name to MIDI number conversion."""
    
    def test_middle_c(self):
        assert note_name_to_midi('C4') == 60
    
    def test_a440(self):
        assert note_name_to_midi('A4') == 69
    
    def test_sharp_note(self):
        assert note_name_to_midi('F#3') == 54
    
    def test_low_note(self):
        assert note_name_to_midi('A0') == 21  # Lowest piano key
    
    def test_high_note(self):
        assert note_name_to_midi('C8') == 108  # Highest piano key
    
    def test_invalid_defaults_to_c4(self):
        assert note_name_to_midi('X9') == 60
    
    def test_all_naturals_c4(self):
        expected = {'C4': 60, 'D4': 62, 'E4': 64, 'F4': 65, 'G4': 67, 'A4': 69, 'B4': 71}
        for name, midi in expected.items():
            assert note_name_to_midi(name) == midi


class TestSynthesizeAudio:
    """Tests for audio synthesis."""
    
    def test_empty_notes(self):
        audio = synthesize_audio([])
        assert len(audio) > 0
    
    def test_single_note(self):
        notes = [{'note_name': 'C4', 'start_time': 0, 'duration': 1.0}]
        audio = synthesize_audio(notes, sample_rate=22050)
        
        # Should be about 1.3 seconds (1.0 + 0.3 release)
        expected_samples = int(1.3 * 22050) + int(2.0 * 22050)  # plus padding
        assert len(audio) > 22050  # At least 1 second
    
    def test_audio_not_silent(self):
        notes = [{'note_name': 'A4', 'start_time': 0, 'duration': 0.5}]
        audio = synthesize_audio(notes, sample_rate=22050)
        assert np.max(np.abs(audio)) > 0.1
    
    def test_audio_normalized(self):
        notes = [
            {'note_name': 'C4', 'start_time': 0, 'duration': 0.5},
            {'note_name': 'E4', 'start_time': 0, 'duration': 0.5},
            {'note_name': 'G4', 'start_time': 0, 'duration': 0.5},
        ]
        audio = synthesize_audio(notes, sample_rate=22050)
        assert np.max(np.abs(audio)) <= 1.0
    
    def test_multiple_notes_sequential(self):
        notes = [
            {'note_name': 'C4', 'start_time': 0, 'duration': 0.5},
            {'note_name': 'D4', 'start_time': 0.5, 'duration': 0.5},
        ]
        audio = synthesize_audio(notes, sample_rate=22050)
        # Should cover both notes
        assert len(audio) >= int(1.0 * 22050)


class TestCreateMidi:
    """Tests for MIDI file creation."""
    
    def test_creates_file(self):
        notes = [
            {'note_name': 'C4', 'start_time': 0, 'duration': 1.0, 'hand': 'right_hand'},
            {'note_name': 'G3', 'start_time': 0, 'duration': 1.0, 'hand': 'left_hand'},
        ]
        
        with tempfile.NamedTemporaryFile(suffix='.mid', delete=False) as f:
            path = f.name
        
        try:
            create_midi(notes, path)
            assert os.path.exists(path)
            assert os.path.getsize(path) > 0
        finally:
            os.unlink(path)
    
    def test_midi_header(self):
        """MIDI files start with 'MThd'."""
        notes = [{'note_name': 'C4', 'start_time': 0, 'duration': 0.5}]
        
        with tempfile.NamedTemporaryFile(suffix='.mid', delete=False) as f:
            path = f.name
        
        try:
            create_midi(notes, path)
            with open(path, 'rb') as f:
                header = f.read(4)
            assert header == b'MThd'
        finally:
            os.unlink(path)


class TestSaveWav:
    """Tests for WAV file saving."""
    
    def test_creates_file(self):
        audio = np.sin(2 * np.pi * 440 * np.arange(22050) / 22050)
        
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            path = f.name
        
        try:
            save_wav(audio, path, sample_rate=22050)
            assert os.path.exists(path)
            assert os.path.getsize(path) > 0
        finally:
            os.unlink(path)
    
    def test_wav_header(self):
        """WAV files start with 'RIFF'."""
        audio = np.zeros(1000)
        
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            path = f.name
        
        try:
            save_wav(audio, path, sample_rate=22050)
            with open(path, 'rb') as f:
                header = f.read(4)
            assert header == b'RIFF'
        finally:
            os.unlink(path)


class TestGenerateFromJson:
    """Tests for the end-to-end generation pipeline."""
    
    def test_generates_all_files(self):
        notes_data = {
            'notes': [
                {'note_name': 'C4', 'start_time': 0, 'duration': 0.5, 'hand': 'right_hand'},
                {'note_name': 'E4', 'start_time': 0.5, 'duration': 0.5, 'hand': 'right_hand'},
                {'note_name': 'G3', 'start_time': 0, 'duration': 1.0, 'hand': 'left_hand'},
            ]
        }
        
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = os.path.join(tmpdir, 'notes.json')
            with open(json_path, 'w') as f:
                json.dump(notes_data, f)
            
            prefix = os.path.join(tmpdir, 'test_output')
            midi_path, wav_path, mp3_path = generate_from_json(json_path, prefix)
            
            assert os.path.exists(midi_path)
            assert os.path.exists(wav_path)
            # MP3 may or may not exist depending on ffmpeg availability
