// ================================================================
//  Tooltip, hand toggles, theme, help, settings, command palette
// ================================================================

// -- Tooltip ---------------------------------------------------------

function showTooltip(e, note) {
    var tt = document.getElementById('note-tooltip');
    var handLabel = note.hand === 'right_hand' ? 'Right Hand' : note.hand === 'left_hand' ? 'Left Hand' : 'Unknown';
    document.getElementById('tt-note').textContent = note.note_name;
    document.getElementById('tt-detail').innerHTML =
        handLabel + '<br>' +
        'Start: ' + note.start_time.toFixed(2) + 's<br>' +
        'Duration: ' + note.duration.toFixed(2) + 's';
    tt.classList.add('visible');
    moveTooltip(e);
}

function moveTooltip(e) {
    var tt = document.getElementById('note-tooltip');
    var x = Math.min(e.clientX + 14, window.innerWidth - 230);
    var y = Math.min(e.clientY - 10, window.innerHeight - 100);
    tt.style.left = x + 'px';
    tt.style.top = y + 'px';
}

function hideTooltip() {
    document.getElementById('note-tooltip').classList.remove('visible');
}

// -- Hand toggles ----------------------------------------------------

function toggleHand(hand) {
    if (hand === 'right') {
        showRightHand = !showRightHand;
        document.getElementById('rh-toggle').classList.toggle('inactive', !showRightHand);
    } else {
        showLeftHand = !showLeftHand;
        document.getElementById('lh-toggle').classList.toggle('inactive', !showLeftHand);
    }
    for (var i = 0; i < noteElements.length; i++) {
        var entry = noteElements[i];
        if (entry.note.hand === 'right_hand') {
            entry.el.style.display = showRightHand ? '' : 'none';
            if (entry.dropLine) entry.dropLine.style.display = showRightHand ? '' : 'none';
        } else if (entry.note.hand === 'left_hand') {
            entry.el.style.display = showLeftHand ? '' : 'none';
            if (entry.dropLine) entry.dropLine.style.display = showLeftHand ? '' : 'none';
        }
    }
}

function updateHandColors() {
    if (!notesData) return;
    var rhNote = null, lhNote = null;
    for (var i = 0; i < notesData.notes.length; i++) {
        var n = notesData.notes[i];
        if (!rhNote && n.hand === 'right_hand' && n.color_rgb) rhNote = n;
        if (!lhNote && n.hand === 'left_hand' && n.color_rgb) lhNote = n;
        if (rhNote && lhNote) break;
    }
    if (rhNote) rhColor = rhNote.color_rgb;
    if (lhNote) lhColor = lhNote.color_rgb;

    document.getElementById('rh-swatch').style.background =
        'rgb(' + rhColor[0] + ',' + rhColor[1] + ',' + rhColor[2] + ')';
    document.getElementById('lh-swatch').style.background =
        'rgb(' + lhColor[0] + ',' + lhColor[1] + ',' + lhColor[2] + ')';
}

// -- Theme -----------------------------------------------------------

function toggleTheme() {
    var html = document.documentElement;
    var current = html.getAttribute('data-theme');
    var next = current === 'light' ? 'dark' : 'light';
    html.setAttribute('data-theme', next);
    var darkToggle = document.getElementById('setting-dark-mode');
    if (darkToggle) darkToggle.classList.toggle('active', next === 'dark');
    if (notesData) renderDensity();
}

// -- Help modal ------------------------------------------------------

function showHelp() {
    document.getElementById('help-modal').classList.add('visible');
}

function hideHelp() {
    document.getElementById('help-modal').classList.remove('visible');
}

// -- Settings --------------------------------------------------------

function loadSettings() {
    try {
        var saved = localStorage.getItem('makemusic_settings');
        if (saved) {
            var parsed = JSON.parse(saved);
            Object.keys(parsed).forEach(function(key) {
                if (key in appSettings) appSettings[key] = parsed[key];
            });
        }
    } catch(e) {}
    applySettings();
}

function saveSettings() {
    try {
        localStorage.setItem('makemusic_settings', JSON.stringify(appSettings));
    } catch(e) {}
}

function applySettings() {
    document.getElementById('setting-drop-lines').classList.toggle('active', appSettings.dropLines);
    document.getElementById('setting-note-labels').classList.toggle('active', appSettings.noteLabels);
    document.getElementById('setting-density').classList.toggle('active', appSettings.density);
    var densityCanvas = document.getElementById('density-canvas');
    if (densityCanvas) densityCanvas.style.display = appSettings.density ? '' : 'none';
    document.getElementById('setting-scroll-speed').value = appSettings.scrollSpeed;
    // keyboard height slider (px)
    var kbSlider = document.getElementById('setting-keyboard-height');
    if (kbSlider) kbSlider.value = appSettings.keyboardHeight;
    document.documentElement.style.setProperty('--keyboard-height', appSettings.keyboardHeight + 'px');

    document.getElementById('setting-rh-color').value = appSettings.rhColorHex;
    document.getElementById('setting-lh-color').value = appSettings.lhColorHex;
    rhColor = hexToRgb(appSettings.rhColorHex);
    lhColor = hexToRgb(appSettings.lhColorHex);

    // Sync dark mode toggle
    var darkToggle = document.getElementById('setting-dark-mode');
    if (darkToggle) {
        var isDark = document.documentElement.getAttribute('data-theme') !== 'light';
        darkToggle.classList.toggle('active', isDark);
    }
} 

