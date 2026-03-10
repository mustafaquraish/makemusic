// ================================================================
//  Piano roll rendering, track lines, density, minimap
// ================================================================

function renderTrackLines() {
    if (!window.keyLayout) return;
    var roll = document.getElementById('piano-roll');
    var existing = roll.querySelectorAll('.track-line');
    for (var i = 0; i < existing.length; i++) existing[i].remove();

    var layout = window.keyLayout;
    for (var idx = 0; idx < layout.whiteKeys.length; idx++) {
        var line = document.createElement('div');
        line.className = 'track-line';
        line.style.left = (idx + 1) * layout.keyWidth + '%';
        roll.appendChild(line);
    }
}

function renderDensity() {
    if (!notesData || notesData.notes.length === 0) return;
    var canvas = document.getElementById('density-canvas');
    var roll = document.getElementById('piano-roll');
    var totalHeight = parseFloat(roll.style.height) || 1;
    canvas.width = 1;
    var canvasH = Math.min(Math.round(totalHeight), 8000);
    canvas.height = canvasH;
    canvas.style.height = totalHeight + 'px';

    var ctx = canvas.getContext('2d');
    var bucketCount = canvasH;
    var buckets = new Float32Array(bucketCount);

    var bottomY = totalHeight - effectiveBottomPadding;
    notesData.notes.forEach(function(note) {
        var yTop = bottomY - (note.start_time + note.duration) * pixelsPerSecond;
        var yBot = bottomY - note.start_time * pixelsPerSecond;
        var t = Math.max(0, Math.floor(yTop / totalHeight * bucketCount));
        var b = Math.min(bucketCount - 1, Math.floor(yBot / totalHeight * bucketCount));
        for (var i = t; i <= b; i++) buckets[i]++;
    });

    var maxDensity = 0;
    for (var i = 0; i < bucketCount; i++) { if (buckets[i] > maxDensity) maxDensity = buckets[i]; }
    if (maxDensity === 0) return;

    var imgData = ctx.createImageData(1, bucketCount);
    var isLight = document.documentElement.getAttribute('data-theme') === 'light';
    for (var i = 0; i < bucketCount; i++) {
        var d = buckets[i] / maxDensity;
        var idx = i * 4;
        if (isLight) {
            imgData.data[idx] = 214;
            imgData.data[idx + 1] = 48;
            imgData.data[idx + 2] = 80;
        } else {
            imgData.data[idx] = 233;
            imgData.data[idx + 1] = 69;
            imgData.data[idx + 2] = 96;
        }
        imgData.data[idx + 3] = Math.floor(d * 18);
    }
    ctx.putImageData(imgData, 0, 0);
}

function renderMinimap() {
    if (!notesData || notesData.notes.length === 0) return;
    var minimap = document.getElementById('minimap');
    var existing = minimap.querySelectorAll('.minimap-note');
    for (var i = 0; i < existing.length; i++) existing[i].remove();

    var mmHeight = minimap.clientHeight;
    var songDur = totalDuration;
    if (songDur <= 0) return;

    var frag = document.createDocumentFragment();
    notesData.notes.forEach(function(note) {
        var el = document.createElement('div');
        el.className = 'minimap-note';
        var top = (note.start_time / songDur) * mmHeight;
        var h = Math.max(1, (note.duration / songDur) * mmHeight);
        var c = note.color_rgb || (note.hand === 'right_hand' ? rhColor : lhColor);
        el.style.cssText = 'top:' + top + 'px;height:' + h + 'px;left:4px;right:4px;' +
            'background:rgb(' + c[0] + ',' + c[1] + ',' + c[2] + ');opacity:0.5;';
        frag.appendChild(el);
    });
    minimap.appendChild(frag);
}

function updateMinimapViewport() {
    if (!notesData || totalDuration <= 0) return;
    var container = document.getElementById('piano-roll-container');
    var minimap = document.getElementById('minimap');
    var roll = document.getElementById('piano-roll');
    var mmHeight = minimap.clientHeight;
    var totalH = parseFloat(roll.style.height) || 1;
    var bottomY = totalH - effectiveBottomPadding;

    var topTime = (bottomY - container.scrollTop) / pixelsPerSecond;
    var botTime = (bottomY - container.scrollTop - container.clientHeight) / pixelsPerSecond;

    var vp = document.getElementById('minimap-viewport');
    var vpTop = Math.max(0, (Math.max(0, botTime) / totalDuration) * mmHeight);
    var vpBot = Math.min(mmHeight, (Math.max(0, topTime) / totalDuration) * mmHeight);
    vp.style.top = vpTop + 'px';
    vp.style.height = Math.max(10, vpBot - vpTop) + 'px';
}

