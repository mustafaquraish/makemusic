// ================================================================
//  File loading, saving, data management
// ================================================================

function loadNotesData(data) {
    notesData = data;

    // Initialize markers array if not present
    if (!data.markers) data.markers = [];

    // Update nextNoteId to be higher than any existing note ID
    if (data.notes && data.notes.length > 0) {
        var maxId = Math.max.apply(null, data.notes.map(function(n) { return n.id || 0; }));
        nextNoteId = Math.max(nextNoteId, maxId + 1);
    }

    // Update nextMarkerId
    if (data.markers.length > 0) {
        var maxMid = Math.max.apply(null, data.markers.map(function(m) { return m.id || 0; }));
        nextMarkerId = Math.max(nextMarkerId, maxMid + 1);
    }

    if (data.notes && data.notes.length > 0) {
        var maxKeyIdx = Math.max.apply(null, data.notes.map(function(n) { return n.key_index; }));
        if (maxKeyIdx > 87) {
            data.notes.forEach(function(n) {
                n.key_index = Math.max(0, Math.min(87, n.key_index - 21));
            });
        }
    }

    var info = document.getElementById('song-info');
    var dur = data.summary && data.summary.duration_range
        ? formatTimeFull(data.summary.duration_range[1]) : '';
    var total = data.summary ? data.summary.total_notes : data.notes.length;
    info.textContent = total + ' notes \u00B7 ' + dur;

    var rhCount = data.summary ? data.summary.right_hand_notes : data.notes.filter(function(n) { return n.hand === 'right_hand'; }).length;
    var lhCount = data.summary ? data.summary.left_hand_notes : data.notes.filter(function(n) { return n.hand === 'left_hand'; }).length;
    document.getElementById('note-count-badge').textContent = 'RH: ' + rhCount + ' | LH: ' + lhCount;

    // Populate song title input
    var titleInput = document.getElementById('song-title');
    if (titleInput) {
        titleInput.value = (data.metadata && data.metadata.title) || 'Untitled';
    }

    updateHandColors();

    var overlay = document.getElementById('loading-overlay');
    overlay.classList.add('hidden');
    setTimeout(function() { overlay.style.display = 'none'; }, 400);

    buildKeyboard();
    renderPianoRoll();
    renderTextNotesList();
    scrollToTime(firstNoteTime - 1);
}

function loadNotesFromURL(url) {
    fetch(url)
        .then(function(r) { return r.json(); })
        .then(function(data) {
            if (!data || !data.notes || !Array.isArray(data.notes)) {
                document.querySelector('#loading-text').textContent = 'Invalid JSON: missing "notes" array.';
                return;
            }
            loadNotesData(data);
        })
        .catch(function(err) {
            console.error('Failed to load:', err);
            document.querySelector('#loading-text').textContent = 'Failed to load data.';
        });
}

function loadExample(url, btn) {
    var original = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<span class="hp-spinner"></span> Loading…';
    fetch(url)
        .then(function(r) { return r.json(); })
        .then(function(data) {
            if (!data || !data.notes || !Array.isArray(data.notes)) {
                document.querySelector('#loading-text').textContent = 'Invalid JSON: missing "notes" array.';
                btn.disabled = false;
                btn.innerHTML = original;
                return;
            }
            loadNotesData(data);
        })
        .catch(function(err) {
            console.error('Failed to load example:', err);
            btn.disabled = false;
            btn.innerHTML = original;
            alert('Failed to load example. Check your connection and try again.');
        });
}

function openFilePicker() {
    document.getElementById('file-input').click();
}

function exportJSON() {
    if (!notesData) {
        alert('No data to export.');
        return;
    }
    var exportData = JSON.parse(JSON.stringify(notesData));
    var blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url;
    a.download = (exportData.metadata && exportData.metadata.title ? exportData.metadata.title.replace(/[^a-z0-9]/gi, '_') : 'makemusic_export') + '.json';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

function startEmpty() {
    var emptyData = {
        metadata: { title: 'Untitled', source: 'MakeMusic Editor' },
        notes: []
    };
    loadNotesData(emptyData);
}

function handleFileLoad(file) {
    if (!file) return;
    var reader = new FileReader();
    reader.onload = function(e) {
        try {
            var data = JSON.parse(e.target.result);
            if (!data.notes || !Array.isArray(data.notes)) {
                alert('Invalid JSON: missing "notes" array.');
                return;
            }
            loadNotesData(data);
        } catch (err) {
            alert('Failed to parse JSON: ' + err.message);
        }
    };
    reader.readAsText(file);
}
