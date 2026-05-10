// ================================================================
//  Event listeners
// ================================================================

// -- Command palette input -------------------------------------------

document.getElementById('command-palette-input').addEventListener('input', function() {
    commandPaletteSelectedIndex = 0;
    renderCommandList(this.value);
});

document.getElementById('command-palette-input').addEventListener('keydown', function(e) {
    if (e.code === 'ArrowDown') {
        e.preventDefault();
        if (filteredCommands.length > 0) {
            commandPaletteSelectedIndex = (commandPaletteSelectedIndex + 1) % filteredCommands.length;
            updateCommandSelection();
        }
    } else if (e.code === 'ArrowUp') {
        e.preventDefault();
        if (filteredCommands.length > 0) {
            commandPaletteSelectedIndex = (commandPaletteSelectedIndex - 1 + filteredCommands.length) % filteredCommands.length;
            updateCommandSelection();
        }
    } else if (e.code === 'Enter') {
        e.preventDefault();
        if (filteredCommands.length > 0 && filteredCommands[commandPaletteSelectedIndex]) {
            var cmd = filteredCommands[commandPaletteSelectedIndex];
            hideCommandPalette();
            cmd.action();
        }
    } else if (e.code === 'Escape') {
        e.preventDefault();
        hideCommandPalette();
    }
});

// -- Context menu ----------------------------------------------------

document.getElementById('context-menu').addEventListener('click', function(e) {
    var item = e.target.closest('.ctx-item');
    if (!item || contextMenuNoteId === null) return;
    var action = item.dataset.action;
    if (action === 'delete') {
        selectedNoteId = contextMenuNoteId;
        deleteSelectedNote();
    } else if (action === 'toggle-hand') {
        selectedNoteId = contextMenuNoteId;
        toggleSelectedNoteHand();
    } else if (action === 'duplicate') {
        duplicateNote(contextMenuNoteId);
    } else if (action === 'edit-lyric') {
        // Open lyrics panel and focus the note's input
        lyricsSelectNote(contextMenuNoteId);
    }
    hideContextMenu();
});

// -- Empty-space context menu ----------------------------------------

document.getElementById('context-menu-empty').addEventListener('click', function(e) {
    var item = e.target.closest('.ctx-item');
    if (!item) return;
    var action = item.dataset.action;
    var menu = document.getElementById('context-menu-empty');
    var clickTime = parseFloat(menu.dataset.clickTime || '0');
    var clickClientX = parseFloat(menu.dataset.clickClientX || '0');
    var clickClientY = parseFloat(menu.dataset.clickClientY || '0');
    if (action === 'add-note-here') {
        addNoteAtPosition(clickClientX, clickClientY);
    } else if (action === 'add-marker-here') {
        showMarkerInput(clickTime);
    } else if (action === 'paste-note') {
        // Future paste functionality
    }
    hideContextMenu();
});

document.getElementById('piano-roll').addEventListener('contextmenu', function(e) {
    if (!editMode) return;
    e.preventDefault();
    var noteBlock = e.target.closest('.note-block');
    if (noteBlock) {
        showContextMenu(e.clientX, e.clientY, parseInt(noteBlock.dataset.noteId));
    } else {
        // Right-click on empty space
        var container = document.getElementById('piano-roll-container');
        var containerRect = container.getBoundingClientRect();
        var scrollY = container.scrollTop + (e.clientY - containerRect.top);
        var time = getTimeAtY(scrollY);
        showEmptyContextMenu(e.clientX, e.clientY, time, e.clientX, e.clientY);
    }
});

document.addEventListener('mousedown', function(e) {
    if (!e.target.closest('#context-menu') && !e.target.closest('#context-menu-empty')) {
        hideContextMenu();
    }
});

// -- Edit mode: note creation drag -----------------------------------

