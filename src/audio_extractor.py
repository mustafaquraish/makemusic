"""
Audio-based note extraction using librosa.

Uses onset detection + pitch estimation to extract notes from audio.
Serves as ground truth for validating visual note detection.
"""
import numpy as np
import librosa
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, field


# Standard piano frequencies (A0 = 27.5 Hz to C8 = 4186 Hz)
NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

# Enharmonic equivalents for display
FLAT_TO_SHARP = {
    'Db': 'C#', 'Eb': 'D#', 'Gb': 'F#', 'Ab': 'G#', 'Bb': 'A#'
}


@dataclass
class AudioNote:
    """A note detected from audio analysis."""
    note_name: str          # e.g. "C4", "G#3"
    midi_number: int        # MIDI note number (0-127)
    start_time: float       # seconds
    duration: float         # seconds
    frequency: float        # Hz
    confidence: float       # 0-1
    velocity: float         # relative volume 0-1


def midi_to_note_name(midi_num: int) -> str:
    """Convert MIDI note number to note name like C4, A#3."""
    octave = (midi_num // 12) - 1
    note_idx = midi_num % 12
    return f"{NOTE_NAMES[note_idx]}{octave}"


def note_name_to_midi(name: str) -> Optional[int]:
    """Convert note name like C4, Bb3 to MIDI number."""
    if not name or len(name) < 2:
        return None
    
    # Parse note letter
    letter = name[0].upper()
    if letter not in 'ABCDEFG':
        return None
    
    rest = name[1:]
    accidental = 0
    octave_str = ''
    
    i = 0
    while i < len(rest):
        ch = rest[i]
        if ch == '#':
            accidental += 1
        elif ch == 'b':
            accidental -= 1
        elif ch == '-' or ch.isdigit():
            octave_str = rest[i:]
            break
        i += 1
    
    if not octave_str:
        return None
    
    try:
        octave = int(octave_str)
    except ValueError:
        return None
    
    # Note index in chromatic scale
    base_notes = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}
    note_in_octave = base_notes.get(letter)
    if note_in_octave is None:
        return None
    
    midi = (octave + 1) * 12 + note_in_octave + accidental
    return midi


def hz_to_midi(freq: float) -> int:
    """Convert frequency in Hz to nearest MIDI note number."""
    if freq <= 0:
        return 0
    return int(round(69 + 12 * np.log2(freq / 440.0)))


def midi_to_hz(midi: int) -> float:
    """Convert MIDI note number to frequency in Hz."""
    return 440.0 * (2.0 ** ((midi - 69) / 12.0))