function renderPianoRoll() {
    if (!notesData) return;
    var roll = document.getElementById('piano-roll');
    var container = document.getElementById('piano-roll-container');

    var existingNotes = roll.querySelectorAll('.note-block, .note-drop-line');
    for (var i = 0; i < existingNotes.length; i++) existingNotes[i].remove();
    noteElements = [];

    var notes = notesData.notes;
    if (notes.length === 0) {
        totalDuration = 0;
        firstNoteTime = 0;
        roll.style.height = container.clientHeight + 'px';
        renderTrackLines();
        return;
    }

    var times = notes.map(function(n) { return n.start_time + n.duration; });
    var startTimes = notes.map(function(n) { return n.start_time; });
    var maxTime = Math.max.apply(null, times);
    totalDuration = maxTime;
    firstNoteTime = Math.min.apply(null, startTimes);

    // Dynamic bottom padding: ensure scroll range always allows reaching time 0
    effectiveBottomPadding = Math.max(BOTTOM_PADDING, Math.ceil(container.clientHeight * 0.35));
    var totalHeight = maxTime * pixelsPerSecond + container.clientHeight;
    roll.style.height = totalHeight + 'px';

    var bottomY = totalHeight - effectiveBottomPadding;
    var frag = document.createDocumentFragment();

    notes.forEach(function(note) {
        var div = document.createElement('div');
        var handClass = (note.hand || 'unknown').replace(/_/g, '-');
        div.className = 'note-block ' + handClass;
        div.dataset.noteId = note.id;
        div.dataset.startTime = note.start_time;
        div.dataset.duration = note.duration;
        div.dataset.keyIndex = note.key_index;
        div.dataset.noteName = note.note_name;
        div.dataset.hand = note.hand || 'unknown';

        var c = note.color_rgb || (note.hand === 'right_hand' ? rhColor : lhColor);
        var colors = getNoteColors(c, note.note_name);

        if ((note.note_name || '').includes('#')) {
            div.classList.add('sharp-note');
        }

        div.style.background = 'linear-gradient(135deg, rgb(' + colors.r + ',' + colors.g + ',' + colors.b + '), rgb(' + colors.r2 + ',' + colors.g2 + ',' + colors.b2 + '))';

        var noteTop = bottomY - (note.start_time + note.duration) * pixelsPerSecond;
        var noteHeight = Math.max(4, note.duration * pixelsPerSecond);
        var leftPct = getKeyLeftPercent(note.key_index);
        var widthPct = getKeyWidthPercent(note.key_index);

        div.style.top = noteTop + 'px';
        div.style.height = noteHeight + 'px';
        div.style.left = leftPct + '%';
        div.style.width = widthPct + '%';

        if (noteHeight > 18 && appSettings.noteLabels) {
            div.textContent = note.note_name || '';
        }

        // Show lyric text if present
        if (note.lyric) {
            var lyricSpan = document.createElement('span');
            lyricSpan.className = 'note-lyric';
            lyricSpan.textContent = note.lyric;
            div.appendChild(lyricSpan);
        }

        if (note.hand === 'right_hand' && !showRightHand) div.style.display = 'none';
        if (note.hand === 'left_hand' && !showLeftHand) div.style.display = 'none';

        // Resize handles for edit mode
        var handleTop = document.createElement('div');
        handleTop.className = 'resize-handle-top';
        div.appendChild(handleTop);
        var handleBottom = document.createElement('div');
        handleBottom.className = 'resize-handle-bottom';
        div.appendChild(handleBottom);

        div.addEventListener('click', function() {
            if (lyricsMode) {
                // In lyrics mode, clicking a note focuses it in the lyrics panel
                lyricsSelectNote(note.id);
                return;
            }
            if (editMode) return;
            if (soundEnabled && samplesLoaded) playNote(note.key_index, Math.min(note.duration, 2));
            scrollToTime(note.start_time);
        });

        div.addEventListener('mouseenter', function(e) { showTooltip(e, note); });
        div.addEventListener('mousemove', function(e) { moveTooltip(e); });
        div.addEventListener('mouseleave', hideTooltip);

        frag.appendChild(div);

        // Drop line from bottom of note to bottom of roll
        var dropLine = document.createElement('div');
        dropLine.className = 'note-drop-line';
        var dropTop = noteTop + noteHeight;
        var dropHeight = bottomY - dropTop;
        if (dropHeight > 0) {
            dropLine.style.top = dropTop + 'px';
            dropLine.style.height = dropHeight + 'px';
            dropLine.style.left = 'calc(' + leftPct + '% + ' + (widthPct / 2) + '%)';
            dropLine.style.color = 'rgb(' + colors.r + ',' + colors.g + ',' + colors.b + ')';
            if (note.hand === 'right_hand' && !showRightHand) dropLine.style.display = 'none';
            if (note.hand === 'left_hand' && !showLeftHand) dropLine.style.display = 'none';
            if (!appSettings.dropLines) dropLine.style.display = 'none';
            dropLine.style.opacity = '0';
            dropLine.style.transition = 'opacity 0.3s ease';
            frag.appendChild(dropLine);
        }

        noteElements.push({ el: div, dropLine: dropLine, note: note });
    });

    roll.appendChild(frag);

    renderTrackLines();
    renderMarkers();
    renderDensity();
    renderMinimap();

    updatePlayhead();
    updateTimeIndicator();
    updateProgressBar();
    updateMinimapViewport();
    updateDropLineVisibility();
}

