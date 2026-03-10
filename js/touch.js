// ================================================================
//  Touch gesture support & mobile UI interactions
//  Handles: long-press, pinch-to-zoom, action sheets, mobile nav
// ================================================================

// -- Device detection ------------------------------------------------

var isTouchDevice = ('ontouchstart' in window) || (navigator.maxTouchPoints > 0);
var isMobileViewport = function() { return window.innerWidth <= 768; };

// -- Long-press detection --------------------------------------------

var longPressTimer = null;
var longPressTriggered = false;
var LONG_PRESS_DURATION = 500; // ms

function initLongPress() {
    var pianoRoll = document.getElementById('piano-roll');

    pianoRoll.addEventListener('touchstart', function(e) {
        if (e.touches.length !== 1) return;
        longPressTriggered = false;
        var touch = e.touches[0];
        var startX = touch.clientX;
        var startY = touch.clientY;
        var target = document.elementFromPoint(startX, startY);

        longPressTimer = setTimeout(function() {
            longPressTriggered = true;
            handleLongPress(startX, startY, target);
        }, LONG_PRESS_DURATION);
    }, { passive: true });

    pianoRoll.addEventListener('touchmove', function(e) {
        if (longPressTimer && e.touches.length === 1) {
            // Cancel long press if finger moved too much
            var touch = e.touches[0];
            clearTimeout(longPressTimer);
            longPressTimer = null;
        }
    }, { passive: true });

    pianoRoll.addEventListener('touchend', function() {
        clearTimeout(longPressTimer);
        longPressTimer = null;
    }, { passive: true });

    pianoRoll.addEventListener('touchcancel', function() {
        clearTimeout(longPressTimer);
        longPressTimer = null;
    }, { passive: true });
}

function handleLongPress(x, y, target) {
    // Haptic feedback if available
    if (navigator.vibrate) navigator.vibrate(30);

    var noteBlock = target ? target.closest('.note-block') : null;

    if (editMode && noteBlock) {
        var noteId = parseInt(noteBlock.dataset.noteId);
        selectNote(noteId);
        showNoteActionSheet(noteId);
    } else if (editMode) {
        var container = document.getElementById('piano-roll-container');
        var containerRect = container.getBoundingClientRect();
        var scrollY = container.scrollTop + (y - containerRect.top);
        var time = getTimeAtY(scrollY);
        showEmptyActionSheet(time, x, y);
    } else if (noteBlock) {
        // In view mode, long press shows note info
        var noteId = parseInt(noteBlock.dataset.noteId);
        var note = notesData.notes.find(function(n) { return n.id === noteId; });
        if (note) showMobileTooltip(note);
    }
}

// -- Mobile tooltip (replaces hover tooltip) -------------------------

function showMobileTooltip(note) {
    var handLabel = note.hand === 'right_hand' ? 'Right Hand' : 'Left Hand';
    var items = [
        { label: note.note_name, detail: handLabel, isHeader: true },
        { label: 'Start: ' + note.start_time.toFixed(2) + 's' },
        { label: 'Duration: ' + note.duration.toFixed(2) + 's' }
    ];
    if (note.lyric) {
        items.push({ label: 'Lyric: ' + note.lyric });
    }
    showActionSheet(items, 'Note Info');
}

// -- Action Sheet (replaces context menus on mobile) -----------------