document.getElementById('piano-roll').addEventListener('mousedown', function(e) {
    if (!editMode || !notesData) return;
    if (e.target.closest('.note-block')) return;
    if (e.button !== 0) return;

    var container = document.getElementById('piano-roll-container');
    var containerRect = container.getBoundingClientRect();
    var scrollY = container.scrollTop + (e.clientY - containerRect.top);
    var time = getTimeAtY(scrollY);
    var keyIndex = getKeyIndexAtX(e.clientX);

    creationDragState = {
        startClientY: e.clientY,
        startScrollY: scrollY,
        startTime: Math.max(0, time),
        keyIndex: keyIndex,
        hasDragged: false
    };

    var preview = document.getElementById('note-creation-preview');
    var hand = editHand;
    var color = hand === 'right_hand' ? rhColor : lhColor;
    preview.style.background = 'rgba(' + color[0] + ',' + color[1] + ',' + color[2] + ', 0.4)';
    preview.style.borderColor = 'rgba(' + color[0] + ',' + color[1] + ',' + color[2] + ', 0.8)';

    var roll = document.getElementById('piano-roll');
    var totalHeight = parseFloat(roll.style.height) || container.clientHeight;
    var bottomY = totalHeight - effectiveBottomPadding;
    var leftPct = getKeyLeftPercent(keyIndex);
    var widthPct = getKeyWidthPercent(keyIndex);
    var minDuration = 0.2;

    // Use clamped time for preview position (matches final note placement)
    var clampedTime = Math.max(0, time);
    var noteTop = bottomY - (clampedTime + minDuration) * pixelsPerSecond;
    var noteH = minDuration * pixelsPerSecond;
    preview.style.left = leftPct + '%';
    preview.style.width = widthPct + '%';
    preview.style.top = noteTop + 'px';
    preview.style.height = Math.max(4, noteH) + 'px';
    preview.style.display = 'block';
});

// -- Edit mode: note selection and drag ------------------------------

document.getElementById('piano-roll').addEventListener('mousedown', function(e) {
    if (!editMode) return;
    var noteBlock = e.target.closest('.note-block');
    if (!noteBlock) return;
    e.preventDefault();
    e.stopPropagation();

    var noteId = parseInt(noteBlock.dataset.noteId);
    selectNote(noteId);

    var note = notesData.notes.find(function(n) { return n.id === noteId; });
    if (!note) return;

    var rect = noteBlock.getBoundingClientRect();
    var isTopEdge = (e.clientY - rect.top) < 8;
    var isBottomEdge = (rect.bottom - e.clientY) < 8;

    editDragState = {
        type: isTopEdge ? 'resize-top' : (isBottomEdge ? 'resize-bottom' : 'move'),
        noteId: noteId,
        startY: e.clientY,
        startX: e.clientX,
        origStartTime: note.start_time,
        origDuration: note.duration,
        origKeyIndex: note.key_index,
        origNoteName: note.note_name
    };
}, true);

// -- Mouse move: creation drag + edit drag ---------------------------

// Snap a candidate time to the nearest edge (start or end) of any other note.
// Returns the snapped time, or the candidate unchanged if no snap within threshold.
function snapToNoteEdge(candidateTime, excludeId) {
    var SNAP_PX = 8;
    var threshold = SNAP_PX / pixelsPerSecond;
    var bestTime = candidateTime;
    var bestDist = threshold;
    notesData.notes.forEach(function(n) {
        if (n.id === excludeId) return;
        [n.start_time, n.start_time + n.duration].forEach(function(t) {
            var dist = Math.abs(t - candidateTime);
            if (dist < bestDist) { bestDist = dist; bestTime = t; }
        });
    });
    return bestTime;
}

