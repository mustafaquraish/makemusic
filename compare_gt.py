#!/usr/bin/env python3
"""Compare detected notes against expanded ground truth from manual.md.

Uses Needleman-Wunsch sequence alignment to find the best alignment
between GT and detection, showing missing/extra/wrong notes clearly.
"""
import json

# Expanded GT from manual.md Perfect RH:
# D E G G  B A G (B+G) A B B A G G G G A B (A + F#) G B A G B D B A G G G G A B C C B A A A G G A B (A + F#)
# Simultaneous notes sorted by center_x (left to right on piano):
#   (B+G) -> G, B  (G is cx~1178, B is cx~1353)
#   (A+F#) -> F#, A  (F# is cx~1122, A is cx~1265)
gt = [
    'D', 'E', 'G', 'G',          # notes 0-3
    'B', 'A', 'G',               # notes 4-6
    'G', 'B',                    # note 7-8: (B+G) simultaneous
    'A', 'B', 'B', 'A',          # notes 9-12
    'G', 'G', 'G', 'G',          # notes 13-16
    'A', 'B',                    # notes 17-18
    'F#', 'A',                   # notes 19-20: (A+F#) simultaneous
    'G', 'B', 'A', 'G',          # notes 21-24
    'B', 'D', 'B', 'A',          # notes 25-28
    'G', 'G', 'G', 'G',          # notes 29-32
    'A', 'B', 'C', 'C',          # notes 33-36
    'B', 'A', 'A', 'A',          # notes 37-40 (assuming A A from manual)
    'G', 'G', 'A', 'B',          # notes 41-44
    'F#', 'A',                   # notes 45-46: (A+F#) simultaneous
]

with open('tmp/output_perfect/notes.json') as f:
    data = json.load(f)
rh = [n for n in data['notes'] if 'right' in n.get('hand', '')]
det_notes = rh[:60]  # take more than GT to find extras
det = [n['note_name'].rstrip('0123456789') for n in det_notes]

# ---- Needleman-Wunsch alignment ----
MATCH = 2
MISMATCH = -1
GAP = -1

n, m = len(gt), len(det)
dp = [[0]*(m+1) for _ in range(n+1)]
for i in range(1, n+1): dp[i][0] = dp[i-1][0] + GAP
for j in range(1, m+1): dp[0][j] = dp[0][j-1] + GAP
for i in range(1, n+1):
    for j in range(1, m+1):
        match_score = dp[i-1][j-1] + (MATCH if gt[i-1] == det[j-1] else MISMATCH)
        dp[i][j] = max(match_score, dp[i-1][j] + GAP, dp[i][j-1] + GAP)

# Traceback
aligned_gt = []
aligned_det = []
aligned_det_idx = []
i, j = n, m
while i > 0 or j > 0:
    if i > 0 and j > 0 and dp[i][j] == dp[i-1][j-1] + (MATCH if gt[i-1] == det[j-1] else MISMATCH):
        aligned_gt.append(gt[i-1])
        aligned_det.append(det[j-1])
        aligned_det_idx.append(j-1)
        i -= 1; j -= 1
    elif i > 0 and dp[i][j] == dp[i-1][j] + GAP:
        aligned_gt.append(gt[i-1])
        aligned_det.append('---')
        aligned_det_idx.append(None)
        i -= 1
    else:
        aligned_gt.append('---')
        aligned_det.append(det[j-1])
        aligned_det_idx.append(j-1)
        j -= 1

aligned_gt.reverse()
aligned_det.reverse()
aligned_det_idx.reverse()

# Print aligned comparison
print(f'GT len:  {len(gt)}')
print(f'Det len: {len(det)}')
print()

matches = 0
missing = 0
extra = 0
wrong = 0
for k in range(len(aligned_gt)):
    g = aligned_gt[k]
    d = aligned_det[k]
    di = aligned_det_idx[k]
    
    if g == d:
        status = '  OK'
        matches += 1
    elif g == '---':
        status = ' EXTRA'
        extra += 1
    elif d == '---':
        status = ' MISSING'
        missing += 1
    else:
        status = ' WRONG'
        wrong += 1
    
    if di is not None:
        dn = det_notes[di]
        info = f't={dn["start_time"]:.2f} dur={dn["duration"]:.2f} cx={dn.get("center_x",0):.0f}'
    else:
        info = ''
    
    print(f'{k:3d}: GT={g:>3}  Det={d:>5} {status:>8}  {info}')

total = len(gt)
print(f'\nMatches: {matches}/{total} ({100*matches/total:.0f}%)')
print(f'Missing: {missing}, Extra: {extra}, Wrong: {wrong}')
