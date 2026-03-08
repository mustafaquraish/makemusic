#!/usr/bin/env python3
"""
Run the analysis pipeline on all videos in music/ directory.
Processes videos in parallel and tracks statistics.

Also generates MIDI/WAV/MP3 for each and validates against ground truth.
"""
import os
import sys
import json
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))

from src.pipeline import analyze_video
from src.mp3_generator import generate_from_json


# Ground truth from manual.md
GROUND_TRUTH = {
    'so_easy_to_fall_in_love': {
        'right_hand': ['A#', 'G', 'D#', 'C', 'A#', 'G', 'D', 'A#', 'D#', 'C', 'D#', 'C', 'D#'],
    },
    'perfect': {
        'right_hand': ['D', 'E', 'G', 'G', 'B', 'A', 'G', 'B', 'G', 'A', 'B', 'B', 'A', 'G', 'G', 'G'],
        'left_hand': ['G', 'G', 'G', 'G', 'G', 'E', 'E', 'E', 'E', 'C', 'C', 'C', 'C'],
    },
}


def process_one_video(video_dir, output_base):
    """Process a single video: analyze + generate audio."""
    song_name = os.path.basename(video_dir)
    video_path = os.path.join(video_dir, 'video.webm')
    output_dir = os.path.join(output_base, f'output_{song_name}')

    if not os.path.exists(video_path):
        return {'song': song_name, 'error': 'video.webm not found'}

    t0 = time.time()
    try:
        data = analyze_video(
            video_path, output_dir,
            analysis_fps=10.0,
            ocr_enabled=False,  # Skip OCR for speed
            verbose=True,
        )
    except Exception as e:
        import traceback
        return {'song': song_name, 'error': str(e), 'traceback': traceback.format_exc()}

    elapsed = time.time() - t0

    # Generate audio
    notes_json = os.path.join(output_dir, 'notes.json')
    audio_prefix = os.path.join(output_dir, song_name)
    try:
        generate_from_json(notes_json, audio_prefix)
    except Exception as e:
        print(f"  Audio generation failed: {e}")

    # Collect stats
    notes = data.get('notes', [])
    rh_notes = [n for n in notes if 'right' in n.get('hand', '')]
    lh_notes = [n for n in notes if 'left' in n.get('hand', '')]

    stats = {
        'song': song_name,
        'total_notes': len(notes),
        'right_hand': len(rh_notes),
        'left_hand': len(lh_notes),
        'elapsed_seconds': round(elapsed, 1),
        'rh_first_16': [n['note_name'] for n in rh_notes[:16]],
        'lh_first_13': [n['note_name'] for n in lh_notes[:13]],
    }

    # Ground truth comparison
    if song_name in GROUND_TRUTH:
        gt = GROUND_TRUTH[song_name]
        if 'right_hand' in gt:
            gt_rh = gt['right_hand']
            detected_rh = stats['rh_first_16'][:len(gt_rh)]
            # Compare pitch class only (strip octave)
            det_pc = []
            for n in detected_rh:
                pc = n.rstrip('0123456789')
                det_pc.append(pc)
            matches = sum(1 for a, b in zip(det_pc, gt_rh) if a == b)
            total = len(gt_rh)
            stats['rh_match'] = f'{matches}/{total} ({100*matches/total:.0f}%)'
            stats['rh_ground_truth'] = gt_rh
            stats['rh_detected_pc'] = det_pc

        if 'left_hand' in gt:
            gt_lh = gt['left_hand']
            detected_lh = stats['lh_first_13'][:len(gt_lh)]
            det_pc = [n.rstrip('0123456789') for n in detected_lh]
            matches = sum(1 for a, b in zip(det_pc, gt_lh) if a == b)
            total = len(gt_lh)
            stats['lh_match'] = f'{matches}/{total} ({100*matches/total:.0f}%)'
            stats['lh_ground_truth'] = gt_lh
            stats['lh_detected_pc'] = det_pc

    return stats


def main():
    music_dir = os.path.join(os.path.dirname(__file__), 'music')
    output_base = os.path.join(os.path.dirname(__file__), 'tmp')
    os.makedirs(output_base, exist_ok=True)

    # Find all video directories
    video_dirs = sorted([
        os.path.join(music_dir, d)
        for d in os.listdir(music_dir)
        if os.path.isdir(os.path.join(music_dir, d))
        and os.path.exists(os.path.join(music_dir, d, 'video.webm'))
    ])

    print(f"Found {len(video_dirs)} videos to process:")
    for d in video_dirs:
        print(f"  - {os.path.basename(d)}")
    print()

    # Process in parallel (2 at a time to avoid memory issues)
    all_stats = []
    with ProcessPoolExecutor(max_workers=2) as executor:
        futures = {
            executor.submit(process_one_video, vd, output_base): os.path.basename(vd)
            for vd in video_dirs
        }
        for future in as_completed(futures):
            name = futures[future]
            try:
                stats = future.result()
                all_stats.append(stats)
                print(f"\n{'='*60}")
                print(f"  COMPLETED: {name}")
                if 'error' in stats:
                    print(f"  ERROR: {stats['error']}")
                else:
                    print(f"  Notes: {stats['total_notes']} (RH={stats['right_hand']}, LH={stats['left_hand']})")
                    print(f"  Time: {stats['elapsed_seconds']}s")
                    if 'rh_match' in stats:
                        print(f"  RH Ground Truth Match: {stats['rh_match']}")
                        print(f"    GT:  {stats.get('rh_ground_truth', [])}")
                        print(f"    Det: {stats.get('rh_detected_pc', [])}")
                    if 'lh_match' in stats:
                        print(f"  LH Ground Truth Match: {stats['lh_match']}")
                        print(f"    GT:  {stats.get('lh_ground_truth', [])}")
                        print(f"    Det: {stats.get('lh_detected_pc', [])}")
                print(f"{'='*60}")
            except Exception as e:
                print(f"\n  FAILED: {name}: {e}")
                all_stats.append({'song': name, 'error': str(e)})

    # Print summary
    print(f"\n\n{'='*60}")
    print(f"  FINAL SUMMARY")
    print(f"{'='*60}")
    for stats in sorted(all_stats, key=lambda s: s['song']):
        if 'error' in stats:
            print(f"  {stats['song']:40s} ERROR: {stats['error'][:40]}")
        else:
            match_info = ''
            if 'rh_match' in stats:
                match_info += f" RH={stats['rh_match']}"
            if 'lh_match' in stats:
                match_info += f" LH={stats['lh_match']}"
            print(f"  {stats['song']:40s} {stats['total_notes']:4d} notes  "
                  f"({stats['right_hand']} RH, {stats['left_hand']} LH)  "
                  f"{stats['elapsed_seconds']:5.1f}s{match_info}")
    print(f"{'='*60}")

    # Save stats
    stats_path = os.path.join(output_base, 'all_stats.json')
    with open(stats_path, 'w') as f:
        json.dump(all_stats, f, indent=2)
    print(f"\nStats saved to {stats_path}")


if __name__ == '__main__':
    main()
