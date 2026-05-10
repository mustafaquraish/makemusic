// ================================================================
//  Edit mode, note CRUD, drag/resize, context menu
// ================================================================

// Helper: re-render keeping the current scroll position
function rerenderPreservingScroll() {
    var container = document.getElementById('piano-roll-container');
    var saved = container.scrollTop;
    renderPianoRoll();
    renderTextNotesList();
    container.scrollTop = saved;
}

function getTimeAtY(y) {
    var roll = document.getElementById('piano-roll');
    var totalHeight = parseFloat(roll.style.height) || 0;
    var bottomY = totalHeight - effectiveBottomPadding;
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

// ================================================================
//  Undo / Redo
// ================================================================

var MAX_UNDO = 100;

function pushUndo(action) {
    if (undoRedoInProgress) return;
    undoStack.push(action);
    if (undoStack.length > MAX_UNDO) undoStack.shift();
    redoStack = [];
}

function undo() {
    if (undoStack.length === 0 || !notesData) return;
    // Flush any pending lyric edit
    var focused = document.activeElement;
    if (focused && focused.classList && focused.classList.contains('lyrics-row-input')) {
        focused.blur();
    }
    undoRedoInProgress = true;
    var action = undoStack.pop();
    redoStack.push(action);
    applyUndoAction(action);
    rerenderPreservingScroll();
    if (lyricsMode) rebuildLyricsPanel();
    // Select restored note after rerender
    if (action.type === 'deleteNote') selectNote(action.noteData.id);
    undoRedoInProgress = false;
}

function redo() {
    if (redoStack.length === 0 || !notesData) return;
    var focused = document.activeElement;
    if (focused && focused.classList && focused.classList.contains('lyrics-row-input')) {
        focused.blur();
    }
    undoRedoInProgress = true;
    var action = redoStack.pop();
    undoStack.push(action);
    applyRedoAction(action);
    rerenderPreservingScroll();
    if (lyricsMode) rebuildLyricsPanel();
    undoRedoInProgress = false;
}

function applyUndoAction(action) {
    switch (action.type) {
        case 'addNote':
        case 'duplicateNote': {
            var idx = notesData.notes.findIndex(function(n) { return n.id === action.noteData.id; });
            if (idx !== -1) notesData.notes.splice(idx, 1);
            if (selectedNoteId === action.noteData.id) selectedNoteId = null;
            break;
        }
        case 'deleteNote': {
            notesData.notes.push(JSON.parse(JSON.stringify(action.noteData)));
            break;
        }
        case 'moveNote': {
            var note = notesData.notes.find(function(n) { return n.id === action.noteId; });
            if (note) {
                note.start_time = action.oldStartTime;
                note.key_index = action.oldKeyIndex;
                note.note_name = action.oldNoteName;
            }
            break;
        }
        case 'resizeNote': {
            var note = notesData.notes.find(function(n) { return n.id === action.noteId; });
            if (note) {
                note.start_time = action.oldStartTime;
                note.duration = action.oldDuration;
            }
            break;
        }
        case 'toggleHand': {
            var note = notesData.notes.find(function(n) { return n.id === action.noteId; });
            if (note) {
                note.hand = action.oldHand;
                note.color_rgb = action.oldColor.slice();
            }
            break;
        }
        case 'editLyric': {
            var note = notesData.notes.find(function(n) { return n.id === action.noteId; });
            if (note) note.lyric = action.oldLyric;
            break;
        }
        case 'addMarker': {
            if (notesData.markers) {
                var idx = notesData.markers.findIndex(function(m) { return m.id === action.markerData.id; });
                if (idx !== -1) notesData.markers.splice(idx, 1);
            }
            break;
        }
        case 'deleteMarker': {
            if (!notesData.markers) notesData.markers = [];
            notesData.markers.push(JSON.parse(JSON.stringify(action.markerData)));
            notesData.markers.sort(function(a, b) { return a.time - b.time; });
            break;
        }
        case 'editMarker': {
            if (notesData.markers) {
                var marker = notesData.markers.find(function(m) { return m.id === action.markerId; });
                if (marker) marker.label = action.oldLabel;
            }
            break;
        }
    }
}

function applyRedoAction(action) {
    switch (action.type) {
        case 'addNote':
        case 'duplicateNote': {
            notesData.notes.push(JSON.parse(JSON.stringify(action.noteData)));
            break;
        }
        case 'deleteNote': {
            var idx = notesData.notes.findIndex(function(n) { return n.id === action.noteData.id; });
            if (idx !== -1) notesData.notes.splice(idx, 1);
            if (selectedNoteId === action.noteData.id) selectedNoteId = null;
            break;
        }
        case 'moveNote': {
            var note = notesData.notes.find(function(n) { return n.id === action.noteId; });
            if (note) {
                note.start_time = action.newStartTime;
                note.key_index = action.newKeyIndex;
                note.note_name = action.newNoteName;
            }
            break;
        }
        case 'resizeNote': {
            var note = notesData.notes.find(function(n) { return n.id === action.noteId; });
            if (note) {
                note.start_time = action.newStartTime;
                note.duration = action.newDuration;
            }
            break;
        }
        case 'toggleHand': {
            var note = notesData.notes.find(function(n) { return n.id === action.noteId; });
            if (note) {
                note.hand = action.newHand;
                note.color_rgb = action.newColor.slice();
            }
            break;
        }
        case 'editLyric': {
            var note = notesData.notes.find(function(n) { return n.id === action.noteId; });
            if (note) note.lyric = action.newLyric;
            break;
        }
        case 'addMarker': {
            if (!notesData.markers) notesData.markers = [];
            notesData.markers.push(JSON.parse(JSON.stringify(action.markerData)));
            notesData.markers.sort(function(a, b) { return a.time - b.time; });
            break;
        }
        case 'deleteMarker': {
            if (notesData.markers) {
                var idx = notesData.markers.findIndex(function(m) { return m.id === action.markerData.id; });
                if (idx !== -1) notesData.markers.splice(idx, 1);
            }
            break;
        }
        case 'editMarker': {
            if (notesData.markers) {
                var marker = notesData.markers.find(function(m) { return m.id === action.markerId; });
                if (marker) marker.label = action.newLabel;
            }
            break;
        }
    }
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
    pushUndo({ type: 'addNote', noteData: JSON.parse(JSON.stringify(newNote)) });
    rerenderPreservingScroll();
    selectNote(newNote.id);
    if (lyricsMode) rebuildLyricsPanel();
}

function deleteSelectedNote() {
    if (selectedNoteId === null || !notesData) return;
    var idx = notesData.notes.findIndex(function(n) { return n.id === selectedNoteId; });
    if (idx !== -1) {
        var deletedNote = JSON.parse(JSON.stringify(notesData.notes[idx]));
        pushUndo({ type: 'deleteNote', noteData: deletedNote });
        notesData.notes.splice(idx, 1);
        selectedNoteId = null;
        rerenderPreservingScroll();
        if (lyricsMode) rebuildLyricsPanel();
    }
}

function toggleSelectedNoteHand() {
    if (selectedNoteId === null || !notesData) return;
    var note = notesData.notes.find(function(n) { return n.id === selectedNoteId; });
    if (!note) return;
    var oldHand = note.hand;
    var oldColor = note.color_rgb.slice();
    note.hand = note.hand === 'right_hand' ? 'left_hand' : 'right_hand';
    note.color_rgb = (note.hand === 'right_hand' ? rhColor : lhColor).slice();
    pushUndo({
        type: 'toggleHand',
        noteId: note.id,
        oldHand: oldHand,
        oldColor: oldColor,
        newHand: note.hand,
        newColor: note.color_rgb.slice()
    });
    rerenderPreservingScroll();
    selectNote(note.id);
    if (lyricsMode) rebuildLyricsPanel();
}

function duplicateNote(noteId) {
    if (!notesData) return;
    var note = notesData.notes.find(function(n) { return n.id === noteId; });
    if (!note) return;
    var newNote = JSON.parse(JSON.stringify(note));
    newNote.id = nextNoteId++;
    newNote.start_time = note.start_time + note.duration + 0.1;
    notesData.notes.push(newNote);
    pushUndo({ type: 'duplicateNote', noteData: JSON.parse(JSON.stringify(newNote)) });
    rerenderPreservingScroll();
    selectNote(newNote.id);
    if (lyricsMode) rebuildLyricsPanel();
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
    pushUndo({ type: 'addMarker', markerData: JSON.parse(JSON.stringify(marker)) });
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
        var bottomY = totalHeight - effectiveBottomPadding;
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
            var oldLabel = marker.label;
            marker.label = label;
            if (oldLabel !== label) {
                pushUndo({ type: 'editMarker', markerId: marker.id, oldLabel: oldLabel, newLabel: label });
            }
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
        var deletedMarker = JSON.parse(JSON.stringify(notesData.markers[idx]));
        pushUndo({ type: 'deleteMarker', markerData: deletedMarker });
        notesData.markers.splice(idx, 1);
        renderMarkers();
    }
}