function showActionSheet(items, title) {
    var overlay = document.getElementById('action-sheet-overlay');
    var sheet = document.getElementById('action-sheet');
    var itemsContainer = document.getElementById('action-sheet-items');
    var titleEl = document.getElementById('action-sheet-title');

    titleEl.textContent = title || '';
    titleEl.style.display = title ? '' : 'none';
    itemsContainer.innerHTML = '';

    items.forEach(function(item) {
        if (item.isSeparator) {
            var sep = document.createElement('div');
            sep.className = 'action-sheet-separator';
            itemsContainer.appendChild(sep);
            return;
        }
        var btn = document.createElement('button');
        btn.className = 'action-sheet-item';
        if (item.isHeader) btn.className += ' action-sheet-header';
        if (item.danger) btn.className += ' danger';
        if (item.disabled) btn.className += ' disabled';

        var content = document.createElement('span');
        content.className = 'action-sheet-item-content';

        if (item.icon) {
            var icon = document.createElement('span');
            icon.className = 'action-sheet-icon';
            icon.textContent = item.icon;
            content.appendChild(icon);
        }

        var labelSpan = document.createElement('span');
        labelSpan.className = 'action-sheet-label';
        labelSpan.textContent = item.label;
        content.appendChild(labelSpan);

        if (item.detail) {
            var detail = document.createElement('span');
            detail.className = 'action-sheet-detail';
            detail.textContent = item.detail;
            content.appendChild(detail);
        }

        btn.appendChild(content);

        if (item.action && !item.disabled && !item.isHeader) {
            btn.addEventListener('click', function() {
                hideActionSheet();
                // Delay action slightly so sheet animation completes
                setTimeout(item.action, 150);
            });
        }
        itemsContainer.appendChild(btn);
    });

    overlay.classList.add('visible');
    sheet.classList.add('visible');

    // Prevent body scroll while sheet is open
    document.body.style.overflow = 'hidden';
}

function hideActionSheet() {
    var overlay = document.getElementById('action-sheet-overlay');
    var sheet = document.getElementById('action-sheet');
    sheet.classList.remove('visible');
    overlay.classList.remove('visible');
    document.body.style.overflow = '';
}

function showNoteActionSheet(noteId) {
    var note = notesData.notes.find(function(n) { return n.id === noteId; });
    if (!note) return;

    var handLabel = note.hand === 'right_hand' ? 'Right Hand' : 'Left Hand';
    var items = [
        { icon: '🔄', label: 'Toggle Hand', detail: '→ ' + (note.hand === 'right_hand' ? 'LH' : 'RH'), action: function() {
            selectedNoteId = noteId;
            toggleSelectedNoteHand();
        }},
        { icon: '📋', label: 'Duplicate Note', action: function() { duplicateNote(noteId); }},
        { icon: '🎵', label: 'Edit Lyric', action: function() { lyricsSelectNote(noteId); }},
        { isSeparator: true },
        { icon: '🗑️', label: 'Delete Note', danger: true, action: function() {
            selectedNoteId = noteId;
            deleteSelectedNote();
        }}
    ];
    showActionSheet(items, note.note_name + ' · ' + handLabel);
}

function showEmptyActionSheet(time, clientX, clientY) {
    var items = [
        { icon: '➕', label: 'Add Note Here', action: function() { addNoteAtPosition(clientX, clientY); }},
        { icon: '📌', label: 'Add Marker Here', action: function() { showMarkerInput(time); }},
    ];
    showActionSheet(items, 'Actions');
}

// -- Overflow / "More" menu for mobile toolbar -----------------------

function showMobileMenu() {
    var items = [
        { icon: '📂', label: 'Open File', action: function() { openFilePicker(); }},
        { icon: '💾', label: 'Save / Export', action: function() { exportJSON(); }},
        { icon: '☁️', label: 'Cloud Storage', action: function() { showGitHub(); }},
        { isSeparator: true },
        { icon: '⚙️', label: 'Settings', action: function() { showSettings(); }},
        { icon: '❓', label: 'Help & Shortcuts', action: function() { showHelp(); }},
    ];
    showActionSheet(items, 'Menu');
}

// -- Mobile playback panel -------------------------------------------

function showMobilePlaybackPanel() {
    var panel = document.getElementById('mobile-playback-panel');
    if (panel.classList.contains('visible')) {
        panel.classList.remove('visible');
        return;
    }
    panel.classList.add('visible');
    syncMobilePlaybackUI();
}

function hideMobilePlaybackPanel() {
    document.getElementById('mobile-playback-panel').classList.remove('visible');
}

