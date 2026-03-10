// ================================================================
//  Application initialization
// ================================================================

// Load saved settings and GitHub config
loadSettings();
loadGitHubConfig();

// Check URL params
var params = new URLSearchParams(window.location.search);
var oauthCode = params.get('code');
var jsonUrl = params.get('json');

// Handle GitHub OAuth callback
if (oauthCode) {
    window.history.replaceState({}, '', window.location.pathname);
    handleOAuthCallback(oauthCode);
} else if (jsonUrl) {
    document.getElementById('loading-spinner').style.display = '';
    document.getElementById('loading-text').textContent = 'Loading notes\u2026';
    document.getElementById('homepage').style.display = 'none';
    loadNotesFromURL(jsonUrl);
} else if (typeof EMBEDDED_NOTES_DATA !== 'undefined') {
    loadNotesData(EMBEDDED_NOTES_DATA);
} else {
    showHomepage();
}

// Homepage drop zone
var hpDropZone = document.getElementById('hp-drop-zone');
if (hpDropZone) {
    hpDropZone.addEventListener('click', function(e) {
        document.getElementById('file-input').click();
    });
    hpDropZone.addEventListener('dragover', function(e) {
        e.preventDefault();
        this.classList.add('drag-over');
    });
    hpDropZone.addEventListener('dragleave', function() {
        this.classList.remove('drag-over');
    });
    hpDropZone.addEventListener('drop', function(e) {
        e.preventDefault();
        this.classList.remove('drag-over');
        var file = e.dataTransfer.files[0];
        if (file && file.name.endsWith('.json')) {
            handleFileLoad(file);
        }
    });
}
