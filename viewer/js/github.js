// ================================================================
//  GitHub OAuth, cloud storage, homepage state
// ================================================================

function loadGitHubConfig() {
    try {
        var saved = localStorage.getItem('makemusic_github');
        if (saved) {
            ghConfig = JSON.parse(saved);
        }
    } catch(e) {}
}

function saveGitHubConfig() {
    try {
        if (ghConfig) {
            localStorage.setItem('makemusic_github', JSON.stringify(ghConfig));
        } else {
            localStorage.removeItem('makemusic_github');
        }
    } catch(e) {}
}

function showGitHub() {
    document.getElementById('github-modal').classList.add('visible');
    updateGitHubUI();
    if (ghConfig && ghConfig.repo) refreshGitHubFiles();
}

function hideGitHub(e) {
    if (e && e.target.id !== 'github-modal') return;
    document.getElementById('github-modal').classList.remove('visible');
}

function updateGitHubUI() {
    var statusBar = document.getElementById('gh-status-bar');
    var statusIcon = document.getElementById('gh-status-icon');
    var statusText = document.getElementById('gh-status-text');
    var connectForm = document.getElementById('gh-connect-form');
    var connectedSection = document.getElementById('gh-connected-section');

    if (ghConfig && ghConfig.token && ghConfig.repo) {
        statusBar.className = 'gh-status connected';
        statusIcon.textContent = '\uD83D\uDFE2';
        statusText.textContent = 'Connected as ' + (ghConfig.username || 'user') + ' \u2192 ' + ghConfig.repo + '/' + ghConfig.path;
        connectForm.style.display = 'none';
        connectedSection.style.display = '';
        var saveInput = document.getElementById('gh-save-filename');
        if (!saveInput.value) {
            var title = (notesData && notesData.metadata && notesData.metadata.title) || 'untitled';
            saveInput.value = title.replace(/[^a-z0-9_-]/gi, '_') + '.json';
        }
    } else {
        statusBar.className = 'gh-status disconnected';
        statusIcon.textContent = '\u26AA';
        statusText.textContent = 'Not connected';
        connectForm.style.display = '';
        connectedSection.style.display = 'none';
    }
}

function signInWithGitHub() {
    var redirectUri = window.location.origin + window.location.pathname;
    var authUrl = 'https://github.com/login/oauth/authorize?client_id=' +
        encodeURIComponent(OAUTH_CLIENT_ID) +
        '&scope=repo' +
        '&redirect_uri=' + encodeURIComponent(redirectUri);
    window.location.href = authUrl;
}

async function handleOAuthCallback(code) {
    try {
        var res = await fetch(OAUTH_PROXY, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ client_id: OAUTH_CLIENT_ID, code: code })
        });
        if (!res.ok) {
            var errData = await res.json().catch(function() { return {}; });
            console.error('OAuth token exchange failed:', errData);
            alert('GitHub sign-in failed. Please try again.');
            return;
        }
        var data = await res.json();
        if (!data.access_token) {
            console.error('No access_token in response:', data);
            alert('GitHub sign-in failed: no access token received.');
            return;
        }

        var userRes = await fetch('https://api.github.com/user', {
            headers: { 'Authorization': 'Bearer ' + data.access_token, 'Accept': 'application/vnd.github.v3+json' }
        });
        var userData = userRes.ok ? await userRes.json() : { login: 'user' };

        var prevConfig = null;
        try {
            var saved = localStorage.getItem('makemusic_github');
            if (saved) prevConfig = JSON.parse(saved);
        } catch(e) {}

        ghConfig = {
            token: data.access_token,
            repo: (prevConfig && prevConfig.repo) || '',
            path: (prevConfig && prevConfig.path) || 'songs',
            username: userData.login
        };
        saveGitHubConfig();
        showHomepage();
    } catch(err) {
        console.error('OAuth callback error:', err);
        alert('GitHub sign-in failed: ' + err.message);
    }
}

// ================================================================
//  Homepage state management
// ================================================================

