"""
Generate MIDI and synthesized audio (WAV/MP3) from extracted notes.

Usage:
    python src/mp3_generator.py <notes.json> <output_prefix>
    
Creates:
    <output_prefix>.mid  - MIDI file
    <output_prefix>.wav  - Synthesized WAV audio (via FluidSynth + SF2 soundfont)
    <output_prefix>.mp3  - MP3 (if ffmpeg available)
"""
import json
import sys
import os
import subprocess
import numpy as np
from typing import List, Dict, Optional

# MIDI generation
from midiutil import MIDIFile


NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

# Default SF2 soundfont path (relative to project root)
DEFAULT_SF2_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                'soundfonts', 'FluidR3_GM.sf2')


def note_name_to_midi(name: str) -> int:
    """Convert note name like 'C4' or 'A#3' to MIDI number."""
    note_part = ''
    octave_part = ''
    for ch in name:
        if ch.isdigit() or (ch == '-' and not octave_part):
            octave_part += ch
        else:
            note_part += ch
    
    if note_part not in NOTE_NAMES or not octave_part:
        return 60  # Default to middle C
    
    note_idx = NOTE_NAMES.index(note_part)
    octave = int(octave_part)
    return (octave + 1) * 12 + note_idx


def create_midi(notes: List[Dict], output_path: str, tempo: int = 120):
    """
    Create a MIDI file from extracted notes.
    
    Args:
        notes: List of note dicts with 'note_name', 'start_time', 'duration', 'hand'
        output_path: Path to write .mid file
        tempo: BPM (used for MIDI timing)
    """
    midi = MIDIFile(2)  # Two tracks: RH and LH
    
    midi.addTrackName(0, 0, "Right Hand")
    midi.addTrackName(1, 0, "Left Hand")
    midi.addTempo(0, 0, tempo)
    midi.addTempo(1, 0, tempo)
    
    # Program: 0 = Acoustic Grand Piano
    midi.addProgramChange(0, 0, 0, 0)
    midi.addProgramChange(1, 1, 0, 0)
    
    beats_per_second = tempo / 60.0
    
    # Sort notes by start time to process them in order
    sorted_notes = sorted(notes, key=lambda n: n['start_time'])
    
    # Track when each (track, pitch) combination ends to prevent overlaps
    # MIDIFile crashes on overlapping notes on the same track+pitch
    last_end: Dict[tuple, float] = {}  # (track, midi_num) -> end_beat
    
    for note in sorted_notes:
        midi_num = note_name_to_midi(note['note_name'])
        start_beat = note['start_time'] * beats_per_second
        duration_beats = max(0.1, note['duration'] * beats_per_second)
        velocity = 80
        
        hand = note.get('hand', 'right_hand')
        if 'left' in hand:
            track = 1
            channel = 1
        else:
            track = 0
            channel = 0
        
        key = (track, midi_num)
        end_beat = start_beat + duration_beats
        
        # If this note overlaps with a previous note on the same key,
        # truncate the previous by not allowing this one to start before it ends
        if key in last_end and start_beat < last_end[key]:
            # Gap between previous end and this start
            gap = start_beat - (last_end[key] - duration_beats)
            # Just move start to after previous end
            start_beat = last_end[key] + 0.01
            duration_beats = end_beat - start_beat
            if duration_beats < 0.05:
                continue  # Skip if too short after adjustment
        
        last_end[key] = start_beat + duration_beats
        midi.addNote(track, channel, midi_num, start_beat, duration_beats, velocity)
    
    with open(output_path, 'wb') as f:
        midi.writeFile(f)
    
    print(f"Created MIDI: {output_path}")


def synthesize_with_fluidsynth(midi_path: str, wav_path: str,
                                sf2_path: Optional[str] = None,
                                sample_rate: int = 44100) -> bool:
    """
    Render MIDI to WAV using FluidSynth with an SF2 soundfont.
    
    Returns True if successful, False if FluidSynth is unavailable.
    """
    if sf2_path is None:
        sf2_path = DEFAULT_SF2_PATH
    
    if not os.path.exists(sf2_path):
        print(f"  SF2 soundfont not found: {sf2_path}")
        return False
    
    try:
        result = subprocess.run(
            ['fluidsynth', '-ni', sf2_path, midi_path,
             '-F', wav_path, '-r', str(sample_rate)],
            capture_output=True, text=True, timeout=120
        )
        if result.returncode == 0 and os.path.exists(wav_path):
            print(f"Created WAV (FluidSynth): {wav_path}")
            return True
        else:
            print(f"  FluidSynth error: {result.stderr[:200]}")
            return False
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        print(f"  FluidSynth not available: {e}")
        return False


