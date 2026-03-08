"""Tests for the keyboard analyzer module."""
import pytest
import numpy as np
import cv2
from src.keyboard_analyzer import (
    KeyInfo, build_keyboard_map, map_x_to_key,
    detect_white_key_positions, detect_black_key_positions,
    group_black_keys, find_best_complete_octave,
    keyboard_map_to_list, keyboard_map_from_list,
    _build_from_reference_c,
)


def make_keyboard_frame(width=1920, height=1080, 
                         keyboard_y=800, keyboard_height=200,
                         num_octaves=3, start_note='C'):
    """Create a synthetic frame with a keyboard pattern."""
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    frame[:keyboard_y, :] = 30  # Dark note area
    
    # White keys in bottom portion
    white_key_width = width // (num_octaves * 7 + 1)
    
    # Draw white keys (bright)
    bottom = keyboard_y + keyboard_height
    for i in range(num_octaves * 7 + 1):
        x1 = i * white_key_width
        x2 = (i + 1) * white_key_width - 1
        frame[keyboard_y:bottom, x1:x2] = [220, 220, 220]  # White keys
        # Gap between keys
        if x2 < width:
            frame[keyboard_y:bottom, x2:x2+1] = [50, 50, 50]
    
    # Draw black keys (dark, top 50% of keyboard)
    black_top = keyboard_y
    black_bottom = keyboard_y + keyboard_height // 2
    
    # In each octave, black keys at positions: 0.5, 1.5, 3.5, 4.5, 5.5 (between white keys)
    black_key_offsets = [0.5, 1.5, 3.5, 4.5, 5.5]  # C#, D#, F#, G#, A#
    black_width = int(white_key_width * 0.6)
    
    for octave in range(num_octaves):
        for offset in black_key_offsets:
            cx = int((octave * 7 + offset + 0.5) * white_key_width)
            x1 = cx - black_width // 2
            x2 = cx + black_width // 2
            if 0 <= x1 and x2 < width:
                frame[black_top:black_bottom, x1:x2] = [20, 20, 20]
    
    return frame


class TestKeyInfo:
    """Tests for the KeyInfo dataclass."""
    
    def test_basic_creation(self):
        key = KeyInfo(center_x=100, note_name='C', is_black=False, octave=4)
        assert key.full_name == 'C4'
        assert key.midi_number == 60
    
    def test_sharp_note(self):
        key = KeyInfo(center_x=200, note_name='F#', is_black=True, octave=3)
        assert key.full_name == 'F#3'
        assert key.midi_number == 54  # (3+1)*12 + 6
    
    def test_a4_midi(self):
        key = KeyInfo(center_x=300, note_name='A', is_black=False, octave=4)
        assert key.midi_number == 69
    
    def test_to_dict(self):
        key = KeyInfo(center_x=100, note_name='C', is_black=False, octave=4)
        d = key.to_dict()
        assert d['center_x'] == 100
        assert d['note_name'] == 'C'
        assert d['is_black'] == False
        assert d['octave'] == 4
        assert d['full_name'] == 'C4'
        assert d['midi'] == 60


class TestMapXToKey:
    """Tests for mapping x-position to nearest key."""
    
    def test_exact_match(self):
        keys = [
            KeyInfo(center_x=100, note_name='C', is_black=False, octave=4),
            KeyInfo(center_x=200, note_name='D', is_black=False, octave=4),
        ]
        result = map_x_to_key(100, keys)
        assert result.note_name == 'C'
    
    def test_nearest_match(self):
        keys = [
            KeyInfo(center_x=100, note_name='C', is_black=False, octave=4),
            KeyInfo(center_x=200, note_name='D', is_black=False, octave=4),
        ]
        result = map_x_to_key(160, keys)
        assert result.note_name == 'D'
    
    def test_empty_map(self):
        result = map_x_to_key(100, [])
        assert result is None


class TestGroupBlackKeys:
    """Tests for black key grouping."""
    
    def test_two_three_pattern(self):
        # Simulated black key positions
        # Group of 2 (C#, D#), then group of 3 (F#, G#, A#)
        centers = [50, 100, 250, 300, 350]  
        groups = group_black_keys(centers, white_key_width=80)
        sizes = [len(g) for g in groups]
        assert sizes == [2, 3]
    
    def test_single_key(self):
        groups = group_black_keys([100], white_key_width=80)
        assert len(groups) == 1
        assert len(groups[0]) == 1
    
    def test_empty(self):
        groups = group_black_keys([], white_key_width=80)
        assert len(groups) == 0


