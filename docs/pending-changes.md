# Pending Changes

> **Purpose:** AI agents and developers log changes here as they work.  
> When it's time to publish, clear this file after transferring entries  
> into `build/patch-notes.md` and `docs/changelog.md`.

---

## Unreleased

### Bug Fixes

*(none yet)*

### New Features

- **Launcher: Install progress bar** - Added a file-by-file progress bar during the extraction/install phase. Previously the launcher appeared frozen during installation with no visual feedback. Now shows a smooth animated progress bar with percentage and file count (e.g. "45% - 230 / 512 files"). Uses the same progress bar already shown during downloads. Changed files: `launcher/lib/extractor.js`, `launcher/main.js`, `launcher/preload.js`, `launcher/renderer.js`.

### Balance Changes

*(none yet)*

### Known Issues

- Lobby chat between connected players not yet working — investigation in progress.
