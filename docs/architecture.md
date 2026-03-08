# MakeMusic - Architecture & Plan

## Project Overview
Convert "falling notes" piano tutorial YouTube videos into interactive, scrollable HTML viewers. The pipeline:
1. **Video → Frames** — extract frames from video using ffmpeg
2. **Frames → Notes** — analyze frames to detect note rectangles, their positions, colors, and text labels  
3. **Notes → JSON** — export structured note data with timing information
4. **JSON → HTML** — interactive viewer with smooth scrolling and optional audio playback

## Key Design Principles
- **No hardcoded assumptions** about intros, colors, or layouts
- **Robust detection** using multiple signals (color segmentation, contour detection, motion tracking)
- **Generalizable** — works across different YouTube channels with different styles
- **Thoroughly tested** — unit tests for every component, integration tests with sample videos

## Architecture

### Module Structure
```
src/
  __init__.py
  frame_extractor.py    # Extract frames from video using ffmpeg
  calibrator.py         # Auto-detect keyboard, note colors, scroll speed, intro
  note_detector.py      # Detect notes in individual frames
  note_tracker.py       # Track notes across frames, build timeline
  key_mapper.py         # Map x-positions to piano keys
  ocr_reader.py         # Read note labels from note rectangles
  json_exporter.py      # Export to JSON format
  pipeline.py           # Orchestrate the full pipeline
  cli.py                # Command-line interface
viewer/
  index.html            # Interactive HTML viewer
tests/
  test_calibrator.py
  test_note_detector.py
  test_note_tracker.py
  test_key_mapper.py
  test_ocr_reader.py
  test_integration.py
  test_viewer.py        # Playwright-based UI tests
```

### Pipeline Stages

#### Stage 1: Frame Extraction (`frame_extractor.py`)
- Use ffmpeg to extract frames at configurable FPS (default: 10fps for analysis)
- Convert to standard format (PNG)
- Return frame paths with timestamps

#### Stage 2: Calibration (`calibrator.py`)
- **Keyboard detection**: Find the piano keyboard area (high-contrast alternating pattern at bottom)
- **Note color detection**: Identify 2 dominant note colors (left/right hand) by finding non-background, non-keyboard colored regions
- **Intro detection**: Track when colored note regions first start appearing and moving vertically
- **Scroll speed estimation**: Track a note across consecutive frames to measure pixels/second
- **Play line detection**: Find the boundary between falling area and keyboard

#### Stage 3: Note Detection (`note_detector.py`)
- For each frame, segment by note colors (with tolerance for sharps/flats)
- Find rectangular contours (notes are rounded rectangles)
- Extract bounding boxes with color classification (left/right hand)
- Apply OCR to read note labels

#### Stage 4: Note Tracking (`note_tracker.py`)
- Track notes across consecutive frames using position + color matching
- Determine note start times (when note first reaches the play line)
- Determine note duration (proportional to rectangle height / scroll speed)
- Handle notes that span multiple frames
- Deduplicate — each unique note should appear once in output

#### Stage 5: Key Mapping (`key_mapper.py`)
- Map each note's x-center position to a piano key
- Either use keyboard anatomy (if detected) or OCR'd labels
- Support full 88-key range

#### Stage 6: JSON Export (`json_exporter.py`)
Output format:
```json
{
  "metadata": {
    "source_video": "path",
    "duration_seconds": 260.0,
    "fps": 60,
    "resolution": [1920, 1080],
    "note_colors": {
      "right_hand": {"rgb": [200, 130, 190], "label": "purple"},
      "left_hand": {"rgb": [220, 240, 60], "label": "green"}
    }
  },
  "notes": [
    {
      "id": 1,
      "note_name": "C4",
      "start_time": 5.2,
      "duration": 0.5,
      "hand": "right",
      "velocity": 80
    }
  ]
}
```

#### Stage 7: HTML Viewer
- Piano-roll style display with horizontal axis = keys, vertical axis = time
- Color-coded by hand (left/right)
- Smooth scrollable interface
- Playback mode with cursor line advancing in real-time
- Togglable audio synthesis using Web Audio API
- Keyboard at bottom as reference

## Observations from Sample Videos

### Perfect (Ed Sheeran)
- 1920x1080, AV1, 60fps, 4:20 duration
- Intro: frames 1-4 (title screen with colored buttons), frames 5-8 (transition)
- Notes start appearing: ~frame 9 (second 9)
- Note colors: Purple/magenta (HSV ~146,84,200) and Yellow-green (HSV ~86,180,200)
- Keyboard area: ~y=644-656
- Dark background (>65% of pixels are dark once playing)

### So Easy to Fall in Love
- 1920x1080, VP9, 60fps, 1:42 duration
- Intro: frames 1-5 (title card, green/yellow background)
- Notes start appearing: ~frame 7 (second 7)
- Note colors: Orange/gold (HSV ~25,120,240)
- Keyboard area: ~y=774-781
- Notable: keyboard region has a brown/wood-like texture

## Risk Areas & Mitigations
| Risk | Mitigation |
|------|-----------|
| OCR fails on small/rotated text | Fall back to key position mapping |
| Different video styles/colors | Adaptive color detection per video |
| Variable intro lengths | Motion-based intro detection |
| Sharp/flat color variations | Color similarity clustering |
| Static watermarks | Background subtraction using frame comparison |
| Different scroll speeds | Per-video calibration |