function syncMobilePlaybackUI() {
    var panel = document.getElementById('mobile-playback-panel');
    if (!panel) return;
    var playBtn = panel.querySelector('.mobile-play-btn');
    if (playBtn) playBtn.textContent = isPlaying ? '⏸' : '▶';
    var loopBtn = panel.querySelector('.mobile-loop-btn');
    if (loopBtn) loopBtn.classList.toggle('active', loopEnabled);
    var speedSel = panel.querySelector('.mobile-speed-select');
    if (speedSel) speedSel.value = String(playbackSpeed);
    var volSlider = panel.querySelector('.mobile-volume-slider');
    if (volSlider) volSlider.value = document.getElementById('volume-slider').value;
}

// -- Mobile edit bar (floating actions for selected note) ------------

function showMobileEditBar() {
    var bar = document.getElementById('mobile-edit-bar');
    if (bar) bar.classList.add('visible');
}

function hideMobileEditBar() {
    var bar = document.getElementById('mobile-edit-bar');
    if (bar) bar.classList.remove('visible');
}

function updateMobileEditBar() {
    if (!isMobileViewport()) return;
    if (editMode && selectedNoteId !== null) {
        showMobileEditBar();
    } else {
        hideMobileEditBar();
    }
}

// -- Mobile bottom nav highlighting ----------------------------------

function setMobileNavActive(tab) {
    var btns = document.querySelectorAll('.mobile-nav-btn');
    for (var i = 0; i < btns.length; i++) {
        btns[i].classList.toggle('active', btns[i].dataset.tab === tab);
    }
}

function handleMobileNavTap(tab) {
    switch (tab) {
        case 'play':
            showMobilePlaybackPanel();
            setMobileNavActive('play');
            break;
        case 'edit':
            if (!notesData) return;
            toggleEditMode();
            setMobileNavActive(editMode ? 'edit' : 'view');
            hideMobilePlaybackPanel();
            break;
        case 'lyrics':
            if (!notesData || !notesData.notes || notesData.notes.length === 0) return;
            toggleLyricsMode();
            setMobileNavActive(lyricsMode ? 'lyrics' : 'view');
            hideMobilePlaybackPanel();
            break;
        case 'more':
            showMobileMenu();
            break;
        default:
            // 'view' tab - exit edit/lyrics mode
            if (lyricsMode) toggleLyricsMode();
            if (editMode) toggleEditMode();
            hideMobilePlaybackPanel();
            setMobileNavActive('view');
            break;
    }
}

// -- Pinch-to-zoom for touch -----------------------------------------

var pinchState = null;

function initPinchZoom() {
    var container = document.getElementById('piano-roll-container');

    container.addEventListener('touchstart', function(e) {
        if (e.touches.length === 2) {
            e.preventDefault();
            var dx = e.touches[0].clientX - e.touches[1].clientX;
            var dy = e.touches[0].clientY - e.touches[1].clientY;
            pinchState = {
                initialDistance: Math.sqrt(dx * dx + dy * dy),
                initialPPS: pixelsPerSecond,
                midY: (e.touches[0].clientY + e.touches[1].clientY) / 2
            };
            // Cancel any long-press
            clearTimeout(longPressTimer);
            longPressTimer = null;
        }
    }, { passive: false });

    container.addEventListener('touchmove', function(e) {
        if (pinchState && e.touches.length === 2) {
            e.preventDefault();
            var dx = e.touches[0].clientX - e.touches[1].clientX;
            var dy = e.touches[0].clientY - e.touches[1].clientY;
            var distance = Math.sqrt(dx * dx + dy * dy);
            var scale = distance / pinchState.initialDistance;
            var newPPS = Math.max(20, Math.min(300, pinchState.initialPPS * scale));

            if (Math.abs(newPPS - pixelsPerSecond) > 0.5) {
                var container = document.getElementById('piano-roll-container');
                var roll = document.getElementById('piano-roll');
                var totalHeight = parseFloat(roll.style.height) || container.clientHeight;
                var bottomY = totalHeight - effectiveBottomPadding;
                var mouseY = container.scrollTop + pinchState.midY - container.getBoundingClientRect().top;
                var timeAtMid = (bottomY - mouseY) / pixelsPerSecond;

                pixelsPerSecond = newPPS;
                document.getElementById('zoom-slider').value = Math.round(pixelsPerSecond);
                rerenderPreservingScroll();

                var newTotalHeight = parseFloat(roll.style.height) || container.clientHeight;
                var newBottomY = newTotalHeight - effectiveBottomPadding;
                var newMidY = newBottomY - timeAtMid * pixelsPerSecond;
                var midScreenOffset = pinchState.midY - container.getBoundingClientRect().top;
                container.scrollTop = newMidY - midScreenOffset;

                updatePlayhead();
                updateTimeIndicator();
                updateProgressBar();
                updateMinimapViewport();
            }
        }
    }, { passive: false });

    container.addEventListener('touchend', function(e) {
        if (e.touches.length < 2) {
            pinchState = null;
        }
    }, { passive: true });
}

