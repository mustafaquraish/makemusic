# Work Log

## 2026-03-01: Project Kickoff

### Session 1: Initial Analysis
- **Explored** workspace: two sample videos (`perfect/video.webm` and `so_easy_to_fall_in_love/video.webm`)
- **Analyzed** video metadata:
  - Perfect: 1920x1080, AV1 codec, 60fps, 4:20 duration
  - So Easy: 1920x1080, VP9 codec, 60fps, 1:42 duration
- **Extracted** sample frames (1fps, first 30 seconds) for both videos
- **Ran** color/region analysis on all frames to understand visual structure
- **Key findings**:
  - Both videos have distinct intro sections (title screens) before notes begin
  - Note colors differ between videos (purple/green vs orange)
  - Keyboard position differs (y=644 vs y=774)
  - Background is predominantly dark during playback
  - Notes are large rectangular regions with consistent colors
- **Created** project architecture document
- **Status**: Beginning implementation of core pipeline

### Session 2: Core Pipeline Implementation
- **Built** all 8 source modules:
  - `frame_extractor.py`: ffmpeg/OpenCV frame extraction
  - `calibrator.py`: Keyboard detection, note colors, intro detection, scroll speed
  - `note_detector.py`: Per-frame contour detection with HSV color masking
  - `note_tracker.py`: Cross-frame linking with timing calculation
  - `key_mapper.py`: X-position to piano key mapping (88 keys)
  - `ocr_reader.py`: EasyOCR-based note label reading
  - `json_exporter.py`: JSON export with validation
  - `pipeline.py` + `cli.py`: Full orchestration
- **Wrote** 57 unit tests across 5 test files — all passing
- **Tested** pipeline on both real videos:
  - So Easy: 120 notes, timing 9–98s (video is 103s)
  - Perfect: 414 notes (125 left, 289 right), timing 7–261s (video is 260s)
- **Fixed** bugs: intro detection on bright title cards, np.int64 serialization, timing caps, overlap resolution

### Session 3: HTML Viewer & UI Tests
- **Built** interactive HTML viewer (`viewer/index.html`):
  - Piano-roll display with scrolling, zoom control
  - Left/right hand color coding (red/blue)
  - Playhead with real-time position tracking
  - Play/Pause with auto-scroll (Space shortcut)
  - Web Audio API synthesizer for sound playback
  - Drag-and-drop JSON loading + URL param loading
  - Responsive keyboard at bottom with active key highlighting
- **Wrote** 23 Playwright tests (headless Chromium):
  - Page load, JSON loading, note rendering, hand classification
  - Keyboard rendering (white + black keys)
  - Piano roll positioning, playhead, zoom
  - Scroll → time indicator, playback toggle, auto-scroll
  - Sound toggle, real data loading for both songs
- **Full suite: 80/80 tests passing** (57 unit + 23 UI)

### Current Status
- Pipeline and viewer are fully functional
- All tests passing
- Demo JSON files available in `viewer/` directory

### Known Limitations
- OCR not yet validated on real video frames (skipped for speed in pipeline tests)
- Key mapping uses position estimation (assumes 52 visible keys starting at key 20)
- Note detection accuracy depends on video quality and color consistency
