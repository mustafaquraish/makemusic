// ================================================================
//  Playback, scroll/time utilities, key highlighting
// ================================================================

function scrollToTime(time) {
    programmaticScroll = true;
    var container = document.getElementById('piano-roll-container');
    var roll = document.getElementById('piano-roll');
    var totalHeight = parseFloat(roll.style.height) || container.clientHeight;
    var bottomY = totalHeight - BOTTOM_PADDING;
    var playheadOffset = container.clientHeight * 0.7;
    var targetY = bottomY - time * pixelsPerSecond - playheadOffset;
    container.scrollTop = Math.max(0, targetY);
    requestAnimationFrame(function() { programmaticScroll = false; });
}

function getTimeAtScroll() {
    var container = document.getElementById('piano-roll-container');
    var roll = document.getElementById('piano-roll');
    var totalHeight = parseFloat(roll.style.height) || container.clientHeight;
    var bottomY = totalHeight - BOTTOM_PADDING;
    var playlineY = container.scrollTop + container.clientHeight * 0.7;
    return (bottomY - playlineY) / pixelsPerSecond;
}

function updatePlayhead() {
    var container = document.getElementById('piano-roll-container');
    var playhead = document.getElementById('playhead');
    playhead.style.top = (container.scrollTop + container.clientHeight * 0.7) + 'px';
}

function updateTimeIndicator() {
    var time = getTimeAtScroll();
    var current = formatTimeFull(time);
    var total = formatTimeFull(totalDuration);
    document.getElementById('time-indicator').textContent = current + ' / ' + total;
}

function updateProgressBar() {
    var time = Math.max(0, getTimeAtScroll());
    var pct = totalDuration > 0 ? Math.min(100, (time / totalDuration) * 100) : 0;
    document.getElementById('progress-bar-fill').style.width = pct + '%';
}

function onProgressClick(e) {
    if (!notesData || totalDuration <= 0) return;
    var rect = e.currentTarget.getBoundingClientRect();
    var pct = (e.clientX - rect.left) / rect.width;
    var time = pct * totalDuration;
    scrollToTime(time);
    if (isPlaying) {
        playbackTimeOffset = time;
        playbackStartTime = performance.now();
        activeNoteIds.clear();
    }
}

// ================================================================
//  Active key highlighting
// ================================================================

function highlightActiveKeys() {
    var activeKeys = document.querySelectorAll('.key.active-rh, .key.active-lh');
    for (var i = 0; i < activeKeys.length; i++) {
        activeKeys[i].classList.remove('active-rh', 'active-lh');
        activeKeys[i].style.removeProperty('background');
    }
    if (!notesData) return;
    var currentTime = getTimeAtScroll();

    notesData.notes.forEach(function(note) {
        if (currentTime >= note.start_time && currentTime <= note.start_time + note.duration) {
            if (note.hand === 'right_hand' && !showRightHand) return;
            if (note.hand === 'left_hand' && !showLeftHand) return;
            var keyEl = document.getElementById('key-' + note.key_index);
            if (keyEl) {
                var cls = note.hand === 'left_hand' ? 'active-lh' : 'active-rh';
                keyEl.classList.add(cls);
                var c = note.color_rgb || (note.hand === 'right_hand' ? rhColor : lhColor);
                keyEl.style.setProperty('background', 'rgb(' + c[0] + ',' + c[1] + ',' + c[2] + ')', 'important');
            }
        }
    });
}

function highlightPlayingNotes() {
    if (!notesData) return;
    var currentTime = getTimeAtScroll();
    for (var i = 0; i < noteElements.length; i++) {
        var entry = noteElements[i];
        var note = entry.note;
        var el = entry.el;
        var isActive = currentTime >= note.start_time && currentTime <= note.start_time + note.duration;
        var isVisible = (note.hand === 'right_hand' ? showRightHand : showLeftHand);
        if (isActive && isVisible) {
            if (!el.classList.contains('playing')) el.classList.add('playing');
        } else {
            if (el.classList.contains('playing')) el.classList.remove('playing');
        }
    }
}

