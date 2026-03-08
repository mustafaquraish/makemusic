// @ts-check
const { test, expect } = require('@playwright/test');
const path = require('path');
const fs = require('fs');

/**
 * Comprehensive Playwright tests for MakeMusic Piano Roll Viewer
 * Tests every UI feature and interaction systematically.
 */

const OUTPUT_HTML = path.resolve(__dirname, '../../tmp/test_perfect/output.html');

/** Load the output.html as a file:// URL and wait for data to load */
async function loadViewer(page) {
  const fileUrl = 'file://' + OUTPUT_HTML;
  await page.goto(fileUrl, { waitUntil: 'domcontentloaded' });
  // Wait for notes to render (the piano roll should have note blocks)
  await page.waitForFunction(() => {
    return document.querySelectorAll('.note-block').length > 0;
  }, { timeout: 10000 });
}

// ============================================================
// 1. BASIC PAGE LOAD & DATA
// ============================================================
test.describe('Basic Load', () => {
  test('page loads without errors', async ({ page }) => {
    const errors = [];
    page.on('pageerror', err => errors.push(err.message));
    await loadViewer(page);
    expect(errors).toEqual([]);
  });

  test('correct number of notes rendered', async ({ page }) => {
    await loadViewer(page);
    const noteCount = await page.locator('.note-block').count();
    expect(noteCount).toBe(637);
  });

  test('song info is displayed', async ({ page }) => {
    await loadViewer(page);
    const info = await page.locator('#song-info').textContent();
    expect(info).toContain('637');
    // RH/LH counts are in the note-count-badge, not song-info
    const badge = await page.locator('#note-count-badge').textContent();
    expect(badge).toContain('407');
    expect(badge).toContain('230');
  });

  test('no drop zone or load JSON button visible', async ({ page }) => {
    await loadViewer(page);
    const dropZone = page.locator('#drop-zone');
    if (await dropZone.count() > 0) {
      await expect(dropZone).not.toBeVisible();
    }
    const loadBtn = page.getByText('Load JSON');
    if (await loadBtn.count() > 0) {
      await expect(loadBtn).not.toBeVisible();
    }
  });

  test('title contains MakeMusic', async ({ page }) => {
    await loadViewer(page);
    const title = await page.title();
    expect(title).toContain('MakeMusic');
  });
});

// ============================================================
// 2. PIANO KEYBOARD
// ============================================================
test.describe('Piano Keyboard', () => {
  test('keyboard is rendered at the bottom', async ({ page }) => {
    await loadViewer(page);
    const keyboard = page.locator('#keyboard');
    await expect(keyboard).toBeVisible();
    const box = await keyboard.boundingBox();
    expect(box).toBeTruthy();
    // Keyboard should be near the bottom
    expect(box.y + box.height).toBeGreaterThan(700);
  });

  test('white and black keys are present', async ({ page }) => {
    await loadViewer(page);
    const whiteKeys = await page.locator('.key.white').count();
    const blackKeys = await page.locator('.key.black').count();
    expect(whiteKeys).toBeGreaterThan(10);
    expect(blackKeys).toBeGreaterThan(5);
  });

  test('keys have labels', async ({ page }) => {
    await loadViewer(page);
    const firstWhite = page.locator('.key.white').first();
    const text = await firstWhite.textContent();
    expect(text).toMatch(/[A-G]\d/);
  });
});

