#!/usr/bin/env python3
"""Quick re-run of just Perfect and So Easy for ground truth comparison."""
import os, sys, time, json
sys.path.insert(0, os.path.dirname(__file__))

from src.pipeline import analyze_video
from src.mp3_generator import generate_from_json

GROUND_TRUTH = {
    'so_easy_to_fall_in_love': {
        'right_hand': ['A#', 'G', 'D#', 'C', 'A#', 'G', 'D', 'A#', 'D#', 'C', 'D#', 'C', 'D#'],
    },
    'perfect': {
        'right_hand': ['D', 'E', 'G', 'G', 'B', 'A', 'G', 'B', 'G', 'A', 'B', 'B', 'A', 'G', 'G', 'G'],
        'left_hand': ['G', 'G', 'G', 'G', 'G', 'E', 'E', 'E', 'E', 'C', 'C', 'C', 'C'],
    },
}

for song in ['so_easy_to_fall_in_love', 'perfect']:
    video_path = f'music/{song}/video.webm'
    output_dir = f'tmp/output_{song}'
    
    print(f"\n{'='*60}")
    print(f"  Processing: {song}")
    print(f"{'='*60}")
    
    t0 = time.time()
    data = analyze_video(video_path, output_dir, analysis_fps=10.0, ocr_enabled=False, verbose=True)
    elapsed = time.time() - t0
    
    notes = data.get('notes', [])
    rh = [n for n in notes if 'right' in n.get('hand', '')]
    lh = [n for n in notes if 'left' in n.get('hand', '')]
    
    print(f"\nTotal: {len(notes)}, RH: {len(rh)}, LH: {len(lh)}, Time: {elapsed:.1f}s")
    
    gt = GROUND_TRUTH[song]
    if 'right_hand' in gt:
        gt_rh = gt['right_hand']
        det_pc = [n['note_name'].rstrip('0123456789') for n in rh[:len(gt_rh)]]
        matches = sum(1 for a, b in zip(det_pc, gt_rh) if a == b)
        print(f"RH: {matches}/{len(gt_rh)} ({100*matches/len(gt_rh):.0f}%)")
        print(f"  GT:  {gt_rh}")
        print(f"  Det: {det_pc}")
    
    if 'left_hand' in gt:
        gt_lh = gt['left_hand']
        det_pc = [n['note_name'].rstrip('0123456789') for n in lh[:len(gt_lh)]]
        matches = sum(1 for a, b in zip(det_pc, gt_lh) if a == b)
        print(f"LH: {matches}/{len(gt_lh)} ({100*matches/len(gt_lh):.0f}%)")
        print(f"  GT:  {gt_lh}")
        print(f"  Det: {det_pc}")
    
    # Show first 20 RH notes with timing
    print(f"\nFirst 20 RH notes:")
    for i, n in enumerate(rh[:20]):
        print(f"  {i}: t={n['start_time']:.2f}s dur={n['duration']:.2f}s {n['note_name']} cx={n.get('center_x',0):.0f}")