// ================================================================
//  Lyrics mode — side panel approach
// ================================================================

function toggleLyricsMode() {
    if (!editMode) toggleEditMode();
    lyricsMode = !lyricsMode;
    document.body.classList.toggle('lyrics-mode', lyricsMode);
    if (lyricsMode) {
        // Default filter to the current edit hand (updates buttons + rebuilds)
        setLyricsHandFilter(editHand);
        showLyricsPanel();
    } else {
        hideLyricsPanel();
    }
}

function showLyricsPanel() {
    document.getElementById('lyrics-panel').classList.add('visible');
}

function hideLyricsPanel() {
    // Flush any pending lyric edit before hiding
    var focused = document.activeElement;
    if (focused && focused.classList && focused.classList.contains('lyrics-row-input')) {
        focused.blur();
    }
    document.getElementById('lyrics-panel').classList.remove('visible');
    lyricsMode = false;
    document.body.classList.remove('lyrics-mode');
}

function setLyricsHandFilter(filter) {
    lyricsHandFilter = filter;
    // Update filter buttons
    var btns = document.querySelectorAll('.lyrics-filter-btn');
    for (var i = 0; i < btns.length; i++) {
        btns[i].classList.toggle('active', btns[i].dataset.filter === filter);
    }
    rebuildLyricsPanel();
}

