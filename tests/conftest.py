"""
Shared test fixtures and utilities for MakeMusic tests.
"""
import numpy as np
import cv2
import pytest
import os

SAMPLE_WIDTH = 1920
SAMPLE_HEIGHT = 1080


def make_blank_frame(width=SAMPLE_WIDTH, height=SAMPLE_HEIGHT, color=(0, 0, 0)):
    """Create a blank frame with the given background color."""
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    frame[:] = color
    return frame


def make_keyboard_frame(width=SAMPLE_WIDTH, height=SAMPLE_HEIGHT,
                        keyboard_y=700, key_width=22, bg_color=(10, 10, 10)):
    """
    Create a frame with a simulated piano keyboard at the bottom.
    
    Returns:
        frame, keyboard_y
    """
    frame = make_blank_frame(width, height, bg_color)
    
    # Draw white keys
    white_keys = 52  # Standard piano has 52 white keys
    key_w = width // white_keys
    for i in range(white_keys):
        x = i * key_w
        cv2.rectangle(frame, (x, keyboard_y), (x + key_w - 2, height - 1),
                     (240, 240, 240), -1)
        # Key border
        cv2.rectangle(frame, (x, keyboard_y), (x + key_w - 2, height - 1),
                     (100, 100, 100), 1)
    
    # Draw black keys
    # Pattern in one octave: skip, black, skip, black, skip, skip, black, skip, black, skip, black, skip
    black_key_positions = [1, 3, 6, 8, 10]  # positions within each octave of 12 semitones
    
    for octave in range(7):
        for pos in black_key_positions:
            # Map to white key position
            white_in_octave = [0, 2, 4, 5, 7, 9, 11]
            if pos in [1, 3]:
                left_white = [0, 2][black_key_positions.index(pos)]
            elif pos in [6, 8, 10]:
                left_white = [3, 4, 5][[6, 8, 10].index(pos)]
            else:
                continue
            
            white_idx = octave * 7 + left_white
            if white_idx >= white_keys - 1:
                break
            
            bx = white_idx * key_w + key_w * 2 // 3
            bw = key_w * 2 // 3
            bh = (height - keyboard_y) * 2 // 3
            cv2.rectangle(frame, (bx, keyboard_y), (bx + bw, keyboard_y + bh),
                         (20, 20, 20), -1)
    
    return frame, keyboard_y


def add_note_rect(frame, x, y, width, height, color_bgr, label=None):
    """
    Add a note rectangle to a frame.
    
    Args:
        frame: Frame to draw on (modified in-place)
        x, y: Top-left corner
        width, height: Note dimensions
        color_bgr: BGR color tuple
        label: Optional text label to draw
    """
    # Draw rounded rectangle (simplified as regular rect with slight rounding)
    cv2.rectangle(frame, (x, y), (x + width, y + height), color_bgr, -1)
    
    # Add border slightly darker
    border_color = tuple(max(0, int(c * 0.7)) for c in color_bgr)
    cv2.rectangle(frame, (x, y), (x + width, y + height), border_color, 2)
    
    if label:
        # Draw text label centered on the note
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = min(width, height) / 60.0
        font_scale = max(0.3, min(font_scale, 1.5))
        thickness = max(1, int(font_scale * 2))
        
        text_size = cv2.getTextSize(label, font, font_scale, thickness)[0]
        tx = x + (width - text_size[0]) // 2
        ty = y + (height + text_size[1]) // 2
        
        cv2.putText(frame, label, (tx, ty), font, font_scale,
                   (255, 255, 255), thickness)
    
    return frame


def make_playing_frame(notes=None, keyboard_y=700, width=SAMPLE_WIDTH, 
                       height=SAMPLE_HEIGHT, bg_color=(10, 10, 10)):
    """
    Create a complete playing frame with keyboard and optional notes.
    
    Args:
        notes: List of dicts with keys: x, y, w, h, color, label (optional)
        keyboard_y: Y position of keyboard
        width, height: Frame dimensions
        bg_color: Background color
    
    Returns:
        frame (BGR numpy array)
    """
    frame, _ = make_keyboard_frame(width, height, keyboard_y, bg_color=bg_color)
    
    if notes:
        for note in notes:
            add_note_rect(
                frame,
                note['x'], note['y'],
                note['w'], note['h'],
                note['color'],
                note.get('label'),
            )
    
    return frame


def make_intro_frame(width=SAMPLE_WIDTH, height=SAMPLE_HEIGHT):
    """Create a typical intro frame (bright title screen)."""
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    # Bright colored background
    frame[:] = (100, 200, 150)  # Greenish
    
    # Add some text-like elements
    cv2.putText(frame, "Piano Tutorial", (width // 4, height // 3),
               cv2.FONT_HERSHEY_SIMPLEX, 3, (255, 255, 255), 5)
    cv2.putText(frame, "Song Name", (width // 3, height // 2),
               cv2.FONT_HERSHEY_SIMPLEX, 2, (50, 50, 50), 3)
    
    return frame


def make_scrolling_sequence(num_frames=20, keyboard_y=700, 
                            scroll_speed_ppf=5, fps=10.0,
                            note_specs=None):
    """
    Create a sequence of frames simulating scrolling notes.
    
    Args:
        num_frames: Number of frames to generate
        keyboard_y: Keyboard Y position
        scroll_speed_ppf: Scroll speed in pixels per frame
        fps: Frames per second (for timestamps)
        note_specs: List of note specifications:
            [{'x': 500, 'w': 60, 'h': 100, 'color': (200, 130, 190),
              'start_y': -50, 'label': 'C4'}]
            start_y is the y-position in the first frame
    
    Returns:
        List of (timestamp, frame_bgr) tuples
    """
    if note_specs is None:
        note_specs = [
            {'x': 500, 'w': 60, 'h': 120, 'color': (200, 130, 190), 
             'start_y': 0, 'label': 'C'},
            {'x': 800, 'w': 60, 'h': 80, 'color': (60, 200, 220),
             'start_y': -100, 'label': 'E'},
        ]
    
    frames = []
    for f_idx in range(num_frames):
        timestamp = f_idx / fps
        
        # Build notes for this frame
        frame_notes = []
        for spec in note_specs:
            y = spec['start_y'] + f_idx * scroll_speed_ppf
            # Only include if any part is visible and above keyboard
            if y + spec['h'] > 0 and y < keyboard_y:
                frame_notes.append({
                    'x': spec['x'],
                    'y': max(0, y),
                    'w': spec['w'],
                    'h': min(spec['h'], keyboard_y - max(0, y)),
                    'color': spec['color'],
                    'label': spec.get('label'),
                })
        
        frame = make_playing_frame(frame_notes, keyboard_y)
        frames.append((timestamp, frame))
    
    return frames


@pytest.fixture
def blank_frame():
    return make_blank_frame()


@pytest.fixture
def keyboard_frame():
    return make_keyboard_frame()


@pytest.fixture
def playing_frame():
    return make_playing_frame(
        notes=[
            {'x': 500, 'y': 200, 'w': 60, 'h': 120, 'color': (200, 130, 190), 'label': 'C'},
            {'x': 800, 'y': 300, 'w': 60, 'h': 80, 'color': (60, 200, 220), 'label': 'E'},
        ]
    )


@pytest.fixture
def scrolling_sequence():
    return make_scrolling_sequence()
