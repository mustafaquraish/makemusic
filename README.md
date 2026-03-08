# MakeMusic - Falling Notes Video Analyzer

Converts "falling notes" piano tutorial videos into interactive HTML viewers.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Analyze a video
python -m src.cli analyze path/to/video.webm -o output/

# Open the viewer
open output/viewer.html
```

## Project Structure
- `src/` — Core analysis pipeline
- `viewer/` — Interactive HTML viewer
- `tests/` — Test suite
- `docs/` — Documentation
- `music/` — Sample videos (gitignored)