function updateDropLineVisibility() {
    if (!appSettings.dropLines || noteElements.length === 0) return;
    var container = document.getElementById('piano-roll-container');
    var scrollTop = container.scrollTop;
    var viewHeight = container.clientHeight;
    var viewTop = scrollTop - 200;
    var viewBottom = scrollTop + viewHeight + 200;

    for (var i = 0; i < noteElements.length; i++) {
        var item = noteElements[i];
        if (!item.dropLine) continue;
        var el = item.el;
        var noteTop = parseFloat(el.style.top);
        var noteHeight = parseFloat(el.style.height);
        var noteBottom = noteTop + noteHeight;

        var isVisible = (noteBottom >= viewTop && noteTop <= viewBottom);
        var hidden = el.style.display === 'none';
        item.dropLine.style.opacity = (isVisible && !hidden) ? '0.18' : '0';
    }
}

// ================================================================
//  Timeline markers
// ================================================================

function renderMarkers() {
    var roll = document.getElementById('piano-roll');
    var existing = roll.querySelectorAll('.marker-line');
    for (var i = 0; i < existing.length; i++) existing[i].remove();

    if (!notesData || !notesData.markers || notesData.markers.length === 0) return;

    var container = document.getElementById('piano-roll-container');
    var totalHeight = parseFloat(roll.style.height) || container.clientHeight;
    var bottomY = totalHeight - effectiveBottomPadding;
    var frag = document.createDocumentFragment();

    notesData.markers.forEach(function(marker) {
        var y = bottomY - marker.time * pixelsPerSecond;
        var line = document.createElement('div');
        line.className = 'marker-line';
        line.dataset.markerId = marker.id;
        line.style.top = y + 'px';

        var label = document.createElement('span');
        label.className = 'marker-label';
        label.textContent = marker.label || '';

        // Markers are always interactive (click to edit, right-click to delete)
        (function(m) {
            label.addEventListener('click', function(e) {
                e.stopPropagation();
                if (editMode) {
                    editMarker(m.id);
                } else {
                    // In view mode, clicking scrolls to the marker time
                    scrollToTime(m.time);
                }
            });
            label.addEventListener('contextmenu', function(e) {
                e.preventDefault();
                e.stopPropagation();
                if (editMode) deleteMarker(m.id);
            });
        })(marker);

        // Delete button visible in edit mode
        if (editMode) {
            var deleteBtn = document.createElement('span');
            deleteBtn.className = 'marker-delete-btn';
            deleteBtn.textContent = '×';
            deleteBtn.title = 'Delete marker';
            (function(m) {
                deleteBtn.addEventListener('click', function(e) {
                    e.stopPropagation();
                    deleteMarker(m.id);
                });
            })(marker);
            label.appendChild(deleteBtn);
        }

        line.appendChild(label);

        frag.appendChild(line);
    });

    roll.appendChild(frag);
}
