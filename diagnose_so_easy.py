#!/usr/bin/env python3
"""Diagnose So Easy note fragmentation."""
import json
from collections import Counter

with open('tmp/output_so_easy_to_fall_in_love/notes.json') as f:
    data = json.load(f)

notes = data['notes']
print(f'Total notes: {len(notes)}')

# Show first 30 notes sorted by start_time
sorted_notes = sorted(notes, key=lambda n: n['start_time'])
print('\nFirst 30 notes by start_time:')
for i, n in enumerate(sorted_notes[:30]):
    print(f"  {i}: t={n['start_time']:.2f}s dur={n['duration']:.2f}s key={n.get('note_name','?')} hand={n['hand']} conf={n.get('confidence',0):.2f}")

# Count unique pitches
pitch_counts = Counter(n.get('note_name', '?') for n in notes)
print(f'\nPitch distribution: {dict(pitch_counts)}')

# Show all unique note names in temporal order (first 40)
print('\nNote sequence (first 40):')
seq = [n.get('note_name', '?') for n in sorted_notes[:40]]
print(' '.join(seq))

# Ground truth: A# G D# C A# G D A# D# C D# C D#
print('\nGround truth: A# G D# C A# G D A# D# C D# C D#')

# Show notes with very short durations (potential fragments)
short = [n for n in sorted_notes if n['duration'] < 0.3]
print(f'\nNotes with duration < 0.3s: {len(short)} out of {len(notes)}')
for n in short[:20]:
    print(f"  t={n['start_time']:.2f}s dur={n['duration']:.2f}s key={n.get('note_name','?')}")

# Detect consecutive same-pitch (potential fragmentation)
print('\nConsecutive same-pitch notes:')
for i in range(len(sorted_notes)-1):
    a, b = sorted_notes[i], sorted_notes[i+1]
    if a.get('note_name') == b.get('note_name') and a.get('note_name'):
        gap = b['start_time'] - (a['start_time'] + a['duration'])
        print(f"  {a.get('note_name')}: {a['start_time']:.2f}+{a['duration']:.2f} -> {b['start_time']:.2f}+{b['duration']:.2f} (gap={gap:.2f}s)")