function rebuildLyricsPanel() {
    if (!notesData) return;
    var list = document.getElementById('lyrics-note-list');
    list.innerHTML = '';

    // Filter and sort notes by time, then by key_index
    lyricsSortedNotes = notesData.notes.slice()
        .filter(function(n) {
            if (lyricsHandFilter === 'all') return true;
            return n.hand === lyricsHandFilter;
        })
        .sort(function(a, b) {
            if (a.start_time !== b.start_time) return a.start_time - b.start_time;
            return a.key_index - b.key_index;
        });

    var frag = document.createDocumentFragment();
    lyricsSortedNotes.forEach(function(note) {
        var row = document.createElement('div');
        row.className = 'lyrics-row';
        row.dataset.noteId = note.id;
        if (note.id === selectedNoteId) row.classList.add('active');

        var handDot = document.createElement('span');
        handDot.className = 'lyrics-hand-dot';
        var handColor = note.hand === 'right_hand' ? rhColor : lhColor;
        handDot.style.background = 'rgb(' + handColor[0] + ',' + handColor[1] + ',' + handColor[2] + ')';
        row.appendChild(handDot);

        var info = document.createElement('span');
        info.className = 'lyrics-note-info';
        info.textContent = note.note_name + ' (' + note.start_time.toFixed(1) + 's)';
        row.appendChild(info);

        var input = document.createElement('input');
        input.type = 'text';
        input.className = 'lyrics-row-input';
        input.placeholder = 'lyric…';
        input.value = note.lyric || '';
        input.autocomplete = 'off';
        input.spellcheck = false;

        (function(n, inp, r) {
            var lyricOnFocus = n.lyric;
            inp.addEventListener('input', function() {
                n.lyric = this.value.trim() || undefined;
                rerenderPreservingScroll();
            });
            inp.addEventListener('focus', function() {
                lyricOnFocus = n.lyric;
                selectNote(n.id);
                scrollToTimeSmooth(n.start_time);
                // Highlight active row
                var allRows = document.querySelectorAll('.lyrics-row');
                for (var j = 0; j < allRows.length; j++) allRows[j].classList.remove('active');
                r.classList.add('active');
            });
            inp.addEventListener('blur', function() {
                var newLyric = n.lyric;
                if (lyricOnFocus !== newLyric) {
                    pushUndo({
                        type: 'editLyric',
                        noteId: n.id,
                        oldLyric: lyricOnFocus,
                        newLyric: newLyric
                    });
                }
            });
            inp.addEventListener('keydown', function(e) {
                if (e.code === 'Tab' || e.code === 'Enter') {
                    e.preventDefault();
                    lyricsAdvance(n.id, e.shiftKey ? -1 : 1);
                } else if (e.code === 'Escape') {
                    e.preventDefault();
                    toggleLyricsMode();
                }
            });
            r.addEventListener('click', function(e) {
                if (e.target === inp) return; // Don't re-focus if already clicking input
                selectNote(n.id);
                scrollToTimeSmooth(n.start_time);
                inp.focus();
                // Highlight active row
                var allRows = document.querySelectorAll('.lyrics-row');
                for (var j = 0; j < allRows.length; j++) allRows[j].classList.remove('active');
                r.classList.add('active');
            });
        })(note, input, row);

        row.appendChild(input);
        frag.appendChild(row);
    });

    list.appendChild(frag);
}