// -- Touch-friendly note editing (tap to select, drag to move) -------

var touchEditState = null;

function initTouchNoteEditing() {
    var pianoRoll = document.getElementById('piano-roll');

    pianoRoll.addEventListener('touchstart', function(e) {
        if (!editMode || !notesData || e.touches.length !== 1) return;
        if (longPressTriggered) return;

        var touch = e.touches[0];
        var target = document.elementFromPoint(touch.clientX, touch.clientY);
        var noteBlock = target ? target.closest('.note-block') : null;

        if (noteBlock) {
            var noteId = parseInt(noteBlock.dataset.noteId);
            selectNote(noteId);
            updateMobileEditBar();

            var note = notesData.notes.find(function(n) { return n.id === noteId; });
            if (!note) return;

            touchEditState = {
                noteId: noteId,
                startX: touch.clientX,
                startY: touch.clientY,
                origStartTime: note.start_time,
                origDuration: note.duration,
                origKeyIndex: note.key_index,
                origNoteName: note.note_name,
                hasMoved: false
            };
        }
    }, { passive: true });

    pianoRoll.addEventListener('touchmove', function(e) {
        if (!touchEditState || e.touches.length !== 1) return;
        var touch = e.touches[0];
        var dx = Math.abs(touch.clientX - touchEditState.startX);
        var dy = Math.abs(touch.clientY - touchEditState.startY);

        if (dx > 10 || dy > 10) {
            touchEditState.hasMoved = true;
            // Cancel long press
            clearTimeout(longPressTimer);
            longPressTimer = null;

            var note = notesData.notes.find(function(n) { return n.id === touchEditState.noteId; });
            if (!note) return;

            var timeDelta = (touch.clientY - touchEditState.startY) / pixelsPerSecond;
            var rawStart = Math.max(0, touchEditState.origStartTime - timeDelta);
            var snappedStart = snapToNoteEdge(rawStart, note.id);
            var rawEnd = rawStart + touchEditState.origDuration;
            var snappedEnd = snapToNoteEdge(rawEnd, note.id);

            if (snappedEnd !== rawEnd) {
                note.start_time = Math.max(0, snappedEnd - touchEditState.origDuration);
            } else if (snappedStart !== rawStart) {
                note.start_time = snappedStart;
            } else {
                note.start_time = rawStart;
            }

            note.key_index = getKeyIndexAtX(touch.clientX);
            note.note_name = PIANO_KEYS[note.key_index] || note.note_name;

            // Direct DOM update for smooth dragging
            var roll = document.getElementById('piano-roll');
            var container = document.getElementById('piano-roll-container');
            var totalHeight = parseFloat(roll.style.height) || container.clientHeight;
            var bottomY = totalHeight - effectiveBottomPadding;
            var noteTop = bottomY - (note.start_time + note.duration) * pixelsPerSecond;
            var noteHeight = Math.max(4, note.duration * pixelsPerSecond);
            var leftPct = getKeyLeftPercent(note.key_index);
            var widthPct = getKeyWidthPercent(note.key_index);

            var item = null;
            for (var i = 0; i < noteElements.length; i++) {
                if (noteElements[i].note.id === touchEditState.noteId) { item = noteElements[i]; break; }
            }
            if (item) {
                item.el.style.top = noteTop + 'px';
                item.el.style.height = noteHeight + 'px';
                item.el.style.left = leftPct + '%';
                item.el.style.width = widthPct + '%';
            }

            e.preventDefault();
        }
    }, { passive: false });

    pianoRoll.addEventListener('touchend', function(e) {
        if (!touchEditState) return;
        if (touchEditState.hasMoved) {
            var note = notesData.notes.find(function(n) { return n.id === touchEditState.noteId; });
            if (note && (note.start_time !== touchEditState.origStartTime || note.key_index !== touchEditState.origKeyIndex)) {
                pushUndo({
                    type: 'moveNote',
                    noteId: note.id,
                    oldStartTime: touchEditState.origStartTime,
                    oldKeyIndex: touchEditState.origKeyIndex,
                    oldNoteName: touchEditState.origNoteName,
                    newStartTime: note.start_time,
                    newKeyIndex: note.key_index,
                    newNoteName: note.note_name
                });
            }
            rerenderPreservingScroll();
            selectNote(touchEditState.noteId);
        }
        touchEditState = null;
    }, { passive: true });
}

