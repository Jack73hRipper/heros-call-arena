# Publish Workflow — Agent Reference

> **Audience:** AI agents and developers who need to push a game update.  
> Read this before running any publish steps.

---

## Overview

Hero's Call Arena ships via **GitHub Releases** (game zip) and **GitHub Pages** (update manifest).  
The launcher checks `latest.json` on GitHub Pages → downloads the zip from Releases → installs.

---

## Key Files

| File | Purpose |
|------|---------|
| `client/package.json` | Source of truth for game version (`"version": "X.Y.Z"`) |
| `docs/pending-changes.md` | **Staging doc** — log every change here as you work |
| `docs/changelog.md` | Permanent detailed changelog (append new entries at the top) |
| `build/patch-notes.md` | Short user-facing release notes (embedded in `latest.json` for the launcher) |
| `scripts/bump-version.bat` | Bumps version in `client/package.json` |
| `scripts/write-patch-notes.bat` | Creates a patch notes template at `build/patch-notes.md` |
| `scripts/build-game-package.bat` | Builds server + client + Electron → `build/arena-v{VERSION}.zip` |
| `scripts/publish-update.bat` | Full pipeline: build → hash → manifest → upload → deploy |
| `scripts/publish-config.json` | Hosting config (currently set to `"github"`) |
| `build/gh-pages-temp/` | Local clone of the `gh-pages` branch (has `latest.json` and `server-url.json`) |

---

## Step-by-Step Publish Process

### 1. Log your changes in `docs/pending-changes.md`

As you make code changes, write what you did under `## Unreleased` in the appropriate category (Bug Fixes, New Features, Balance Changes). Be specific — include file names and what was changed. This is how the next agent (or you) will know what goes into the release.

### 2. Bump the version

```
scripts\bump-version.bat patch
```

Options: `patch` (0.1.2 → 0.1.3), `minor` (0.1.2 → 0.2.0), `major` (0.1.2 → 1.0.0)

**Verify no BOM was introduced:**
```powershell
$b = [System.IO.File]::ReadAllBytes("client\package.json")
if ($b[0] -eq 239 -and $b[1] -eq 187 -and $b[2] -eq 191) { "BOM (bad)" } else { "No BOM (good)" }
```

### 3. Write patch notes

Create/overwrite `build/patch-notes.md` with concise, user-facing release notes. Use this format:

```markdown
## v{VERSION} — Short Title

**Bug Fixes**
- Fixed X not working in Y

**New Features**
- Added Z
```

Transfer relevant entries from `docs/pending-changes.md` into these notes.

### 4. Update the changelog

Add a new section at the top of `docs/changelog.md` (below the header, above older entries) with detailed technical notes about what changed and why.

### 5. Commit and push to main

```
git add -A
git commit -m "v{VERSION}: Brief description"
git push origin main
```

> **Note:** `git push` in PowerShell 5.1 may show exit code 1 even on success because it writes progress to stderr. Check the output for `main -> main` to confirm it worked.

### 6. Build the game package

```
scripts\build-game-package.bat
```

This runs PyInstaller → Vite → electron-builder → zip. Output: `build/arena-v{VERSION}.zip`

Requires:
- Python venv at `.venv/` with deps installed
- Node.js with `npm install` done in `client/`
- PyInstaller installed in the venv

### 7. Create GitHub Release

```
gh release create v{VERSION} "build/arena-v{VERSION}.zip" --title "v{VERSION} — Title" --notes-file "build/patch-notes.md"
```

### 8. Deploy `latest.json` to GitHub Pages

Generate and push the manifest so the launcher detects the update:

```powershell
# Get zip metadata
$zip = "build\arena-v{VERSION}.zip"
$size = (Get-Item $zip).Length
$hash = (Get-FileHash $zip -Algorithm SHA256).Hash.ToLower()

# Read patch notes
$notes = (Get-Content "build\patch-notes.md" -Raw).TrimEnd()

# Build JSON
$obj = @{
  version = '{VERSION}'
  releaseDate = (Get-Date -Format 'yyyy-MM-dd')
  downloadUrl = 'https://github.com/Jack73hRipper/heros-call-arena/releases/download/v{VERSION}/arena-v{VERSION}.zip'
  downloadSize = [long]$size
  sha256 = $hash
  patchNotes = $notes
  minLauncherVersion = '1.0.0'
}

# Write BOM-free JSON
$json = $obj | ConvertTo-Json -Depth 10
[System.IO.File]::WriteAllText(
  "build\gh-pages-temp\latest.json",
  $json,
  [System.Text.UTF8Encoding]::new($false)
)

# Push to gh-pages
Push-Location "build\gh-pages-temp"
git add latest.json
git commit -m "Update latest.json for v{VERSION}"
git push origin gh-pages
Pop-Location
```

### 9. Clean up `docs/pending-changes.md`

After a successful publish, clear the entries under `## Unreleased` (replace with `*(none yet)*`) so the next round of work starts fresh. Keep any `Known Issues` that are still unresolved.

---

## Known Gotchas

| Issue | Details |
|-------|---------|
| **BOM in package.json** | PowerShell 5.1's `Set-Content -Encoding UTF8` writes a BOM. Vite's PostCSS config loader chokes on it. Always use `[System.IO.File]::WriteAllText()` with `UTF8Encoding($false)`. The bump script is already fixed. |
| **`publish-update.bat` step 5 upload** | Has a batch syntax error (`"not was unexpected"`). Workaround: run steps 7–8 above manually instead of relying on the script's upload step. Building (steps 1–4 of the script) works fine. |
| **`git push` exit code 1** | PowerShell treats stderr output as an error. Git push writes progress to stderr. Look for `main -> main` in the output to confirm success. |
| **`wmic` date field** | The `publish-update.bat` script uses `wmic` which can produce garbled dates. When generating `latest.json` manually, use `Get-Date -Format 'yyyy-MM-dd'` instead. |
| **`gh-pages-temp` directory** | If it doesn't exist, the `publish-update.bat` creates it as a fresh git init. But if it already exists (from a previous publish), just `cd` into it and commit/push — don't reinitialize. |

---

## Quick Reference — Minimal Publish

If everything is committed and you just need to push a release:

```
scripts\bump-version.bat patch
# Write build/patch-notes.md
# Update docs/changelog.md
git add -A && git commit -m "v{VERSION}: description" && git push origin main
scripts\build-game-package.bat
gh release create v{VERSION} "build/arena-v{VERSION}.zip" --title "v{VERSION} — Title" --notes-file "build/patch-notes.md"
# Generate + push latest.json (see step 8 above)
```