class TestBuildFromReferenceC:
    """Tests for building keyboard from a known C position."""
    
    def test_three_octaves(self):
        # 22 white keys = 3 octaves + 1
        white_centers = [i * 80 + 40 for i in range(22)]
        keys = _build_from_reference_c(white_centers, c_idx=0, 
                                        white_key_width=80.0, octave_offset=3)
        
        # Should have 22 white + 15 black = 37 keys
        white_keys = [k for k in keys if not k.is_black]
        black_keys = [k for k in keys if k.is_black]
        
        assert len(white_keys) == 22
        assert len(black_keys) == 15  # 5 per full octave * 3
        
        # First key should be C3
        assert keys[0].full_name == 'C3'
        
        # Check note names repeat correctly
        expected_white = ['C', 'D', 'E', 'F', 'G', 'A', 'B'] * 3 + ['C']
        actual_white = [k.note_name for k in white_keys]
        assert actual_white == expected_white
    
    def test_octave_offset(self):
        white_centers = [i * 80 + 40 for i in range(8)]
        keys = _build_from_reference_c(white_centers, c_idx=0,
                                        white_key_width=80.0, octave_offset=4)
        white_keys = [k for k in keys if not k.is_black]
        assert white_keys[0].full_name == 'C4'
        assert white_keys[7].full_name == 'C5'
    
    def test_non_zero_c_idx(self):
        """When C is not the first white key (e.g., starts with A)."""
        white_centers = [i * 80 + 40 for i in range(9)]  # A2, B2, C3, D3, ...
        keys = _build_from_reference_c(white_centers, c_idx=2,
                                        white_key_width=80.0, octave_offset=3)
        white_keys = [k for k in keys if not k.is_black]
        assert white_keys[0].note_name == 'A'  # (0-2)%7 = 5 → A
        assert white_keys[1].note_name == 'B'
        assert white_keys[2].note_name == 'C'
        assert white_keys[2].octave == 3


class TestKeyboardSerialization:
    """Tests for keyboard map serialization."""
    
    def test_round_trip(self):
        keys = [
            KeyInfo(center_x=100, note_name='C', is_black=False, octave=4),
            KeyInfo(center_x=140, note_name='C#', is_black=True, octave=4),
            KeyInfo(center_x=180, note_name='D', is_black=False, octave=4),
        ]
        
        data = keyboard_map_to_list(keys)
        restored = keyboard_map_from_list(data)
        
        assert len(restored) == 3
        assert restored[0].full_name == 'C4'
        assert restored[1].full_name == 'C#4'
        assert restored[1].is_black == True
        assert restored[2].center_x == 180


class TestBuildKeyboardMap:
    """Tests for full keyboard map building from a frame."""
    
    def test_synthetic_keyboard(self):
        """Test with a synthetic keyboard image."""
        frame = make_keyboard_frame(
            width=1920, height=1080,
            keyboard_y=800, keyboard_height=200,
            num_octaves=3
        )
        
        keys = build_keyboard_map(frame, keyboard_y=800, keyboard_height=200)
        
        # Should detect keys
        assert len(keys) > 10
        
        # Should have both white and black keys
        white = [k for k in keys if not k.is_black]
        black = [k for k in keys if k.is_black]
        assert len(white) > 0
        assert len(black) > 0
        
        # Keys should be sorted by x position
        for i in range(len(keys) - 1):
            assert keys[i].center_x <= keys[i+1].center_x
    
    def test_octave_names_sequence(self):
        """Check that note names follow the chromatic sequence."""
        frame = make_keyboard_frame(num_octaves=2)
        keys = build_keyboard_map(frame, keyboard_y=800, keyboard_height=200)
        
        # Check that same-name notes increase in octave
        c_keys = [k for k in keys if k.note_name == 'C']
        for i in range(len(c_keys) - 1):
            assert c_keys[i].octave < c_keys[i+1].octave

