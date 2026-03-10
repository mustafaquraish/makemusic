// ================================================================
//  Edit mode, note CRUD, drag/resize, context menu
// ================================================================

// Helper: re-render keeping the current scroll position
function rerenderPreservingScroll() {
    var container = document.getElementById('piano-roll-container');
    var saved = container.scrollTop;
    renderPianoRoll();
    container.scrollTop = saved;
}

function getTimeAtY(y) {
    var roll = document.getElementById('piano-roll');
    var totalHeight = parseFloat(roll.style.height) || 0;
    var bottomY = totalHeight - BOTTOM_PADDING;
    return (bottomY - y) / pixelsPerSecond;
}

function getKeyIndexAtX(clientX) {
    if (!window.keyLayout) return 39;
    var container = document.getElementById('piano-roll-container');
    var containerRect = container.getBoundingClientRect();
    var xPct = ((clientX - containerRect.left) / containerRect.width) * 100;
    var layout = window.keyLayout;
    var bestKey = layout.minKey;
    var bestDist = Infinity;
    for (var i = layout.minKey; i <= layout.maxKey; i++) {
        var keyCenter = getKeyXPercent(i);
        var dist = Math.abs(keyCenter - xPct);
        if (dist < bestDist) {
            bestDist = dist;
            bestKey = i;
        }
    }
    return bestKey;
}

function toggleEditMode() {
    editMode = !editMode;
    document.body.classList.toggle('edit-mode', editMode);
    document.getElementById('edit-mode-btn').classList.toggle('active', editMode);
    if (!editMode) {
        deselectNote();
    }
}

function selectNote(noteId) {
    deselectNote();
    selectedNoteId = noteId;
    var el = document.querySelector('.note-block[data-note-id="' + noteId + '"]');
    if (el) el.classList.add('selected');
}

function deselectNote() {
    if (selectedNoteId !== null) {
        var el = document.querySelector('.note-block.selected');
        if (el) el.classList.remove('selected');
        selectedNoteId = null;
    }
}

function setEditHand(hand) {
    editHand = hand;
    document.getElementById('edit-hand-rh').classList.toggle('active', hand === 'right_hand');
    document.getElementById('edit-hand-lh').classList.toggle('active', hand === 'left_hand');
}

function addNoteAtPosition(clientX, clientY, duration) {
    if (!notesData) return;
    var container = document.getElementById('piano-roll-container');
    var containerRect = container.getBoundingClientRect();
    var scrollY = container.scrollTop + (clientY - containerRect.top);
    var time = getTimeAtY(scrollY);
    var keyIndex = getKeyIndexAtX(clientX);
    var noteName = PIANO_KEYS[keyIndex] || 'C4';
    var hand = editHand;
    var color = hand === 'right_hand' ? rhColor : lhColor;

    var newNote = {
        id: nextNoteId++,
        note_name: noteName,
        start_time: Math.max(0, time),
        duration: duration || 1.0,
        hand: hand,
        key_index: keyIndex,
        center_x: 0,
        color_rgb: color.slice()
    };

    notesData.notes.push(newNote);
    rerenderPreservingScroll();
    selectNote(newNote.id);
}

function deleteSelectedNote() {
    if (selectedNoteId === null || !notesData) return;
    var idx = notesData.notes.findIndex(function(n) { return n.id === selectedNoteId; });
    if (idx !== -1) {
        notesData.notes.splice(idx, 1);
        selectedNoteId = null;
        rerenderPreservingScroll();
    }
}

function toggleSelectedNoteHand() {
    if (selectedNoteId === null || !notesData) return;
    var note = notesData.notes.find(function(n) { return n.id === selectedNoteId; });
    if (!note) return;
    note.hand = note.hand === 'right_hand' ? 'left_hand' : 'right_hand';
    note.color_rgb = (note.hand === 'right_hand' ? rhColor : lhColor).slice();
    rerenderPreservingScroll();
    selectNote(note.id);
}