function toggleSetting(key) {
    appSettings[key] = !appSettings[key];
    saveSettings();
    applySettings();
    if (notesData) rerenderPreservingScroll();
}

function changeSetting(key, value) {
    appSettings[key] = parseInt(value);
    saveSettings();
    applySettings();
    // changing keyboard height doesn't affect note rendering but the
    // CSS variable drives the layout, so trigger a repaint just in case
    if (key === 'keyboardHeight' && notesData) rerenderPreservingScroll();
}

function changeHandColor(hand, hexValue) {
    if (hand === 'right') {
        appSettings.rhColorHex = hexValue;
        rhColor = hexToRgb(hexValue);
    } else {
        appSettings.lhColorHex = hexValue;
        lhColor = hexToRgb(hexValue);
    }
    saveSettings();
    updateHandColors();
    if (notesData) {
        notesData.notes.forEach(function(n) {
            n.color_rgb = (n.hand === 'right_hand' ? rhColor : lhColor).slice();
        });
        rerenderPreservingScroll();
    }
}

function resetSettings() {
    appSettings = {
        dropLines: true,
        noteLabels: true,
        density: true,
        scrollSpeed: 120,
        keyboardHeight: 100,
        rhColorHex: '#6495ED',
        lhColorHex: '#48BF91'
    };
    saveSettings();
    applySettings();
    updateHandColors();
    if (notesData) {
        notesData.notes.forEach(function(n) {
            n.color_rgb = (n.hand === 'right_hand' ? rhColor : lhColor).slice();
        });
        rerenderPreservingScroll();
    }
}

function showSettings() {
    document.getElementById('settings-modal').classList.add('visible');
}

function hideSettings(e) {
    if (e && e.target.id !== 'settings-modal') return;
    document.getElementById('settings-modal').classList.remove('visible');
}

// -- Command palette -------------------------------------------------