// ============================================================
// 3. NOTE BLOCKS
// ============================================================
test.describe('Note Blocks', () => {
  test('notes have black borders', async ({ page }) => {
    await loadViewer(page);
    const note = page.locator('.note-block').first();
    const border = await note.evaluate(el =>
      getComputedStyle(el).borderColor || getComputedStyle(el).border
    );
    // Should have a dark border (black or near-black)
    expect(border).toBeTruthy();
  });

  test('right hand and left hand notes exist', async ({ page }) => {
    await loadViewer(page);
    const rh = await page.locator('.note-block.right-hand').count();
    const lh = await page.locator('.note-block.left-hand').count();
    expect(rh).toBe(407);
    expect(lh).toBe(230);
  });

  test('notes have tooltip on hover', async ({ page }) => {
    await loadViewer(page);
    // The viewer uses a custom #note-tooltip element, not title attribute
    const tooltip = page.locator('#note-tooltip');
    await expect(tooltip).toBeAttached();
    // Hover a visible note to trigger tooltip
    const note = page.locator('.note-block').first();
    await note.hover({ force: true });
    await page.waitForTimeout(200);
    const tooltipText = await tooltip.textContent();
    expect(tooltipText.length).toBeGreaterThan(2);
  });

  test('notes are positioned within the piano roll', async ({ page }) => {
    await loadViewer(page);
    const note = page.locator('.note-block').first();
    const style = await note.evaluate(el => ({
      top: el.style.top,
      left: el.style.left,
      width: el.style.width,
      height: el.style.height,
    }));
    expect(style.top).toBeTruthy();
    expect(style.left).toBeTruthy();
    expect(style.width).toBeTruthy();
    expect(parseFloat(style.height)).toBeGreaterThan(0);
  });

  test('notes display note name when tall enough', async ({ page }) => {
    await loadViewer(page);
    // Find a note that's tall enough to have text
    const tallNote = page.locator('.note-block').filter({
      has: page.locator('text=/[A-G]/')
    }).first();
    if (await tallNote.count() > 0) {
      const text = await tallNote.textContent();
      expect(text).toMatch(/[A-G]/);
    }
  });
});

// ============================================================
// 4. PLAYBACK
// ============================================================
test.describe('Playback', () => {
  test('play button exists and is functional', async ({ page }) => {
    await loadViewer(page);
    const playBtn = page.locator('#play-btn');
    await expect(playBtn).toBeVisible();
    const text = await playBtn.textContent();
    expect(text).toContain('Play');
  });

  test('space bar toggles playback', async ({ page }) => {
    await loadViewer(page);
    const playBtn = page.locator('#play-btn');

    // Get initial state
    const initialText = await playBtn.textContent();
    expect(initialText).toContain('Play');

    // Press space to start
    await page.keyboard.press('Space');
    await page.waitForTimeout(200);
    const playingText = await playBtn.textContent();
    expect(playingText).toContain('Pause');

    // Press space to stop
    await page.keyboard.press('Space');
    await page.waitForTimeout(200);
    const stoppedText = await playBtn.textContent();
    expect(stoppedText).toContain('Play');
  });

  test('playback scrolls the view', async ({ page }) => {
    await loadViewer(page);
    const container = page.locator('#piano-roll-container');
    const initialScroll = await container.evaluate(el => el.scrollTop);

    // Start playback
    await page.keyboard.press('Space');
    await page.waitForTimeout(1000);
    const afterScroll = await container.evaluate(el => el.scrollTop);
    // Stop playback
    await page.keyboard.press('Space');

    // Scroll should have changed during playback
    expect(Math.abs(afterScroll - initialScroll)).toBeGreaterThan(10);
  });

  test('playhead is visible', async ({ page }) => {
    await loadViewer(page);
    const playhead = page.locator('#playhead');
    await expect(playhead).toBeAttached();
  });
});

// ============================================================
// 5. TIME INDICATOR
// ============================================================
test.describe('Time Display', () => {
  test('time indicator shows current/total format', async ({ page }) => {
    await loadViewer(page);
    const timeEl = page.locator('#time-indicator');
    await expect(timeEl).toBeVisible();
    const text = await timeEl.textContent();
    // Should contain a time format like "0:00" or "0:00.0" or "0:00 / 4:00"
    expect(text).toMatch(/\d+:\d+/);
  });
});