def extract_notes_from_audio(audio_path: str,
                              min_note_duration: float = 0.05,
                              onset_threshold: float = 0.3,
                              pitch_confidence_threshold: float = 0.5,
                              min_midi: int = 21,   # A0
                              max_midi: int = 108,  # C8
                              ) -> List[AudioNote]:
    """
    Extract notes from an audio file using onset detection and pitch tracking.
    
    Approach:
    1. Load audio and compute onset frames  
    2. Use pyin pitch tracking for fundamental frequency
    3. Segment into notes based on onsets and pitch changes
    4. Filter by confidence and duration
    
    Args:
        audio_path: Path to audio file (wav, mp3, etc.)
        min_note_duration: Minimum note length in seconds
        onset_threshold: Sensitivity for onset detection (lower = more sensitive)
        pitch_confidence_threshold: Minimum confidence for pitch detection
        min_midi: Lowest MIDI note to consider
        max_midi: Highest MIDI note to consider
    
    Returns:
        List of AudioNote objects sorted by start_time
    """
    # Load audio
    y, sr = librosa.load(audio_path, sr=22050, mono=True)
    
    # Compute onset strength and onset frames
    onset_env = librosa.onset.onset_strength(y=y, sr=sr)
    onset_frames = librosa.onset.onset_detect(
        y=y, sr=sr, onset_envelope=onset_env,
        backtrack=True, delta=onset_threshold
    )
    onset_times = librosa.frames_to_time(onset_frames, sr=sr)
    
    # Pitch tracking using pyin (probabilistic YIN)
    fmin = midi_to_hz(min_midi)
    fmax = midi_to_hz(max_midi)
    
    f0, voiced_flag, voiced_prob = librosa.pyin(
        y, fmin=fmin, fmax=fmax, sr=sr,
        frame_length=2048, hop_length=512
    )
    
    times = librosa.times_like(f0, sr=sr, hop_length=512)
    
    # Convert f0 to MIDI note numbers
    midi_notes = np.zeros_like(f0)
    for i, freq in enumerate(f0):
        if freq is not None and not np.isnan(freq) and freq > 0:
            midi_notes[i] = hz_to_midi(freq)
        else:
            midi_notes[i] = 0
    
    # Also compute a chromagram for polyphonic detection
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr, hop_length=512)
    chroma_times = librosa.times_like(chroma, sr=sr, hop_length=512)
    
    # RMS energy for velocity estimation
    rms = librosa.feature.rms(y=y, hop_length=512)[0]
    rms_max = rms.max() if rms.max() > 0 else 1.0
    
    # --- Strategy 1: Onset-based note extraction ---
    notes = []
    
    # For each onset, find the pitch in that region
    for i, onset_t in enumerate(onset_times):
        # End time: next onset or +2 seconds
        if i + 1 < len(onset_times):
            end_t = onset_times[i + 1]
        else:
            end_t = onset_t + 2.0
        
        # Find pitch frames in this window
        mask = (times >= onset_t) & (times < end_t)
        if not np.any(mask):
            continue
        
        window_midi = midi_notes[mask]
        window_voiced = voiced_prob[mask] if voiced_prob is not None else np.ones(mask.sum())
        window_rms = rms[mask[:len(rms)]] if mask.sum() <= len(rms) else rms[-mask.sum():]
        
        # Filter to voiced frames with valid midi
        valid = (window_midi > 0) & (window_voiced > pitch_confidence_threshold)
        if not np.any(valid):
            continue
        
        # Find the dominant pitch (most common MIDI note)
        valid_midi = window_midi[valid]
        if len(valid_midi) == 0:
            continue
        
        # Use median for robustness
        dominant_midi = int(round(np.median(valid_midi)))
        
        if dominant_midi < min_midi or dominant_midi > max_midi:
            continue
        
        # Calculate actual duration (how long this pitch persists)
        # Find the extent of this pitch
        pitch_region = midi_notes[mask]
        duration_frames = 0
        for m in pitch_region:
            if abs(m - dominant_midi) <= 0.5:
                duration_frames += 1
            elif duration_frames > 0:
                break
        
        frame_duration = 512 / sr
        duration = max(duration_frames * frame_duration, min_note_duration)
        
        # Cap at the onset window
        duration = min(duration, end_t - onset_t)
        
        # Confidence: average voiced probability
        conf = float(np.mean(window_voiced[valid]))
        
        # Velocity from RMS
        rms_slice = rms[mask[:len(rms)]] if np.sum(mask[:len(rms)]) > 0 else np.array([0.5])
        velocity = float(np.mean(rms_slice) / rms_max)
        
        note = AudioNote(
            note_name=midi_to_note_name(dominant_midi),
            midi_number=dominant_midi,
            start_time=round(float(onset_t), 3),
            duration=round(float(duration), 3),
            frequency=round(float(midi_to_hz(dominant_midi)), 1),
            confidence=round(conf, 3),
            velocity=round(velocity, 3)
        )
        notes.append(note)
    
    # --- Strategy 2: Chroma-based polyphonic extraction ---
    # Detect notes that might be missed by monophonic pyin
    # Look for strong chroma energy between onsets
    poly_notes = _extract_polyphonic_notes(
        chroma, chroma_times, onset_times, rms, rms_max,
        min_note_duration, min_midi, max_midi, sr
    )
    
    # Merge polyphonic notes with onset-based, avoiding duplicates
    for pn in poly_notes:
        is_dup = False
        for n in notes:
            if (abs(n.start_time - pn.start_time) < 0.1 and 
                abs(n.midi_number - pn.midi_number) <= 1):
                is_dup = True
                break
        if not is_dup:
            notes.append(pn)
    
    # Limit to at most 4 notes per onset (reduce polyphonic noise)
    notes.sort(key=lambda n: (n.start_time, -n.confidence))
    filtered = []
    i = 0
    while i < len(notes):
        # Group notes with same onset time (within 50ms)
        group = [notes[i]]
        j = i + 1
        while j < len(notes) and abs(notes[j].start_time - notes[i].start_time) < 0.05:
            group.append(notes[j])
            j += 1
        # Keep top 4 by confidence
        group.sort(key=lambda n: -n.confidence)
        filtered.extend(group[:4])
        i = j
    notes = filtered
    
    # Sort by time
    notes.sort(key=lambda n: (n.start_time, n.midi_number))
    
    # Remove very short notes
    notes = [n for n in notes if n.duration >= min_note_duration]
    
    return notes


