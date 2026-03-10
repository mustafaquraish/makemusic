// ================================================================
//  Audio (Tone.js + Salamander Grand Piano)
// ================================================================

function initAudio() {
    if (samplesLoading || samplesLoaded) return Promise.resolve();
    samplesLoading = true;

    var indicator = document.getElementById('sample-loading-indicator');

    // Step 1: Instant playback via a lightweight PolySynth
    pianoLimiter = new Tone.Limiter(-3).toDestination();
    pianoSynth = new Tone.PolySynth(Tone.Synth, { maxPolyphony: 16 });
    pianoSynth.set({
        oscillator: { type: 'triangle' },
        envelope: { attack: 0.005, decay: 1.0, sustain: 0.1, release: 1.5 },
        volume: -12,
    });
    pianoSynth.connect(pianoLimiter);
    var vol = parseInt(document.getElementById('volume-slider').value);
    pianoSynth.volume.value = volumeToDb(vol);
    samplesLoaded = true;
    samplesLoading = false;

    // Step 2: Background-load Salamander and hot-swap
    indicator.innerHTML = '<span class="sample-spinner"></span> Upgrading to piano samples\u2026';
    indicator.style.display = 'block';

    var tempSampler = new Tone.Sampler({
        urls: {
            'A0': 'A0.mp3', 'C1': 'C1.mp3', 'D#1': 'Ds1.mp3', 'F#1': 'Fs1.mp3',
            'A1': 'A1.mp3', 'C2': 'C2.mp3', 'D#2': 'Ds2.mp3', 'F#2': 'Fs2.mp3',
            'A2': 'A2.mp3', 'C3': 'C3.mp3', 'D#3': 'Ds3.mp3', 'F#3': 'Fs3.mp3',
            'A3': 'A3.mp3', 'C4': 'C4.mp3', 'D#4': 'Ds4.mp3', 'F#4': 'Fs4.mp3',
            'A4': 'A4.mp3', 'C5': 'C5.mp3', 'D#5': 'Ds5.mp3', 'F#5': 'Fs5.mp3',
            'A5': 'A5.mp3', 'C6': 'C6.mp3', 'D#6': 'Ds6.mp3', 'F#6': 'Fs6.mp3',
            'A6': 'A6.mp3', 'C7': 'C7.mp3', 'D#7': 'Ds7.mp3',
            'A7': 'A7.mp3', 'C8': 'C8.mp3',
        },
        baseUrl: 'https://tonejs.github.io/audio/salamander/',
        release: 1,
        onload: function() {
            try { pianoSynth.disconnect(); pianoSynth.dispose(); } catch (e) {}
            try { pianoLimiter.disconnect(); pianoLimiter.dispose(); } catch (e) {}
            pianoLimiter = new Tone.Limiter(-3).toDestination();
            tempSampler.connect(pianoLimiter);
            var vol2 = parseInt(document.getElementById('volume-slider').value);
            tempSampler.volume.value = volumeToDb(vol2);
            pianoSynth = tempSampler;
            indicator.style.display = 'none';
            console.log('Salamander Piano samples loaded and hot-swapped');
        },
        onerror: function() {
            try { tempSampler.dispose(); } catch (e) {}
            indicator.style.display = 'none';
            console.log('Salamander load failed; keeping PolySynth');
        },
    });

    return Promise.resolve();
}

function playNote(keyIndex, duration) {
    if (!soundEnabled || !pianoSynth || !samplesLoaded) return;
    var noteName = PIANO_KEYS[keyIndex];
    if (!noteName) return;
    try {
        var dur = Math.max(0.05, Math.min(duration, 4));
        pianoSynth.triggerAttackRelease(noteName, dur);
    } catch (e) { /* polyphony overflow */ }
}

function stopAllNotes() {
    if (pianoSynth && samplesLoaded) {
        try { pianoSynth.releaseAll(); } catch (e) {}
    }
    activeNoteIds.clear();
}
