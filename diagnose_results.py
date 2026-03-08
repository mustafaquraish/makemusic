#!/usr/bin/env python3
"""Quick analysis of So Easy and Perfect results."""
import json

# === So Easy ===
print("=== SO EASY TO FALL IN LOVE ===")
with open('tmp/output_so_easy_to_fall_in_love/notes.json') as f:
    data = json.load(f)

notes = sorted(data['notes'], key=lambda n: n['start_time'])
print(f"Total notes: {len(notes)}")
print(f"\nFirst 20 notes:")
for i, n in enumerate(notes[:20]):
    print(f"  {i}: t={n['start_time']:.2f}s dur={n['duration']:.2f}s key={n.get('note_name','?')} det={n.get('detection_count',0)}")

print(f"\nGT:  A# G D# C A# G D A# D# C D# C D#")
pitches = [n.get('note_name','?').replace('4','').replace('3','') for n in notes[:20]]
print(f"Det: {' '.join(pitches[:13])}")

# Check for consecutive same-pitch
print(f"\nConsecutive same-pitch:")
for i in range(min(20, len(notes)-1)):
    a, b = notes[i], notes[i+1]
    an = a.get('note_name','')
    bn = b.get('note_name','')
    if an == bn:
        gap = b['start_time'] - (a['start_time'] + a['duration'])
        print(f"  {i}-{i+1}: {an} gap={gap:.2f}s dur1={a['duration']:.2f}s dur2={b['duration']:.2f}s")

# === Perfect ===
print("\n\n=== PERFECT ===")
with open('tmp/output_perfect/notes.json') as f:
    data = json.load(f)

notes = sorted(data['notes'], key=lambda n: n['start_time'])
rh = [n for n in notes if n['hand'] == 'right_hand']
lh = [n for n in notes if n['hand'] == 'left_hand']

print(f"Total: {len(notes)}, RH: {len(rh)}, LH: {len(lh)}")
print(f"\nFirst 20 RH notes:")
for i, n in enumerate(rh[:20]):
    print(f"  {i}: t={n['start_time']:.2f}s dur={n['duration']:.2f}s key={n.get('note_name','?')} cx={n.get('center_x',0):.0f} det={n.get('detection_count',0)}")

print(f"\nGT:  D E F F B A G (B+G) A B B A G G G")
print(f"Det: {' '.join(n.get('note_name','?') for n in rh[:16])}")

print(f"\nFirst 16 LH notes:")
for i, n in enumerate(lh[:16]):
    print(f"  {i}: t={n['start_time']:.2f}s dur={n['duration']:.2f}s key={n.get('note_name','?')} cx={n.get('center_x',0):.0f}")

print(f"\nGT:  G G G G G E E E E C C C C")
print(f"Det: {' '.join(n.get('note_name','?') for n in lh[:13])}")

# Check the 3rd RH note (should be F, detected as G)
if len(rh) > 2:
    n = rh[2]
    print(f"\nNote 3 (should be F): cx={n.get('center_x',0):.0f}, mapped to {n.get('note_name','?')}")
    # F4=cx1090, F#4=cx1127, G4=cx1177
    print(f"  Distance to F4 (cx=1090): {abs(n.get('center_x',0) - 1090):.0f}px")
    print(f"  Distance to F#4 (cx=1127): {abs(n.get('center_x',0) - 1127):.0f}px")
    print(f"  Distance to G4 (cx=1177): {abs(n.get('center_x',0) - 1177):.0f}px")