function lyricsAdvance(currentNoteId, direction) {
    var idx = lyricsSortedNotes.findIndex(function(n) { return n.id === currentNoteId; });
    var nextIdx = idx + direction;
    if (nextIdx >= 0 && nextIdx < lyricsSortedNotes.length) {
        var nextNote = lyricsSortedNotes[nextIdx];
        selectNote(nextNote.id);
        scrollToTimeSmooth(nextNote.start_time);
        // Focus the corresponding input row
        var nextRow = document.querySelector('.lyrics-row[data-note-id="' + nextNote.id + '"] .lyrics-row-input');
        if (nextRow) nextRow.focus();
        // Scroll the panel to show the focused row
        var rowEl = document.querySelector('.lyrics-row[data-note-id="' + nextNote.id + '"]');
        if (rowEl) rowEl.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
        // Update active highlight
        var allRows = document.querySelectorAll('.lyrics-row');
        for (var j = 0; j < allRows.length; j++) allRows[j].classList.remove('active');
        if (rowEl) rowEl.classList.add('active');
    }
}

function lyricsSelectNote(noteId) {
    var note = notesData.notes.find(function(n) { return n.id === noteId; });
    if (!note) return;
    if (!lyricsMode) {
        if (!editMode) toggleEditMode();
        lyricsMode = true;
        document.body.classList.add('lyrics-mode');
        // Default filter to the note's hand (preserves hand context)
        setLyricsHandFilter(note.hand);
        showLyricsPanel();
    } else {
        // Already in lyrics mode — if the note isn't visible with current filter, switch
        var noteVisible = (lyricsHandFilter === 'all' || note.hand === lyricsHandFilter);
        if (!noteVisible) {
            setLyricsHandFilter(note.hand);
        }
    }
    selectNote(noteId);
    scrollToTimeSmooth(note.start_time);
    var inp = document.querySelector('.lyrics-row[data-note-id="' + noteId + '"] .lyrics-row-input');
    if (inp) {
        inp.focus();
        // Scroll the panel row into view
        var rowEl = inp.closest('.lyrics-row');
        if (rowEl) rowEl.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
        var allRows = document.querySelectorAll('.lyrics-row');
        for (var j = 0; j < allRows.length; j++) allRows[j].classList.remove('active');
        if (rowEl) rowEl.classList.add('active');
    }
}

function scrollToTimeSmooth(time) {
    var container = document.getElementById('piano-roll-container');
    var roll = document.getElementById('piano-roll');
    var totalHeight = parseFloat(roll.style.height) || container.clientHeight;
    var bottomY = totalHeight - effectiveBottomPadding;
    var playheadOffset = container.clientHeight * 0.7;
    var targetY = bottomY - time * pixelsPerSecond - playheadOffset;
    programmaticScroll = true;
    container.scrollTo({ top: Math.max(0, targetY), behavior: 'smooth' });
    // Reset programmaticScroll after animation
    setTimeout(function() { programmaticScroll = false; }, 500);
}