// -- Touch note creation (tap on empty space in edit mode) -----------

function initTouchNoteCreation() {
    var pianoRoll = document.getElementById('piano-roll');

    pianoRoll.addEventListener('touchend', function(e) {
        if (!editMode || !notesData) return;
        if (longPressTriggered) return;
        if (touchEditState && touchEditState.hasMoved) return;
        if (e.changedTouches.length !== 1) return;

        var touch = e.changedTouches[0];
        var target = document.elementFromPoint(touch.clientX, touch.clientY);

        // Don't create note if we tapped on an existing note
        if (target && target.closest('.note-block')) return;
        // Don't create note if we tapped on a marker
        if (target && target.closest('.marker-label')) return;

        // For touch, single tap on empty space creates a note (easier than drag)
        // Only on mobile, where drag-to-create is impractical
        if (isMobileViewport()) {
            addNoteAtPosition(touch.clientX, touch.clientY);
        }
    }, { passive: true });
}

// -- Initialize all touch systems ------------------------------------

function initTouchSupport() {
    initLongPress();
    initPinchZoom();
    initTouchNoteEditing();
    initTouchNoteCreation();

    // Close action sheet on overlay tap
    var overlay = document.getElementById('action-sheet-overlay');
    if (overlay) {
        overlay.addEventListener('click', function(e) {
            if (e.target === overlay) hideActionSheet();
        });
    }

    // Update mobile nav state when edit/lyrics mode changes
    var origToggleEditMode = toggleEditMode;
    toggleEditMode = function() {
        origToggleEditMode();
        if (isMobileViewport()) {
            setMobileNavActive(editMode ? 'edit' : 'view');
            updateMobileEditBar();
            hideMobilePlaybackPanel();
        }
    };

    var origToggleLyricsMode = toggleLyricsMode;
    toggleLyricsMode = function() {
        origToggleLyricsMode();
        if (isMobileViewport()) {
            setMobileNavActive(lyricsMode ? 'lyrics' : (editMode ? 'edit' : 'view'));
        }
    };

    // Update mobile edit bar when note selection changes
    var origSelectNote = selectNote;
    selectNote = function(noteId) {
        origSelectNote(noteId);
        updateMobileEditBar();
    };

    var origDeselectNote = deselectNote;
    deselectNote = function() {
        origDeselectNote();
        updateMobileEditBar();
    };

    // Sync play button state
    var origStartPlayback = startPlayback;
    startPlayback = function() {
        origStartPlayback();
        syncMobilePlaybackUI();
    };

    var origStopPlayback = stopPlayback;
    stopPlayback = function() {
        origStopPlayback();
        syncMobilePlaybackUI();
    };

    // Handle resize to toggle mobile nav visibility
    window.addEventListener('resize', function() {
        var nav = document.getElementById('mobile-nav');
        if (nav) {
            nav.style.display = isMobileViewport() ? 'flex' : 'none';
        }
    });
}