def synthesize_audio(notes: List[Dict], sample_rate: int = 44100) -> np.ndarray:
    """
    Synthesize piano-like audio from notes using additive synthesis.
    
    This is the FALLBACK when FluidSynth/SF2 is not available.
    Uses fundamental + harmonics with ADSR envelope for a piano-like tone.
    """
    if not notes:
        return np.zeros(sample_rate)
    
    max_end = max(n['start_time'] + n['duration'] for n in notes) + 2.0
    total_samples = int(max_end * sample_rate)
    audio = np.zeros(total_samples, dtype=np.float64)
    
    harmonics = [1.0, 0.5, 0.25, 0.12, 0.06]
    
    for i, note in enumerate(notes):
        midi = note_name_to_midi(note['note_name'])
        freq = 440.0 * 2**((midi - 69) / 12.0)
        
        start_sample = int(note['start_time'] * sample_rate)
        duration = max(0.05, note['duration'])
        total_dur = duration + 0.3
        num_samples = int(total_dur * sample_rate)
        
        if start_sample + num_samples > total_samples:
            num_samples = total_samples - start_sample
        
        if num_samples <= 0:
            continue
        
        t = np.arange(num_samples) / sample_rate
        
        attack = 0.005
        decay = min(0.3, duration * 0.4)
        sustain_level = 0.3
        release_start = duration
        release = 0.3
        
        envelope = np.ones(num_samples)
        for j in range(num_samples):
            time = t[j]
            if time < attack:
                envelope[j] = time / attack
            elif time < attack + decay:
                envelope[j] = 1.0 - (1.0 - sustain_level) * (time - attack) / decay
            elif time < release_start:
                envelope[j] = sustain_level
            else:
                rel_time = time - release_start
                envelope[j] = sustain_level * max(0, 1.0 - rel_time / release)
        
        wave = np.zeros(num_samples)
        for h_idx, h_amp in enumerate(harmonics):
            h_freq = freq * (h_idx + 1)
            if h_freq > sample_rate / 2:
                break
            wave += h_amp * np.sin(2 * np.pi * h_freq * t)
        
        wave *= envelope
        velocity_scale = 0.08
        
        end_sample = start_sample + num_samples
        audio[start_sample:end_sample] += wave * velocity_scale
        
        if (i + 1) % 50 == 0:
            print(f"  Synthesized {i + 1}/{len(notes)} notes...")
    
    peak = np.max(np.abs(audio))
    if peak > 0:
        audio = audio / peak * 0.9
    
    return audio


def save_wav(audio: np.ndarray, path: str, sample_rate: int = 44100):
    """Save audio as WAV file."""
    import wave
    import struct
    
    audio_16bit = (audio * 32767).astype(np.int16)
    
    with wave.open(path, 'w') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(audio_16bit.tobytes())
    
    print(f"Created WAV: {path} ({len(audio)/sample_rate:.1f}s)")


def wav_to_mp3(wav_path: str, mp3_path: str):
    """Convert WAV to MP3 using ffmpeg."""
    try:
        subprocess.run([
            'ffmpeg', '-y', '-i', wav_path,
            '-codec:a', 'libmp3lame', '-qscale:a', '2',
            mp3_path
        ], capture_output=True, check=True)
        print(f"Created MP3: {mp3_path}")
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"MP3 conversion failed (ffmpeg required): {e}")


def generate_from_json(json_path: str, output_prefix: str,
                       sf2_path: Optional[str] = None):
    """Generate MIDI and audio from a notes.json file."""
    with open(json_path) as f:
        data = json.load(f)
    
    notes = data['notes']
    print(f"Loaded {len(notes)} notes from {json_path}")
    
    # Create MIDI
    midi_path = output_prefix + '.mid'
    create_midi(notes, midi_path)
    
    # Try FluidSynth + SF2 first (proper piano sound)
    wav_path = output_prefix + '.wav'
    used_fluidsynth = synthesize_with_fluidsynth(midi_path, wav_path,
                                                  sf2_path=sf2_path)
    
    if not used_fluidsynth:
        # Fallback to additive synthesis
        print(f"Falling back to additive synthesis...")
        audio = synthesize_audio(notes)
        save_wav(audio, wav_path)
    
    # Convert to MP3
    mp3_path = output_prefix + '.mp3'
    wav_to_mp3(wav_path, mp3_path)
    
    return midi_path, wav_path, mp3_path


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print(f"Usage: python {sys.argv[0]} <notes.json> <output_prefix>")
        print(f"  Example: python {sys.argv[0]} tmp/output_easy/notes.json tmp/easy_synth")
        sys.exit(1)
    
    sf2 = sys.argv[3] if len(sys.argv) > 3 else None
    generate_from_json(sys.argv[1], sys.argv[2], sf2_path=sf2)