// ================================================================
//  Playback control
// ================================================================

function togglePlayback() {
    if (isPlaying) {
        stopPlayback();
    } else {
        startPlayback();
    }
}

function startPlayback() {
    if (!notesData) return;
    isPlaying = true;
    var btn = document.getElementById('play-btn');
    btn.innerHTML = '<span class="icon">\u23F8</span> <span class="btn-label">Pause</span>';
    btn.classList.add('active');
    playbackStartTime = performance.now();
    playbackTimeOffset = getTimeAtScroll();
    activeNoteIds.clear();
    if (soundEnabled && !samplesLoaded && !samplesLoading) {
        initAudio();
    }
    animatePlayback();
}

function stopPlayback() {
    isPlaying = false;
    var btn = document.getElementById('play-btn');
    btn.innerHTML = '<span class="icon">\u25B6</span> <span class="btn-label">Play</span>';
    btn.classList.remove('active');
    if (animationFrameId) {
        cancelAnimationFrame(animationFrameId);
        animationFrameId = null;
    }
    stopAllNotes();
}

function animatePlayback() {
    if (!isPlaying) return;

    var elapsed = (performance.now() - playbackStartTime) / 1000 * playbackSpeed;
    var currentSongTime = playbackTimeOffset + elapsed;

    scrollToTime(currentSongTime);

    if (currentSongTime >= totalDuration + 2) {
        if (loopEnabled) {
            playbackTimeOffset = firstNoteTime - 1;
            playbackStartTime = performance.now();
            activeNoteIds.clear();
        } else {
            stopPlayback();
            return;
        }
    }

    var container = document.getElementById('piano-roll-container');
    if (container.scrollTop <= 0 && !loopEnabled) {
        stopPlayback();
        return;
    }

    updatePlayhead();
    updateTimeIndicator();
    updateProgressBar();
    highlightActiveKeys();
    highlightPlayingNotes();
    updateMinimapViewport();

    if (soundEnabled && samplesLoaded) {
        var ct = getTimeAtScroll();
        notesData.notes.forEach(function(note) {
            if (note.hand === 'right_hand' && !showRightHand) return;
            if (note.hand === 'left_hand' && !showLeftHand) return;
            var noteEnd = note.start_time + note.duration;
            if (ct >= note.start_time && ct <= noteEnd) {
                if (!activeNoteIds.has(note.id)) {
                    activeNoteIds.add(note.id);
                    var remainingDur = noteEnd - ct;
                    playNote(note.key_index, remainingDur);
                }
            } else if (ct > noteEnd) {
                activeNoteIds.delete(note.id);
            }
        });
    }

    animationFrameId = requestAnimationFrame(animatePlayback);
}

// ================================================================
//  Speed & loop
// ================================================================

function setSpeed(speed) {
    var oldSpeed = playbackSpeed;
    playbackSpeed = speed;
    document.getElementById('speed-select').value = String(speed);
    if (isPlaying) {
        var elapsed = (performance.now() - playbackStartTime) / 1000 * oldSpeed;
        playbackTimeOffset += elapsed;
        playbackStartTime = performance.now();
    }
}

function toggleLoop() {
    loopEnabled = !loopEnabled;
    document.getElementById('loop-btn').classList.toggle('active', loopEnabled);
}

// ================================================================
//  Manual scroll with auto-pause/resume
// ================================================================

function onUserScrollIntent() {
    if (isPlaying && !userIsScrolling) {
        userIsScrolling = true;
        wasPlayingBeforeScroll = true;
        stopPlayback();
    }
    if (userIsScrolling) {
        clearTimeout(scrollResumeTimer);
        scrollResumeTimer = setTimeout(function() {
            userIsScrolling = false;
            if (wasPlayingBeforeScroll) {
                wasPlayingBeforeScroll = false;
                startPlayback();
            }
        }, 200);
    }
}