var allCommands = [
    { icon: '\u25B6', label: 'Play / Pause', shortcut: 'Space', action: togglePlayback },
    { icon: '\uD83D\uDD01', label: 'Toggle Loop', shortcut: 'L', action: toggleLoop },
    { icon: '\u23EE', label: 'Jump to Start', shortcut: 'Home', action: function() { if (notesData) scrollToTime(firstNoteTime - 1); } },
    { icon: '\u23ED', label: 'Jump to End', shortcut: 'End', action: function() { if (notesData) scrollToTime(totalDuration); } },
    { icon: '\uD83C\uDFB9', label: 'Toggle Right Hand', shortcut: '1', action: function() { toggleHand('right'); } },
    { icon: '\uD83C\uDFB9', label: 'Toggle Left Hand', shortcut: '2', action: function() { toggleHand('left'); } },
    { icon: '\u2600\uFE0F', label: 'Toggle Theme (Dark/Light)', shortcut: 'T', action: toggleTheme },
    { icon: '\uD83D\uDCC2', label: 'Open JSON File', shortcut: '\u2318O', action: openFilePicker },
    { icon: '\uD83D\uDCBE', label: 'Save/Export JSON', shortcut: '\u2318S', action: exportJSON },
    { icon: '\uD83D\uDCC4', label: 'New Empty Project', shortcut: '', action: startEmpty },
    { icon: '\uD83D\uDD0A', label: 'Volume Up', shortcut: '', action: function() {
        var slider = document.getElementById('volume-slider');
        slider.value = Math.min(100, parseInt(slider.value) + 10);
        slider.dispatchEvent(new Event('input'));
    }},
    { icon: '\uD83D\uDD09', label: 'Volume Down', shortcut: '', action: function() {
        var slider = document.getElementById('volume-slider');
        slider.value = Math.max(0, parseInt(slider.value) - 10);
        slider.dispatchEvent(new Event('input'));
    }},
    { icon: '\uD83D\uDD0D', label: 'Zoom In', shortcut: 'Ctrl+Scroll\u2191', action: function() {
        pixelsPerSecond = Math.min(300, pixelsPerSecond * 1.2);
        document.getElementById('zoom-slider').value = Math.round(pixelsPerSecond);
        if (notesData) { var t = getTimeAtScroll(); rerenderPreservingScroll(); scrollToTime(t); }
    }},
    { icon: '\uD83D\uDD0D', label: 'Zoom Out', shortcut: 'Ctrl+Scroll\u2193', action: function() {
        pixelsPerSecond = Math.max(20, pixelsPerSecond / 1.2);
        document.getElementById('zoom-slider').value = Math.round(pixelsPerSecond);
        if (notesData) { var t = getTimeAtScroll(); rerenderPreservingScroll(); scrollToTime(t); }
    }},
    { icon: '\u23E9', label: 'Speed: 0.25\u00D7', shortcut: '', action: function() { setSpeed(0.25); } },
    { icon: '\u23E9', label: 'Speed: 0.5\u00D7', shortcut: '', action: function() { setSpeed(0.5); } },
    { icon: '\u23E9', label: 'Speed: 0.75\u00D7', shortcut: '', action: function() { setSpeed(0.75); } },
    { icon: '\u23E9', label: 'Speed: 1\u00D7', shortcut: '', action: function() { setSpeed(1); } },
    { icon: '\u23E9', label: 'Speed: 1.5\u00D7', shortcut: '', action: function() { setSpeed(1.5); } },
    { icon: '\u23E9', label: 'Speed: 2\u00D7', shortcut: '', action: function() { setSpeed(2); } },
    { icon: '\u2753', label: 'Show Keyboard Shortcuts', shortcut: '?', action: showHelp },
    { icon: '\u2B06', label: 'Scroll Up', shortcut: '\u2191', action: function() { document.getElementById('piano-roll-container').scrollBy({ top: -appSettings.scrollSpeed, behavior: 'smooth' }); } },
    { icon: '\u2B07', label: 'Scroll Down', shortcut: '\u2193', action: function() { document.getElementById('piano-roll-container').scrollBy({ top: appSettings.scrollSpeed, behavior: 'smooth' }); } },
    { icon: '\u270F\uFE0F', label: 'Toggle Edit Mode', shortcut: 'E', action: toggleEditMode },
    { icon: '\uD83D\uDDD1\uFE0F', label: 'Delete Selected Note', shortcut: 'Del', action: deleteSelectedNote },
    { icon: '\uD83D\uDD04', label: 'Toggle Selected Note Hand', shortcut: 'H', action: toggleSelectedNoteHand },
    { icon: '\u2699\uFE0F', label: 'Open Settings', shortcut: '', action: showSettings },
    { icon: '\uD83D\uDD04', label: 'Toggle Edit Hand (RH/LH)', shortcut: 'R', action: function() { setEditHand(editHand === 'right_hand' ? 'left_hand' : 'right_hand'); } },
    { icon: '\uD83D\uDCCD', label: 'Add Marker at Current Position', shortcut: 'M', action: addMarkerAtScroll },
    { icon: '\uD83C\uDFB5', label: 'Toggle Lyrics Mode', shortcut: 'W', action: toggleLyricsMode },
];

function renderCommandList(query) {
    var list = document.getElementById('command-palette-list');
    list.innerHTML = '';
    filteredCommands = query
        ? allCommands.filter(function(cmd) { return fuzzyMatch(query, cmd.label); })
        : allCommands.slice();

    if (filteredCommands.length === 0) {
        list.innerHTML = '<div class="cmd-no-results">No matching commands</div>';
        return;
    }

    commandPaletteSelectedIndex = Math.min(commandPaletteSelectedIndex, filteredCommands.length - 1);

    filteredCommands.forEach(function(cmd, i) {
        var item = document.createElement('div');
        item.className = 'cmd-item' + (i === commandPaletteSelectedIndex ? ' selected' : '');
        item.innerHTML = '<span class="cmd-icon">' + cmd.icon + '</span>' +
            '<span class="cmd-label">' + cmd.label + '</span>' +
            (cmd.shortcut ? '<span class="cmd-shortcut">' + cmd.shortcut + '</span>' : '');
        item.addEventListener('click', function() {
            hideCommandPalette();
            cmd.action();
        });
        item.addEventListener('mouseenter', function() {
            commandPaletteSelectedIndex = i;
            updateCommandSelection();
        });
        list.appendChild(item);
    });
}

function updateCommandSelection() {
    var items = document.querySelectorAll('#command-palette-list .cmd-item');
    for (var i = 0; i < items.length; i++) {
        items[i].classList.toggle('selected', i === commandPaletteSelectedIndex);
    }
    if (items[commandPaletteSelectedIndex]) {
        items[commandPaletteSelectedIndex].scrollIntoView({ block: 'nearest' });
    }
}

function showCommandPalette() {
    commandPaletteOpen = true;
    commandPaletteSelectedIndex = 0;
    var overlay = document.getElementById('command-palette-overlay');
    overlay.classList.add('visible');
    var input = document.getElementById('command-palette-input');
    input.value = '';
    input.focus();
    renderCommandList('');
}

function hideCommandPalette() {
    commandPaletteOpen = false;
    document.getElementById('command-palette-overlay').classList.remove('visible');
}
