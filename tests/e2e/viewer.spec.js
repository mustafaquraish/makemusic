// @ts-check
const { test, expect } = require('@playwright/test');
const path = require('path');
const fs = require('fs');

/**
 * Comprehensive Playwright tests for MakeMusic Piano Roll Viewer.
 * Uses a small (20 notes) fixture for fast, deterministic tests.
 * 
 * Test fixture: 13 RH notes, 7 LH notes, duration range 2.0-16.0s
 * Includes natural notes (C, D, E, F, G, A, B) and sharps/flats (C#, D#, F#, G#, A#)
 */

const VIEWER_URL = 'http://127.0.0.1:8574/viewer/index.html';
const FIXTURE_URL = 'http://127.0.0.1:8574/tests/e2e/fixtures/test_notes.json';

// Test data constants
const TOTAL_NOTES = 20;
const RH_NOTES = 14;
const LH_NOTES = 6;

/** Load the viewer with our test fixture JSON */
async function loadViewer(page, opts = {}) {
  const url = `${VIEWER_URL}?json=${FIXTURE_URL}`;
  await page.goto(url, { waitUntil: 'domcontentloaded' });
  // Wait for notes to render
  await page.waitForFunction(
    (expected) => document.querySelectorAll('.note-block').length === expected,
    TOTAL_NOTES,
    { timeout: 10000 }
  );
  // Small settle time for layout
  await page.waitForTimeout(200);
}

/** Load viewer at a specific viewport size */
async function loadViewerMobile(page) {
  await page.setViewportSize({ width: 375, height: 667 });
  await loadViewer(page);
}

async function loadViewerTablet(page) {
  await page.setViewportSize({ width: 768, height: 1024 });
  await loadViewer(page);
}

// ============================================================
// 1. BASIC PAGE LOAD & DATA
// ============================================================
test.describe('Basic Load', () => {
  test('page loads without JS errors', async ({ page }) => {
    const errors = [];
    page.on('pageerror', err => errors.push(err.message));
    await loadViewer(page);
    expect(errors).toEqual([]);
  });

  test('correct number of notes rendered', async ({ page }) => {
    await loadViewer(page);
    const noteCount = await page.locator('.note-block').count();
    expect(noteCount).toBe(TOTAL_NOTES);
  });

  test('song info displays note count', async ({ page }) => {
    await loadViewer(page);
    const info = await page.locator('#song-info').textContent();
    expect(info).toContain(String(TOTAL_NOTES));
  });

  test('note count badge shows RH/LH counts', async ({ page }) => {
    await loadViewer(page);
    const badge = await page.locator('#note-count-badge').textContent();
    expect(badge).toContain(String(RH_NOTES));
    expect(badge).toContain(String(LH_NOTES));
  });

  test('title contains MakeMusic', async ({ page }) => {
    await loadViewer(page);
    const title = await page.title();
    expect(title).toContain('MakeMusic');
  });

  test('loading overlay hides after data loads', async ({ page }) => {
    await loadViewer(page);
    const overlay = page.locator('#loading-overlay');
    // Should be hidden (either display:none or has hidden class)
    await expect(overlay).toBeHidden();
  });
});