function duplicateNote(noteId) {
    if (!notesData) return;
    var note = notesData.notes.find(function(n) { return n.id === noteId; });
    if (!note) return;
    var newNote = JSON.parse(JSON.stringify(note));
    newNote.id = nextNoteId++;
    newNote.start_time = note.start_time + note.duration + 0.1;
    notesData.notes.push(newNote);
    rerenderPreservingScroll();
    selectNote(newNote.id);
}

// ================================================================
//  Context menu
// ================================================================

function showContextMenu(x, y, noteId) {
    contextMenuNoteId = noteId;
    selectNote(noteId);
    var menu = document.getElementById('context-menu');
    var menuW = 180, menuH = 120;
    var winW = window.innerWidth, winH = window.innerHeight;
    var left = (x + menuW > winW) ? x - menuW : x;
    var top = (y + menuH > winH) ? y - menuH : y;
    menu.style.left = Math.max(0, left) + 'px';
    menu.style.top = Math.max(0, top) + 'px';
    menu.classList.add('visible');
}

function hideContextMenu() {
    document.getElementById('context-menu').classList.remove('visible');
    document.getElementById('context-menu-empty').classList.remove('visible');
    contextMenuNoteId = null;
}

function showEmptyContextMenu(x, y, time, clientX, clientY) {
    hideContextMenu();
    var menu = document.getElementById('context-menu-empty');
    menu.dataset.clickTime = time;
    menu.dataset.clickClientX = clientX;
    menu.dataset.clickClientY = clientY;
    var menuW = 200, menuH = 100;
    var winW = window.innerWidth, winH = window.innerHeight;
    var left = (x + menuW > winW) ? x - menuW : x;
    var top = (y + menuH > winH) ? y - menuH : y;
    menu.style.left = Math.max(0, left) + 'px';
    menu.style.top = Math.max(0, top) + 'px';
    menu.classList.add('visible');
}

// ================================================================
//  Marker CRUD with inline input
// ================================================================

// State for marker inline input
var markerInputMode = null; // null | { type: 'add', time: Number } | { type: 'edit', id: Number }

function addMarkerAtTime(time, label) {
    if (!notesData) return;
    if (!notesData.markers) notesData.markers = [];
    var marker = {
        id: nextMarkerId++,
        time: Math.max(0, time),
        label: label || 'Section'
    };
    notesData.markers.push(marker);
    notesData.markers.sort(function(a, b) { return a.time - b.time; });
    rerenderPreservingScroll();
    return marker;
}

function showMarkerInput(time, existingMarkerId) {
    hideMarkerInput();
    var overlay = document.getElementById('marker-input-overlay');
    var input = document.getElementById('marker-input');

    if (existingMarkerId !== undefined) {
        // Edit existing marker
        var marker = notesData.markers.find(function(m) { return m.id === existingMarkerId; });
        if (!marker) return;
        markerInputMode = { type: 'edit', id: existingMarkerId };
        input.value = marker.label || '';

        // Position near the marker line
        var markerEl = document.querySelector('.marker-line[data-marker-id="' + existingMarkerId + '"]');
        if (markerEl) {
            var rect = markerEl.getBoundingClientRect();
            overlay.style.left = (rect.left + 60) + 'px';
            overlay.style.top = (rect.top - 20) + 'px';
        } else {
            overlay.style.left = '50%';
            overlay.style.top = '50%';
        }
    } else {
        // Add new marker
        markerInputMode = { type: 'add', time: time };
        input.value = '';

        // Position at center of visible area
        var container = document.getElementById('piano-roll-container');
        var containerRect = container.getBoundingClientRect();
        var roll = document.getElementById('piano-roll');
        var totalHeight = parseFloat(roll.style.height) || container.clientHeight;
        var bottomY = totalHeight - BOTTOM_PADDING;
        var y = bottomY - time * pixelsPerSecond;
        var screenY = y - container.scrollTop + containerRect.top;
        overlay.style.left = (containerRect.left + 100) + 'px';
        overlay.style.top = Math.max(50, Math.min(screenY, window.innerHeight - 50)) + 'px';
    }

    overlay.style.display = 'block';
    input.focus();
    input.select();
}

