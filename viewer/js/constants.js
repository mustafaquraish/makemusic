// ================================================================
//  Piano key definitions and utility functions
// ================================================================

var NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'];

var PIANO_88 = [];
for (var octave = 0; octave <= 8; octave++) {
    for (var i = 0; i < NOTE_NAMES.length; i++) {
        PIANO_88.push(NOTE_NAMES[i] + octave);
    }
}

var A0_INDEX = NOTE_NAMES.indexOf('A');
var PIANO_KEYS = PIANO_88.slice(A0_INDEX, A0_INDEX + 88);

/** Bottom padding in px below the last note in the piano roll */
var BOTTOM_PADDING = 80;

function isBlackKey(keyName) {
    return keyName ? keyName.includes('#') : false;
}

function hexToRgb(hex) {
    return [
        parseInt(hex.slice(1, 3), 16),
        parseInt(hex.slice(3, 5), 16),
        parseInt(hex.slice(5, 7), 16)
    ];
}

function rgbToHex(rgb) {
    return '#' + rgb.map(function(c) { return ('0' + c.toString(16)).slice(-2); }).join('');
}

function formatTimeFull(seconds) {
    var s = Math.max(0, seconds);
    var m = Math.floor(s / 60);
    var sec = Math.floor(s % 60);
    return m + ':' + (sec < 10 ? '0' : '') + sec;
}

function volumeToDb(val) {
    if (val <= 0) return -Infinity;
    return (val / 100) * 40 - 40;
}

function fuzzyMatch(query, text) {
    query = query.toLowerCase();
    text = text.toLowerCase();
    if (text.includes(query)) return true;
    var qi = 0;
    for (var ti = 0; ti < text.length && qi < query.length; ti++) {
        if (text[ti] === query[qi]) qi++;
    }
    return qi === query.length;
}

/**
 * Compute note display color (darkened for sharps).
 * Returns { r, g, b, r2, g2, b2 } for gradient endpoints.
 */
function getNoteColors(colorRgb, noteName) {
    var r = colorRgb[0], g = colorRgb[1], b = colorRgb[2];
    if ((noteName || '').includes('#')) {
        r = Math.max(0, Math.round(r * 0.75));
        g = Math.max(0, Math.round(g * 0.75));
        b = Math.max(0, Math.round(b * 0.75));
    }
    return {
        r: r, g: g, b: b,
        r2: Math.max(0, r - 30),
        g2: Math.max(0, g - 30),
        b2: Math.max(0, b - 30)
    };
}
