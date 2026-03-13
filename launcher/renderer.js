/**
 * Renderer Script — Hero's Call Arena Launcher
 *
 * Handles UI events and state display.
 * Phase L4: full download → verify → install → launch flow with progress bar.
 * Phase L6: launcher self-update notification.
 * Phase L7: settings panel, loading spinner, smooth progress, repair, keyboard shortcuts.
 */

document.addEventListener('DOMContentLoaded', () => {
  const btnPlay       = document.getElementById('btnPlay');
  const btnMinimize   = document.getElementById('btnMinimize');
  const btnClose      = document.getElementById('btnClose');
  const btnSettings   = document.getElementById('btnSettings');
  const statusMessage = document.getElementById('statusMessage');
  const versionLabel  = document.getElementById('versionLabel');
  const patchNotes    = document.getElementById('patchNotes');
  const playLabel     = btnPlay.querySelector('.play-btn__label');
  const progressWrapper = document.getElementById('progressWrapper');
  const progressFill    = document.getElementById('progressFill');
  const progressText    = document.getElementById('progressText');
  const statusSpinner   = document.getElementById('statusSpinner');

  /* Phase L6: launcher self-update elements */
  const launcherUpdateBar  = document.getElementById('launcherUpdateBar');
  const launcherUpdateText = document.getElementById('launcherUpdateText');
  const btnLauncherRestart = document.getElementById('btnLauncherRestart');

  /* Phase L7: settings panel elements */
  const settingsOverlay     = document.getElementById('settingsOverlay');
  const btnSettingsClose    = document.getElementById('btnSettingsClose');
  const btnSettingsSave     = document.getElementById('btnSettingsSave');
  const btnBrowseDir        = document.getElementById('btnBrowseDir');
  const btnRepair           = document.getElementById('btnRepair');
  const settingsInstallDir  = document.getElementById('settingsInstallDir');
  const settingsAutoCheck   = document.getElementById('settingsAutoCheck');
  const settingsMinimizeToTray = document.getElementById('settingsMinimizeToTray');

  /** Current launcher state — drives button text and behaviour. */
  let currentState = 'checking'; // checking | not-installed | up-to-date | update-available | check-failed | downloading | verifying | installing | launching | playing
  let latestManifest = null;
  let installedResult = null;

  /** Smooth progress bar animation state */
  let displayedProgress = 0;
  let targetProgress = 0;
  let progressAnimFrame = null;

  /* ──────────────────────────────────────────────
     Window chrome
     ────────────────────────────────────────────── */
  btnMinimize.addEventListener('click', () => window.launcherAPI.minimizeWindow());
  btnClose.addEventListener('click', () => window.launcherAPI.closeWindow());

  /* ──────────────────────────────────────────────
     UI state machine
     ────────────────────────────────────────────── */
  function applyState(state, result) {
    currentState = state;

    // Remove all state classes, then add the active one
    btnPlay.classList.remove('play-btn--install', 'play-btn--update', 'play-btn--offline', 'play-btn--disabled');

    // Hide progress bar by default; shown during download and install
    if (state !== 'downloading' && state !== 'installing') {
      progressWrapper.style.display = 'none';
    }

    // Show/hide spinner — visible only during 'checking'
    statusSpinner.style.display = state === 'checking' ? 'inline-flex' : 'none';

    switch (state) {
      case 'checking':
        playLabel.textContent = 'CHECKING...';
        btnPlay.classList.add('play-btn--disabled');
        btnPlay.disabled = true;
        statusMessage.textContent = 'Checking for updates…';
        break;

      case 'not-installed':
        playLabel.textContent = 'INSTALL';
        btnPlay.classList.add('play-btn--install');
        btnPlay.disabled = false;
        statusMessage.textContent = 'Game not installed';
        if (result && result.latest) {
          versionLabel.textContent = `Latest: v${result.latest.version}`;
        }
        break;

      case 'up-to-date':
        playLabel.textContent = 'PLAY';
        btnPlay.disabled = false;
        statusMessage.textContent = `Ready — v${result.installed.version}`;
        versionLabel.textContent = `v${result.installed.version}`;
        break;

      case 'update-available':
        playLabel.textContent = 'UPDATE';
        btnPlay.classList.add('play-btn--update');
        btnPlay.disabled = false;
        statusMessage.textContent = `Update available — v${result.latest.version}`;
        versionLabel.textContent = `v${result.installed.version} → v${result.latest.version}`;
        break;

      case 'check-failed':
        btnPlay.disabled = false;
        if (result && result.installed) {
          playLabel.textContent = 'PLAY';
          btnPlay.classList.add('play-btn--offline');
          statusMessage.textContent = 'Offline — play last installed version';
          versionLabel.textContent = `v${result.installed.version} (offline)`;
        } else {
          playLabel.textContent = 'RETRY';
          btnPlay.classList.add('play-btn--offline');
          statusMessage.textContent = 'Could not check for updates';
          versionLabel.textContent = 'No connection';
        }
        break;

      case 'downloading':
        playLabel.textContent = 'CANCEL';
        btnPlay.disabled = false;
        btnPlay.classList.remove('play-btn--disabled');
        statusMessage.textContent = 'Downloading…';
        progressWrapper.style.display = 'flex';
        break;

      case 'verifying':
        playLabel.textContent = 'VERIFYING...';
        btnPlay.classList.add('play-btn--disabled');
        btnPlay.disabled = true;
        statusMessage.textContent = 'Verifying download…';
        break;

      case 'installing':
        playLabel.textContent = 'INSTALLING...';
        btnPlay.classList.add('play-btn--disabled');
        btnPlay.disabled = true;
        statusMessage.textContent = 'Installing…';
        progressWrapper.style.display = 'flex';
        displayedProgress = 0;
        targetProgress = 0;
        progressFill.style.width = '0%';
        progressText.textContent = '0%';
        break;

      case 'launching':
        playLabel.textContent = 'LAUNCHING...';
        btnPlay.classList.add('play-btn--disabled');
        btnPlay.disabled = true;
        statusMessage.textContent = 'Launching game…';
        break;

      case 'playing':
        playLabel.textContent = 'PLAYING';
        btnPlay.classList.add('play-btn--disabled');
        btnPlay.disabled = true;
        statusMessage.textContent = 'Game is running';
        break;

      case 'error':
        playLabel.textContent = 'RETRY';
        btnPlay.disabled = false;
        statusMessage.textContent = result && result.error ? result.error : 'An error occurred';
        statusMessage.classList.add('status__message--error');
        // Clear error class after a moment for next state change
        setTimeout(() => statusMessage.classList.remove('status__message--error'), 0);
        break;
    }
  }

  /* ──────────────────────────────────────────────
     Patch notes rendering (simple markdown subset)
     ────────────────────────────────────────────── */
  function renderPatchNotes(markdown) {
    if (!markdown) return;

    // Sanitise: strip any HTML tags that might be in the markdown
    const sanitised = markdown.replace(/<[^>]*>/g, '');

    const lines = sanitised.split('\n');
    let html = '<div class="patchnotes__entry">';
    let inList = false;

    for (const line of lines) {
      const trimmed = line.trim();

      if (trimmed.startsWith('### ')) {
        if (inList) { html += '</ul>'; inList = false; }
        html += `<h3>${escapeHtml(trimmed.slice(4))}</h3>`;
      } else if (trimmed.startsWith('## ')) {
        if (inList) { html += '</ul>'; inList = false; }
        html += `<h3>${escapeHtml(trimmed.slice(3))}</h3>`;
      } else if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
        if (!inList) { html += '<ul>'; inList = true; }
        html += `<li>${escapeHtml(trimmed.slice(2))}</li>`;
      } else if (trimmed === '') {
        if (inList) { html += '</ul>'; inList = false; }
      }
    }
    if (inList) html += '</ul>';
    html += '</div>';

    patchNotes.innerHTML = html;
  }

  /** Escape HTML entities for safe insertion */
  function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  /* ──────────────────────────────────────────────
     Version check on launch
     ────────────────────────────────────────────── */
  async function runVersionCheck() {
    applyState('checking', null);

    const result = await window.launcherAPI.checkForUpdates();
    latestManifest = result.latest;
    installedResult = result.installed;

    applyState(result.state, result);

    // Show patch notes from remote manifest
    if (result.latest && result.latest.patchNotes) {
      renderPatchNotes(result.latest.patchNotes);
    }
  }

  // Kick off on startup
  runVersionCheck();

  /* ──────────────────────────────────────────────
     Smooth progress bar animation (Phase L7)
     ────────────────────────────────────────────── */
  function animateProgress() {
    const diff = targetProgress - displayedProgress;
    if (Math.abs(diff) < 0.1) {
      displayedProgress = targetProgress;
    } else {
      // Ease toward target — smooth interpolation
      displayedProgress += diff * 0.15;
    }

    progressFill.style.width = displayedProgress + '%';

    if (Math.abs(targetProgress - displayedProgress) > 0.1) {
      progressAnimFrame = requestAnimationFrame(animateProgress);
    } else {
      progressAnimFrame = null;
    }
  }

  function setProgress(pct) {
    targetProgress = pct;
    if (!progressAnimFrame) {
      progressAnimFrame = requestAnimationFrame(animateProgress);
    }
  }

  /* ──────────────────────────────────────────────
     Download progress callback (from main process)
     ────────────────────────────────────────────── */
  window.launcherAPI.onDownloadProgress(({ received, total }) => {
    if (total > 0) {
      const pct = Math.min(100, (received / total) * 100);
      setProgress(pct);
      const receivedMB = (received / 1_000_000).toFixed(0);
      const totalMB = (total / 1_000_000).toFixed(0);
      progressText.textContent = `${Math.round(pct)}% — ${receivedMB} / ${totalMB} MB`;
    } else {
      const receivedMB = (received / 1_000_000).toFixed(1);
      progressText.textContent = `${receivedMB} MB`;
    }
  });

  /* ──────────────────────────────────────────────
     Extract progress callback (from main process)
     ────────────────────────────────────────────── */
  window.launcherAPI.onExtractProgress(({ extracted, total }) => {
    if (total > 0) {
      const pct = Math.min(100, (extracted / total) * 100);
      setProgress(pct);
      progressText.textContent = `${Math.round(pct)}% — ${extracted} / ${total} files`;
    }
  });

  /* ──────────────────────────────────────────────
     Install status callback (from main process)
     ────────────────────────────────────────────── */
  window.launcherAPI.onInstallStatus((status) => {
    switch (status) {
      case 'downloading':
        applyState('downloading', null);
        break;
      case 'verifying':
        applyState('verifying', null);
        break;
      case 'installing':
        applyState('installing', null);
        break;
      case 'ready':
        // Install complete — refresh state
        runVersionCheck();
        break;
      case 'error':
        // Error will be shown via the start-install return value
        break;
    }
  });

  /* ──────────────────────────────────────────────
     Game exited callback (from main process)
     ────────────────────────────────────────────── */
  window.launcherAPI.onGameExited((_code) => {
    // Re-check for updates when the game closes
    runVersionCheck();
  });

  /* ──────────────────────────────────────────────
     Install / Update flow
     ────────────────────────────────────────────── */
  async function startInstallOrUpdate() {
    if (!latestManifest) return;

    applyState('downloading', null);
    displayedProgress = 0;
    targetProgress = 0;
    progressFill.style.width = '0%';
    progressText.textContent = '0%';

    const result = await window.launcherAPI.startInstall(latestManifest);

    if (result.success) {
      // State will be updated via onInstallStatus → 'ready' → runVersionCheck
      return;
    }

    // Error
    applyState('error', { error: result.error });
  }

  /* ──────────────────────────────────────────────
     Launch game
     ────────────────────────────────────────────── */
  async function launchGame() {
    applyState('launching', null);
    const result = await window.launcherAPI.launchGame();

    if (result.success) {
      applyState('playing', null);
    } else {
      applyState('error', { error: result.error });
    }
  }

  /* ──────────────────────────────────────────────
     Play / Install / Update button
     ────────────────────────────────────────────── */
  btnPlay.addEventListener('click', () => {
    switch (currentState) {
      case 'not-installed':
      case 'update-available':
        startInstallOrUpdate();
        break;

      case 'up-to-date':
        launchGame();
        break;

      case 'downloading':
        // Cancel download
        window.launcherAPI.cancelInstall();
        runVersionCheck();
        break;

      case 'check-failed':
        // If we have a local install, allow play. Otherwise retry.
        if (installedResult) {
          launchGame();
        } else {
          runVersionCheck();
        }
        break;

      case 'error':
        // Retry — re-check for updates
        runVersionCheck();
        break;
    }
  });

  /* ── Settings panel (Phase L7) ── */
  let settingsOpen = false;

  async function openSettings() {
    const s = await window.launcherAPI.getSettings();
    settingsInstallDir.value = s.installDir || '';
    settingsAutoCheck.checked = s.autoCheckUpdates !== false;
    settingsMinimizeToTray.checked = !!s.minimizeToTray;
    settingsOverlay.style.display = 'flex';
    settingsOpen = true;
  }

  function closeSettings() {
    settingsOverlay.style.display = 'none';
    settingsOpen = false;
  }

  btnSettings.addEventListener('click', openSettings);
  btnSettingsClose.addEventListener('click', closeSettings);

  settingsOverlay.addEventListener('click', (e) => {
    if (e.target === settingsOverlay) closeSettings();
  });

  btnBrowseDir.addEventListener('click', async () => {
    const dir = await window.launcherAPI.browseInstallDir();
    if (dir) settingsInstallDir.value = dir;
  });

  btnSettingsSave.addEventListener('click', async () => {
    await window.launcherAPI.saveSettings({
      installDir: settingsInstallDir.value,
      autoCheckUpdates: settingsAutoCheck.checked,
      minimizeToTray: settingsMinimizeToTray.checked,
    });
    closeSettings();
  });

  btnRepair.addEventListener('click', async () => {
    if (!confirm('This will delete the installed game and re-download it. Continue?')) return;
    btnRepair.disabled = true;
    btnRepair.textContent = 'Repairing…';
    const result = await window.launcherAPI.repairGame();
    btnRepair.disabled = false;
    btnRepair.textContent = 'Repair Game';
    closeSettings();
    if (result.success) {
      runVersionCheck(); // Will show "not-installed" → user clicks Install
    } else {
      statusMessage.textContent = result.error || 'Repair failed';
    }
  });

  /* ── Keyboard shortcuts (Phase L7) ── */
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      if (settingsOpen) {
        closeSettings();
      } else {
        window.launcherAPI.closeWindow();
      }
      return;
    }
    if (e.key === 'Enter' && !btnPlay.disabled && !settingsOpen) {
      btnPlay.click();
    }
  });

  /* ──────────────────────────────────────────────
     Phase L6: Launcher self-update handling
     ────────────────────────────────────────────── */
  window.launcherAPI.onLauncherUpdateStatus((data) => {
    switch (data.status) {
      case 'checking':
        // Silent — no UI needed while checking
        break;

      case 'available':
        launcherUpdateBar.style.display = 'flex';
        launcherUpdateText.textContent = `Launcher update v${data.version} downloading…`;
        btnLauncherRestart.style.display = 'none';
        break;

      case 'downloading':
        launcherUpdateBar.style.display = 'flex';
        launcherUpdateText.textContent = `Downloading launcher update… ${data.percent}%`;
        btnLauncherRestart.style.display = 'none';
        break;

      case 'downloaded':
        launcherUpdateBar.style.display = 'flex';
        launcherUpdateText.textContent = `Launcher v${data.version} ready — restart to apply`;
        btnLauncherRestart.style.display = 'inline-block';
        break;

      case 'up-to-date':
      case 'dev-mode':
        launcherUpdateBar.style.display = 'none';
        break;

      case 'error':
        // Non-fatal — hide the bar, don't bother the user
        launcherUpdateBar.style.display = 'none';
        break;
    }
  });

  btnLauncherRestart.addEventListener('click', () => {
    window.launcherAPI.installLauncherUpdate();
  });
});