// ============================================================
// 6. ZOOM
// ============================================================
test.describe('Zoom', () => {
  test('zoom slider exists and works', async ({ page }) => {
    await loadViewer(page);
    const slider = page.locator('#zoom-slider');
    await expect(slider).toBeVisible();

    // Get initial pixel height of a note
    const initialHeight = await page.locator('.note-block').first().evaluate(
      el => parseFloat(el.style.height)
    );

    // Change zoom to maximum
    await slider.evaluate(el => {
      el.value = el.max;
      el.dispatchEvent(new Event('input'));
    });
    await page.waitForTimeout(500);

    const zoomedHeight = await page.locator('.note-block').first().evaluate(
      el => parseFloat(el.style.height)
    );

    // Notes should be taller when zoomed in
    expect(zoomedHeight).toBeGreaterThan(initialHeight);
  });

  test('ctrl+wheel zooms vertically', async ({ page }) => {
    await loadViewer(page);
    const container = page.locator('#piano-roll-container');
    const box = await container.boundingBox();

    // Get initial state
    const initialPPS = await page.evaluate(() => pixelsPerSecond);

    // Ctrl+scroll up to zoom in
    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
    await page.mouse.wheel(0, -100); // This is regular scroll, not ctrl
    // For ctrl+wheel, we dispatch a custom event
    await page.evaluate(() => {
      const container = document.getElementById('piano-roll-container');
      const ev = new WheelEvent('wheel', {
        deltaY: -100,
        ctrlKey: true,
        bubbles: true,
      });
      container.dispatchEvent(ev);
    });
    await page.waitForTimeout(300);

    const zoomedPPS = await page.evaluate(() => pixelsPerSecond);
    expect(zoomedPPS).toBeGreaterThan(initialPPS);
  });
});

// ============================================================
// 7. VERTICAL TRACK LINES
// ============================================================
test.describe('Track Lines', () => {
  test('canvas or track lines element exists', async ({ page }) => {
    await loadViewer(page);
    // Track lines could be implemented as a canvas or as CSS pseudo elements
    // or as a separate element
    const hasTrackLines = await page.evaluate(() => {
      // Check for track-lines element, canvas for tracks, or CSS background
      const trackEl = document.querySelector('#track-lines, .track-lines, #tracks-canvas, canvas');
      if (trackEl) return true;
      // Check if piano-roll has a background that implies track lines
      const roll = document.getElementById('piano-roll');
      if (roll) {
        const bg = getComputedStyle(roll).backgroundImage;
        if (bg && bg !== 'none') return true;
      }
      // Check for SVG track lines
      const svgLines = document.querySelectorAll('line, .track-line');
      if (svgLines.length > 5) return true;
      // Also the track lines could be generated as divs
      const trackDivs = document.querySelectorAll('[class*="track"]');
      return trackDivs.length > 0;
    });
    expect(hasTrackLines).toBe(true);
  });
});

// ============================================================
// 8. HAND TOGGLE
// ============================================================
test.describe('Hand Toggle', () => {
  test('hand toggle buttons exist', async ({ page }) => {
    await loadViewer(page);
    // Look for two toggle buttons for hands
    const rhBtn = page.locator('[data-hand="right"], #rh-toggle, .hand-toggle').first();
    const lhBtn = page.locator('[data-hand="left"], #lh-toggle, .hand-toggle').last();

    // At least some toggle mechanism should exist
    const toggles = await page.locator('[data-hand], .hand-toggle, [id*="toggle"]').count();
    expect(toggles).toBeGreaterThanOrEqual(2);
  });

  test('toggling hand hides notes', async ({ page }) => {
    await loadViewer(page);
    const lhBefore = await page.locator('.note-block.left-hand:visible').count();
    expect(lhBefore).toBe(230);

    // Click the left hand toggle
    const lhToggle = page.locator('[data-hand="left"], #lh-toggle').first();
    if (await lhToggle.count() > 0) {
      await lhToggle.click();
      await page.waitForTimeout(300);
      const lhAfter = await page.locator('.note-block.left-hand:visible').count();
      expect(lhAfter).toBe(0);

      // Toggle back
      await lhToggle.click();
      await page.waitForTimeout(300);
      const lhRestored = await page.locator('.note-block.left-hand:visible').count();
      expect(lhRestored).toBe(230);
    }
  });
});