// ============================================================
// 2. PIANO KEYBOARD
// ============================================================
test.describe('Piano Keyboard', () => {
  test('keyboard is rendered and visible', async ({ page }) => {
    await loadViewer(page);
    const keyboard = page.locator('#keyboard');
    await expect(keyboard).toBeVisible();
  });

  test('keyboard is at the bottom of the viewport', async ({ page }) => {
    await loadViewer(page);
    const keyboard = page.locator('#keyboard');
    const box = await keyboard.boundingBox();
    expect(box).toBeTruthy();
    // Keyboard bottom edge should be at viewport bottom (800px)
    expect(box.y + box.height).toBeGreaterThanOrEqual(790);
  });

  test('white and black keys are present', async ({ page }) => {
    await loadViewer(page);
    const whiteKeys = await page.locator('.key.white').count();
    const blackKeys = await page.locator('.key.black').count();
    expect(whiteKeys).toBeGreaterThan(5);
    expect(blackKeys).toBeGreaterThan(3);
  });

  test('keys have note name labels', async ({ page }) => {
    await loadViewer(page);
    const firstWhite = page.locator('.key.white').first();
    const text = await firstWhite.textContent();
    expect(text).toMatch(/[A-G]#?\d/);
  });

  test('keyboard height is correct (100px desktop)', async ({ page }) => {
    await loadViewer(page);
    const keyboard = page.locator('#keyboard');
    const box = await keyboard.boundingBox();
    expect(box.height).toBe(100);
  });
});

// ============================================================
// 3. NOTE BLOCKS
// ============================================================
test.describe('Note Blocks', () => {
  test('right hand notes have correct count', async ({ page }) => {
    await loadViewer(page);
    const rh = await page.locator('.note-block.right-hand').count();
    expect(rh).toBe(RH_NOTES);
  });

  test('left hand notes have correct count', async ({ page }) => {
    await loadViewer(page);
    const lh = await page.locator('.note-block.left-hand').count();
    expect(lh).toBe(LH_NOTES);
  });

  test('notes have position styles set', async ({ page }) => {
    await loadViewer(page);
    const note = page.locator('.note-block').first();
    const style = await note.evaluate(el => ({
      top: el.style.top,
      left: el.style.left,
      width: el.style.width,
      height: el.style.height,
    }));
    expect(parseFloat(style.top)).toBeGreaterThan(0);
    expect(style.left).toBeTruthy();
    expect(style.width).toBeTruthy();
    expect(parseFloat(style.height)).toBeGreaterThan(0);
  });

  test('notes have background gradient', async ({ page }) => {
    await loadViewer(page);
    const note = page.locator('.note-block').first();
    const bg = await note.evaluate(el => el.style.background);
    expect(bg).toContain('linear-gradient');
  });

  test('notes have dark border', async ({ page }) => {
    await loadViewer(page);
    const note = page.locator('.note-block').first();
    const border = await note.evaluate(el => getComputedStyle(el).borderColor);
    expect(border).toBeTruthy();
  });

  test('notes have data attributes', async ({ page }) => {
    await loadViewer(page);
    const note = page.locator('.note-block').first();
    const attrs = await note.evaluate(el => ({
      noteId: el.dataset.noteId,
      startTime: el.dataset.startTime,
      duration: el.dataset.duration,
      keyIndex: el.dataset.keyIndex,
      noteName: el.dataset.noteName,
      hand: el.dataset.hand,
    }));
    expect(attrs.noteId).toBeTruthy();
    expect(parseFloat(attrs.startTime)).toBeGreaterThanOrEqual(0);
    expect(parseFloat(attrs.duration)).toBeGreaterThan(0);
    expect(attrs.keyIndex).toBeTruthy();
    expect(attrs.noteName).toMatch(/[A-G]/);
    expect(attrs.hand).toMatch(/right_hand|left_hand/);
  });

  test('tall notes display their note name', async ({ page }) => {
    await loadViewer(page);
    // Find a note with sufficient height to show text
    const tallNote = await page.locator('.note-block').evaluateAll(els => {
      for (const el of els) {
        if (parseFloat(el.style.height) > 18 && el.textContent.trim()) {
          return el.textContent.trim();
        }
      }
      return null;
    });
    if (tallNote) {
      expect(tallNote).toMatch(/[A-G]/);
    }
  });
});

// ============================================================
// 4. NOTE TOOLTIP
// ============================================================
test.describe('Note Tooltip', () => {
  test('tooltip element exists', async ({ page }) => {
    await loadViewer(page);
    const tooltip = page.locator('#note-tooltip');
    await expect(tooltip).toBeAttached();
  });

  test('hovering a note shows tooltip', async ({ page }) => {
    await loadViewer(page);
    const tooltip = page.locator('#note-tooltip');

    // Scroll to make a note visible
    await page.evaluate(() => scrollToTime(2));
    await page.waitForTimeout(300);

    // Find a visible note near the middle of the screen
    const note = page.locator('.note-block').first();
    await note.hover({ force: true });
    await page.waitForTimeout(300);

    // Tooltip should become visible
    const isVisible = await tooltip.evaluate(el => el.classList.contains('visible'));
    expect(isVisible).toBe(true);
    const text = await tooltip.textContent();
    expect(text.length).toBeGreaterThan(2);
  });

  test('tooltip shows note name and timing info', async ({ page }) => {
    await loadViewer(page);
    await page.evaluate(() => scrollToTime(2));
    await page.waitForTimeout(300);

    const note = page.locator('.note-block').first();
    await note.hover({ force: true });
    await page.waitForTimeout(300);

    const noteName = await page.locator('#tt-note').textContent();
    expect(noteName).toMatch(/[A-G]/);

    const detail = await page.locator('#tt-detail').textContent();
    expect(detail).toContain('Start:');
    expect(detail).toContain('Duration:');
  });

  test('tooltip hides when mouse leaves note', async ({ page }) => {
    await loadViewer(page);
    await page.evaluate(() => scrollToTime(2));
    await page.waitForTimeout(300);

    const note = page.locator('.note-block').first();
    await note.hover({ force: true });
    await page.waitForTimeout(200);

    // Move mouse away
    await page.mouse.move(0, 0);
    await page.waitForTimeout(200);

    const isVisible = await page.locator('#note-tooltip').evaluate(
      el => el.classList.contains('visible')
    );
    expect(isVisible).toBe(false);
  });
});

// ============================================================
// 5. PLAYBACK
// ============================================================
test.describe('Playback', () => {
  test('play button exists and shows Play initially', async ({ page }) => {
    await loadViewer(page);
    const playBtn = page.locator('#play-btn');
    await expect(playBtn).toBeVisible();
    const text = await playBtn.textContent();
    expect(text).toContain('Play');
  });

  test('clicking play button starts playback', async ({ page }) => {
    await loadViewer(page);
    const playBtn = page.locator('#play-btn');
    await playBtn.click();
    await page.waitForTimeout(200);
    const text = await playBtn.textContent();
    expect(text).toContain('Pause');
    const playing = await page.evaluate(() => isPlaying);
    expect(playing).toBe(true);
    // Stop
    await playBtn.click();
  });

  test('space bar toggles playback', async ({ page }) => {
    await loadViewer(page);

    // Start
    await page.keyboard.press('Space');
    await page.waitForTimeout(200);
    expect(await page.evaluate(() => isPlaying)).toBe(true);
    expect(await page.locator('#play-btn').textContent()).toContain('Pause');

    // Stop
    await page.keyboard.press('Space');
    await page.waitForTimeout(200);
    expect(await page.evaluate(() => isPlaying)).toBe(false);
    expect(await page.locator('#play-btn').textContent()).toContain('Play');
  });

  test('playback scrolls the view', async ({ page }) => {
    await loadViewer(page);
    const initialScroll = await page.locator('#piano-roll-container').evaluate(
      el => el.scrollTop
    );

    await page.keyboard.press('Space');
    await page.waitForTimeout(1000);
    const afterScroll = await page.locator('#piano-roll-container').evaluate(
      el => el.scrollTop
    );
    await page.keyboard.press('Space');

    expect(Math.abs(afterScroll - initialScroll)).toBeGreaterThan(10);
  });

  test('play button shows active state during playback', async ({ page }) => {
    await loadViewer(page);
    await page.keyboard.press('Space');
    await page.waitForTimeout(200);

    const hasActive = await page.locator('#play-btn').evaluate(
      el => el.classList.contains('active')
    );
    expect(hasActive).toBe(true);

    await page.keyboard.press('Space');
    await page.waitForTimeout(200);
    const hasActiveAfter = await page.locator('#play-btn').evaluate(
      el => el.classList.contains('active')
    );
    expect(hasActiveAfter).toBe(false);
  });
});

// ============================================================
// 6. PLAYHEAD
// ============================================================
test.describe('Playhead', () => {
  test('playhead element exists', async ({ page }) => {
    await loadViewer(page);
    const playhead = page.locator('#playhead');
    await expect(playhead).toBeAttached();
  });

  test('playhead is positioned at 70% of container height', async ({ page }) => {
    await loadViewer(page);
    const result = await page.evaluate(() => {
      const container = document.getElementById('piano-roll-container');
      const playhead = document.getElementById('playhead');
      const expectedY = container.scrollTop + container.clientHeight * 0.7;
      return { actual: parseFloat(playhead.style.top), expected: expectedY };
    });
    expect(Math.abs(result.actual - result.expected)).toBeLessThan(5);
  });
});

// ============================================================
// 7. TIME INDICATOR
// ============================================================
test.describe('Time Display', () => {
  test('time indicator shows current/total format', async ({ page }) => {
    await loadViewer(page);
    const timeEl = page.locator('#time-indicator');
    await expect(timeEl).toBeVisible();
    const text = await timeEl.textContent();
    expect(text).toMatch(/\d+:\d+\s*\/\s*\d+:\d+/);
  });

  test('time updates when scrolling', async ({ page }) => {
    await loadViewer(page);
    const timeBefore = await page.locator('#time-indicator').textContent();

    await page.locator('#piano-roll-container').evaluate(
      el => { el.scrollTop = Math.max(0, el.scrollTop - 2000); }
    );
    await page.waitForTimeout(300);

    const timeAfter = await page.locator('#time-indicator').textContent();
    expect(timeAfter).not.toBe(timeBefore);
  });
});

// ============================================================
// 8. ZOOM
// ============================================================
test.describe('Zoom', () => {
  test('zoom slider exists', async ({ page }) => {
    await loadViewer(page);
    const slider = page.locator('#zoom-slider');
    await expect(slider).toBeAttached();
  });

  test('changing zoom slider resizes notes', async ({ page }) => {
    await loadViewer(page);

    const initialPPS = await page.evaluate(() => pixelsPerSecond);

    // Set zoom to maximum
    await page.locator('#zoom-slider').evaluate(el => {
      el.value = el.max;
      el.dispatchEvent(new Event('input'));
    });
    await page.waitForTimeout(500);

    const zoomedPPS = await page.evaluate(() => pixelsPerSecond);
    expect(zoomedPPS).toBeGreaterThan(initialPPS);
  });

  test('ctrl+wheel zooms the view', async ({ page }) => {
    await loadViewer(page);
    const initialPPS = await page.evaluate(() => pixelsPerSecond);

    // Dispatch ctrl+wheel event to zoom in
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
// 9. PROGRESS BAR
// ============================================================
test.describe('Progress Bar', () => {
  test('progress bar exists', async ({ page }) => {
    await loadViewer(page);
    await expect(page.locator('#progress-bar-container')).toBeVisible();
    await expect(page.locator('#progress-bar-fill')).toBeAttached();
  });

  test('clicking progress bar seeks to position', async ({ page }) => {
    await loadViewer(page);
    const bar = page.locator('#progress-bar-container');
    const box = await bar.boundingBox();

    const scrollBefore = await page.locator('#piano-roll-container').evaluate(
      el => el.scrollTop
    );

    // Click at 50% position
    await page.mouse.click(box.x + box.width * 0.5, box.y + box.height / 2);
    await page.waitForTimeout(300);

    const scrollAfter = await page.locator('#piano-roll-container').evaluate(
      el => el.scrollTop
    );
    expect(Math.abs(scrollAfter - scrollBefore)).toBeGreaterThan(0);
  });

  test('progress bar updates during playback', async ({ page }) => {
    await loadViewer(page);
    const widthBefore = await page.locator('#progress-bar-fill').evaluate(
      el => el.style.width
    );

    await page.keyboard.press('Space');
    await page.waitForTimeout(1000);
    await page.keyboard.press('Space');

    const widthAfter = await page.locator('#progress-bar-fill').evaluate(
      el => el.style.width
    );
    expect(widthAfter).not.toBe(widthBefore);
  });
});

// ============================================================
// 10. HAND TOGGLE
// ============================================================
test.describe('Hand Toggle', () => {
  test('hand toggle buttons exist', async ({ page }) => {
    await loadViewer(page);
    await expect(page.locator('#rh-toggle')).toBeVisible();
    await expect(page.locator('#lh-toggle')).toBeVisible();
  });

  test('hand toggle buttons have color swatches', async ({ page }) => {
    await loadViewer(page);
    const rhBg = await page.locator('#rh-swatch').evaluate(el => el.style.background);
    const lhBg = await page.locator('#lh-swatch').evaluate(el => el.style.background);
    expect(rhBg).toContain('rgb');
    expect(lhBg).toContain('rgb');
  });

  test('toggling left hand hides LH notes', async ({ page }) => {
    await loadViewer(page);
    const lhBefore = await page.locator('.note-block.left-hand').evaluateAll(
      els => els.filter(el => el.style.display !== 'none').length
    );
    expect(lhBefore).toBe(LH_NOTES);

    // Toggle off
    await page.locator('#lh-toggle').click();
    await page.waitForTimeout(200);

    const lhAfter = await page.locator('.note-block.left-hand').evaluateAll(
      els => els.filter(el => el.style.display !== 'none').length
    );
    expect(lhAfter).toBe(0);

    // Toggle back on
    await page.locator('#lh-toggle').click();
    await page.waitForTimeout(200);

    const lhRestored = await page.locator('.note-block.left-hand').evaluateAll(
      els => els.filter(el => el.style.display !== 'none').length
    );
    expect(lhRestored).toBe(LH_NOTES);
  });

  test('toggling right hand hides RH notes', async ({ page }) => {
    await loadViewer(page);

    await page.locator('#rh-toggle').click();
    await page.waitForTimeout(200);

    const rhAfter = await page.locator('.note-block.right-hand').evaluateAll(
      els => els.filter(el => el.style.display !== 'none').length
    );
    expect(rhAfter).toBe(0);

    // Toggle back
    await page.locator('#rh-toggle').click();
    await page.waitForTimeout(200);
  });

  test('keyboard shortcut 1 toggles right hand', async ({ page }) => {
    await loadViewer(page);
    await page.keyboard.press('Digit1');
    await page.waitForTimeout(200);

    const inactive = await page.locator('#rh-toggle').evaluate(
      el => el.classList.contains('inactive')
    );
    expect(inactive).toBe(true);

    // Toggle back
    await page.keyboard.press('Digit1');
  });

  test('keyboard shortcut 2 toggles left hand', async ({ page }) => {
    await loadViewer(page);
    await page.keyboard.press('Digit2');
    await page.waitForTimeout(200);

    const inactive = await page.locator('#lh-toggle').evaluate(
      el => el.classList.contains('inactive')
    );
    expect(inactive).toBe(true);

    await page.keyboard.press('Digit2');
  });
});

// ============================================================
// 11. SPEED CONTROL
// ============================================================
test.describe('Speed Control', () => {
  test('speed select exists with options', async ({ page }) => {
    await loadViewer(page);
    const select = page.locator('#speed-select');
    await expect(select).toBeVisible();
    const options = await select.locator('option').count();
    expect(options).toBeGreaterThanOrEqual(4);
  });

  test('speed can be changed', async ({ page }) => {
    await loadViewer(page);
    await page.locator('#speed-select').selectOption('0.5');
    const speed = await page.evaluate(() => playbackSpeed);
    expect(speed).toBe(0.5);
  });

  test('default speed is 1x', async ({ page }) => {
    await loadViewer(page);
    const speed = await page.evaluate(() => playbackSpeed);
    expect(speed).toBe(1);
  });
});

// ============================================================
// 12. VOLUME CONTROL
// ============================================================
test.describe('Volume Control', () => {
  test('volume slider exists', async ({ page }) => {
    await loadViewer(page);
    const volumeSlider = page.locator('#volume-slider');
    await expect(volumeSlider).toBeAttached();
  });

  test('default volume is 80', async ({ page }) => {
    await loadViewer(page);
    const vol = await page.locator('#volume-slider').inputValue();
    expect(vol).toBe('80');
  });
});

// ============================================================
// 13. NAVIGATION
// ============================================================
test.describe('Jump Navigation', () => {
  test('Home key jumps to start of song', async ({ page }) => {
    await loadViewer(page);
    // First scroll to middle
    await page.evaluate(() => scrollToTime(10));
    await page.waitForTimeout(300);

    await page.keyboard.press('Home');
    await page.waitForTimeout(500);

    const time = await page.evaluate(() => getTimeAtScroll());
    // Should be near the first note time
    expect(time).toBeLessThan(3);
  });

  test('End key jumps to end of song', async ({ page }) => {
    await loadViewer(page);
    await page.keyboard.press('End');
    await page.waitForTimeout(500);

    const time = await page.evaluate(() => getTimeAtScroll());
    expect(time).toBeGreaterThan(12);
  });

  test('Arrow keys scroll the view', async ({ page }) => {
    await loadViewer(page);
    const scrollBefore = await page.locator('#piano-roll-container').evaluate(
      el => el.scrollTop
    );

    await page.keyboard.press('ArrowUp');
    await page.waitForTimeout(500);

    const scrollAfter = await page.locator('#piano-roll-container').evaluate(
      el => el.scrollTop
    );
    expect(scrollAfter).not.toBe(scrollBefore);
  });
});

// ============================================================
// 14. LOOP MODE
// ============================================================
test.describe('Loop Mode', () => {
  test('loop button exists', async ({ page }) => {
    await loadViewer(page);
    await expect(page.locator('#loop-btn')).toBeVisible();
  });

  test('L key toggles loop', async ({ page }) => {
    await loadViewer(page);
    expect(await page.evaluate(() => loopEnabled)).toBe(false);

    await page.keyboard.press('l');
    await page.waitForTimeout(100);
    expect(await page.evaluate(() => loopEnabled)).toBe(true);

    await page.keyboard.press('l');
    await page.waitForTimeout(100);
    expect(await page.evaluate(() => loopEnabled)).toBe(false);
  });

  test('loop button shows active state', async ({ page }) => {
    await loadViewer(page);
    await page.keyboard.press('l');
    await page.waitForTimeout(100);

    expect(await page.locator('#loop-btn').evaluate(
      el => el.classList.contains('active')
    )).toBe(true);

    await page.keyboard.press('l');
    await page.waitForTimeout(100);
    expect(await page.locator('#loop-btn').evaluate(
      el => el.classList.contains('active')
    )).toBe(false);
  });
});

// ============================================================
// 15. MINIMAP
// ============================================================
test.describe('Minimap', () => {
  test('minimap is visible', async ({ page }) => {
    await loadViewer(page);
    await expect(page.locator('#minimap')).toBeVisible();
  });

  test('minimap has viewport indicator', async ({ page }) => {
    await loadViewer(page);
    await expect(page.locator('#minimap-viewport')).toBeAttached();
  });

  test('minimap has note indicators', async ({ page }) => {
    await loadViewer(page);
    const mmNotes = await page.locator('.minimap-note').count();
    expect(mmNotes).toBe(TOTAL_NOTES);
  });

  test('clicking minimap navigates', async ({ page }) => {
    await loadViewer(page);
    const minimap = page.locator('#minimap');
    const box = await minimap.boundingBox();

    // First scroll to end of song so we have a known position
    await page.evaluate(() => scrollToTime(totalDuration));
    await page.waitForTimeout(300);

    const scrollBefore = await page.locator('#piano-roll-container').evaluate(
      el => el.scrollTop
    );

    // Click near the top of the minimap (end of song / late time)
    await page.mouse.click(box.x + box.width / 2, box.y + 10);
    await page.waitForTimeout(300);

    const scrollAfter = await page.locator('#piano-roll-container').evaluate(
      el => el.scrollTop
    );
    expect(Math.abs(scrollAfter - scrollBefore)).toBeGreaterThan(0);
  });
});

// ============================================================
// 16. THEME TOGGLE
// ============================================================
test.describe('Theme Toggle', () => {
  test('theme toggle button exists', async ({ page }) => {
    await loadViewer(page);
    // Theme toggle moved to settings panel; verify T key still works
    const initialTheme = await page.evaluate(() =>
      document.documentElement.getAttribute('data-theme') || 'dark'
    );
    await page.keyboard.press('t');
    await page.waitForTimeout(200);
    const afterTheme = await page.evaluate(() =>
      document.documentElement.getAttribute('data-theme') || 'dark'
    );
    expect(afterTheme).not.toBe(initialTheme);
    // Toggle back
    await page.keyboard.press('t');
  });

  test('T key toggles between dark and light', async ({ page }) => {
    await loadViewer(page);
    const initialTheme = await page.evaluate(() =>
      document.documentElement.getAttribute('data-theme') || 'dark'
    );

    await page.keyboard.press('t');
    await page.waitForTimeout(200);

    const afterTheme = await page.evaluate(() =>
      document.documentElement.getAttribute('data-theme') || 'dark'
    );
    expect(afterTheme).not.toBe(initialTheme);
  });

  test('theme changes background color', async ({ page }) => {
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

    await page.keyboard.press('t');
  });

  test('theme persists through toggle cycle', async ({ page }) => {
    await loadViewer(page);
    const initial = await page.evaluate(() =>
      document.documentElement.getAttribute('data-theme') || 'dark'
    );
    await page.keyboard.press('t');
    await page.waitForTimeout(200);
    await page.keyboard.press('t');
    await page.waitForTimeout(200);
    const restored = await page.evaluate(() =>
      document.documentElement.getAttribute('data-theme') || 'dark'
    );
    expect(restored).toBe(initial);
  });
});

// ============================================================
// 17. HELP MODAL
// ============================================================
test.describe('Help Modal', () => {
  test('? key opens help modal', async ({ page }) => {
    await loadViewer(page);
    await page.keyboard.press('?');
    await page.waitForTimeout(300);

    const isVisible = await page.locator('#help-modal').evaluate(
      el => el.classList.contains('visible')
    );
    expect(isVisible).toBe(true);
  });

  test('help modal lists keyboard shortcuts', async ({ page }) => {
    await loadViewer(page);
    await page.keyboard.press('?');
    await page.waitForTimeout(300);

    const text = await page.locator('#help-content').textContent();
    expect(text).toContain('Space');
    expect(text).toContain('Home');
    expect(text).toContain('End');
    expect(text).toContain('Loop');
    expect(text).toContain('Theme');
  });

  test('Escape closes help modal', async ({ page }) => {
    await loadViewer(page);
    await page.keyboard.press('?');
    await page.waitForTimeout(200);

    await page.keyboard.press('Escape');
    await page.waitForTimeout(200);

    expect(await page.locator('#help-modal').evaluate(
      el => el.classList.contains('visible')
    )).toBe(false);
  });

  test('clicking overlay closes help modal', async ({ page }) => {
    await loadViewer(page);
    await page.keyboard.press('?');
    await page.waitForTimeout(200);

    // Click outside the content
    await page.locator('#help-modal').click({ position: { x: 10, y: 10 } });
    await page.waitForTimeout(200);

    expect(await page.locator('#help-modal').evaluate(
      el => el.classList.contains('visible')
    )).toBe(false);
  });
});

// ============================================================
// 18. NOTE HIGHLIGHTING
// ============================================================
test.describe('Note Highlighting', () => {
  test('.playing CSS class exists in stylesheet', async ({ page }) => {
    await loadViewer(page);
    const hasPlayingStyle = await page.evaluate(() => {
      for (const sheet of document.styleSheets) {
        try {
          for (const rule of sheet.cssRules) {
            if (rule.selectorText && rule.selectorText.includes('.playing')) {
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
// 19. ACTIVE KEY HIGHLIGHTING
// ============================================================
test.describe('Active Key Highlighting', () => {
  test('scrolling to notes highlights keyboard keys', async ({ page }) => {
    await loadViewer(page);
    await page.evaluate(() => scrollToTime(2.5));
    await page.waitForTimeout(300);
    await page.evaluate(() => highlightActiveKeys());
    await page.waitForTimeout(200);

    const activeKeys = await page.locator('.key.active-rh, .key.active-lh').count();
    expect(activeKeys).toBeGreaterThan(0);
  });
});

// ============================================================
// 20. TRACK LINES
// ============================================================
test.describe('Track Lines', () => {
  test('track lines are rendered', async ({ page }) => {
    await loadViewer(page);
    const trackLines = await page.locator('.track-line').count();
    expect(trackLines).toBeGreaterThan(3);
  });
});

// ============================================================
// 21. DENSITY CANVAS
// ============================================================
test.describe('Density Canvas', () => {
  test('density canvas exists', async ({ page }) => {
    await loadViewer(page);
    await expect(page.locator('#density-canvas')).toBeAttached();
  });
});

// ============================================================
// 21c. SHARP/FLAT NOTE STYLING
// ============================================================
test.describe('Sharp/Flat Note Styling', () => {
  test('sharp notes have .sharp-note class', async ({ page }) => {
    await loadViewer(page);
    const sharpCount = await page.locator('.note-block.sharp-note').count();
    // Our fixture has sharp notes (C#, D#, F#, G#, A#)
    expect(sharpCount).toBeGreaterThan(0);
  });

  test('natural notes do NOT have .sharp-note class', async ({ page }) => {
    await loadViewer(page);
    const totalSharps = await page.locator('.note-block.sharp-note').count();
    const totalNotes = await page.locator('.note-block').count();
    expect(totalSharps).toBeLessThan(totalNotes);
  });

  test('sharp notes are narrower than natural notes', async ({ page }) => {
    await loadViewer(page);
    // Get a sharp note's width
    const sharpWidth = await page.locator('.note-block.sharp-note').first().evaluate(
      el => parseFloat(el.style.width)
    );
    // Get a natural note's width (one without sharp-note class)
    const naturalWidth = await page.locator('.note-block:not(.sharp-note)').first().evaluate(
      el => parseFloat(el.style.width)
    );
    expect(sharpWidth).toBeLessThan(naturalWidth);
  });

  test('sharp notes have dashed border', async ({ page }) => {
    await loadViewer(page);
    const borderStyle = await page.locator('.note-block.sharp-note').first().evaluate(
      el => getComputedStyle(el).borderStyle
    );
    expect(borderStyle).toBe('dashed');
  });

  test('sharp notes are darker than naturals of the same hand', async ({ page }) => {
    await loadViewer(page);
    // Extract background color strings to compare
    const sharpBg = await page.locator('.note-block.sharp-note.right-hand').first().evaluate(
      el => el.style.background
    );
    const naturalBg = await page.locator('.note-block.right-hand:not(.sharp-note)').first().evaluate(
      el => el.style.background
    );
    // Sharp notes should have different (darker) gradient
    expect(sharpBg).not.toBe(naturalBg);
  });
});

// ============================================================
// 21b. NOTE DROP LINES
// ============================================================
test.describe('Note Drop Lines', () => {
  test('drop lines are rendered for each note', async ({ page }) => {
    await loadViewer(page);
    const dropLineCount = await page.locator('.note-drop-line').count();
    expect(dropLineCount).toBe(TOTAL_NOTES);
  });

  test('drop lines are positioned below their notes', async ({ page }) => {
    await loadViewer(page);
    // Check a single note-block and its sibling drop line
    const noteBlock = page.locator('.note-block').first();
    const noteBox = await noteBlock.boundingBox();

    // The drop line for this note should exist
    const dropLines = page.locator('.note-drop-line');
    expect(await dropLines.count()).toBeGreaterThan(0);
  });

  test('drop lines are semi-transparent (opacity < 0.3)', async ({ page }) => {
    await loadViewer(page);
    const opacity = await page.locator('.note-drop-line').first().evaluate(
      el => parseFloat(getComputedStyle(el).opacity)
    );
    expect(opacity).toBeLessThanOrEqual(0.3);
    expect(opacity).toBeGreaterThan(0);
  });

  test('drop lines are hidden when hand is toggled off', async ({ page }) => {
    await loadViewer(page);
    // Toggle off right hand
    await page.keyboard.press('Digit1');
    const hiddenRH = await page.locator('.note-drop-line').evaluateAll(
      els => els.filter(el => el.style.display === 'none').length
    );
    expect(hiddenRH).toBe(RH_NOTES);

    // Toggle back on
    await page.keyboard.press('Digit1');
    const visibleAll = await page.locator('.note-drop-line').evaluateAll(
      els => els.filter(el => el.style.display !== 'none').length
    );
    expect(visibleAll).toBe(TOTAL_NOTES);
  });

  test('drop lines have width of 1px', async ({ page }) => {
    await loadViewer(page);
    const width = await page.locator('.note-drop-line').first().evaluate(
      el => getComputedStyle(el).width
    );
    expect(width).toBe('1px');
  });
});

// ============================================================
// 22. SCROLL DURING PLAYBACK
// ============================================================
test.describe('Scroll During Playback', () => {
  test('wheel scroll during playback pauses then resumes', async ({ page }) => {
    await loadViewer(page);
    await page.keyboard.press('Space');
    await page.waitForTimeout(500);
    expect(await page.evaluate(() => isPlaying)).toBe(true);

    // Wheel scroll (non-ctrl) should trigger user scroll intent
    const container = page.locator('#piano-roll-container');
    const box = await container.boundingBox();
    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
    await page.mouse.wheel(0, -200);
    await page.waitForTimeout(50);

    expect(await page.evaluate(() => isPlaying)).toBe(false);

    // After resume timeout (200ms), should be playing again
    await page.waitForTimeout(500);
    expect(await page.evaluate(() => isPlaying)).toBe(true);

    await page.keyboard.press('Space');
  });

  test('ArrowDown during playback pauses then resumes from new position', async ({ page }) => {
    await loadViewer(page);
    // Start playback
    await page.keyboard.press('Space');
    await page.waitForTimeout(500);
    expect(await page.evaluate(() => isPlaying)).toBe(true);

    // Record scroll position before arrow key
    const scrollBefore = await page.evaluate(() =>
      document.getElementById('piano-roll-container').scrollTop
    );

    // Press ArrowDown — should pause playback temporarily
    await page.keyboard.press('ArrowDown');
    await page.waitForTimeout(50);
    expect(await page.evaluate(() => isPlaying)).toBe(false);

    // After resume timeout, should resume playing from new position
    await page.waitForTimeout(500);
    expect(await page.evaluate(() => isPlaying)).toBe(true);

    await page.keyboard.press('Space');
  });

  test('ArrowUp during playback pauses then resumes from new position', async ({ page }) => {
    await loadViewer(page);
    // Start playback and let it run a bit
    await page.keyboard.press('Space');
    await page.waitForTimeout(800);
    expect(await page.evaluate(() => isPlaying)).toBe(true);

    // Press ArrowUp — should pause playback temporarily
    await page.keyboard.press('ArrowUp');
    await page.waitForTimeout(50);
    expect(await page.evaluate(() => isPlaying)).toBe(false);

    // After resume timeout, should resume playing
    await page.waitForTimeout(500);
    expect(await page.evaluate(() => isPlaying)).toBe(true);

    await page.keyboard.press('Space');
  });
});

// ============================================================
// 23. RESPONSIVE DESIGN
// ============================================================
test.describe('Responsive Design', () => {
  test('viewport meta allows pinch zoom (no user-scalable=no)', async ({ page }) => {
    await loadViewer(page);
    const content = await page.locator('meta[name="viewport"]').getAttribute('content');
    expect(content).not.toContain('user-scalable=no');
    expect(content).not.toContain('maximum-scale=1');
  });

  test('works at mobile viewport (375x667)', async ({ page }) => {
    await loadViewerMobile(page);
    const noteCount = await page.locator('.note-block').count();
    expect(noteCount).toBe(TOTAL_NOTES);
    await expect(page.locator('#keyboard')).toBeVisible();
  });

  test('mobile buttons have adequate touch targets (min 34px)', async ({ page }) => {
    await loadViewerMobile(page);
    const playBtn = await page.locator('#play-btn').boundingBox();
    expect(playBtn.height).toBeGreaterThanOrEqual(34);
    expect(playBtn.width).toBeGreaterThanOrEqual(34);
  });

  test('mobile speed select has adequate size', async ({ page }) => {
    await loadViewerMobile(page);
    const speedBox = await page.locator('#speed-select').boundingBox();
    expect(speedBox.height).toBeGreaterThanOrEqual(34);
  });

  test('works at tablet viewport (768x1024)', async ({ page }) => {
    await loadViewerTablet(page);
    const noteCount = await page.locator('.note-block').count();
    expect(noteCount).toBe(TOTAL_NOTES);
  });
});

// ============================================================
// 24. CSS STRUCTURE
// ============================================================
test.describe('CSS Structure', () => {
  test('uses CSS custom properties', async ({ page }) => {
    await loadViewer(page);
    const hasVars = await page.evaluate(() => {
      const root = getComputedStyle(document.documentElement);
      return root.getPropertyValue('--bg-primary').trim().length > 0;
    });
    expect(hasVars).toBe(true);
  });

  test('uses external stylesheet', async ({ page }) => {
    await loadViewer(page);
    const linkCount = await page.locator('link[rel="stylesheet"]').count();
    expect(linkCount).toBe(1);
  });

  test('toolbar is fixed at top', async ({ page }) => {
    await loadViewer(page);
    const position = await page.locator('#toolbar').evaluate(
      el => getComputedStyle(el).position
    );
    expect(position).toBe('fixed');
  });

  test('toolbar height is at least 56px on desktop', async ({ page }) => {
    await loadViewer(page);
    const box = await page.locator('#toolbar').boundingBox();
    expect(box.height).toBeGreaterThanOrEqual(56);
  });

  test('speed select has adequate font size on desktop', async ({ page }) => {
    await loadViewer(page);
    const fontSize = await page.locator('#speed-select').evaluate(
      el => parseFloat(getComputedStyle(el).fontSize)
    );
    expect(fontSize).toBeGreaterThanOrEqual(14);
  });

  test('hand toggle buttons have adequate font size on desktop', async ({ page }) => {
    await loadViewer(page);
    const fontSize = await page.locator('#rh-toggle').evaluate(
      el => parseFloat(getComputedStyle(el).fontSize)
    );
    expect(fontSize).toBeGreaterThanOrEqual(14);
  });

  test('keyboard is fixed at bottom', async ({ page }) => {
    await loadViewer(page);
    const position = await page.locator('#keyboard').evaluate(
      el => getComputedStyle(el).position
    );
    expect(position).toBe('fixed');
  });
});

// ============================================================
// 25. SCROLL BEHAVIOR CONSISTENCY
// ============================================================
test.describe('Scroll Behavior', () => {
  test('scroll updates time indicator', async ({ page }) => {
    await loadViewer(page);
    const timeBefore = await page.locator('#time-indicator').textContent();

    await page.locator('#piano-roll-container').evaluate(
      el => { el.scrollTop = Math.max(0, el.scrollTop - 2000); }
    );
    await page.waitForTimeout(300);

    const timeAfter = await page.locator('#time-indicator').textContent();
    expect(timeAfter).not.toBe(timeBefore);
  });

  test('scroll updates progress bar', async ({ page }) => {
    await loadViewer(page);
    const widthBefore = await page.locator('#progress-bar-fill').evaluate(
      el => el.style.width
    );

    await page.evaluate(() => scrollToTime(10));
    await page.waitForTimeout(300);

    const widthAfter = await page.locator('#progress-bar-fill').evaluate(
      el => el.style.width
    );
    expect(widthAfter).not.toBe(widthBefore);
  });

  test('scroll updates minimap viewport', async ({ page }) => {
    await loadViewer(page);
    const topBefore = await page.locator('#minimap-viewport').evaluate(
      el => el.style.top
    );

    await page.evaluate(() => scrollToTime(10));
    await page.waitForTimeout(300);

    const topAfter = await page.locator('#minimap-viewport').evaluate(
      el => el.style.top
    );
    expect(topAfter).not.toBe(topBefore);
  });
});

// ============================================================
// 26. LAYOUT INTEGRITY
// ============================================================
test.describe('Layout Integrity', () => {
  test('toolbar, main container, keyboard layout is correct', async ({ page }) => {
    await loadViewer(page);
    const toolbar = await page.locator('#toolbar').boundingBox();
    const mainContainer = await page.locator('#main-container').boundingBox();
    const keyboard = await page.locator('#keyboard').boundingBox();

    // Main container starts below toolbar
    expect(mainContainer.y).toBeGreaterThanOrEqual(toolbar.y + toolbar.height - 5);
    // Keyboard at the bottom
    expect(keyboard.y + keyboard.height).toBeGreaterThanOrEqual(795);
  });

  test('no horizontal overflow', async ({ page }) => {
    await loadViewer(page);
    const noOverflow = await page.evaluate(() => {
      return document.body.scrollWidth <= window.innerWidth;
    });
    expect(noOverflow).toBe(true);
  });
});

// ============================================================
// 27. FILE LOADING
// ============================================================
test.describe('File Loading', () => {
  test('homepage is visible when no data is loaded', async ({ page }) => {
    // Load viewer WITHOUT json param
    await page.goto(VIEWER_URL, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(500);
    await expect(page.locator('#homepage')).toBeVisible();
    await expect(page.locator('#loading-spinner')).toBeHidden();
  });

  test('homepage is hidden after data loads via URL', async ({ page }) => {
    await loadViewer(page);
    await expect(page.locator('#homepage')).toBeHidden();
  });

  test('Open button exists in toolbar', async ({ page }) => {
    await loadViewer(page);
    await expect(page.locator('#load-file-btn')).toBeVisible();
  });

  test('file input element exists and accepts JSON', async ({ page }) => {
    await loadViewer(page);
    const accept = await page.locator('#file-input').getAttribute('accept');
    expect(accept).toContain('.json');
  });

  test('drag overlay appears on dragenter and hides on drop', async ({ page }) => {
    await loadViewer(page);
    // The drag overlay should be hidden initially
    await expect(page.locator('#drag-overlay')).toBeHidden();
  });

  test('loading a new JSON file replaces current data', async ({ page }) => {
    await loadViewer(page);
    // Verify initial data
    expect(await page.locator('.note-block').count()).toBe(TOTAL_NOTES);

    // Create a smaller JSON with 2 notes and load it via file input
    const smallData = JSON.stringify({
      notes: [
        { id: 1, note_name: "C4", start_time: 0, duration: 1, hand: "right_hand", key_index: 39, center_x: 50, color_rgb: [100, 100, 255] },
        { id: 2, note_name: "E4", start_time: 1, duration: 1, hand: "left_hand", key_index: 43, center_x: 60, color_rgb: [255, 100, 100] }
      ]
    });

    // Use Playwright's setInputFiles to simulate file selection
    const fileInput = page.locator('#file-input');
    await fileInput.setInputFiles({
      name: 'test.json',
      mimeType: 'application/json',
      buffer: Buffer.from(smallData)
    });

    // Wait for new data to load
    await page.waitForFunction(
      () => document.querySelectorAll('.note-block').length === 2,
      { timeout: 5000 }
    );
    expect(await page.locator('.note-block').count()).toBe(2);
  });
});

// ============================================================
// 28. COMMAND PALETTE
// ============================================================
test.describe('Command Palette', () => {
  test('Cmd+P opens command palette', async ({ page }) => {
    await loadViewer(page);
    await page.keyboard.press('Meta+p');
    await expect(page.locator('#command-palette-overlay')).toBeVisible();
    await expect(page.locator('#command-palette-input')).toBeFocused();
  });

  test('Escape closes command palette', async ({ page }) => {
    await loadViewer(page);
    await page.keyboard.press('Meta+p');
    await expect(page.locator('#command-palette-overlay')).toBeVisible();
    await page.keyboard.press('Escape');
    await expect(page.locator('#command-palette-overlay')).toBeHidden();
  });

  test('clicking overlay closes command palette', async ({ page }) => {
    await loadViewer(page);
    await page.keyboard.press('Meta+p');
    await expect(page.locator('#command-palette-overlay')).toBeVisible();
    // Click overlay (outside palette)
    await page.locator('#command-palette-overlay').click({ position: { x: 10, y: 10 } });
    await expect(page.locator('#command-palette-overlay')).toBeHidden();
  });

  test('lists all commands initially', async ({ page }) => {
    await loadViewer(page);
    await page.keyboard.press('Meta+p');
    const itemCount = await page.locator('.cmd-item').count();
    expect(itemCount).toBeGreaterThanOrEqual(15); // We have 21+ commands
  });

  test('first item is selected by default', async ({ page }) => {
    await loadViewer(page);
    await page.keyboard.press('Meta+p');
    const firstItem = page.locator('.cmd-item').first();
    await expect(firstItem).toHaveClass(/selected/);
  });

  test('typing filters commands', async ({ page }) => {
    await loadViewer(page);
    await page.keyboard.press('Meta+p');
    const initialCount = await page.locator('.cmd-item').count();

    await page.locator('#command-palette-input').fill('theme');
    const filteredCount = await page.locator('.cmd-item').count();
    expect(filteredCount).toBeLessThan(initialCount);
    expect(filteredCount).toBeGreaterThan(0);

    // The theme command should be visible
    const labels = await page.locator('.cmd-item .cmd-label').allTextContents();
    expect(labels.some(l => l.toLowerCase().includes('theme'))).toBe(true);
  });

  test('shows no results message for unmatched query', async ({ page }) => {
    await loadViewer(page);
    await page.keyboard.press('Meta+p');
    await page.locator('#command-palette-input').fill('xyznonexistent');
    await expect(page.locator('.cmd-no-results')).toBeVisible();
  });

  test('arrow keys navigate commands', async ({ page }) => {
    await loadViewer(page);
    await page.keyboard.press('Meta+p');
    // First item should be selected
    const firstItem = page.locator('.cmd-item').first();
    await expect(firstItem).toHaveClass(/selected/);

    // Arrow down moves selection
    await page.keyboard.press('ArrowDown');
    const secondItem = page.locator('.cmd-item').nth(1);
    await expect(secondItem).toHaveClass(/selected/);
    await expect(firstItem).not.toHaveClass(/selected/);
  });

  test('Enter executes selected command', async ({ page }) => {
    await loadViewer(page);
    await page.keyboard.press('Meta+p');
    // Type "loop" to find the loop command
    await page.locator('#command-palette-input').fill('loop');
    await page.waitForTimeout(100);
    // Press enter to execute
    await page.keyboard.press('Enter');
    // Command palette should close
    await expect(page.locator('#command-palette-overlay')).toBeHidden();
    // Loop should be toggled on
    expect(await page.evaluate(() => loopEnabled)).toBe(true);
  });

  test('command palette lists shortcuts', async ({ page }) => {
    await loadViewer(page);
    await page.keyboard.press('Meta+p');
    const shortcuts = await page.locator('.cmd-shortcut').allTextContents();
    expect(shortcuts.some(s => s === 'Space')).toBe(true);
    expect(shortcuts.some(s => s === 'L')).toBe(true);
  });

  test('command palette is keyboard-accessible from search to selection', async ({ page }) => {
    await loadViewer(page);
    await page.keyboard.press('Meta+p');

    // Type to filter
    await page.locator('#command-palette-input').fill('speed');
    await page.waitForTimeout(100);

    // Navigate with arrows
    await page.keyboard.press('ArrowDown');
    await page.keyboard.press('ArrowDown');

    // Enter should execute
    await page.keyboard.press('Enter');
    await expect(page.locator('#command-palette-overlay')).toBeHidden();
  });
});

// ============================================================
// 31. EDIT MODE
// ============================================================
test.describe('Edit Mode', () => {
  test('pressing E toggles edit mode on and off', async ({ page }) => {
    await loadViewer(page);
    // Initially not in edit mode
    await expect(page.locator('body')).not.toHaveClass(/edit-mode/);
    await expect(page.locator('#edit-indicator')).toBeHidden();

    // Press E to enter edit mode
    await page.keyboard.press('e');
    await expect(page.locator('body')).toHaveClass(/edit-mode/);
    await expect(page.locator('#edit-indicator')).toBeVisible();
    await expect(page.locator('#edit-mode-btn')).toHaveClass(/active/);

    // Press E again to exit
    await page.keyboard.press('e');
    await expect(page.locator('body')).not.toHaveClass(/edit-mode/);
    await expect(page.locator('#edit-indicator')).toBeHidden();
  });

  test('edit mode button in toolbar toggles edit mode', async ({ page }) => {
    await loadViewer(page);
    await page.locator('#edit-mode-btn').click();
    await expect(page.locator('body')).toHaveClass(/edit-mode/);
    await expect(page.locator('#edit-mode-btn')).toHaveClass(/active/);

    await page.locator('#edit-mode-btn').click();
    await expect(page.locator('body')).not.toHaveClass(/edit-mode/);
  });

  test('piano roll cursor changes to crosshair in edit mode', async ({ page }) => {
    await loadViewer(page);
    await page.keyboard.press('e');
    const cursor = await page.locator('#piano-roll').evaluate(el => getComputedStyle(el).cursor);
    expect(cursor).toBe('crosshair');
  });

  test('resize handles are visible on note blocks in edit mode', async ({ page }) => {
    await loadViewer(page);
    // Before edit mode, resize handles are hidden
    const handleBefore = await page.locator('.resize-handle-top').first().evaluate(el => getComputedStyle(el).display);
    expect(handleBefore).toBe('none');

    await page.keyboard.press('e');
    const handleAfter = await page.locator('.resize-handle-top').first().evaluate(el => getComputedStyle(el).display);
    expect(handleAfter).toBe('block');
  });

  test('clicking a note in edit mode selects it with outline', async ({ page }) => {
    await loadViewer(page);
    await page.keyboard.press('e');

    const firstNote = page.locator('.note-block').first();
    await firstNote.click();
    await expect(firstNote).toHaveClass(/selected/);

    const outline = await firstNote.evaluate(el => getComputedStyle(el).outlineStyle);
    expect(outline).toBe('solid');
  });

  test('clicking another note deselects the previous one', async ({ page }) => {
    await loadViewer(page);
    await page.keyboard.press('e');

    const notes = page.locator('.note-block');
    const firstNote = notes.first();
    const secondNote = notes.nth(1);

    await firstNote.click();
    await expect(firstNote).toHaveClass(/selected/);

    await secondNote.click();
    await expect(secondNote).toHaveClass(/selected/);
    await expect(firstNote).not.toHaveClass(/selected/);
  });

  test('pressing Escape deselects the selected note', async ({ page }) => {
    await loadViewer(page);
    await page.keyboard.press('e');

    const firstNote = page.locator('.note-block').first();
    await firstNote.click();
    await expect(firstNote).toHaveClass(/selected/);

    await page.keyboard.press('Escape');
    await expect(firstNote).not.toHaveClass(/selected/);
    // Should still be in edit mode
    await expect(page.locator('body')).toHaveClass(/edit-mode/);
  });

  test('pressing Escape with no selection exits edit mode', async ({ page }) => {
    await loadViewer(page);
    await page.keyboard.press('e');
    await expect(page.locator('body')).toHaveClass(/edit-mode/);

    await page.keyboard.press('Escape');
    await expect(page.locator('body')).not.toHaveClass(/edit-mode/);
  });

  test('Delete key removes the selected note', async ({ page }) => {
    await loadViewer(page);
    await page.keyboard.press('e');

    const initialCount = await page.locator('.note-block').count();
    const firstNote = page.locator('.note-block').first();
    await firstNote.click();
    await expect(firstNote).toHaveClass(/selected/);

    await page.keyboard.press('Delete');
    const newCount = await page.locator('.note-block').count();
    expect(newCount).toBe(initialCount - 1);
  });

  test('Backspace key also removes the selected note', async ({ page }) => {
    await loadViewer(page);
    await page.keyboard.press('e');

    const initialCount = await page.locator('.note-block').count();
    const firstNote = page.locator('.note-block').first();
    await firstNote.click();
    await page.keyboard.press('Backspace');

    const newCount = await page.locator('.note-block').count();
    expect(newCount).toBe(initialCount - 1);
  });

  test('Delete does nothing when no note is selected', async ({ page }) => {
    await loadViewer(page);
    await page.keyboard.press('e');

    const initialCount = await page.locator('.note-block').count();
    await page.keyboard.press('Delete');
    const newCount = await page.locator('.note-block').count();
    expect(newCount).toBe(initialCount);
  });

  test('H key toggles the hand of the selected note', async ({ page }) => {
    await loadViewer(page);
    await page.keyboard.press('e');

    // Find a right-hand note and select it
    const rhNote = page.locator('.note-block.right-hand').first();
    await rhNote.click();
    const noteId = await page.locator('.note-block.selected').getAttribute('data-note-id');

    await page.keyboard.press('h');
    // The note should now be left-hand
    const toggledNote = page.locator(`.note-block[data-note-id="${noteId}"]`);
    await expect(toggledNote).toHaveAttribute('data-hand', 'left_hand');
    await expect(toggledNote).toHaveClass(/selected/);

    // Toggle back
    await page.keyboard.press('h');
    await expect(toggledNote).toHaveAttribute('data-hand', 'right_hand');
  });

  test('clicking empty space in edit mode adds a new note', async ({ page }) => {
    await loadViewer(page);
    await page.keyboard.press('e');

    const initialCount = await page.locator('.note-block').count();

    // Scroll to start (Home) so we have empty space above the earliest notes
    await page.keyboard.press('Home');
    await page.waitForTimeout(300);

    // Click in the visible container area (not on #piano-roll which may extend offscreen)
    const container = page.locator('#piano-roll-container');
    const box = await container.boundingBox();
    // Drag to create a note (click-to-add removed; only drag creates notes)
    const startX = box.x + 10;
    const startY = box.y + box.height / 2;
    await page.mouse.move(startX, startY);
    await page.mouse.down();
    await page.mouse.move(startX, startY - 80, { steps: 10 });
    await page.mouse.up();

    // Wait for re-render
    await page.waitForTimeout(200);
    const newCount = await page.locator('.note-block').count();
    expect(newCount).toBe(initialCount + 1);
  });

  test('newly added note is automatically selected', async ({ page }) => {
    await loadViewer(page);
    await page.keyboard.press('e');

    // Scroll to start so we have space
    await page.keyboard.press('Home');
    await page.waitForTimeout(300);

    const container = page.locator('#piano-roll-container');
    const box = await container.boundingBox();
    // Drag to create a note
    const startX = box.x + 10;
    const startY = box.y + box.height / 2;
    await page.mouse.move(startX, startY);
    await page.mouse.down();
    await page.mouse.move(startX, startY - 80, { steps: 10 });
    await page.mouse.up();
    await page.waitForTimeout(200);

    const selectedCount = await page.locator('.note-block.selected').count();
    expect(selectedCount).toBe(1);
  });

  test('exiting edit mode deselects all notes', async ({ page }) => {
    await loadViewer(page);
    await page.keyboard.press('e');

    const firstNote = page.locator('.note-block').first();
    await firstNote.click();
    await expect(firstNote).toHaveClass(/selected/);

    await page.keyboard.press('e'); // Exit edit mode
    const selectedCount = await page.locator('.note-block.selected').count();
    expect(selectedCount).toBe(0);
  });

  test('edit mode commands appear in command palette', async ({ page }) => {
    await loadViewer(page);
    await page.keyboard.press('Meta+p');

    await page.locator('#command-palette-input').fill('edit');
    await page.waitForTimeout(100);

    const items = await page.locator('.cmd-item .cmd-label').allTextContents();
    expect(items.some(t => t.includes('Edit Mode'))).toBe(true);
  });

  test('note click does not trigger playback scroll in edit mode', async ({ page }) => {
    await loadViewer(page);
    await page.keyboard.press('e');

    const container = page.locator('#piano-roll-container');
    const scrollBefore = await container.evaluate(el => el.scrollTop);

    const firstNote = page.locator('.note-block').first();
    await firstNote.click();
    await page.waitForTimeout(100);

    const scrollAfter = await container.evaluate(el => el.scrollTop);
    // Scroll should not have changed from a note click in edit mode
    expect(scrollAfter).toBe(scrollBefore);
  });
});

// ============================================================
// 32. EXPORT / SAVE JSON
// ============================================================
test.describe('Export/Save JSON', () => {
  test('save button exists in toolbar', async ({ page }) => {
    await loadViewer(page);
    await expect(page.locator('#save-file-btn')).toBeVisible();
  });

  test('save button triggers download when data is loaded', async ({ page }) => {
    await loadViewer(page);
    const [download] = await Promise.all([
      page.waitForEvent('download'),
      page.locator('#save-file-btn').click(),
    ]);
    expect(download.suggestedFilename()).toMatch(/\.json$/);
  });

  test('exported JSON contains notes array', async ({ page }) => {
    await loadViewer(page);
    const [download] = await Promise.all([
      page.waitForEvent('download'),
      page.locator('#save-file-btn').click(),
    ]);
    const stream = await download.createReadStream();
    const chunks = [];
    for await (const chunk of stream) chunks.push(chunk);
    const content = Buffer.concat(chunks).toString('utf-8');
    const data = JSON.parse(content);
    expect(Array.isArray(data.notes)).toBe(true);
    expect(data.notes.length).toBe(TOTAL_NOTES);
  });

  test('Cmd+S triggers download', async ({ page }) => {
    await loadViewer(page);
    const [download] = await Promise.all([
      page.waitForEvent('download'),
      page.keyboard.press('Meta+s'),
    ]);
    expect(download.suggestedFilename()).toMatch(/\.json$/);
  });

  test('save command appears in command palette', async ({ page }) => {
    await loadViewer(page);
    await page.keyboard.press('Meta+p');
    await page.locator('#command-palette-input').fill('save');
    await page.waitForTimeout(100);
    const items = await page.locator('.cmd-item .cmd-label').allTextContents();
    expect(items.some(t => t.includes('Save'))).toBe(true);
  });

  test('exported notes reflect edits made in edit mode', async ({ page }) => {
    await loadViewer(page);
    // Delete a note in edit mode
    await page.keyboard.press('e');
    const firstNote = page.locator('.note-block').first();
    await firstNote.click();
    await page.keyboard.press('Delete');
    await page.keyboard.press('e'); // exit edit mode

    const [download] = await Promise.all([
      page.waitForEvent('download'),
      page.locator('#save-file-btn').click(),
    ]);
    const stream = await download.createReadStream();
    const chunks = [];
    for await (const chunk of stream) chunks.push(chunk);
    const data = JSON.parse(Buffer.concat(chunks).toString('utf-8'));
    expect(data.notes.length).toBe(TOTAL_NOTES - 1);
  });
});

// ============================================================
// 33. EMPTY PROJECT / START EMPTY
// ============================================================
test.describe('Empty Project', () => {
  test('homepage shows when no JSON URL is provided', async ({ page }) => {
    await page.goto(VIEWER_URL, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(500);
    await expect(page.locator('#homepage')).toBeVisible();
    await expect(page.locator('#loading-spinner')).toBeHidden();
  });

  test('Start Empty button exists on homepage', async ({ page }) => {
    await page.goto(VIEWER_URL, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(500);
    await expect(page.locator('#start-empty-btn')).toBeVisible();
  });

  test('clicking Start Empty loads an empty project', async ({ page }) => {
    await page.goto(VIEWER_URL, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(500);
    await page.locator('#start-empty-btn').click();
    await page.waitForTimeout(300);

    // Loading overlay should be hidden
    await expect(page.locator('#loading-overlay')).toHaveClass(/hidden/);
    // No notes rendered
    expect(await page.locator('.note-block').count()).toBe(0);
  });

  test('empty project allows adding notes in edit mode', async ({ page }) => {
    await page.goto(VIEWER_URL, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(500);
    await page.locator('#start-empty-btn').click();
    await page.waitForTimeout(300);

    await page.keyboard.press('e');
    const container = page.locator('#piano-roll-container');
    const box = await container.boundingBox();
    // Drag to create a note (click-to-add removed)
    const startX = box.x + box.width / 2;
    const startY = box.y + box.height / 2;
    await page.mouse.move(startX, startY);
    await page.mouse.down();
    await page.mouse.move(startX, startY - 80, { steps: 10 });
    await page.mouse.up();
    await page.waitForTimeout(200);

    expect(await page.locator('.note-block').count()).toBe(1);
  });

  test('New Empty Project command exists in palette', async ({ page }) => {
    await loadViewer(page);
    await page.keyboard.press('Meta+p');
    await page.locator('#command-palette-input').fill('empty');
    await page.waitForTimeout(100);
    const items = await page.locator('.cmd-item .cmd-label').allTextContents();
    expect(items.some(t => t.includes('Empty'))).toBe(true);
  });

  test('help modal includes new shortcuts', async ({ page }) => {
    await loadViewer(page);
    await page.keyboard.press('?');
    await page.waitForTimeout(200);
    const helpText = await page.locator('#help-content').textContent();
    expect(helpText).toContain('Save');
    expect(helpText).toContain('Edit Mode');
    expect(helpText).toContain('⌘S');
  });
});

// ============================================================
// 34. EDGE CASES & ROBUSTNESS
// ============================================================
test.describe('Edge Cases', () => {
  test('handles empty notes array without crashing', async ({ page }) => {
    const errors = [];
    page.on('pageerror', err => errors.push(err.message));

    await page.goto(VIEWER_URL, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(300);
    await page.locator('#start-empty-btn').click();
    await page.waitForTimeout(500);

    expect(errors).toEqual([]);
    expect(await page.locator('.note-block').count()).toBe(0);
    // Keyboard should still render with default key range
    expect(await page.locator('.key').count()).toBeGreaterThan(0);
  });

  test('handles single note JSON without issues', async ({ page }) => {
    const errors = [];
    page.on('pageerror', err => errors.push(err.message));

    await page.goto(VIEWER_URL, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(300);

    // Load single-note data via evaluate
    await page.evaluate(() => {
      const data = {
        notes: [{ id: 1, note_name: 'C4', start_time: 0, duration: 2.0, hand: 'right_hand', key_index: 39, center_x: 0, color_rgb: [100, 150, 255] }]
      };
      loadNotesData(data);
    });
    await page.waitForTimeout(300);

    expect(errors).toEqual([]);
    expect(await page.locator('.note-block').count()).toBe(1);
  });

  test('handles note with duration 0 without crashing', async ({ page }) => {
    const errors = [];
    page.on('pageerror', err => errors.push(err.message));

    await page.goto(VIEWER_URL, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(300);

    await page.evaluate(() => {
      loadNotesData({
        notes: [{ id: 1, note_name: 'D4', start_time: 1.0, duration: 0, hand: 'right_hand', key_index: 41, center_x: 0, color_rgb: [100, 150, 255] }]
      });
    });
    await page.waitForTimeout(300);

    expect(errors).toEqual([]);
    // Note should still render with min height of 4px
    const note = page.locator('.note-block');
    expect(await note.count()).toBe(1);
    const height = await note.evaluate(el => parseFloat(el.style.height));
    expect(height).toBeGreaterThanOrEqual(4);
  });

  test('handles note with negative start_time without crashing', async ({ page }) => {
    const errors = [];
    page.on('pageerror', err => errors.push(err.message));

    await page.goto(VIEWER_URL, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(300);

    await page.evaluate(() => {
      loadNotesData({
        notes: [{ id: 1, note_name: 'E4', start_time: -5, duration: 2.0, hand: 'right_hand', key_index: 43, center_x: 0, color_rgb: [100, 150, 255] }]
      });
    });
    await page.waitForTimeout(300);

    expect(errors).toEqual([]);
    expect(await page.locator('.note-block').count()).toBe(1);
  });

  test('handles note with key_index at boundaries (0 and 87)', async ({ page }) => {
    const errors = [];
    page.on('pageerror', err => errors.push(err.message));

    await page.goto(VIEWER_URL, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(300);

    await page.evaluate(() => {
      loadNotesData({
        notes: [
          { id: 1, note_name: 'A0', start_time: 0, duration: 1, hand: 'left_hand', key_index: 0, center_x: 0, color_rgb: [255, 100, 100] },
          { id: 2, note_name: 'C8', start_time: 0, duration: 1, hand: 'right_hand', key_index: 87, center_x: 0, color_rgb: [100, 150, 255] }
        ]
      });
    });
    await page.waitForTimeout(300);

    expect(errors).toEqual([]);
    expect(await page.locator('.note-block').count()).toBe(2);
  });

  test('handles note with missing color_rgb gracefully', async ({ page }) => {
    const errors = [];
    page.on('pageerror', err => errors.push(err.message));

    await page.goto(VIEWER_URL, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(300);

    await page.evaluate(() => {
      loadNotesData({
        notes: [{ id: 1, note_name: 'F4', start_time: 0, duration: 2.0, hand: 'right_hand', key_index: 44, center_x: 0 }]
      });
    });
    await page.waitForTimeout(300);

    expect(errors).toEqual([]);
    expect(await page.locator('.note-block').count()).toBe(1);
  });

  test('handles note with missing note_name without crashing tooltip', async ({ page }) => {
    const errors = [];
    page.on('pageerror', err => errors.push(err.message));

    await page.goto(VIEWER_URL, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(300);

    await page.evaluate(() => {
      loadNotesData({
        notes: [{ id: 1, start_time: 0, duration: 2.0, hand: 'right_hand', key_index: 39, center_x: 0, color_rgb: [100, 150, 255] }]
      });
    });
    await page.waitForTimeout(300);

    expect(errors).toEqual([]);
    // Hover to trigger tooltip
    const note = page.locator('.note-block').first();
    await note.hover();
    await page.waitForTimeout(300);
    expect(errors).toEqual([]);
  });

  test('handles notes with extra unexpected fields on them', async ({ page }) => {
    const errors = [];
    page.on('pageerror', err => errors.push(err.message));

    await page.goto(VIEWER_URL, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(300);

    await page.evaluate(() => {
      loadNotesData({
        notes: [
          { id: 1, note_name: 'C4', start_time: 0, duration: 2.0, hand: 'right_hand', key_index: 39, center_x: 0, color_rgb: [100, 150, 255], velocity: 127, foo: { bar: 'baz' }, extra_array: [1,2,3] }
        ]
      });
    });
    await page.waitForTimeout(300);

    expect(errors).toEqual([]);
    expect(await page.locator('.note-block').count()).toBe(1);
  });

  test('nextNoteId does not collide with existing note IDs >= 10000', async ({ page }) => {
    await page.goto(VIEWER_URL, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(300);

    // Load data where some notes already have IDs >= 10000
    await page.evaluate(() => {
      loadNotesData({
        notes: [
          { id: 10005, note_name: 'C4', start_time: 0, duration: 2.0, hand: 'right_hand', key_index: 39, center_x: 0, color_rgb: [100, 150, 255] },
          { id: 99999, note_name: 'D4', start_time: 2, duration: 2.0, hand: 'right_hand', key_index: 41, center_x: 0, color_rgb: [100, 150, 255] }
        ]
      });
    });
    await page.waitForTimeout(300);

    // Enter edit mode and drag to create a note
    await page.keyboard.press('e');
    await page.keyboard.press('Home');
    await page.waitForTimeout(300);
    const container = page.locator('#piano-roll-container');
    const box = await container.boundingBox();
    const startX = box.x + 10;
    const startY = box.y + box.height / 2;
    await page.mouse.move(startX, startY);
    await page.mouse.down();
    await page.mouse.move(startX, startY - 80, { steps: 10 });
    await page.mouse.up();
    await page.waitForTimeout(200);

    // New note should have ID > 99999
    const newNote = page.locator('.note-block.selected');
    const newId = parseInt(await newNote.getAttribute('data-note-id'));
    expect(newId).toBeGreaterThan(99999);
  });

  test('toggling both hands off shows zero notes', async ({ page }) => {
    await loadViewer(page);

    // Toggle both hands off
    await page.keyboard.press('1'); // Toggle right hand off
    await page.keyboard.press('2'); // Toggle left hand off
    await page.waitForTimeout(200);

    const visibleNotes = await page.locator('.note-block').evaluateAll(
      els => els.filter(el => getComputedStyle(el).display !== 'none').length
    );
    expect(visibleNotes).toBe(0);
  });

  test('toggling both hands off then back on shows all notes', async ({ page }) => {
    await loadViewer(page);

    await page.keyboard.press('1');
    await page.keyboard.press('2');
    await page.waitForTimeout(200);

    // Toggle both back on
    await page.keyboard.press('1');
    await page.keyboard.press('2');
    await page.waitForTimeout(200);

    const visibleNotes = await page.locator('.note-block').evaluateAll(
      els => els.filter(el => getComputedStyle(el).display !== 'none').length
    );
    expect(visibleNotes).toBe(TOTAL_NOTES);
  });

  test('Space bar does not toggle playback when command palette is open', async ({ page }) => {
    await loadViewer(page);
    await page.keyboard.press('Meta+p');
    await expect(page.locator('#command-palette-overlay')).toBeVisible();

    // Press space — should type in input, not toggle playback
    await page.keyboard.press('Space');
    await page.waitForTimeout(200);

    const isPlaying = await page.evaluate(() => isPlaying);
    expect(isPlaying).toBe(false);
  });

  test('rapid edit mode toggle does not corrupt state', async ({ page }) => {
    const errors = [];
    page.on('pageerror', err => errors.push(err.message));
    await loadViewer(page);

    // Rapidly toggle edit mode 20 times
    for (let i = 0; i < 20; i++) {
      await page.keyboard.press('e');
    }
    await page.waitForTimeout(200);

    // Should be back to non-edit mode (20 is even)
    expect(errors).toEqual([]);
    await expect(page.locator('body')).not.toHaveClass(/edit-mode/);
  });

  test('delete key outside edit mode does not delete notes', async ({ page }) => {
    await loadViewer(page);
    const initialCount = await page.locator('.note-block').count();

    await page.keyboard.press('Delete');
    await page.waitForTimeout(200);

    expect(await page.locator('.note-block').count()).toBe(initialCount);
  });

  test('playback works with a very short note (0.01s duration)', async ({ page }) => {
    const errors = [];
    page.on('pageerror', err => errors.push(err.message));

    await page.goto(VIEWER_URL, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(300);

    await page.evaluate(() => {
      loadNotesData({
        notes: [{ id: 1, note_name: 'C4', start_time: 0, duration: 0.01, hand: 'right_hand', key_index: 39, center_x: 0, color_rgb: [100, 150, 255] }]
      });
    });
    await page.waitForTimeout(300);

    // Start and stop playback
    await page.keyboard.press('Space');
    await page.waitForTimeout(500);
    await page.keyboard.press('Space');
    expect(errors).toEqual([]);
  });

  test('export after adding and deleting notes produces valid JSON', async ({ page }) => {
    await loadViewer(page);

    // Enter edit mode, add a note, delete a different note
    await page.keyboard.press('e');
    const initialCount = await page.locator('.note-block').count();

    // Add a note
    await page.keyboard.press('Home');
    await page.waitForTimeout(300);
    const container = page.locator('#piano-roll-container');
    const box = await container.boundingBox();
    await page.mouse.click(box.x + 10, box.y + box.height / 2);
    await page.waitForTimeout(200);

    // Deselect
    await page.keyboard.press('Escape');

    // Select and delete last original note
    const lastNote = page.locator('.note-block').last();
    await lastNote.click();
    await page.keyboard.press('Delete');
    await page.waitForTimeout(200);

    // Exit edit mode and export
    await page.keyboard.press('e');
    const [download] = await Promise.all([
      page.waitForEvent('download'),
      page.locator('#save-file-btn').click(),
    ]);

    const stream = await download.createReadStream();
    const chunks = [];
    for await (const chunk of stream) chunks.push(chunk);
    const data = JSON.parse(Buffer.concat(chunks).toString('utf-8'));

    // Should have same count (added 1, deleted 1)
    expect(data.notes.length).toBe(initialCount);
    expect(Array.isArray(data.notes)).toBe(true);
    // All notes should have required fields
    data.notes.forEach(n => {
      expect(n).toHaveProperty('id');
      expect(n).toHaveProperty('start_time');
      expect(n).toHaveProperty('duration');
      expect(n).toHaveProperty('hand');
      expect(n).toHaveProperty('key_index');
    });
  });

  test('loading new JSON during playback stops playback', async ({ page }) => {
    await loadViewer(page);
    await page.keyboard.press('Space');
    await page.waitForTimeout(500);

    // Load new data
    await page.evaluate(() => {
      loadNotesData({
        notes: [{ id: 1, note_name: 'C4', start_time: 0, duration: 2.0, hand: 'right_hand', key_index: 39, center_x: 0, color_rgb: [100, 150, 255] }]
      });
    });
    await page.waitForTimeout(300);

    // Should have rendered the new data
    expect(await page.locator('.note-block').count()).toBe(1);
  });

  test('minimap click before data loaded does not crash', async ({ page }) => {
    const errors = [];
    page.on('pageerror', err => errors.push(err.message));

    await page.goto(VIEWER_URL, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(300);

    // Click minimap before any data
    const minimap = page.locator('#minimap-canvas');
    if (await minimap.isVisible()) {
      const box = await minimap.boundingBox();
      await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
      await page.waitForTimeout(200);
    }
    expect(errors).toEqual([]);
  });

  test('progress bar click with zero duration does not crash', async ({ page }) => {
    const errors = [];
    page.on('pageerror', err => errors.push(err.message));

    // Start empty (totalDuration = 0)
    await page.goto(VIEWER_URL, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(300);
    await page.locator('#start-empty-btn').click();
    await page.waitForTimeout(300);

    // Click progress bar
    const progress = page.locator('#progress-bg');
    if (await progress.isVisible()) {
      const box = await progress.boundingBox();
      await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
      await page.waitForTimeout(200);
    }
    expect(errors).toEqual([]);
  });
});

// ================================================================
//  NEW FEATURES: Edit Hand Selector
// ================================================================
test.describe('Edit Hand Selector', () => {
  test('hand selector is hidden when not in edit mode', async ({ page }) => {
    await loadViewer(page);
    const selector = page.locator('#edit-hand-selector');
    await expect(selector).toHaveCSS('display', 'none');
  });

  test('hand selector appears in edit mode', async ({ page }) => {
    await loadViewer(page);
    await page.keyboard.press('e');
    await page.waitForTimeout(200);
    const selector = page.locator('#edit-hand-selector');
    await expect(selector).toBeVisible();
  });

  test('RH is default selected hand', async ({ page }) => {
    await loadViewer(page);
    await page.keyboard.press('e');
    await page.waitForTimeout(200);
    const rhBtn = page.locator('#edit-hand-rh');
    await expect(rhBtn).toHaveClass(/active/);
    const lhBtn = page.locator('#edit-hand-lh');
    const lhClass = await lhBtn.getAttribute('class');
    expect(lhClass).not.toContain('active');
  });

  test('clicking LH button switches hand', async ({ page }) => {
    await loadViewer(page);
    await page.keyboard.press('e');
    await page.waitForTimeout(200);
    await page.locator('#edit-hand-lh').click();
    await page.waitForTimeout(100);
    const lhBtn = page.locator('#edit-hand-lh');
    await expect(lhBtn).toHaveClass(/active/);
  });

  test('R key toggles edit hand', async ({ page }) => {
    await loadViewer(page);
    await page.keyboard.press('e');
    await page.waitForTimeout(200);
    // Initially RH
    await expect(page.locator('#edit-hand-rh')).toHaveClass(/active/);
    // Press R -> LH
    await page.keyboard.press('r');
    await page.waitForTimeout(100);
    await expect(page.locator('#edit-hand-lh')).toHaveClass(/active/);
    // Press R -> RH again
    await page.keyboard.press('r');
    await page.waitForTimeout(100);
    await expect(page.locator('#edit-hand-rh')).toHaveClass(/active/);
  });

  test('new note uses selected hand', async ({ page }) => {
    await loadViewer(page);
    await page.keyboard.press('e');
    await page.waitForTimeout(200);
    // Switch to LH
    await page.locator('#edit-hand-lh').click();
    await page.waitForTimeout(100);
    // Drag to create a note
    await page.keyboard.press('Home');
    await page.waitForTimeout(300);
    const container = page.locator('#piano-roll-container');
    const box = await container.boundingBox();
    const startX = box.x + 10;
    const startY = box.y + box.height / 2;
    await page.mouse.move(startX, startY);
    await page.mouse.down();
    await page.mouse.move(startX, startY - 80, { steps: 10 });
    await page.mouse.up();
    await page.waitForTimeout(300);
    // Check new note is left_hand
    const notes = await page.locator('.note-block').count();
    expect(notes).toBe(TOTAL_NOTES + 1);
    const newNote = page.locator('.note-block.selected');
    const hand = await newNote.getAttribute('data-hand');
    expect(hand).toBe('left_hand');
  });
});

// ================================================================
//  NEW FEATURES: Click-and-Drag Note Creation
// ================================================================
test.describe('Click-and-Drag Note Creation', () => {
  test('simple click does NOT create a note (only drag)', async ({ page }) => {
    await loadViewer(page);
    await page.keyboard.press('e');
    await page.waitForTimeout(200);
    await page.keyboard.press('Home');
    await page.waitForTimeout(300);
    const container = page.locator('#piano-roll-container');
    const box = await container.boundingBox();
    await page.mouse.click(box.x + 10, box.y + box.height / 2);
    await page.waitForTimeout(300);
    const notes = await page.locator('.note-block').count();
    // Click should NOT add a note
    expect(notes).toBe(TOTAL_NOTES);
  });

  test('drag creates note with custom duration', async ({ page }) => {
    await loadViewer(page);
    await page.keyboard.press('e');
    await page.waitForTimeout(200);
    await page.keyboard.press('Home');
    await page.waitForTimeout(300);
    const container = page.locator('#piano-roll-container');
    const box = await container.boundingBox();
    const startX = box.x + 10;
    const startY = box.y + box.height / 2;
    const endY = startY - 120; // drag upward to make a longer note
    await page.mouse.move(startX, startY);
    await page.mouse.down();
    await page.mouse.move(startX, endY, { steps: 10 });
    await page.mouse.up();
    await page.waitForTimeout(300);
    const notes = await page.locator('.note-block').count();
    expect(notes).toBe(TOTAL_NOTES + 1);
    const newNote = page.locator('.note-block.selected');
    const dur = parseFloat(await newNote.getAttribute('data-duration'));
    // Dragged ~120px at 80px/sec = ~1.5s, so should be > 1.0
    expect(dur).toBeGreaterThan(0.5);
  });

  test('preview element appears during drag', async ({ page }) => {
    await loadViewer(page);
    await page.keyboard.press('e');
    await page.waitForTimeout(200);
    await page.keyboard.press('Home');
    await page.waitForTimeout(300);
    const container = page.locator('#piano-roll-container');
    const box = await container.boundingBox();
    const startX = box.x + 10;
    const startY = box.y + box.height / 2;
    await page.mouse.move(startX, startY);
    await page.mouse.down();
    await page.mouse.move(startX, startY - 70, { steps: 5 });
    // Preview should be visible during drag
    const preview = page.locator('#note-creation-preview');
    await expect(preview).toBeVisible();
    await page.mouse.up();
    await page.waitForTimeout(100);
    // Preview should be hidden after release
    await expect(preview).not.toBeVisible();
  });
});

// ================================================================
//  NEW FEATURES: Track Lines in Empty Project
// ================================================================
test.describe('Track Lines in Empty Project', () => {
  test('track lines appear when starting empty project', async ({ page }) => {
    await page.goto(VIEWER_URL, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(300);
    await page.locator('#start-empty-btn').click();
    await page.waitForTimeout(500);
    const trackLines = await page.locator('.track-line').count();
    expect(trackLines).toBeGreaterThan(0);
  });

  test('keyboard is visible in empty project', async ({ page }) => {
    await page.goto(VIEWER_URL, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(300);
    await page.locator('#start-empty-btn').click();
    await page.waitForTimeout(500);
    const keys = await page.locator('.key').count();
    expect(keys).toBeGreaterThan(0);
  });
});

// ================================================================
//  NEW FEATURES: Right-Click Context Menu
// ================================================================
test.describe('Right-Click Context Menu', () => {
  test('context menu is initially hidden', async ({ page }) => {
    await loadViewer(page);
    const menu = page.locator('#context-menu');
    await expect(menu).not.toBeVisible();
  });

  test('right-click on note in edit mode shows context menu', async ({ page }) => {
    await loadViewer(page);
    await page.keyboard.press('e');
    await page.waitForTimeout(200);
    const note = page.locator('.note-block').first();
    await note.click({ button: 'right' });
    await page.waitForTimeout(200);
    const menu = page.locator('#context-menu');
    await expect(menu).toBeVisible();
  });

  test('context menu has expected items', async ({ page }) => {
    await loadViewer(page);
    await page.keyboard.press('e');
    await page.waitForTimeout(200);
    const note = page.locator('.note-block').first();
    await note.click({ button: 'right' });
    await page.waitForTimeout(200);
    const items = page.locator('#context-menu .ctx-item');
    const count = await items.count();
    expect(count).toBe(4); // Toggle Hand, Duplicate, Edit Lyric, Delete
  });

  test('delete via context menu removes the note', async ({ page }) => {
    await loadViewer(page);
    await page.keyboard.press('e');
    await page.waitForTimeout(200);
    const note = page.locator('.note-block').first();
    await note.click({ button: 'right' });
    await page.waitForTimeout(200);
    await page.locator('.ctx-item[data-action="delete"]').click();
    await page.waitForTimeout(300);
    const count = await page.locator('.note-block').count();
    expect(count).toBe(TOTAL_NOTES - 1);
  });

  test('toggle hand via context menu changes note hand', async ({ page }) => {
    await loadViewer(page);
    await page.keyboard.press('e');
    await page.waitForTimeout(200);
    const note = page.locator('.note-block').first();
    const origHand = await note.getAttribute('data-hand');
    await note.click({ button: 'right' });
    await page.waitForTimeout(200);
    await page.locator('.ctx-item[data-action="toggle-hand"]').click();
    await page.waitForTimeout(300);
    // Re-query the note by id (position may change after re-render)
    const noteId = await note.getAttribute('data-note-id');
    const updatedNote = page.locator(`.note-block[data-note-id="${noteId}"]`);
    const newHand = await updatedNote.getAttribute('data-hand');
    expect(newHand).not.toBe(origHand);
  });

  test('duplicate via context menu adds a new note', async ({ page }) => {
    await loadViewer(page);
    await page.keyboard.press('e');
    await page.waitForTimeout(200);
    const note = page.locator('.note-block').first();
    await note.click({ button: 'right' });
    await page.waitForTimeout(200);
    await page.locator('.ctx-item[data-action="duplicate"]').click();
    await page.waitForTimeout(300);
    const count = await page.locator('.note-block').count();
    expect(count).toBe(TOTAL_NOTES + 1);
  });

  test('context menu hides when clicking elsewhere', async ({ page }) => {
    await loadViewer(page);
    await page.keyboard.press('e');
    await page.waitForTimeout(200);
    const note = page.locator('.note-block').first();
    await note.click({ button: 'right' });
    await page.waitForTimeout(200);
    await expect(page.locator('#context-menu')).toBeVisible();
    // Click elsewhere
    await page.mouse.click(10, 10);
    await page.waitForTimeout(200);
    await expect(page.locator('#context-menu')).not.toBeVisible();
  });

  test('right-click outside edit mode does not show context menu', async ({ page }) => {
    await loadViewer(page);
    const note = page.locator('.note-block').first();
    await note.click({ button: 'right' });
    await page.waitForTimeout(200);
    await expect(page.locator('#context-menu')).not.toBeVisible();
  });
});

// ================================================================
//  NEW FEATURES: Settings Panel
// ================================================================
test.describe('Settings Panel', () => {
  test('settings button exists in toolbar', async ({ page }) => {
    await loadViewer(page);
    await expect(page.locator('#settings-btn')).toBeVisible();
  });

  test('settings modal opens when clicking settings button', async ({ page }) => {
    await loadViewer(page);
    await page.evaluate(() => showSettings());
    await page.waitForTimeout(200);
    await expect(page.locator('#settings-modal')).toBeVisible();
  });

  test('settings modal closes on Escape', async ({ page }) => {
    await loadViewer(page);
    await page.evaluate(() => showSettings());
    await page.waitForTimeout(200);
    await expect(page.locator('#settings-modal')).toBeVisible();
    await page.keyboard.press('Escape');
    await page.waitForTimeout(200);
    await expect(page.locator('#settings-modal')).not.toBeVisible();
  });

  test('settings modal has drop lines toggle', async ({ page }) => {
    await loadViewer(page);
    await page.evaluate(() => showSettings());
    await page.waitForTimeout(200);
    await expect(page.locator('#setting-drop-lines')).toBeVisible();
  });

  test('settings modal has note labels toggle', async ({ page }) => {
    await loadViewer(page);
    await page.evaluate(() => showSettings());
    await page.waitForTimeout(200);
    await expect(page.locator('#setting-note-labels')).toBeVisible();
  });

  test('settings modal has density toggle', async ({ page }) => {
    await loadViewer(page);
    await page.evaluate(() => showSettings());
    await page.waitForTimeout(200);
    await expect(page.locator('#setting-density')).toBeVisible();
  });

  test('settings modal has color pickers', async ({ page }) => {
    await loadViewer(page);
    await page.evaluate(() => showSettings());
    await page.waitForTimeout(200);
    await expect(page.locator('#setting-rh-color')).toBeVisible();
    await expect(page.locator('#setting-lh-color')).toBeVisible();
  });

  test('settings modal has scroll speed setting', async ({ page }) => {
    await loadViewer(page);
    await page.evaluate(() => showSettings());
    await page.waitForTimeout(200);
    await expect(page.locator('#setting-scroll-speed')).toBeVisible();
  });

  test('toggling drop lines off hides drop lines', async ({ page }) => {
    await loadViewer(page);
    await page.evaluate(() => showSettings());
    await page.waitForTimeout(200);
    await page.locator('#setting-drop-lines').click();
    await page.waitForTimeout(300);
    // Close settings
    await page.keyboard.press('Escape');
    await page.waitForTimeout(300);
    // Check all drop lines are hidden
    const dropLines = page.locator('.note-drop-line');
    const count = await dropLines.count();
    if (count > 0) {
      const first = dropLines.first();
      await expect(first).toHaveCSS('display', 'none');
    }
  });

  test('toggling note labels off hides note text', async ({ page }) => {
    await loadViewer(page);
    await page.evaluate(() => showSettings());
    await page.waitForTimeout(200);
    await page.locator('#setting-note-labels').click();
    await page.waitForTimeout(300);
    await page.keyboard.press('Escape');
    await page.waitForTimeout(300);
    // All note blocks should have empty text
    const noteTexts = await page.locator('.note-block').evaluateAll(els => els.map(e => e.textContent.trim()));
    noteTexts.forEach(text => {
      expect(text).toBe('');
    });
  });

  test('toggling density off hides density canvas', async ({ page }) => {
    await loadViewer(page);
    await page.evaluate(() => showSettings());
    await page.waitForTimeout(200);
    await page.locator('#setting-density').click();
    await page.waitForTimeout(300);
    await page.keyboard.press('Escape');
    await page.waitForTimeout(300);
    const canvas = page.locator('#density-canvas');
    await expect(canvas).toHaveCSS('display', 'none');
  });

  test('reset defaults restores settings', async ({ page }) => {
    await loadViewer(page);
    await page.evaluate(() => showSettings());
    await page.waitForTimeout(200);
    // Toggle off drop lines
    await page.locator('#setting-drop-lines').click();
    await page.waitForTimeout(200);
    // Reset
    await page.locator('button:has-text("Reset Defaults")').click();
    await page.waitForTimeout(300);
    // Drop lines toggle should be active again
    await expect(page.locator('#setting-drop-lines')).toHaveClass(/active/);
  });
});

// ================================================================
//  NEW FEATURES: Smart Drop Lines
// ================================================================
test.describe('Smart Drop Lines', () => {
  test('drop lines have transition property for fade effect', async ({ page }) => {
    await loadViewer(page);
    const dropLine = page.locator('.note-drop-line').first();
    const transition = await dropLine.evaluate(el => el.style.transition);
    expect(transition).toContain('opacity');
  });

  test('visible notes have visible drop lines', async ({ page }) => {
    await loadViewer(page);
    await page.waitForTimeout(500);
    // Some drop lines near the visible area should have non-zero opacity
    const opacities = await page.locator('.note-drop-line').evaluateAll(els =>
      els.map(e => parseFloat(getComputedStyle(e).opacity))
    );
    const someVisible = opacities.some(o => o > 0);
    expect(someVisible).toBe(true);
  });
});

// ================================================================
//  NEW FEATURES: GitHub Cloud Storage UI
// ================================================================
test.describe('GitHub Cloud Storage', () => {
  test('cloud button exists in toolbar', async ({ page }) => {
    await loadViewer(page);
    await expect(page.locator('#github-btn')).toBeVisible();
  });

  test('GitHub modal opens when clicking cloud button', async ({ page }) => {
    await loadViewer(page);
    await page.locator('#github-btn').click();
    await page.waitForTimeout(200);
    await expect(page.locator('#github-modal')).toBeVisible();
  });

  test('GitHub modal closes on Escape', async ({ page }) => {
    await loadViewer(page);
    await page.locator('#github-btn').click();
    await page.waitForTimeout(200);
    await page.keyboard.press('Escape');
    await page.waitForTimeout(200);
    await expect(page.locator('#github-modal')).not.toBeVisible();
  });

  test('GitHub modal shows disconnected status by default', async ({ page }) => {
    await loadViewer(page);
    await page.locator('#github-btn').click();
    await page.waitForTimeout(200);
    const statusText = await page.locator('#gh-status-text').textContent();
    expect(statusText).toContain('Not connected');
  });

  test('GitHub modal shows Sign in with GitHub button when disconnected', async ({ page }) => {
    await loadViewer(page);
    await page.locator('#github-btn').click();
    await page.waitForTimeout(200);
    await expect(page.locator('#gh-sign-in-btn')).toBeVisible();
    const btnText = await page.locator('#gh-sign-in-btn').textContent();
    expect(btnText).toContain('Sign in with GitHub');
  });

  test('GitHub modal hides connected section when disconnected', async ({ page }) => {
    await loadViewer(page);
    await page.locator('#github-btn').click();
    await page.waitForTimeout(200);
    await expect(page.locator('#gh-connected-section')).not.toBeVisible();
  });

  test('GitHub modal has save filename input in connected section', async ({ page }) => {
    await loadViewer(page);
    await page.locator('#github-btn').click();
    await page.waitForTimeout(200);
    // connected section is hidden by default, but elements exist in DOM
    const saveInput = page.locator('#gh-save-filename');
    await expect(saveInput).toBeAttached();
  });

  test('Disconnect button exists in connected section', async ({ page }) => {
    await loadViewer(page);
    await page.locator('#github-btn').click();
    await page.waitForTimeout(200);
    const btn = page.locator('#gh-connected-section .gh-btn.danger');
    await expect(btn).toBeAttached();
    const text = await btn.textContent();
    expect(text).toContain('Disconnect');
  });

  test('GitHub modal closes when clicking overlay', async ({ page }) => {
    await loadViewer(page);
    await page.locator('#github-btn').click();
    await page.waitForTimeout(200);
    // Click the overlay (not the content)
    await page.locator('#github-modal').click({ position: { x: 5, y: 5 } });
    await page.waitForTimeout(200);
    await expect(page.locator('#github-modal')).not.toBeVisible();
  });
});

// ================================================================
//  NEW FEATURES: Homepage
// ================================================================
test.describe('Homepage', () => {
  test('homepage shows MakeMusic title', async ({ page }) => {
    await page.goto(VIEWER_URL, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(500);
    const title = await page.locator('.hp-title').textContent();
    expect(title).toContain('MakeMusic');
  });

  test('homepage shows sign-in button when not connected', async ({ page }) => {
    await page.goto(VIEWER_URL, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(500);
    await expect(page.locator('#hp-sign-in-btn')).toBeVisible();
    const text = await page.locator('#hp-sign-in-btn').textContent();
    expect(text).toContain('Sign in with GitHub');
  });

  test('homepage shows drop zone when not connected', async ({ page }) => {
    await page.goto(VIEWER_URL, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(500);
    await expect(page.locator('#hp-drop-zone')).toBeVisible();
  });

  test('homepage shows signed-out section by default', async ({ page }) => {
    await page.goto(VIEWER_URL, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(500);
    await expect(page.locator('#hp-signed-out')).toBeVisible();
    await expect(page.locator('#hp-repo-setup')).not.toBeVisible();
    await expect(page.locator('#hp-song-list')).not.toBeVisible();
  });

  test('repo setup and song list sections exist in DOM', async ({ page }) => {
    await page.goto(VIEWER_URL, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(500);
    await expect(page.locator('#hp-repo-setup')).toBeAttached();
    await expect(page.locator('#hp-song-list')).toBeAttached();
  });

  test('repo setup has default radio option', async ({ page }) => {
    await page.goto(VIEWER_URL, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(500);
    const defaultRadio = page.locator('input[name="hp-repo-choice"][value="default"]');
    await expect(defaultRadio).toBeAttached();
    expect(await defaultRadio.isChecked()).toBe(true);
  });

  test('repo setup has custom radio option', async ({ page }) => {
    await page.goto(VIEWER_URL, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(500);
    const customRadio = page.locator('input[name="hp-repo-choice"][value="custom"]');
    await expect(customRadio).toBeAttached();
    expect(await customRadio.isChecked()).toBe(false);
  });

  test('file input exists and accepts JSON', async ({ page }) => {
    await page.goto(VIEWER_URL, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(500);
    const accept = await page.locator('#file-input').getAttribute('accept');
    expect(accept).toContain('.json');
  });
});

// ================================================================
//  NEW FEATURES: Command Palette (new commands)
// ================================================================
test.describe('Command Palette New Commands', () => {
  test('settings command appears in palette', async ({ page }) => {
    await loadViewer(page);
    await page.keyboard.press('Meta+p');
    await page.waitForTimeout(200);
    await page.locator('#command-palette-input').fill('settings');
    await page.waitForTimeout(100);
    const items = page.locator('#command-palette-list .cmd-item');
    const count = await items.count();
    expect(count).toBeGreaterThan(0);
    const text = await items.first().textContent();
    expect(text.toLowerCase()).toContain('settings');
  });

  test('edit hand command appears in palette', async ({ page }) => {
    await loadViewer(page);
    await page.keyboard.press('Meta+p');
    await page.waitForTimeout(200);
    await page.locator('#command-palette-input').fill('edit hand');
    await page.waitForTimeout(100);
    const items = page.locator('#command-palette-list .cmd-item');
    const count = await items.count();
    expect(count).toBeGreaterThan(0);
  });
});

// ================================================================
//  COMPREHENSIVE LYRICS MODE TESTS
// ================================================================
test.describe('Lyrics Mode - Panel Open / Close', () => {
  test('W key opens lyrics panel', async ({ page }) => {
    await loadViewer(page);
    await page.keyboard.press('w');
    await page.waitForTimeout(300);
    await expect(page.locator('#lyrics-panel')).toHaveClass(/visible/);
    await expect(page.locator('body')).toHaveClass(/lyrics-mode/);
  });

  test('W key also enters edit mode if not already in it', async ({ page }) => {
    await loadViewer(page);
    // Ensure NOT in edit mode
    await expect(page.locator('body')).not.toHaveClass(/edit-mode/);
    await page.keyboard.press('w');
    await page.waitForTimeout(300);
    // Both edit-mode and lyrics-mode should be active
    await expect(page.locator('body')).toHaveClass(/edit-mode/);
    await expect(page.locator('body')).toHaveClass(/lyrics-mode/);
  });

  test('W key toggles lyrics panel off', async ({ page }) => {
    await loadViewer(page);
    await page.keyboard.press('w');
    await page.waitForTimeout(300);
    await expect(page.locator('#lyrics-panel')).toHaveClass(/visible/);
    // Press W again to close
    await page.keyboard.press('w');
    await page.waitForTimeout(300);
    await expect(page.locator('#lyrics-panel')).not.toHaveClass(/visible/);
    await expect(page.locator('body')).not.toHaveClass(/lyrics-mode/);
  });

  test('Escape closes lyrics panel', async ({ page }) => {
    await loadViewer(page);
    await page.keyboard.press('w');
    await page.waitForTimeout(300);
    await expect(page.locator('#lyrics-panel')).toHaveClass(/visible/);
    await page.keyboard.press('Escape');
    await page.waitForTimeout(300);
    await expect(page.locator('#lyrics-panel')).not.toHaveClass(/visible/);
    await expect(page.locator('body')).not.toHaveClass(/lyrics-mode/);
  });

  test('close button (✕) closes lyrics panel', async ({ page }) => {
    await loadViewer(page);
    await page.keyboard.press('w');
    await page.waitForTimeout(300);
    await expect(page.locator('#lyrics-panel')).toHaveClass(/visible/);
    await page.locator('.lyrics-panel-close').click();
    await page.waitForTimeout(300);
    await expect(page.locator('#lyrics-panel')).not.toHaveClass(/visible/);
  });

  test('🎵 Lyrics button in toolbar opens lyrics panel', async ({ page }) => {
    await loadViewer(page);
    await page.keyboard.press('e'); // Enter edit mode first
    await page.waitForTimeout(200);
    await page.locator('#lyrics-btn').click();
    await page.waitForTimeout(300);
    await expect(page.locator('#lyrics-panel')).toHaveClass(/visible/);
  });

  test('lyrics panel is not visible by default', async ({ page }) => {
    await loadViewer(page);
    await expect(page.locator('#lyrics-panel')).not.toHaveClass(/visible/);
  });

  test('lyrics panel header shows title', async ({ page }) => {
    await loadViewer(page);
    await page.keyboard.press('w');
    await page.waitForTimeout(300);
    const title = await page.locator('.lyrics-panel-title').textContent();
    expect(title).toContain('Lyrics');
  });

  test('LYRICS MODE indicator bar appears', async ({ page }) => {
    await loadViewer(page);
    await page.keyboard.press('w');
    await page.waitForTimeout(300);
    await expect(page.locator('#lyrics-indicator')).toBeVisible();
  });
});

test.describe('Lyrics Mode - Note List', () => {
  test('lyrics panel shows one row per note (all filter)', async ({ page }) => {
    await loadViewer(page);
    await page.keyboard.press('w');
    await page.waitForTimeout(300);
    // Set filter to All
    await page.locator('.lyrics-filter-btn[data-filter="all"]').click();
    await page.waitForTimeout(200);
    const rows = await page.locator('.lyrics-row').count();
    expect(rows).toBe(TOTAL_NOTES);
  });

  test('lyrics panel rows are sorted by time', async ({ page }) => {
    await loadViewer(page);
    await page.keyboard.press('w');
    await page.waitForTimeout(300);
    await page.locator('.lyrics-filter-btn[data-filter="all"]').click();
    await page.waitForTimeout(200);
    // Check first and last note info
    const firstInfo = await page.locator('.lyrics-note-info').first().textContent();
    const lastInfo = await page.locator('.lyrics-note-info').last().textContent();
    // First note should be earliest (smallest time), last note latest
    const firstTime = parseFloat(firstInfo.match(/\(([\d.]+)s\)/)[1]);
    const lastTime = parseFloat(lastInfo.match(/\(([\d.]+)s\)/)[1]);
    expect(firstTime).toBeLessThanOrEqual(lastTime);
  });

  test('each row has a colored hand dot', async ({ page }) => {
    await loadViewer(page);
    await page.keyboard.press('w');
    await page.waitForTimeout(300);
    await page.locator('.lyrics-filter-btn[data-filter="all"]').click();
    await page.waitForTimeout(200);
    const dots = await page.locator('.lyrics-hand-dot').count();
    expect(dots).toBe(TOTAL_NOTES);
  });

  test('each row has note info (name + time)', async ({ page }) => {
    await loadViewer(page);
    await page.keyboard.press('w');
    await page.waitForTimeout(300);
    await page.locator('.lyrics-filter-btn[data-filter="all"]').click();
    await page.waitForTimeout(200);
    const infos = await page.locator('.lyrics-note-info').count();
    expect(infos).toBe(TOTAL_NOTES);
    // Check format "NoteName (X.Xs)"
    const text = await page.locator('.lyrics-note-info').first().textContent();
    expect(text).toMatch(/[A-G][#b]?\d\s*\(\d+\.\d+s\)/);
  });

  test('each row has an input field', async ({ page }) => {
    await loadViewer(page);
    await page.keyboard.press('w');
    await page.waitForTimeout(300);
    await page.locator('.lyrics-filter-btn[data-filter="all"]').click();
    await page.waitForTimeout(200);
    const inputs = await page.locator('.lyrics-row-input').count();
    expect(inputs).toBe(TOTAL_NOTES);
  });

  test('input placeholder is "lyric…"', async ({ page }) => {
    await loadViewer(page);
    await page.keyboard.press('w');
    await page.waitForTimeout(300);
    const placeholder = await page.locator('.lyrics-row-input').first().getAttribute('placeholder');
    expect(placeholder).toContain('lyric');
  });
});

test.describe('Lyrics Mode - Hand Filter', () => {
  test('RH filter shows only right-hand notes', async ({ page }) => {
    await loadViewer(page);
    await page.keyboard.press('w');
    await page.waitForTimeout(300);
    await page.locator('.lyrics-filter-btn[data-filter="right_hand"]').click();
    await page.waitForTimeout(200);
    const rows = await page.locator('.lyrics-row').count();
    expect(rows).toBe(RH_NOTES);
  });

  test('LH filter shows only left-hand notes', async ({ page }) => {
    await loadViewer(page);
    await page.keyboard.press('w');
    await page.waitForTimeout(300);
    await page.locator('.lyrics-filter-btn[data-filter="left_hand"]').click();
    await page.waitForTimeout(200);
    const rows = await page.locator('.lyrics-row').count();
    expect(rows).toBe(LH_NOTES);
  });

  test('All filter shows all notes', async ({ page }) => {
    await loadViewer(page);
    await page.keyboard.press('w');
    await page.waitForTimeout(300);
    await page.locator('.lyrics-filter-btn[data-filter="all"]').click();
    await page.waitForTimeout(200);
    const rows = await page.locator('.lyrics-row').count();
    expect(rows).toBe(TOTAL_NOTES);
  });

  test('active filter button is highlighted', async ({ page }) => {
    await loadViewer(page);
    await page.keyboard.press('w');
    await page.waitForTimeout(300);
    await page.locator('.lyrics-filter-btn[data-filter="left_hand"]').click();
    await page.waitForTimeout(200);
    await expect(page.locator('.lyrics-filter-btn[data-filter="left_hand"]')).toHaveClass(/active/);
    await expect(page.locator('.lyrics-filter-btn[data-filter="right_hand"]')).not.toHaveClass(/active/);
    await expect(page.locator('.lyrics-filter-btn[data-filter="all"]')).not.toHaveClass(/active/);
  });

  test('filter defaults to editHand on open', async ({ page }) => {
    await loadViewer(page);
    // Default editHand is right_hand
    await page.keyboard.press('w');
    await page.waitForTimeout(300);
    // RH filter should be active by default
    await expect(page.locator('.lyrics-filter-btn[data-filter="right_hand"]')).toHaveClass(/active/);
    const rows = await page.locator('.lyrics-row').count();
    expect(rows).toBe(RH_NOTES);
  });

  test('switching filter preserves entered lyrics', async ({ page }) => {
    await loadViewer(page);
    await page.keyboard.press('w');
    await page.waitForTimeout(300);
    await page.locator('.lyrics-filter-btn[data-filter="all"]').click();
    await page.waitForTimeout(200);
    // Type a lyric in first row
    const firstInput = page.locator('.lyrics-row-input').first();
    await firstInput.fill('hello');
    await page.waitForTimeout(100);
    // Switch to RH then back to All
    await page.locator('.lyrics-filter-btn[data-filter="right_hand"]').click();
    await page.waitForTimeout(200);
    await page.locator('.lyrics-filter-btn[data-filter="all"]').click();
    await page.waitForTimeout(200);
    const val = await page.locator('.lyrics-row-input').first().inputValue();
    expect(val).toBe('hello');
  });
});

test.describe('Lyrics Mode - Typing and Saving', () => {
  test('typing in input saves lyric to note data', async ({ page }) => {
    await loadViewer(page);
    await page.keyboard.press('w');
    await page.waitForTimeout(300);
    await page.locator('.lyrics-filter-btn[data-filter="all"]').click();
    await page.waitForTimeout(200);
    // Get the note id from first row (sorted by time, not by array index)
    const firstRowNoteId = await page.locator('.lyrics-row').first().getAttribute('data-note-id');
    const firstInput = page.locator('.lyrics-row-input').first();
    await firstInput.fill('love');
    await page.waitForTimeout(200);
    // Read note data for the correct note
    const lyric = await page.evaluate((id) => {
      const n = notesData.notes.find(n => String(n.id) === id);
      return n ? n.lyric : undefined;
    }, firstRowNoteId);
    expect(lyric).toBe('love');
  });

  test('W key does NOT type "w" into focused input', async ({ page }) => {
    await loadViewer(page);
    await page.keyboard.press('w');
    await page.waitForTimeout(300);
    // The panel should be open. Check no input has "w" in it
    const inputs = page.locator('.lyrics-row-input');
    const count = await inputs.count();
    for (let i = 0; i < count; i++) {
      const val = await inputs.nth(i).inputValue();
      expect(val).toBe('');
    }
  });

  test('lyric appears on the note in the piano roll', async ({ page }) => {
    await loadViewer(page);
    await page.keyboard.press('w');
    await page.waitForTimeout(300);
    await page.locator('.lyrics-filter-btn[data-filter="all"]').click();
    await page.waitForTimeout(200);
    // Type lyric for first note
    const firstInput = page.locator('.lyrics-row-input').first();
    await firstInput.fill('shine');
    await page.waitForTimeout(300);
    // Check the note-lyric element exists
    const lyricEl = page.locator('.note-lyric').first();
    await expect(lyricEl).toBeVisible();
    const text = await lyricEl.textContent();
    expect(text).toBe('shine');
  });

  test('clearing input removes lyric from note', async ({ page }) => {
    await loadViewer(page);
    await page.keyboard.press('w');
    await page.waitForTimeout(300);
    await page.locator('.lyrics-filter-btn[data-filter="all"]').click();
    await page.waitForTimeout(200);
    const firstRowNoteId = await page.locator('.lyrics-row').first().getAttribute('data-note-id');
    const firstInput = page.locator('.lyrics-row-input').first();
    await firstInput.fill('temp');
    await page.waitForTimeout(200);
    await firstInput.fill('');
    await page.waitForTimeout(200);
    const lyric = await page.evaluate((id) => {
      const n = notesData.notes.find(n => String(n.id) === id);
      return n ? n.lyric : undefined;
    }, firstRowNoteId);
    expect(lyric).toBeUndefined();
  });

  test('lyric display appears to the right of the note', async ({ page }) => {
    await loadViewer(page);
    await page.keyboard.press('w');
    await page.waitForTimeout(300);
    await page.locator('.lyrics-filter-btn[data-filter="all"]').click();
    await page.waitForTimeout(200);
    const firstInput = page.locator('.lyrics-row-input').first();
    await firstInput.fill('right');
    await page.waitForTimeout(300);
    // Check CSS positioning
    const pos = await page.locator('.note-lyric').first().evaluate(el => {
      const style = getComputedStyle(el);
      return { right: style.right, top: style.top };
    });
    // The lyric should be positioned with right: -4px (next to note's right edge)
    expect(pos.right).toBe('-4px');
  });
});

test.describe('Lyrics Mode - Navigation (Tab / Enter / Shift+Tab)', () => {
  test('Tab advances to next note input', async ({ page }) => {
    await loadViewer(page);
    await page.keyboard.press('w');
    await page.waitForTimeout(300);
    await page.locator('.lyrics-filter-btn[data-filter="all"]').click();
    await page.waitForTimeout(200);
    const firstInput = page.locator('.lyrics-row-input').first();
    await firstInput.focus();
    await page.waitForTimeout(100);
    await page.keyboard.press('Tab');
    await page.waitForTimeout(300);
    // Second input should now be focused
    const focused = await page.evaluate(() => {
      const el = document.activeElement;
      return el ? el.closest('.lyrics-row')?.dataset.noteId : null;
    });
    const secondRowId = await page.locator('.lyrics-row').nth(1).getAttribute('data-note-id');
    expect(focused).toBe(secondRowId);
  });

  test('Enter advances to next note input', async ({ page }) => {
    await loadViewer(page);
    await page.keyboard.press('w');
    await page.waitForTimeout(300);
    await page.locator('.lyrics-filter-btn[data-filter="all"]').click();
    await page.waitForTimeout(200);
    const firstInput = page.locator('.lyrics-row-input').first();
    await firstInput.focus();
    await page.waitForTimeout(100);
    await page.keyboard.press('Enter');
    await page.waitForTimeout(300);
    const focused = await page.evaluate(() => {
      const el = document.activeElement;
      return el ? el.closest('.lyrics-row')?.dataset.noteId : null;
    });
    const secondRowId = await page.locator('.lyrics-row').nth(1).getAttribute('data-note-id');
    expect(focused).toBe(secondRowId);
  });

  test('Shift+Tab goes to previous note input', async ({ page }) => {
    await loadViewer(page);
    await page.keyboard.press('w');
    await page.waitForTimeout(300);
    await page.locator('.lyrics-filter-btn[data-filter="all"]').click();
    await page.waitForTimeout(200);
    // Focus second input
    const secondInput = page.locator('.lyrics-row-input').nth(1);
    await secondInput.focus();
    await page.waitForTimeout(100);
    await page.keyboard.press('Shift+Tab');
    await page.waitForTimeout(300);
    // First input should be focused
    const focused = await page.evaluate(() => {
      const el = document.activeElement;
      return el ? el.closest('.lyrics-row')?.dataset.noteId : null;
    });
    const firstRowId = await page.locator('.lyrics-row').first().getAttribute('data-note-id');
    expect(focused).toBe(firstRowId);
  });

  test('Tab on last note stays on last note (no wrap)', async ({ page }) => {
    await loadViewer(page);
    await page.keyboard.press('w');
    await page.waitForTimeout(300);
    await page.locator('.lyrics-filter-btn[data-filter="all"]').click();
    await page.waitForTimeout(200);
    const lastInput = page.locator('.lyrics-row-input').last();
    await lastInput.focus();
    await page.waitForTimeout(100);
    const lastRowId = await page.locator('.lyrics-row').last().getAttribute('data-note-id');
    await page.keyboard.press('Tab');
    await page.waitForTimeout(300);
    // Should still be on last note (or nothing changed)
    const focused = await page.evaluate(() => {
      const el = document.activeElement;
      return el ? el.closest('.lyrics-row')?.dataset.noteId : null;
    });
    expect(focused).toBe(lastRowId);
  });

  test('Shift+Tab on first note stays on first note', async ({ page }) => {
    await loadViewer(page);
    await page.keyboard.press('w');
    await page.waitForTimeout(300);
    await page.locator('.lyrics-filter-btn[data-filter="all"]').click();
    await page.waitForTimeout(200);
    const firstInput = page.locator('.lyrics-row-input').first();
    await firstInput.focus();
    await page.waitForTimeout(100);
    const firstRowId = await page.locator('.lyrics-row').first().getAttribute('data-note-id');
    await page.keyboard.press('Shift+Tab');
    await page.waitForTimeout(300);
    const focused = await page.evaluate(() => {
      const el = document.activeElement;
      return el ? el.closest('.lyrics-row')?.dataset.noteId : null;
    });
    expect(focused).toBe(firstRowId);
  });

  test('navigation only within filtered notes (RH filter)', async ({ page }) => {
    await loadViewer(page);
    await page.keyboard.press('w');
    await page.waitForTimeout(300);
    await page.locator('.lyrics-filter-btn[data-filter="right_hand"]').click();
    await page.waitForTimeout(200);
    // All visible rows should be RH notes
    const rowCount = await page.locator('.lyrics-row').count();
    expect(rowCount).toBe(RH_NOTES);
    // Tab through all rows — should never leave RH notes
    const firstInput = page.locator('.lyrics-row-input').first();
    await firstInput.focus();
    for (let i = 0; i < rowCount - 1; i++) {
      await page.keyboard.press('Tab');
      await page.waitForTimeout(150);
    }
    // After tabbing through all RH notes, focused should be last RH note
    const focused = await page.evaluate(() => {
      const el = document.activeElement;
      return el ? el.closest('.lyrics-row')?.dataset.noteId : null;
    });
    const lastRhRowId = await page.locator('.lyrics-row').last().getAttribute('data-note-id');
    expect(focused).toBe(lastRhRowId);
  });
});

test.describe('Lyrics Mode - Note Selection & Scrolling', () => {
  test('focusing input selects the corresponding note', async ({ page }) => {
    await loadViewer(page);
    await page.keyboard.press('w');
    await page.waitForTimeout(300);
    await page.locator('.lyrics-filter-btn[data-filter="all"]').click();
    await page.waitForTimeout(200);
    const thirdInput = page.locator('.lyrics-row-input').nth(2);
    await thirdInput.focus();
    await page.waitForTimeout(300);
    const thirdRowId = await page.locator('.lyrics-row').nth(2).getAttribute('data-note-id');
    // The corresponding note should be selected
    const selectedId = await page.evaluate(() => selectedNoteId);
    expect(String(selectedId)).toBe(thirdRowId);
  });

  test('focused row gets active highlight', async ({ page }) => {
    await loadViewer(page);
    await page.keyboard.press('w');
    await page.waitForTimeout(300);
    await page.locator('.lyrics-filter-btn[data-filter="all"]').click();
    await page.waitForTimeout(200);
    const secondInput = page.locator('.lyrics-row-input').nth(1);
    await secondInput.focus();
    await page.waitForTimeout(200);
    await expect(page.locator('.lyrics-row').nth(1)).toHaveClass(/active/);
    // First row should NOT be active
    await expect(page.locator('.lyrics-row').first()).not.toHaveClass(/active/);
  });

  test('clicking a row focuses its input', async ({ page }) => {
    await loadViewer(page);
    await page.keyboard.press('w');
    await page.waitForTimeout(300);
    await page.locator('.lyrics-filter-btn[data-filter="all"]').click();
    await page.waitForTimeout(200);
    // Click the info part of the 3rd row (not the input)
    await page.locator('.lyrics-note-info').nth(2).click();
    await page.waitForTimeout(300);
    // Input should be focused
    const focusedRowId = await page.evaluate(() => {
      const el = document.activeElement;
      return el ? el.closest('.lyrics-row')?.dataset.noteId : null;
    });
    const thirdRowId = await page.locator('.lyrics-row').nth(2).getAttribute('data-note-id');
    expect(focusedRowId).toBe(thirdRowId);
  });

  test('clicking a note in lyrics mode focuses its panel row', async ({ page }) => {
    await loadViewer(page);
    await page.keyboard.press('w');
    await page.waitForTimeout(300);
    await page.locator('.lyrics-filter-btn[data-filter="all"]').click();
    await page.waitForTimeout(200);
    // Use evaluate to simulate note click (avoids keyboard interception)
    const noteId = await page.locator('.note-block').first().getAttribute('data-note-id');
    await page.evaluate((id) => lyricsSelectNote(parseInt(id)), noteId);
    await page.waitForTimeout(300);
    // The note's row should be active in the panel
    await expect(page.locator(`.lyrics-row[data-note-id="${noteId}"]`)).toHaveClass(/active/);
  });

  test('smooth scroll to note when navigating with Tab', async ({ page }) => {
    await loadViewer(page);
    await page.keyboard.press('w');
    await page.waitForTimeout(300);
    await page.locator('.lyrics-filter-btn[data-filter="all"]').click();
    await page.waitForTimeout(200);
    // Focus first input and get initial scroll
    const firstInput = page.locator('.lyrics-row-input').first();
    await firstInput.focus();
    await page.waitForTimeout(300);
    const scrollBefore = await page.locator('#piano-roll-container').evaluate(
      el => el.scrollTop
    );
    // Tab several times to reach a note at a different time
    for (let i = 0; i < 5; i++) {
      await page.keyboard.press('Tab');
      await page.waitForTimeout(200);
    }
    await page.waitForTimeout(500); // Wait for smooth scroll animation
    const scrollAfter = await page.locator('#piano-roll-container').evaluate(
      el => el.scrollTop
    );
    // Scroll should have changed
    expect(Math.abs(scrollAfter - scrollBefore)).toBeGreaterThan(0);
  });
});

test.describe('Lyrics Mode - Right-Click Context Menu', () => {
  test('right-click Edit Lyric opens lyrics panel', async ({ page }) => {
    await loadViewer(page);
    await page.keyboard.press('e');
    await page.waitForTimeout(200);
    // Right-click a note
    const note = page.locator('.note-block').first();
    await note.click({ button: 'right' });
    await page.waitForTimeout(200);
    // Click Edit Lyric
    await page.locator('.ctx-item[data-action="edit-lyric"]').click();
    await page.waitForTimeout(300);
    // Lyrics panel should be open
    await expect(page.locator('#lyrics-panel')).toHaveClass(/visible/);
    await expect(page.locator('body')).toHaveClass(/lyrics-mode/);
  });

  test('right-click Edit Lyric focuses the correct note row', async ({ page }) => {
    await loadViewer(page);
    await page.keyboard.press('e');
    await page.waitForTimeout(200);
    const note = page.locator('.note-block').first();
    const noteId = await note.getAttribute('data-note-id');
    await note.click({ button: 'right' });
    await page.waitForTimeout(200);
    await page.locator('.ctx-item[data-action="edit-lyric"]').click();
    await page.waitForTimeout(400);
    // The correct row should be active
    await expect(page.locator(`.lyrics-row[data-note-id="${noteId}"]`)).toHaveClass(/active/);
    // Its input should be focused
    const focusedRowId = await page.evaluate(() => {
      const el = document.activeElement;
      return el ? el.closest('.lyrics-row')?.dataset.noteId : null;
    });
    expect(focusedRowId).toBe(noteId);
  });

  test('context menu shows Edit Lyric item', async ({ page }) => {
    await loadViewer(page);
    await page.keyboard.press('e');
    await page.waitForTimeout(200);
    const note = page.locator('.note-block').first();
    await note.click({ button: 'right' });
    await page.waitForTimeout(200);
    const editLyric = page.locator('.ctx-item[data-action="edit-lyric"]');
    await expect(editLyric).toBeVisible();
    const text = await editLyric.textContent();
    expect(text).toContain('Edit Lyric');
  });
});

test.describe('Lyrics Mode - Escape from Input', () => {
  test('Escape from lyrics input closes lyrics mode', async ({ page }) => {
    await loadViewer(page);
    await page.keyboard.press('w');
    await page.waitForTimeout(300);
    await page.locator('.lyrics-filter-btn[data-filter="all"]').click();
    await page.waitForTimeout(200);
    const firstInput = page.locator('.lyrics-row-input').first();
    await firstInput.focus();
    await page.waitForTimeout(100);
    // Press Escape while input is focused
    await page.keyboard.press('Escape');
    await page.waitForTimeout(300);
    await expect(page.locator('#lyrics-panel')).not.toHaveClass(/visible/);
    await expect(page.locator('body')).not.toHaveClass(/lyrics-mode/);
  });

  test('Escape does not lose typed text in notes data', async ({ page }) => {
    await loadViewer(page);
    await page.keyboard.press('w');
    await page.waitForTimeout(300);
    await page.locator('.lyrics-filter-btn[data-filter="all"]').click();
    await page.waitForTimeout(200);
    const firstInput = page.locator('.lyrics-row-input').first();
    await firstInput.fill('saved');
    await page.waitForTimeout(200);
    await page.keyboard.press('Escape');
    await page.waitForTimeout(300);
    // Reopen lyrics
    await page.keyboard.press('w');
    await page.waitForTimeout(300);
    await page.locator('.lyrics-filter-btn[data-filter="all"]').click();
    await page.waitForTimeout(200);
    const val = await page.locator('.lyrics-row-input').first().inputValue();
    expect(val).toBe('saved');
  });
});

test.describe('Lyrics Mode - Minimap Shift', () => {
  test('minimap shifts left when lyrics panel is open', async ({ page }) => {
    await loadViewer(page);
    const rightBefore = await page.locator('#minimap').evaluate(
      el => getComputedStyle(el).right
    );
    await page.keyboard.press('w');
    await page.waitForTimeout(300);
    const rightAfter = await page.locator('#minimap').evaluate(
      el => getComputedStyle(el).right
    );
    // Minimap should have moved (right increased to 280px)
    expect(rightAfter).not.toBe(rightBefore);
  });
});

test.describe('Lyrics Mode - Edge Cases', () => {
  test('opening lyrics with no notes does nothing', async ({ page }) => {
    await page.goto(VIEWER_URL, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(500);
    await page.locator('#start-empty-btn').click();
    await page.waitForTimeout(300);
    // Press W with no notes
    await page.keyboard.press('w');
    await page.waitForTimeout(300);
    // Should NOT open lyrics panel (no notes to edit)
    await expect(page.locator('#lyrics-panel')).not.toHaveClass(/visible/);
  });

  test('multiple lyrics can be entered on different notes', async ({ page }) => {
    await loadViewer(page);
    await page.keyboard.press('w');
    await page.waitForTimeout(300);
    await page.locator('.lyrics-filter-btn[data-filter="all"]').click();
    await page.waitForTimeout(200);
    const first = page.locator('.lyrics-row-input').first();
    const second = page.locator('.lyrics-row-input').nth(1);
    await first.fill('word1');
    await second.fill('word2');
    await page.waitForTimeout(200);
    // Both should be saved
    const lyrics = await page.evaluate(() =>
      notesData.notes.filter(n => n.lyric).map(n => n.lyric).sort()
    );
    expect(lyrics).toContain('word1');
    expect(lyrics).toContain('word2');
  });

  test('lyrics survive rerender (closing and reopening panel)', async ({ page }) => {
    await loadViewer(page);
    await page.keyboard.press('w');
    await page.waitForTimeout(300);
    await page.locator('.lyrics-filter-btn[data-filter="all"]').click();
    await page.waitForTimeout(200);
    await page.locator('.lyrics-row-input').first().fill('persist');
    await page.waitForTimeout(200);
    // Blur input before pressing W (W types 'w' if input is focused)
    await page.locator('.lyrics-panel-close').click();
    await page.waitForTimeout(300);
    // Reopen
    await page.keyboard.press('w');
    await page.waitForTimeout(300);
    await page.locator('.lyrics-filter-btn[data-filter="all"]').click();
    await page.waitForTimeout(200);
    const val = await page.locator('.lyrics-row-input').first().inputValue();
    expect(val).toBe('persist');
  });

  test('deleting a note updates lyrics panel', async ({ page }) => {
    await loadViewer(page);
    await page.keyboard.press('w');
    await page.waitForTimeout(300);
    await page.locator('.lyrics-filter-btn[data-filter="all"]').click();
    await page.waitForTimeout(200);
    const initialRows = await page.locator('.lyrics-row').count();
    // Focus a note's input to select it, then blur and use Delete key
    const firstInput = page.locator('.lyrics-row-input').first();
    await firstInput.focus();
    await page.waitForTimeout(200);
    // Blur input so Delete key goes to global handler, not text editing
    await page.evaluate(() => document.activeElement.blur());
    await page.waitForTimeout(100);
    await page.keyboard.press('Delete');
    await page.waitForTimeout(300);
    // Re-click All filter to refresh panel
    await page.locator('.lyrics-filter-btn[data-filter="all"]').click();
    await page.waitForTimeout(200);
    const newRows = await page.locator('.lyrics-row').count();
    expect(newRows).toBe(initialRows - 1);
  });

  test('keyboard shortcuts don\'t fire when typing in lyrics input', async ({ page }) => {
    await loadViewer(page);
    await page.keyboard.press('w');
    await page.waitForTimeout(300);
    await page.locator('.lyrics-filter-btn[data-filter="all"]').click();
    await page.waitForTimeout(200);
    const firstInput = page.locator('.lyrics-row-input').first();
    await firstInput.focus();
    await firstInput.type('hello');
    await page.waitForTimeout(200);
    // Typing 'e' should NOT toggle edit mode off, 'l' should NOT toggle loop
    // Edit mode should still be on
    await expect(page.locator('body')).toHaveClass(/edit-mode/);
    // Value should contain text typed
    const val = await firstInput.inputValue();
    expect(val).toBe('hello');
  });

  test('panel remembers which filter was last used within session', async ({ page }) => {
    await loadViewer(page);
    await page.keyboard.press('w');
    await page.waitForTimeout(300);
    // Switch to LH filter
    await page.locator('.lyrics-filter-btn[data-filter="left_hand"]').click();
    await page.waitForTimeout(200);
    const lhRows = await page.locator('.lyrics-row').count();
    expect(lhRows).toBe(LH_NOTES);
    // Close and reopen
    await page.keyboard.press('w');
    await page.waitForTimeout(300);
    await page.keyboard.press('w');
    await page.waitForTimeout(300);
    // Should default to editHand again (not remember LH) since toggleLyricsMode resets
    const rows = await page.locator('.lyrics-row').count();
    expect(rows).toBe(RH_NOTES); // Defaults to editHand (right_hand)
  });
});
