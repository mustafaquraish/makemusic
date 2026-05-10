// ================================================================
//  Global mutable state
// ================================================================

var notesData = null;
var pixelsPerSecond = 80;
var isPlaying = false;
var soundEnabled = true;
var playbackSpeed = 1;
var loopEnabled = false;
var playbackStartTime = 0;
var playbackTimeOffset = 0;
var animationFrameId = null;
var pianoSynth = null;
var pianoLimiter = null;
var activeNoteIds = new Set();
var samplesLoaded = false;
var samplesLoading = false;

var showRightHand = true;
var showLeftHand = true;
var rhColor = [183, 123, 192];
var lhColor = [75, 222, 195];

var totalDuration = 0;
var firstNoteTime = 0;

var userIsScrolling = false;
var wasPlayingBeforeScroll = false;
var scrollResumeTimer = null;
var programmaticScroll = false;

var noteElements = [];

// Edit mode
var editMode = false;
var selectedNoteId = null;
var editDragState = null;
var nextNoteId = 10000;
var editHand = 'right_hand';
var creationDragState = null;
var contextMenuNoteId = null;

// Markers (timeline sections like verse, chorus)
var nextMarkerId = 1;

// Lyrics mode
var lyricsMode = false;
var lyricsSortedNotes = [];
var lyricsHandFilter = 'all'; // 'all', 'right_hand', 'left_hand'

// Undo/Redo
var undoStack = [];
var redoStack = [];
var undoRedoInProgress = false;

// Dynamic bottom padding — computed in renderPianoRoll
var effectiveBottomPadding = BOTTOM_PADDING;

// Command palette
var commandPaletteOpen = false;
var commandPaletteSelectedIndex = 0;
var filteredCommands = [];

// View mode
var textNotesOnlyMode = false;
var textViewStripOctaveNumbers = false;
var textViewShowLyrics = false;

// Settings with defaults
var appSettings = {
    dropLines: true,
    noteLabels: true,
    density: true,
    scrollSpeed: 120,
    // height of the on‑screen piano keyboard in pixels
    keyboardHeight: 100,
    rhColorHex: '#6495ED',
    lhColorHex: '#48BF91'
};

// GitHub OAuth
var OAUTH_PROXY = 'https://github-oauth-proxy.mustafaq9.workers.dev';
var OAUTH_CLIENT_ID = (function() {
    if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
        return 'Ov23liXQfJJcoAaMIdJm';
    }
    return 'Ov23liVzEUg6aUgl7hm6';
})();
var ghConfig = null;