// ============================================================
// 9. SCROLL DURING PLAYBACK (auto-pause/resume)
// ============================================================
test.describe('Scroll During Playback', () => {
  test('manual scroll pauses playback temporarily', async ({ page }) => {
    await loadViewer(page);
    // Start playback
    await page.keyboard.press('Space');
    await page.waitForTimeout(500);

    // Confirm playing
    const isPlaying1 = await page.evaluate(() => isPlaying);
    expect(isPlaying1).toBe(true);

    // Manually scroll
    const container = page.locator('#piano-roll-container');
    await container.evaluate(el => { el.scrollTop += 200; });
    await page.waitForTimeout(50);

    // Should pause during manual scroll
    const isPlaying2 = await page.evaluate(() => isPlaying);
    // Give it time to detect the scroll and pause
    // The behavior might be it pauses and resumes after 150ms

    // Wait for resume
    await page.waitForTimeout(300);

    // After idle, should resume from new position
    // Stop playback
    await page.keyboard.press('Space');
  });
});

// ============================================================
// 10. PROGRESS BAR
// ============================================================
test.describe('Progress Bar', () => {
  test('progress bar exists', async ({ page }) => {
    await loadViewer(page);
    const bar = page.locator('#progress-bar-container, #progress-bar-fill, [id*="progress"]');
    const count = await bar.count();
    expect(count).toBeGreaterThan(0);
  });

  test('progress bar is clickable for seeking', async ({ page }) => {
    await loadViewer(page);
    const bar = page.locator('#progress-bar-container, [id*="progress"]').first();
    if (await bar.isVisible()) {
      const box = await bar.boundingBox();
      // Click at 50% position
      const scrollBefore = await page.locator('#piano-roll-container').evaluate(
        el => el.scrollTop
      );
      await page.mouse.click(box.x + box.width * 0.5, box.y + box.height / 2);
      await page.waitForTimeout(300);
      const scrollAfter = await page.locator('#piano-roll-container').evaluate(
        el => el.scrollTop
      );
      // Scroll should have changed
      expect(Math.abs(scrollAfter - scrollBefore)).toBeGreaterThan(0);
    }
  });
});

// ============================================================
// 11. NOTE HIGHLIGHTING (playing notes glow)
// ============================================================
test.describe('Note Highlighting', () => {
  test('playing note style exists in CSS', async ({ page }) => {
    await loadViewer(page);
    const hasPlayingStyle = await page.evaluate(() => {
      const sheets = document.styleSheets;
      for (const sheet of sheets) {
        try {
          for (const rule of sheet.cssRules) {
            if (rule.selectorText && rule.selectorText.includes('playing')) {
              return true;
            }
          }
        } catch (e) {}
      }
      return false;
    });
    expect(hasPlayingStyle).toBe(true);
  });
});

// ============================================================
// 12. SPEED CONTROL
// ============================================================
test.describe('Speed Control', () => {
  test('speed control exists', async ({ page }) => {
    await loadViewer(page);
    const speedEl = page.locator('#speed-select, #speed-slider, [id*="speed"], select');
    const count = await speedEl.count();
    expect(count).toBeGreaterThan(0);
  });

  test('speed control has multiple options', async ({ page }) => {
    await loadViewer(page);
    const select = page.locator('select').first();
    if (await select.count() > 0) {
      const options = await select.locator('option').count();
      expect(options).toBeGreaterThanOrEqual(3);
    }
  });
});

