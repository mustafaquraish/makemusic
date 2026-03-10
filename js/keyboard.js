// ================================================================
//  Keyboard building and layout
// ================================================================

function buildKeyboard() {
    var wrapper = document.getElementById('keyboard-wrapper');
    wrapper.innerHTML = '';

    var minKey = 20, maxKey = 72;
    if (notesData && notesData.notes.length > 0) {
        var keys = notesData.notes.map(function(n) { return n.key_index; });
        minKey = Math.max(0, Math.min.apply(null, keys) - 3);
        maxKey = Math.min(87, Math.max.apply(null, keys) + 3);
    }

    var whiteKeys = [];
    var blackKeys = [];
    for (var i = minKey; i <= maxKey; i++) {
        var name = PIANO_KEYS[i];
        if (!name) continue;
        if (isBlackKey(name)) {
            blackKeys.push({ index: i, name: name });
        } else {
            whiteKeys.push({ index: i, name: name });
        }
    }

    var totalWhite = whiteKeys.length;
    var keyWidth = 100 / totalWhite;

    whiteKeys.forEach(function(key) {
        var el = document.createElement('div');
        el.className = 'key white';
        el.dataset.keyIndex = key.index;
        el.id = 'key-' + key.index;
        el.style.width = keyWidth + '%';
        el.textContent = key.name;
        wrapper.appendChild(el);
    });

    var whiteIdx = 0;
    for (var i = minKey; i <= maxKey; i++) {
        var name = PIANO_KEYS[i];
        if (!name) continue;
        if (isBlackKey(name)) {
            var el = document.createElement('div');
            el.className = 'key black';
            el.dataset.keyIndex = i;
            el.id = 'key-' + i;
            el.style.left = (whiteIdx - 0.3) * keyWidth + '%';
            el.style.width = keyWidth * 0.6 + '%';
            el.textContent = name;
            wrapper.appendChild(el);
        } else {
            whiteIdx++;
        }
    }

    window.keyLayout = { minKey: minKey, maxKey: maxKey, whiteKeys: whiteKeys, totalWhite: totalWhite, keyWidth: keyWidth };
}

function getKeyXPercent(keyIndex) {
    if (!window.keyLayout) return 50;
    var layout = window.keyLayout;
    var whiteIdx = 0;
    for (var i = layout.minKey; i <= layout.maxKey; i++) {
        var name = PIANO_KEYS[i];
        if (!name) continue;
        if (i === keyIndex) {
            return isBlackKey(name)
                ? (whiteIdx - 0.3) * layout.keyWidth + layout.keyWidth * 0.3
                : whiteIdx * layout.keyWidth + layout.keyWidth / 2;
        }
        if (!isBlackKey(name)) whiteIdx++;
    }
    return 50;
}

function getKeyWidthPercent(keyIndex) {
    if (!window.keyLayout) return 2;
    var kw = window.keyLayout.keyWidth;
    var name = PIANO_KEYS[keyIndex];
    return isBlackKey(name) ? kw * 0.6 : kw * 0.9;
}

function getKeyLeftPercent(keyIndex) {
    return getKeyXPercent(keyIndex) - getKeyWidthPercent(keyIndex) / 2;
}