document.addEventListener('mousemove', function(e) {
    if (creationDragState) {
        var dy = Math.abs(e.clientY - creationDragState.startClientY);
        if (dy > 5) creationDragState.hasDragged = true;

        var container = document.getElementById('piano-roll-container');
        var containerRect = container.getBoundingClientRect();
        var currentScrollY = container.scrollTop + (e.clientY - containerRect.top);
        var currentTime = Math.max(0, getTimeAtY(currentScrollY));

        var startTime = Math.min(creationDragState.startTime, currentTime);
        var endTime = Math.max(creationDragState.startTime, currentTime);
        var duration = Math.max(0.1, endTime - startTime);

        var roll = document.getElementById('piano-roll');
        var totalHeight = parseFloat(roll.style.height) || container.clientHeight;
        var bottomY = totalHeight - effectiveBottomPadding;

        var preview = document.getElementById('note-creation-preview');
        var noteTop = bottomY - (startTime + duration) * pixelsPerSecond;
        var noteH = duration * pixelsPerSecond;
        preview.style.top = noteTop + 'px';
        preview.style.height = Math.max(4, noteH) + 'px';
        return;
    }

    if (!editDragState) return;
    var note = notesData.notes.find(function(n) { return n.id === editDragState.noteId; });
    if (!note) { editDragState = null; return; }

    var dy = e.clientY - editDragState.startY;
    var timeDelta = dy / pixelsPerSecond;
    var snapIndicatorTime = null; // time of the edge being snapped to (null = no snap)

    if (editDragState.type === 'move') {
        var rawStart   = Math.max(0, editDragState.origStartTime - timeDelta);
        var rawEnd     = rawStart + editDragState.origDuration;
        // Try snapping the leading (top/end) edge first, then the trailing (bottom/start) edge.
        var snappedEnd   = snapToNoteEdge(rawEnd,   note.id);
        var snappedStart = snapToNoteEdge(rawStart,  note.id);
        if (snappedEnd !== rawEnd) {
            note.start_time   = Math.max(0, snappedEnd - editDragState.origDuration);
            snapIndicatorTime = snappedEnd;
        } else if (snappedStart !== rawStart) {
            note.start_time   = snappedStart;
            snapIndicatorTime = snappedStart;
        } else {
            note.start_time = rawStart;
        }
        note.key_index  = getKeyIndexAtX(e.clientX);
        note.note_name  = PIANO_KEYS[note.key_index] || note.note_name;
    } else if (editDragState.type === 'resize-top') {
        // Top edge controls end time
        var rawEnd = editDragState.origStartTime + Math.max(0.1, editDragState.origDuration - timeDelta);
        var snapped = snapToNoteEdge(rawEnd, note.id);
        note.duration = Math.max(0.1, snapped - note.start_time);
        if (snapped !== rawEnd) snapIndicatorTime = snapped;
    } else if (editDragState.type === 'resize-bottom') {
        // Bottom edge controls start time
        var endTime  = editDragState.origStartTime + editDragState.origDuration;
        var rawStart = Math.max(0, Math.min(editDragState.origStartTime - timeDelta, endTime - 0.1));
        var snapped  = snapToNoteEdge(rawStart, note.id);
        note.start_time = Math.max(0, Math.min(snapped, endTime - 0.1));
        note.duration   = endTime - note.start_time;
        if (snapped !== rawStart) snapIndicatorTime = snapped;
    }

    // ---- Direct DOM update — avoids full re-render to prevent flicker ----
    var roll      = document.getElementById('piano-roll');
    var container = document.getElementById('piano-roll-container');
    var totalHeight = parseFloat(roll.style.height) || container.clientHeight;
    var bottomY   = totalHeight - effectiveBottomPadding;
    var noteTop   = bottomY - (note.start_time + note.duration) * pixelsPerSecond;
    var noteHeight = Math.max(4, note.duration * pixelsPerSecond);
    var leftPct   = getKeyLeftPercent(note.key_index);
    var widthPct  = getKeyWidthPercent(note.key_index);

    var item = null;
    for (var i = 0; i < noteElements.length; i++) {
        if (noteElements[i].note.id === editDragState.noteId) { item = noteElements[i]; break; }
    }
    if (item) {
        var el = item.el;
        el.style.top    = noteTop    + 'px';
        el.style.height = noteHeight + 'px';
        el.style.left   = leftPct   + '%';
        el.style.width  = widthPct  + '%';
        // Update note label text without destroying child resize-handles
        var labelNode = el.firstChild;
        if (labelNode && labelNode.nodeType === Node.TEXT_NODE) {
            labelNode.nodeValue = (noteHeight > 18 && appSettings.noteLabels) ? (note.note_name || '') : '';
        } else if (noteHeight > 18 && appSettings.noteLabels) {
            el.insertBefore(document.createTextNode(note.note_name || ''), el.firstChild);
        }
        // Update drop line
        if (item.dropLine) {
            var dropTop    = noteTop + noteHeight;
            var dropHeight = bottomY - dropTop;
            if (dropHeight > 0) {
                item.dropLine.style.top    = dropTop    + 'px';
                item.dropLine.style.height = dropHeight + 'px';
                item.dropLine.style.left   = 'calc(' + leftPct + '% + ' + (widthPct / 2) + '%)';
            }
        }
    }
    // Show/hide snap indicator line
    var snapEl = document.getElementById('snap-indicator');
    if (snapIndicatorTime !== null) {
        snapEl.style.top     = (bottomY - snapIndicatorTime * pixelsPerSecond) + 'px';
        snapEl.style.display = 'block';
    } else {
        snapEl.style.display = 'none';
    }});

// -- Mouse up: creation drag end + edit drag end ---------------------