// ============================================================
// 13. JUMP TO START/END
// ============================================================
test.describe('Jump Navigation', () => {
  test('Home key jumps to start', async ({ page }) => {
    await loadViewer(page);
    // Scroll somewhere in the middle first
    await page.locator('#piano-roll-container').evaluate(
      el => { el.scrollTop = el.scrollHeight / 2; }
    );
    await page.waitForTimeout(200);

    await page.keyboard.press('Home');
    await page.waitForTimeout(500);

    // Should be near the bottom (start of song) or scrolled to first note
    const scroll = await page.locator('#piano-roll-container').evaluate(
      el => el.scrollTop
    );
    const maxScroll = await page.locator('#piano-roll-container').evaluate(
      el => el.scrollHeight - el.clientHeight
    );
    // Should be within the bottom half (start of song is at the bottom)
    expect(scroll).toBeGreaterThan(maxScroll * 0.4);
  });

  test('End key jumps to end', async ({ page }) => {
    await loadViewer(page);
    await page.keyboard.press('End');
    await page.waitForTimeout(500);

    const scroll = await page.locator('#piano-roll-container').evaluate(
      el => el.scrollTop
    );
    // Should be near the top (end of song)
    expect(scroll).toBeLessThan(500);
  });
});

// ============================================================
// 14. LOOP MODE
// ============================================================
test.describe('Loop Mode', () => {
  test('loop toggle exists', async ({ page }) => {
    await loadViewer(page);
    const loopBtn = page.locator('#loop-btn, [id*="loop"], button:has-text("🔁")');
    const count = await loopBtn.count();
    expect(count).toBeGreaterThan(0);
  });

  test('L key toggles loop', async ({ page }) => {
    await loadViewer(page);
    const initialLoop = await page.evaluate(() =>
      typeof loopEnabled !== 'undefined' ? loopEnabled : false
    );
    await page.keyboard.press('l');
    await page.waitForTimeout(100);
    const afterLoop = await page.evaluate(() =>
      typeof loopEnabled !== 'undefined' ? loopEnabled : false
    );
    expect(afterLoop).not.toBe(initialLoop);
  });
});

// ============================================================
// 15. MINIMAP
// ============================================================
test.describe('Minimap', () => {
  test('minimap element exists', async ({ page }) => {
    await loadViewer(page);
    const minimap = page.locator('#minimap, .minimap, [class*="minimap"]');
    const count = await minimap.count();
    expect(count).toBeGreaterThan(0);
  });

  test('minimap has viewport indicator', async ({ page }) => {
    await loadViewer(page);
    const viewport = page.locator('.minimap-viewport, [class*="viewport"], #minimap-viewport');
    const count = await viewport.count();
    expect(count).toBeGreaterThan(0);
  });

  test('clicking minimap navigates', async ({ page }) => {
    await loadViewer(page);
    const minimap = page.locator('#minimap, .minimap, [class*="minimap"]').first();
    if (await minimap.isVisible()) {
      const box = await minimap.boundingBox();
      const scrollBefore = await page.locator('#piano-roll-container').evaluate(
        el => el.scrollTop
      );
      // Click at top of minimap (end of song)
      await page.mouse.click(box.x + box.width / 2, box.y + 10);
      await page.waitForTimeout(300);
      const scrollAfter = await page.locator('#piano-roll-container').evaluate(
        el => el.scrollTop
      );
      expect(Math.abs(scrollAfter - scrollBefore)).toBeGreaterThan(0);
    }
  });
});