function showHomepage() {
    var homepage = document.getElementById('homepage');
    var signedOut = document.getElementById('hp-signed-out');
    var repoSetup = document.getElementById('hp-repo-setup');
    var songList = document.getElementById('hp-song-list');
    var spinner = document.getElementById('loading-spinner');
    var loadingText = document.getElementById('loading-text');

    spinner.style.display = 'none';
    loadingText.style.display = 'none';
    homepage.style.display = '';

    if (ghConfig && ghConfig.token && ghConfig.repo) {
        signedOut.style.display = 'none';
        repoSetup.style.display = 'none';
        songList.style.display = '';
        document.getElementById('hp-user-display').textContent = ghConfig.username;
        document.getElementById('hp-repo-badge').textContent = ghConfig.repo.split('/')[1] || ghConfig.repo;
        loadHomepageSongs();
    } else if (ghConfig && ghConfig.token) {
        signedOut.style.display = 'none';
        repoSetup.style.display = '';
        songList.style.display = 'none';
        document.getElementById('hp-username').textContent = ghConfig.username;
        document.getElementById('hp-default-repo-name').textContent = ghConfig.username + '/makemusic_db';
        document.getElementById('hp-repo-status').textContent = '';
        document.getElementById('hp-create-repo-btn').style.display = 'none';
        document.getElementById('hp-continue-btn').style.display = '';
    } else {
        signedOut.style.display = '';
        repoSetup.style.display = 'none';
        songList.style.display = 'none';
    }
}

function updateRepoChoice() {
    var choice = document.querySelector('input[name="hp-repo-choice"]:checked').value;
    var customInput = document.getElementById('hp-custom-repo-name');
    customInput.disabled = (choice !== 'custom');
    if (choice === 'custom') customInput.focus();
    document.getElementById('hp-repo-status').textContent = '';
    document.getElementById('hp-create-repo-btn').style.display = 'none';
    document.getElementById('hp-continue-btn').style.display = '';
}

function getSelectedRepoName() {
    var choice = document.querySelector('input[name="hp-repo-choice"]:checked').value;
    if (choice === 'default') {
        return 'makemusic_db';
    }
    return document.getElementById('hp-custom-repo-name').value.trim();
}

function getSelectedRepoFull() {
    var name = getSelectedRepoName();
    if (!name) return '';
    return ghConfig.username + '/' + name;
}

async function continueWithRepo() {
    if (!ghConfig || !ghConfig.token) return;
    var repoName = getSelectedRepoName();
    if (!repoName) {
        document.getElementById('hp-repo-status').innerHTML = '<span style="color:#e94560;">Please enter a repository name.</span>';
        return;
    }

    var fullRepo = ghConfig.username + '/' + repoName;
    var statusEl = document.getElementById('hp-repo-status');
    statusEl.innerHTML = '<span style="color:var(--text-secondary);">Checking repository\u2026</span>';
    document.getElementById('hp-continue-btn').disabled = true;

    try {
        var res = await fetch('https://api.github.com/repos/' + fullRepo, {
            headers: { 'Authorization': 'Bearer ' + ghConfig.token, 'Accept': 'application/vnd.github.v3+json' }
        });

        if (res.ok) {
            ghConfig.repo = fullRepo;
            ghConfig.path = 'songs';
            saveGitHubConfig();
            showHomepage();
        } else if (res.status === 404) {
            statusEl.innerHTML = '<span style="color:#e9a045;">Repository "' + fullRepo + '" does not exist yet.</span>';
            document.getElementById('hp-create-repo-btn').style.display = '';
            document.getElementById('hp-continue-btn').style.display = 'none';
        } else {
            statusEl.innerHTML = '<span style="color:#e94560;">Failed to check repository (HTTP ' + res.status + ').</span>';
        }
    } catch(err) {
        statusEl.innerHTML = '<span style="color:#e94560;">Error: ' + err.message + '</span>';
    } finally {
        document.getElementById('hp-continue-btn').disabled = false;
    }
}

async function createSelectedRepo() {
    if (!ghConfig || !ghConfig.token) return;
    var repoName = getSelectedRepoName();
    if (!repoName) return;

    var statusEl = document.getElementById('hp-repo-status');
    var createBtn = document.getElementById('hp-create-repo-btn');
    createBtn.disabled = true;
    statusEl.innerHTML = '<span style="color:var(--text-secondary);">Creating repository\u2026</span>';

    try {
        var res = await fetch('https://api.github.com/user/repos', {
            method: 'POST',
            headers: {
                'Authorization': 'Bearer ' + ghConfig.token,
                'Accept': 'application/vnd.github.v3+json',
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                name: repoName,
                description: 'MakeMusic song storage',
                private: true,
                auto_init: true
            })
        });

        if (res.ok || res.status === 201) {
            var fullRepo = ghConfig.username + '/' + repoName;
            ghConfig.repo = fullRepo;
            ghConfig.path = 'songs';
            saveGitHubConfig();
            statusEl.innerHTML = '<span style="color:#48BF91;">Repository created!</span>';
            setTimeout(function() { showHomepage(); }, 500);
        } else {
            var errData = await res.json().catch(function() { return {}; });
            statusEl.innerHTML = '<span style="color:#e94560;">Failed to create: ' + (errData.message || 'Unknown error') + '</span>';
        }
    } catch(err) {
        statusEl.innerHTML = '<span style="color:#e94560;">Error: ' + err.message + '</span>';
    } finally {
        createBtn.disabled = false;
    }
}

