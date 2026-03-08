#!/usr/bin/env python3
"""Diagnose Perfect pitch mapping."""
import json

with open('tmp/output_perfect/notes.json') as f:
    data = json.load(f)

notes = sorted(data['notes'], key=lambda n: n['start_time'])
rh = [n for n in notes if n['hand'] == 'right_hand']

print('First 20 RH notes:')
for i, n in enumerate(rh[:20]):
    cx = n.get('avg_cx', 0)
    print(f"  {i}: t={n['start_time']:.2f}s dur={n['duration']:.2f}s key={n.get('note_name','?')} cx={cx:.0f}")

print()
print('Ground truth RH: D E F F B A G (B+G) A B B A G G G')
print('Detected RH pitches:', ' '.join(n.get('note_name','?') for n in rh[:16]))

# Check cx positions for the notes that should be F
print()
for i in [2, 3]:
    if i < len(rh):
        n = rh[i]
        print(f"Note {i} (should be F): cx={n.get('avg_cx',0):.0f} -> mapped to {n.get('note_name','?')}")

# F4=cx1090, F#4=cx1127, G4=cx1177
# Check gap between E4=cx1002 and F4=cx1090
print()
print("Key center_x values from keyboard map:")
print("  E4 = 1002")
print("  F4 = 1090") 
print("  F#4 = 1127 (black)")
print("  G4 = 1177")
print(f"  Gap E4->F4 = {1090-1002} pixels (88px)")
print(f"  Gap F4->G4 = {1177-1090} pixels (87px)")
print(f"  This is a whole octave pattern, E->F should be 1 semitone (same as C->C#)")
print()

# Show all unique cx values for notes detected as G4
g4_rh = [n for n in rh if n.get('note_name', '') == 'G4']
print(f"All notes named G4 (first 10 cx values): {[round(n.get('avg_cx',0)) for n in g4_rh[:10]]}")

# F notes
f4_rh = [n for n in rh if n.get('note_name', '') == 'F4']
print(f"All notes named F4 (first 10 cx values): {[round(n.get('avg_cx',0)) for n in f4_rh[:10]]}")

# Notes in cx range 1060-1200 (F4-G4 zone)
fg_zone = [n for n in rh if 1060 < n.get('avg_cx',0) < 1200]
print(f"\nNotes in F4-G4 zone (cx 1060-1200): {len(fg_zone)}")
for n in fg_zone[:15]:
    print(f"  cx={n.get('avg_cx',0):.0f} -> {n.get('note_name','?')} t={n['start_time']:.2f}s")

# LH analysis
lh = [n for n in notes if n['hand'] == 'left_hand']
print(f"\nFirst 20 LH notes:")
for i, n in enumerate(lh[:20]):
    print(f"  {i}: t={n['start_time']:.2f}s dur={n['duration']:.2f}s key={n.get('note_name','?')} cx={n.get('avg_cx',0):.0f}")
print('Ground truth LH: G G G G G E E E E C C C C')
print('Detected LH pitches:', ' '.join(n.get('note_name','?') for n in lh[:13]))