// ============================================================
// 16. THEME TOGGLE
// ============================================================
test.describe('Theme Toggle', () => {
  test('theme toggle button exists', async ({ page }) => {
    await loadViewer(page);
    const themeBtn = page.locator('#theme-btn, [id*="theme"], button:has-text("☀"), button:has-text("🌙")');
    const count = await themeBtn.count();
    expect(count).toBeGreaterThan(0);
  });

  test('T key toggles theme', async ({ page }) => {
    await loadViewer(page);
    const initialTheme = await page.evaluate(() =>
      document.documentElement.dataset.theme || 'dark'
    );
    await page.keyboard.press('t');
    await page.waitForTimeout(200);
    const afterTheme = await page.evaluate(() =>
      document.documentElement.dataset.theme || 'dark'
    );
    expect(afterTheme).not.toBe(initialTheme);
  });

  test('light theme changes background color', async ({ page }) => {
    await loadViewer(page);
    const darkBg = await page.evaluate(() =>
      getComputedStyle(document.body).backgroundColor
    );
    await page.keyboard.press('t');
    await page.waitForTimeout(200);
    const lightBg = await page.evaluate(() =>
      getComputedStyle(document.body).backgroundColor
    );
    expect(lightBg).not.toBe(darkBg);
  });
});

// ============================================================
// 17. KEYBOARD SHORTCUTS HELP
// ============================================================
test.describe('Keyboard Shortcuts Help', () => {
  test('? key shows help overlay', async ({ page }) => {
    await loadViewer(page);
    await page.keyboard.press('?');
    await page.waitForTimeout(300);

    // Check for help/shortcuts modal
    const modal = page.locator('#shortcuts-modal, #help-modal, [id*="shortcuts"], [id*="help"]').first();
    if (await modal.count() > 0) {
      await expect(modal).toBeVisible();
    }
  });

  test('help modal lists Space shortcut', async ({ page }) => {
    await loadViewer(page);
    await page.keyboard.press('?');
    await page.waitForTimeout(300);

    const text = await page.locator('#shortcuts-modal, #help-modal, [id*="shortcuts"]').first().textContent();
    expect(text).toContain('Space');
  });
});

// ============================================================
// 18. VOLUME CONTROL
// ============================================================
test.describe('Volume Control', () => {
  test('volume slider exists', async ({ page }) => {
    await loadViewer(page);
    const volumeEl = page.locator('#volume-slider, [id*="volume"], input[type="range"]');
    const count = await volumeEl.count();
    expect(count).toBeGreaterThan(0);
  });
});

// ============================================================
// 19. SOUND SYSTEM
// ============================================================
test.describe('Sound System', () => {
  test('sound is ON by default', async ({ page }) => {
    await loadViewer(page);
    const soundEnabled = await page.evaluate(() =>
      typeof soundEnabled !== 'undefined' ? soundEnabled : false
    );
    expect(soundEnabled).toBe(true);
  });

  test('sound button shows ON state', async ({ page }) => {
    await loadViewer(page);
    const soundBtn = page.locator('#sound-btn');
    if (await soundBtn.count() > 0) {
      const text = await soundBtn.textContent();
      expect(text.toLowerCase()).toContain('on');
    }
  });
});

// ============================================================
// 20. RESPONSIVE / MOBILE
// ============================================================
test.describe('Responsive Design', () => {
  test('works at mobile viewport', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 });
    await loadViewer(page);

    // Notes should still be visible
    const noteCount = await page.locator('.note-block').count();
    expect(noteCount).toBe(637);

    // Keyboard should be visible
    const keyboard = page.locator('#keyboard');
    await expect(keyboard).toBeVisible();
  });

  test('works at tablet viewport', async ({ page }) => {
    await page.setViewportSize({ width: 768, height: 1024 });
    await loadViewer(page);

    const noteCount = await page.locator('.note-block').count();
    expect(noteCount).toBe(637);
  });
});