def _extract_polyphonic_notes(chroma, chroma_times, onset_times, rms, rms_max,
                               min_duration, min_midi, max_midi, sr):
    """Extract additional notes from chromagram for polyphonic content."""
    notes = []
    
    # For each onset window, check all 12 chroma bins for strong energy
    for i, onset_t in enumerate(onset_times):
        end_t = onset_times[i + 1] if i + 1 < len(onset_times) else onset_t + 2.0
        
        mask = (chroma_times >= onset_t) & (chroma_times < end_t)
        if not np.any(mask):
            continue
        
        window_chroma = chroma[:, mask]
        
        # Find chroma bins with strong energy
        mean_energy = window_chroma.mean(axis=1)
        threshold = max(mean_energy.max() * 0.4, 0.15)
        
        active_chromas = np.where(mean_energy > threshold)[0]
        
        for chroma_idx in active_chromas:
            # Chroma gives us pitch class, we need to determine octave
            # Use the window's median energy profile to estimate octave
            # This is approximate - chroma alone doesn't give octave
            
            # Map chroma index to note name
            # librosa chroma: index 0 = C, 1 = C#, ...
            note_name_base = NOTE_NAMES[chroma_idx]
            
            # Estimate octave from frequency content
            # For piano, most common range is C3-C6 (MIDI 48-84)
            # We'll use the chroma energy as a rough guide
            for octave in range(3, 6):
                midi_num = (octave + 1) * 12 + chroma_idx
                if midi_num < min_midi or midi_num > max_midi:
                    continue
                
                note_name = f"{note_name_base}{octave}"
                
                # Only add if there are at least 3 active frames
                active_frames = np.sum(window_chroma[chroma_idx] > threshold)
                if active_frames < 3:
                    continue
                
                frame_dur = 512 / sr
                duration = min(active_frames * frame_dur, end_t - onset_t)
                
                if duration < min_duration:
                    continue
                
                rms_mask = (chroma_times >= onset_t) & (chroma_times < end_t)
                rms_slice = rms[rms_mask[:len(rms)]] if np.sum(rms_mask[:len(rms)]) > 0 else np.array([0.5])
                velocity = float(np.mean(rms_slice) / rms_max)
                
                notes.append(AudioNote(
                    note_name=note_name,
                    midi_number=midi_num,
                    start_time=round(float(onset_t), 3),
                    duration=round(float(duration), 3),
                    frequency=round(float(midi_to_hz(midi_num)), 1),
                    confidence=round(float(mean_energy[chroma_idx]), 3),
                    velocity=round(velocity, 3)
                ))
                break  # Only use first matching octave
    
    return notes


def compare_note_sequences(audio_notes: List[AudioNote],
                           visual_notes: list,
                           time_tolerance: float = 0.5,
                           ) -> Dict:
    """
    Compare audio-extracted notes with visually-extracted notes.
    
    Args:
        audio_notes: Notes from audio analysis
        visual_notes: Notes from visual analysis (dicts with note_name, start_time, etc.)
        time_tolerance: Max time difference (seconds) to consider a match
    
    Returns:
        Dict with comparison results
    """
    matched = []
    audio_unmatched = list(range(len(audio_notes)))
    visual_unmatched = list(range(len(visual_notes)))
    
    # For each audio note, find the closest visual note
    for ai, anote in enumerate(audio_notes):
        best_vi = None
        best_score = float('inf')
        
        a_midi = anote.midi_number
        
        for vi in visual_unmatched:
            vnote = visual_notes[vi]
            v_name = vnote.get('note_name', '')
            v_midi = note_name_to_midi(v_name)
            if v_midi is None:
                continue
            
            time_diff = abs(anote.start_time - vnote['start_time'])
            if time_diff > time_tolerance:
                continue
            
            pitch_diff = abs(a_midi - v_midi)
            score = time_diff + pitch_diff * 0.1  # Prioritize time proximity
            
            if score < best_score:
                best_score = score
                best_vi = vi
        
        if best_vi is not None:
            vnote = visual_notes[best_vi]
            v_midi = note_name_to_midi(vnote.get('note_name', ''))
            matched.append({
                'audio_note': anote.note_name,
                'visual_note': vnote.get('note_name', '?'),
                'audio_midi': a_midi,
                'visual_midi': v_midi,
                'pitch_match': a_midi == v_midi,
                'pitch_diff': abs(a_midi - (v_midi or 0)),
                'time_diff': abs(anote.start_time - vnote['start_time']),
                'audio_time': anote.start_time,
                'visual_time': vnote['start_time'],
            })
            audio_unmatched.remove(ai)
            visual_unmatched.remove(best_vi)
    
    pitch_matches = sum(1 for m in matched if m['pitch_match'])
    close_matches = sum(1 for m in matched if m['pitch_diff'] <= 2)
    
    return {
        'total_audio_notes': len(audio_notes),
        'total_visual_notes': len(visual_notes),
        'matched_pairs': len(matched),
        'exact_pitch_matches': pitch_matches,
        'close_pitch_matches': close_matches,
        'audio_only': len(audio_unmatched),
        'visual_only': len(visual_unmatched),
        'match_rate': pitch_matches / max(len(matched), 1),
        'close_match_rate': close_matches / max(len(matched), 1),
        'avg_time_diff': np.mean([m['time_diff'] for m in matched]) if matched else 0,
        'avg_pitch_diff': np.mean([m['pitch_diff'] for m in matched]) if matched else 0,
        'matches': matched,
        'audio_unmatched_indices': audio_unmatched,
        'visual_unmatched_indices': visual_unmatched,
    }


def notes_to_list(notes: List[AudioNote]) -> List[Dict]:
    """Convert AudioNote list to list of dicts for JSON export."""
    return [
        {
            'note_name': n.note_name,
            'midi_number': int(n.midi_number),
            'start_time': float(n.start_time),
            'duration': float(n.duration),
            'frequency': float(n.frequency),
            'confidence': float(n.confidence),
            'velocity': float(n.velocity),
        }
        for n in notes
    ]