async function loadHomepageSongs() {
    if (!ghConfig || !ghConfig.repo) return;
    var songsEl = document.getElementById('hp-songs');
    songsEl.innerHTML = '<div class="hp-loading">Loading songs\u2026</div>';

    try {
        var res = await fetch('https://api.github.com/repos/' + ghConfig.repo + '/contents/' + ghConfig.path, {
            headers: { 'Authorization': 'Bearer ' + ghConfig.token, 'Accept': 'application/vnd.github.v3+json' }
        });

        if (res.status === 404) {
            songsEl.innerHTML = '<div class="hp-empty">No songs yet. Create your first one!</div>';
            return;
        }
        if (!res.ok) {
            songsEl.innerHTML = '<div class="hp-empty">Failed to load songs.</div>';
            return;
        }

        var files = await res.json();
        if (!Array.isArray(files)) {
            songsEl.innerHTML = '<div class="hp-empty">Unexpected response.</div>';
            return;
        }

        var jsonFiles = files.filter(function(f) { return f.name.endsWith('.json'); });
        if (jsonFiles.length === 0) {
            songsEl.innerHTML = '<div class="hp-empty">No songs yet. Create your first one!</div>';
            return;
        }

        songsEl.innerHTML = '';
        jsonFiles.forEach(function(file) {
            var item = document.createElement('div');
            item.className = 'hp-song-item';
            var displayName = file.name.replace(/\.json$/, '').replace(/_/g, ' ');
            item.innerHTML = '<span>\uD83C\uDFB5</span><span class="hp-song-name">' + displayName + '</span><span class="hp-song-size">' + (Math.round(file.size / 1024) || '<1') + ' KB</span>';
            item.addEventListener('click', function() { loadGitHubFile(file.path, file.name, { homepage: true }); });
            songsEl.appendChild(item);
        });
    } catch(err) {
        songsEl.innerHTML = '<div class="hp-empty">Error: ' + err.message + '</div>';
    }
}

/**
 * Load a JSON file from GitHub.
 * opts.homepage: if true, disables homepage song items during load
 * opts.closeModal: if true, closes the github modal after load
 */
async function loadGitHubFile(filePath, fileName, opts) {
    if (!ghConfig) return;
    opts = opts || {};

    // Visual feedback for homepage items
    var items = null;
    if (opts.homepage) {
        var songsEl = document.getElementById('hp-songs');
        items = songsEl.querySelectorAll('.hp-song-item');
        items.forEach(function(it) { it.style.pointerEvents = 'none'; it.style.opacity = '0.5'; });
    }

    try {
        var res = await fetch('https://api.github.com/repos/' + ghConfig.repo + '/contents/' + filePath, {
            headers: { 'Authorization': 'Bearer ' + ghConfig.token, 'Accept': 'application/vnd.github.v3+json' }
        });

        if (!res.ok) {
            alert('Failed to load: ' + fileName);
            if (items) items.forEach(function(it) { it.style.pointerEvents = ''; it.style.opacity = ''; });
            return;
        }

        var fileData = await res.json();
        var decoded = decodeURIComponent(escape(atob(fileData.content.replace(/\n/g, ''))));
        var data = JSON.parse(decoded);

        if (!data.notes || !Array.isArray(data.notes)) {
            alert('Invalid JSON: missing "notes" array.');
            if (items) items.forEach(function(it) { it.style.pointerEvents = ''; it.style.opacity = ''; });
            return;
        }

        loadNotesData(data);
        document.getElementById('gh-save-filename').value = fileName;

        if (opts.homepage) {
            updateGitHubUI();
        }
        if (opts.closeModal) {
            document.getElementById('github-modal').classList.remove('visible');
        }
    } catch(err) {
        alert('Failed to load: ' + err.message);
        if (items) items.forEach(function(it) { it.style.pointerEvents = ''; it.style.opacity = ''; });
    }
}