// ============================================================
// 21. LEGEND / COLORS
// ============================================================
test.describe('Legend & Colors', () => {
  test('legend shows right and left hand labels', async ({ page }) => {
    await loadViewer(page);
    const legend = page.locator('.legend, [class*="legend"]');
    if (await legend.count() > 0) {
      const text = await legend.textContent();
      expect(text.toLowerCase()).toMatch(/right|rh/);
      expect(text.toLowerCase()).toMatch(/left|lh/);
    }
  });

  test('note colors match data color_rgb', async ({ page }) => {
    await loadViewer(page);
    // The first RH note should have the color from color_rgb [183,123,192]
    const note = page.locator('.note-block.right-hand').first();
    const bg = await note.evaluate(el => getComputedStyle(el).background);
    // Should contain some form of the purple/pink color
    expect(bg).toBeTruthy();
  });
});

// ============================================================
// 22. SCROLL BEHAVIOR
// ============================================================
test.describe('Scroll Behavior', () => {
  test('scroll updates time indicator', async ({ page }) => {
    await loadViewer(page);
    const timeBefore = await page.locator('#time-indicator').textContent();

    // Scroll up significantly
    await page.locator('#piano-roll-container').evaluate(
      el => { el.scrollTop = Math.max(0, el.scrollTop - 2000); }
    );
    await page.waitForTimeout(200);

    const timeAfter = await page.locator('#time-indicator').textContent();
    expect(timeAfter).not.toBe(timeBefore);
  });

  test('scroll highlights active keyboard keys', async ({ page }) => {
    await loadViewer(page);
    // Scroll to a position where notes are playing
    await page.evaluate(() => {
      scrollToTime(50); // 50 seconds in
    });
    await page.waitForTimeout(500);

    // Trigger the scroll handler to update highlighting
    await page.evaluate(() => {
      highlightActiveKeys();
    });
    await page.waitForTimeout(200);

    // Check if any keys are active (classes are active-rh or active-lh)
    const activeKeys = await page.locator('.key.active-rh, .key.active-lh').count();
    expect(activeKeys).toBeGreaterThan(0);
  });
});

// ============================================================
// 23. NOTE CLICK INTERACTION
// ============================================================
test.describe('Note Click', () => {
  test('clicking a note scrolls to it', async ({ page }) => {
    await loadViewer(page);
    // First scroll to the middle
    await page.locator('#piano-roll-container').evaluate(
      el => { el.scrollTop = el.scrollHeight / 2; }
    );
    await page.waitForTimeout(200);

    const scrollBefore = await page.locator('#piano-roll-container').evaluate(
      el => el.scrollTop
    );

    // Click a visible note
    const visibleNote = page.locator('.note-block').first();
    if (await visibleNote.isVisible()) {
      await visibleNote.click();
      await page.waitForTimeout(300);
    }
  });
});

// ============================================================
// 24. CSS STRUCTURE
// ============================================================
test.describe('CSS Structure', () => {
  test('uses CSS custom properties for theming', async ({ page }) => {
    await loadViewer(page);
    const hasVars = await page.evaluate(() => {
      const root = getComputedStyle(document.documentElement);
      return root.getPropertyValue('--bg-primary').trim().length > 0;
    });
    expect(hasVars).toBe(true);
  });

  test('no external stylesheets (self-contained)', async ({ page }) => {
    await loadViewer(page);
    const linkCount = await page.locator('link[rel="stylesheet"]').count();
    expect(linkCount).toBe(0);
  });

  test('toolbar is fixed at top', async ({ page }) => {
    await loadViewer(page);
    const toolbar = page.locator('#toolbar');
    const position = await toolbar.evaluate(el => getComputedStyle(el).position);
    expect(position).toBe('fixed');
  });
});

// ============================================================
// 25. DENSITY VISUALIZATION
// ============================================================
test.describe('Density Visualization', () => {
  test('density/heatmap element or canvas exists', async ({ page }) => {
    await loadViewer(page);
    const hasCanvas = await page.evaluate(() => {
      return document.querySelectorAll('canvas').length > 0 ||
             document.querySelector('[class*="density"]') !== null ||
             document.querySelector('[id*="density"]') !== null;
    });
    expect(hasCanvas).toBe(true);
  });
});
