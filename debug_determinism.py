#!/usr/bin/env python3
"""Debug script to find non-determinism in note tracking."""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))

import src.note_tracker as nt
import hashlib

# Monkey-patch to capture pre/post merge
orig_merge = nt.NoteTracker._merge_fragments

def patched_merge(self, notes):
    # Print notes around t=16-22s, cx=1100-1400 (where Perfect RH has issues)
    relevant = [n for n in notes if 16 < n.start_time < 22 and 1100 < n.center_x < 1400]
    for n in sorted(relevant, key=lambda n: (n.start_time, n.center_x)):
        print(f'  PRE-MERGE: t={n.start_time:.4f} dur={n.duration:.4f} cx={n.center_x:.0f} hand={n.hand} det={n.detection_count}')
    result = orig_merge(self, notes)
    relevant2 = [n for n in result if 16 < n.start_time < 22 and 1100 < n.center_x < 1400]
    for n in sorted(relevant2, key=lambda n: (n.start_time, n.center_x)):
        print(f'  POST-MERGE: t={n.start_time:.4f} dur={n.duration:.4f} cx={n.center_x:.0f} hand={n.hand}')
    return result

nt.NoteTracker._merge_fragments = patched_merge

from src.pipeline import analyze_video

data = analyze_video('music/perfect/video.webm', 'tmp/debug_det', analysis_fps=10.0, ocr_enabled=False, verbose=False)
rh = [n for n in data['notes'] if 'right' in n.get('hand', '')]
det_pc = [n['note_name'].rstrip('0123456789') for n in rh[:16]]
print(f'\nResult: {det_pc}')
for i, n in enumerate(rh[:10]):
    print(f'  {i}: t={n["start_time"]:.4f}s {n["note_name"]} cx={n.get("center_x",0):.0f}')