// Keep backward-compatible aliases for HTML onclick handlers and tests
function loadHomepageSong(filePath, fileName) {
    return loadGitHubFile(filePath, fileName, { homepage: true });
}

function loadFromGitHub(filePath, fileName) {
    return loadGitHubFile(filePath, fileName, { closeModal: true });
}

function disconnectGitHub() {
    ghConfig = null;
    saveGitHubConfig();
    updateGitHubUI();
}

function disconnectAndReload() {
    ghConfig = null;
    saveGitHubConfig();
    showHomepage();
}

async function saveToGitHub() {
    if (!ghConfig || !notesData) return;
    var filename = document.getElementById('gh-save-filename').value.trim();
    if (!filename) {
        alert('Please enter a filename.');
        return;
    }
    if (!filename.endsWith('.json')) filename += '.json';

    var msgEl = document.getElementById('gh-save-message');
    msgEl.style.display = '';
    msgEl.textContent = 'Saving...';
    msgEl.style.color = 'var(--text-secondary)';

    var filePath = ghConfig.path + '/' + filename;
    var content = btoa(unescape(encodeURIComponent(JSON.stringify(notesData, null, 2))));

    try {
        var existingRes = await fetch('https://api.github.com/repos/' + ghConfig.repo + '/contents/' + filePath, {
            headers: { 'Authorization': 'Bearer ' + ghConfig.token, 'Accept': 'application/vnd.github.v3+json' }
        });
        var sha = null;
        if (existingRes.ok) {
            var existing = await existingRes.json();
            sha = existing.sha;
        }

        var body = {
            message: 'Update ' + filename + ' via MakeMusic',
            content: content
        };
        if (sha) body.sha = sha;

        var saveRes = await fetch('https://api.github.com/repos/' + ghConfig.repo + '/contents/' + filePath, {
            method: 'PUT',
            headers: {
                'Authorization': 'Bearer ' + ghConfig.token,
                'Accept': 'application/vnd.github.v3+json',
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(body)
        });

        if (saveRes.ok) {
            msgEl.textContent = '\u2705 Saved successfully!';
            msgEl.style.color = '#48BF91';
            refreshGitHubFiles();
            setTimeout(function() { msgEl.style.display = 'none'; }, 3000);
        } else {
            var err = await saveRes.json();
            msgEl.textContent = '\u274C Save failed: ' + (err.message || 'Unknown error');
            msgEl.style.color = '#e94560';
        }
    } catch(err) {
        msgEl.textContent = '\u274C Save failed: ' + err.message;
        msgEl.style.color = '#e94560';
    }
}

async function refreshGitHubFiles() {
    if (!ghConfig) return;
    var listEl = document.getElementById('gh-file-list');
    listEl.innerHTML = '<div class="gh-message">Loading...</div>';

    try {
        var res = await fetch('https://api.github.com/repos/' + ghConfig.repo + '/contents/' + ghConfig.path, {
            headers: { 'Authorization': 'Bearer ' + ghConfig.token, 'Accept': 'application/vnd.github.v3+json' }
        });

        if (res.status === 404) {
            listEl.innerHTML = '<div class="gh-message">No files yet. Save your first file to create the folder.</div>';
            return;
        }
        if (!res.ok) {
            listEl.innerHTML = '<div class="gh-message">Failed to load files.</div>';
            return;
        }

        var files = await res.json();
        if (!Array.isArray(files)) {
            listEl.innerHTML = '<div class="gh-message">Unexpected response from GitHub.</div>';
            return;
        }

        var jsonFiles = files.filter(function(f) { return f.name.endsWith('.json'); });
        if (jsonFiles.length === 0) {
            listEl.innerHTML = '<div class="gh-message">No JSON files found in ' + ghConfig.path + '/</div>';
            return;
        }

        listEl.innerHTML = '';
        jsonFiles.forEach(function(file) {
            var item = document.createElement('div');
            item.className = 'gh-file-item';
            item.innerHTML = '<span>\uD83D\uDCC4</span><span class="gh-file-name">' + file.name + '</span><span class="gh-file-date">' + (Math.round(file.size / 1024) || '<1') + ' KB</span>';
            item.addEventListener('click', function() { loadFromGitHub(file.path, file.name); });
            listEl.appendChild(item);
        });
    } catch(err) {
        listEl.innerHTML = '<div class="gh-message">Error: ' + err.message + '</div>';
    }
}