function hideMarkerInput() {
    document.getElementById('marker-input-overlay').style.display = 'none';
    markerInputMode = null;
}

function commitMarkerInput() {
    var input = document.getElementById('marker-input');
    var label = input.value.trim() || 'Section';
    if (markerInputMode && markerInputMode.type === 'add') {
        addMarkerAtTime(markerInputMode.time, label);
    } else if (markerInputMode && markerInputMode.type === 'edit') {
        var marker = notesData.markers.find(function(m) { return m.id === markerInputMode.id; });
        if (marker) {
            marker.label = label;
            renderMarkers();
        }
    }
    hideMarkerInput();
}

function addMarkerAtScroll() {
    var time = getTimeAtScroll();
    showMarkerInput(time);
}

function editMarker(markerId) {
    if (!notesData || !notesData.markers) return;
    showMarkerInput(undefined, markerId);
}

function deleteMarker(markerId) {
    if (!notesData || !notesData.markers) return;
    var idx = notesData.markers.findIndex(function(m) { return m.id === markerId; });
    if (idx !== -1) {
        notesData.markers.splice(idx, 1);
        renderMarkers();
    }
}

// ================================================================
//  Lyrics mode
// ================================================================

function toggleLyricsMode() {
    if (!editMode) toggleEditMode();
    lyricsMode = !lyricsMode;
    document.body.classList.toggle('lyrics-mode', lyricsMode);
    if (lyricsMode) {
        // Sort notes by start_time, then by key_index (lower note first)
        lyricsSortedNotes = notesData.notes.slice().sort(function(a, b) {
            if (a.start_time !== b.start_time) return a.start_time - b.start_time;
            return a.key_index - b.key_index;
        });
        // Select first note and show lyrics input
        if (lyricsSortedNotes.length > 0) {
            selectNote(lyricsSortedNotes[0].id);
            showLyricsInput(lyricsSortedNotes[0]);
        }
    } else {
        hideLyricsInput();
    }
}

function showLyricsInput(note) {
    var el = document.querySelector('.note-block[data-note-id="' + note.id + '"]');
    if (!el) return;
    var rect = el.getBoundingClientRect();
    var overlay = document.getElementById('lyrics-input-overlay');
    var input = document.getElementById('lyrics-input');
    overlay.style.display = 'block';
    overlay.style.left = rect.left + 'px';
    overlay.style.top = (rect.bottom + 4) + 'px';
    input.value = note.lyric || '';
    input.focus();
    input.select();

    // Scroll the note into view if needed
    scrollToTime(note.start_time);
}

function hideLyricsInput() {
    document.getElementById('lyrics-input-overlay').style.display = 'none';
}

function saveLyricAndAdvance(direction) {
    if (!notesData || !lyricsMode) return;
    var input = document.getElementById('lyrics-input');
    var note = notesData.notes.find(function(n) { return n.id === selectedNoteId; });
    if (note) {
        note.lyric = input.value.trim() || undefined;
    }

    // Find current index in sorted list
    var idx = lyricsSortedNotes.findIndex(function(n) { return n.id === selectedNoteId; });
    var nextIdx = idx + direction;
    if (nextIdx >= 0 && nextIdx < lyricsSortedNotes.length) {
        var nextNote = lyricsSortedNotes[nextIdx];
        selectNote(nextNote.id);
        showLyricsInput(nextNote);
    } else {
        // End of notes, exit lyrics mode
        hideLyricsInput();
    }

    // Refresh rendering
    rerenderPreservingScroll();
    if (selectedNoteId !== null) selectNote(selectedNoteId);
}
