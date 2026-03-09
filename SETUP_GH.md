# GitHub Cloud Storage Setup Guide

MakeMusic can save and load your music files from a GitHub repository, giving you free cloud storage with version history.

## Overview

MakeMusic uses **GitHub OAuth** to securely sign you in and access your repositories. No tokens to copy — just click "Sign in with GitHub", authorize the app, and choose a repo. Your files are stored as regular JSON files in your GitHub repo, so you always own your data.

## Step-by-Step Setup

### 1. Create a GitHub Repository

1. Go to [github.com/new](https://github.com/new)
2. Name it something like `my-music` or `makemusic-files`
3. Set it to **Private** (recommended) or Public
4. Check "Add a README file" (optional, helps initialize the repo)
5. Click **Create repository**

### 2. Connect MakeMusic to GitHub

1. Open MakeMusic in your browser
2. Click the **☁️ Cloud** button in the toolbar
3. Click **"Sign in with GitHub"**
4. GitHub will ask you to authorize MakeMusic — click **Authorize**
5. You'll be redirected back to MakeMusic, now signed in
6. Enter your repo in `owner/repo` format (e.g., `johndoe/my-music`)
7. Optionally change the folder path (default: `makemusic`)
8. Click **Connect Repo**

### 3. Using Cloud Storage

Once connected:
- **Save**: Enter a filename and click Save. The file will be created (or updated) in your GitHub repo
- **Load**: Click "Refresh Files" to see all your saved files, then click one to load it
- **Auto-save filename**: When you load a file, the save filename is automatically set to match, so subsequent saves update the same file

## How It Works

- MakeMusic uses GitHub's standard OAuth flow to authenticate you securely
- A lightweight proxy exchanges the OAuth code for an access token (your credentials never touch MakeMusic's servers)
- Files are stored as JSON in your GitHub repo under the folder path you specified (default: `makemusic/`)
- Each save creates a new commit in your repo, giving you full version history
- The connection (OAuth token + repo info) is saved in your browser's localStorage

## File Structure in Your Repo

```
my-music/
├── README.md
└── makemusic/          ← your configured folder
    ├── river_flows.json
    ├── moonlight.json
    └── my_composition.json
```

## Security Notes

- Authentication uses GitHub's standard OAuth flow — you sign in directly on github.com
- The OAuth token is stored in your browser's `localStorage` and only sent to `api.github.com`
- A Cloudflare Worker proxy handles the token exchange (it never stores your token)
- If you use a shared computer, click **Disconnect** when done to remove the token from localStorage
- You can revoke MakeMusic's access at any time from [github.com/settings/applications](https://github.com/settings/applications)

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Sign-in page doesn't load | Check your internet connection and try again |
| "Cannot access repository" | Check the repo name format (`owner/repo`) and that your GitHub account has access to the repo |
| "Save failed" | The OAuth token may have expired — click Disconnect and sign in again |
| Files not showing | Click "Refresh Files" — files only appear after the first save creates the folder |

## FAQ

**Q: Is this free?**
A: Yes! GitHub repos are free (public or private), and the API has generous rate limits (5000 requests/hour for authenticated users).

**Q: Can I use an existing repo?**
A: Yes! MakeMusic only reads/writes to the folder path you configure. It won't touch other files.

**Q: What happens if I disconnect?**
A: Your OAuth token is removed from localStorage. Files in your GitHub repo are NOT deleted. You can also revoke access from GitHub's settings.

**Q: Can I access my files from a different browser/device?**
A: Yes, just sign in with GitHub on the new device and connect to the same repo.

**Q: Do I need to create the folder in my repo first?**
A: No, the folder is automatically created when you save your first file.