document.addEventListener('mouseup', function(e) {
    if (creationDragState) {
        var preview = document.getElementById('note-creation-preview');
        preview.style.display = 'none';

        if (creationDragState.hasDragged) {
            var container = document.getElementById('piano-roll-container');
            var containerRect = container.getBoundingClientRect();
            var currentScrollY = container.scrollTop + (e.clientY - containerRect.top);
            var currentTime = Math.max(0, getTimeAtY(currentScrollY));

            var startTime = Math.min(creationDragState.startTime, currentTime);
            var endTime = Math.max(creationDragState.startTime, currentTime);
            var duration = Math.max(0.1, endTime - startTime);

            // Only create note if drag exceeded minimum pixel distance AND minimum duration
            var dragPx = Math.abs(e.clientY - creationDragState.startClientY);
            if (dragPx >= MIN_DRAG_PX && duration >= MIN_NOTE_DURATION) {
                var keyIndex = creationDragState.keyIndex;
                var noteName = PIANO_KEYS[keyIndex] || 'C4';
                var hand = editHand;
                var color = hand === 'right_hand' ? rhColor : lhColor;

                var newNote = {
                    id: nextNoteId++,
                    note_name: noteName,
                    start_time: Math.max(0, startTime),
                    duration: duration,
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
        }
        // Single clicks (no drag) no longer create notes — prevents accidental placement
        creationDragState = null;
        return;
    }

    if (editDragState) {
        var finalNoteId = editDragState.noteId;
        var draggedNote = notesData.notes.find(function(n) { return n.id === finalNoteId; });
        if (draggedNote) {
            if (editDragState.type === 'move') {
                if (draggedNote.start_time !== editDragState.origStartTime || draggedNote.key_index !== editDragState.origKeyIndex) {
                    pushUndo({
                        type: 'moveNote',
                        noteId: draggedNote.id,
                        oldStartTime: editDragState.origStartTime,
                        oldKeyIndex: editDragState.origKeyIndex,
                        oldNoteName: editDragState.origNoteName,
                        newStartTime: draggedNote.start_time,
                        newKeyIndex: draggedNote.key_index,
                        newNoteName: draggedNote.note_name
                    });
                }
            } else if (editDragState.type === 'resize-top' || editDragState.type === 'resize-bottom') {
                if (draggedNote.start_time !== editDragState.origStartTime || draggedNote.duration !== editDragState.origDuration) {
                    pushUndo({
                        type: 'resizeNote',
                        noteId: draggedNote.id,
                        oldStartTime: editDragState.origStartTime,
                        oldDuration: editDragState.origDuration,
                        newStartTime: draggedNote.start_time,
                        newDuration: draggedNote.duration
                    });
                }
            }
        }
        editDragState = null;
        // Hide snap indicator when drag ends
        document.getElementById('snap-indicator').style.display = 'none';
        rerenderPreservingScroll();
        selectNote(finalNoteId);
    }
});

// -- File input ------------------------------------------------------

// Lyrics-input event listeners removed — lyrics now use side panel with
// per-row inputs; their keydown handlers are set up in rebuildLyricsPanel().

document.getElementById('marker-input').addEventListener('keydown', function(e) {
    if (e.code === 'Enter') {
        e.preventDefault();
        commitMarkerInput();
    } else if (e.code === 'Escape') {
        e.preventDefault();
        hideMarkerInput();
    }
});

document.getElementById('marker-input').addEventListener('blur', function() {
    // Auto-close after a short delay (allows click events to fire first)
    setTimeout(function() {
        if (markerInputMode) hideMarkerInput();
    }, 150);
});

document.getElementById('song-title').addEventListener('input', function() {
    if (notesData) {
        if (!notesData.metadata) notesData.metadata = {};
        notesData.metadata.title = this.value || 'Untitled';
    }
});

document.getElementById('file-input').addEventListener('change', function(e) {
    handleFileLoad(e.target.files[0]);
    this.value = '';
});

// -- Global drag-and-drop -------------------------------------------

var dragCounter = 0;
document.addEventListener('dragenter', function(e) {
    e.preventDefault();
    dragCounter++;
    document.getElementById('drag-overlay').classList.add('visible');
});
document.addEventListener('dragleave', function(e) {
    dragCounter--;
    if (dragCounter <= 0) {
        dragCounter = 0;
        document.getElementById('drag-overlay').classList.remove('visible');
    }
});
document.addEventListener('dragover', function(e) {
    e.preventDefault();
});
document.addEventListener('drop', function(e) {
    e.preventDefault();
    dragCounter = 0;
    document.getElementById('drag-overlay').classList.remove('visible');
    var file = e.dataTransfer.files[0];
    if (file && file.name.endsWith('.json')) {
        handleFileLoad(file);
    }
});

// -- Pinch-to-zoom ---------------------------------------------------

document.getElementById('piano-roll-container').addEventListener('wheel', function(e) {
    if (e.ctrlKey || e.metaKey) {
        e.preventDefault();

        var container = this;
        var roll = document.getElementById('piano-roll');
        var totalHeight = parseFloat(roll.style.height) || container.clientHeight;
        var bottomY = totalHeight - effectiveBottomPadding;
        var mouseY = container.scrollTop + e.clientY - container.getBoundingClientRect().top;
        var timeAtMouse = (bottomY - mouseY) / pixelsPerSecond;

        var delta = -e.deltaY;
        var zoomFactor = 1 + Math.sign(delta) * 0.08;
        var oldPPS = pixelsPerSecond;
        pixelsPerSecond = Math.max(20, Math.min(300, pixelsPerSecond * zoomFactor));

        document.getElementById('zoom-slider').value = Math.round(pixelsPerSecond);

        if (Math.abs(pixelsPerSecond - oldPPS) < 0.01) return;

        rerenderPreservingScroll();

        var newTotalHeight = parseFloat(roll.style.height) || container.clientHeight;
        var newBottomY = newTotalHeight - effectiveBottomPadding;
        var newMouseY = newBottomY - timeAtMouse * pixelsPerSecond;
        var mouseScreenOffset = e.clientY - container.getBoundingClientRect().top;
        container.scrollTop = newMouseY - mouseScreenOffset;

        updatePlayhead();
        updateTimeIndicator();
        updateProgressBar();
        updateMinimapViewport();
    }
}, { passive: false });

// -- Scroll events ---------------------------------------------------

document.getElementById('piano-roll-container').addEventListener('scroll', function() {
    updatePlayhead();
    updateTimeIndicator();
    updateProgressBar();
    highlightActiveKeys();
    highlightPlayingNotes();
    updateMinimapViewport();
    updateDropLineVisibility();
});

document.getElementById('piano-roll-container').addEventListener('wheel', function(e) {
    if (!e.ctrlKey && !e.metaKey) {
        onUserScrollIntent();
    }
}, { passive: true });

document.getElementById('piano-roll-container').addEventListener('touchstart', function() {
    onUserScrollIntent();
}, { passive: true });

document.getElementById('piano-roll-container').addEventListener('touchmove', function() {
    onUserScrollIntent();
}, { passive: true });

// -- Minimap click ---------------------------------------------------

document.getElementById('minimap').addEventListener('click', function(e) {
    if (!notesData || totalDuration <= 0) return;
    var rect = this.getBoundingClientRect();
    var pct = (e.clientY - rect.top) / rect.height;
    var time = pct * totalDuration;
    scrollToTime(time);
    if (isPlaying) {
        playbackTimeOffset = time;
        playbackStartTime = performance.now();
        activeNoteIds.clear();
    }
});

// -- Toolbar events --------------------------------------------------

document.getElementById('zoom-slider').addEventListener('input', function() {
    var timeAtPlayhead = getTimeAtScroll();
    pixelsPerSecond = parseInt(this.value);
    if (notesData) {
        rerenderPreservingScroll();
        scrollToTime(timeAtPlayhead);
    }
});

document.getElementById('volume-slider').addEventListener('input', function() {
    var vol = parseInt(this.value);
    if (pianoSynth && samplesLoaded) {
        pianoSynth.volume.value = volumeToDb(vol);
    }
});

document.getElementById('speed-select').addEventListener('change', function() {
    var oldSpeed = playbackSpeed;
    playbackSpeed = parseFloat(this.value);
    if (isPlaying) {
        var elapsed = (performance.now() - playbackStartTime) / 1000 * oldSpeed;
        playbackTimeOffset += elapsed;
        playbackStartTime = performance.now();
    }
});

// -- Keyboard shortcuts ----------------------------------------------

document.addEventListener('keydown', function(e) {
    if ((e.metaKey || e.ctrlKey) && e.code === 'KeyP') {
        e.preventDefault();
        if (commandPaletteOpen) {
            hideCommandPalette();
        } else {
            showCommandPalette();
        }
        return;
    }

    if (e.target.id === 'command-palette-input') return;
    if (e.target.id === 'marker-input') return;
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT' || e.target.tagName === 'TEXTAREA') return;

    if ((e.metaKey || e.ctrlKey) && e.code === 'KeyO') {
        e.preventDefault();
        openFilePicker();
        return;
    }

    if ((e.metaKey || e.ctrlKey) && e.code === 'KeyS') {
        e.preventDefault();
        exportJSON();
        return;
    }

    if ((e.metaKey || e.ctrlKey) && e.code === 'KeyZ') {
        e.preventDefault();
        if (e.shiftKey) {
            redo();
        } else {
            undo();
        }
        return;
    }

    if ((e.metaKey || e.ctrlKey) && e.code === 'KeyY') {
        e.preventDefault();
        redo();
        return;
    }

    if (textNotesOnlyMode) {
        if (e.code === 'Escape') {
            e.preventDefault();
            toggleTextNotesMode(false);
        }
        return;
    }

    switch (e.code) {
        case 'Space':
            e.preventDefault();
            togglePlayback();
            break;
        case 'Home':
            e.preventDefault();
            if (notesData) scrollToTime(firstNoteTime - 1);
            if (isPlaying) {
                playbackTimeOffset = firstNoteTime - 1;
                playbackStartTime = performance.now();
                activeNoteIds.clear();
            }
            break;
        case 'End':
            e.preventDefault();
            if (notesData) scrollToTime(totalDuration);
            if (isPlaying) stopPlayback();
            break;
        case 'ArrowUp':
            e.preventDefault();
            onUserScrollIntent();
            document.getElementById('piano-roll-container').scrollBy({ top: -appSettings.scrollSpeed, behavior: 'smooth' });
            break;
        case 'ArrowDown':
            e.preventDefault();
            onUserScrollIntent();
            document.getElementById('piano-roll-container').scrollBy({ top: appSettings.scrollSpeed, behavior: 'smooth' });
            break;
        case 'KeyL':
            toggleLoop();
            break;
        case 'KeyT':
            toggleTheme();
            break;
        case 'Digit1':
            toggleHand('right');
            break;
        case 'Digit2':
            toggleHand('left');
            break;
        case 'KeyE':
            toggleEditMode();
            break;
        case 'Delete':
        case 'Backspace':
            if (editMode && selectedNoteId !== null) {
                e.preventDefault();
                deleteSelectedNote();
            }
            break;
        case 'KeyH':
            if (editMode && selectedNoteId !== null) {
                toggleSelectedNoteHand();
            }
            break;
        case 'KeyR':
            if (editMode) {
                setEditHand(editHand === 'right_hand' ? 'left_hand' : 'right_hand');
            }
            break;
        case 'KeyM':
            if (!editMode) break;
            addMarkerAtScroll();
            break;
        case 'KeyW':
            if (notesData && notesData.notes.length > 0) {
                toggleLyricsMode();
            }
            break;
        case 'Escape':
            if (markerInputMode) {
                hideMarkerInput();
            } else if (lyricsMode) {
                toggleLyricsMode();
            } else if (document.getElementById('github-modal').classList.contains('visible')) {
                document.getElementById('github-modal').classList.remove('visible');
            } else if (document.getElementById('settings-modal').classList.contains('visible')) {
                document.getElementById('settings-modal').classList.remove('visible');
            } else if (document.getElementById('context-menu').classList.contains('visible')) {
                hideContextMenu();
            } else if (commandPaletteOpen) {
                hideCommandPalette();
            } else if (editMode && selectedNoteId !== null) {
                deselectNote();
            } else if (editMode) {
                toggleEditMode();
            } else {
                hideHelp();
            }
            break;
        default:
            if (e.key === '?') {
                var modal = document.getElementById('help-modal');
                if (modal.classList.contains('visible')) {
                    hideHelp();
                } else {
                    showHelp();
                }
            }
            break;
    }
});

// -- Tone.js audio context resume ------------------------------------

function ensureToneStarted() {
    if (typeof Tone !== 'undefined' && Tone.context && Tone.context.state !== 'running') {
        Tone.start().catch(function() {});
    }
}
document.addEventListener('click', ensureToneStarted, { once: false });
document.addEventListener('keydown', ensureToneStarted, { once: false });

// -- Window resize ---------------------------------------------------

var resizeTimer = null;
window.addEventListener('resize', function() {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(function() {
        if (notesData) {
            var t = getTimeAtScroll();
            buildKeyboard();
            rerenderPreservingScroll();
            scrollToTime(t);
        }
    }, 150);
});
