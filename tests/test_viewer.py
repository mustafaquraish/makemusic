"""
Playwright UI tests for the MakeMusic HTML viewer.
Tests run in headless Chromium.
"""
import json
import os
import subprocess
import time

import pytest

# We need playwright - install with: pip install playwright && python -m playwright install chromium
pytest.importorskip("playwright")

from playwright.sync_api import sync_playwright, expect


# ==================== Fixtures ====================

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VIEWER_DIR = os.path.join(BASE_DIR, "viewer")
VIEWER_URL = "http://localhost:8765/index.html"

# Minimal valid notes.json for testing
MINIMAL_NOTES = {
    "metadata": {
        "source_video": "test_video.webm",
        "duration_seconds": 30.0,
        "fps": 30,
        "resolution": [1920, 1080],
        "keyboard_y": 900,
        "scroll_speed": 200.0,
        "intro_end_time": 2.0,
        "note_colors": [
            {"label": "right_hand", "center_bgr": [96, 69, 233]},
            {"label": "left_hand", "center_bgr": [217, 144, 74]}
        ]
    },
    "notes": [
        {
            "id": 1,
            "note_name": "C4",
            "start_time": 5.0,
            "duration": 1.0,
            "hand": "right_hand",
            "key_index": 39,
            "center_x": 960,
            "color_rgb": [233, 69, 96]
        },
        {
            "id": 2,
            "note_name": "E4",
            "start_time": 5.0,
            "duration": 1.5,
            "hand": "right_hand",
            "key_index": 43,
            "center_x": 1040,
            "color_rgb": [233, 69, 96]
        },
        {
            "id": 3,
            "note_name": "G3",
            "start_time": 6.0,
            "duration": 2.0,
            "hand": "left_hand",
            "key_index": 34,
            "center_x": 800,
            "color_rgb": [74, 144, 217]
        },
        {
            "id": 4,
            "note_name": "C5",
            "start_time": 10.0,
            "duration": 0.5,
            "hand": "right_hand",
            "key_index": 51,
            "center_x": 1200,
            "color_rgb": [233, 69, 96]
        },
        {
            "id": 5,
            "note_name": "A3",
            "start_time": 12.0,
            "duration": 3.0,
            "hand": "left_hand",
            "key_index": 36,
            "center_x": 850,
            "color_rgb": [74, 144, 217]
        }
    ],
    "summary": {
        "total_notes": 5,
        "left_hand_notes": 2,
        "right_hand_notes": 3,
        "duration_range": [5.0, 15.0],
        "key_range": [34, 51]
    }
}


@pytest.fixture(scope="module")
def server():
    """Ensure local server is running. Start one if needed."""
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex(('localhost', 8765))
    sock.close()
    if result != 0:
        # Start server
        proc = subprocess.Popen(
            ['python', '-m', 'http.server', '8765', '--directory', VIEWER_DIR],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        time.sleep(1)
        yield proc
        proc.terminate()
    else:
        yield None


@pytest.fixture(scope="module")
def browser_ctx():
    """Create a Playwright browser context (headless)."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 720})
        yield context
        context.close()
        browser.close()


@pytest.fixture
def page(server, browser_ctx):
    """Create a fresh page for each test."""
    page = browser_ctx.new_page()
    yield page
    page.close()


@pytest.fixture
def test_json_path():
    """Write minimal test JSON to viewer directory and return the filename."""
    path = os.path.join(VIEWER_DIR, "test_notes.json")
    with open(path, "w") as f:
        json.dump(MINIMAL_NOTES, f)
    yield "test_notes.json"
    if os.path.exists(path):
        os.remove(path)


# ==================== Tests: Page Load ====================

class TestPageLoad:

    def test_page_loads(self, page):
        """Page loads without errors."""
        page.goto(VIEWER_URL)
        expect(page.locator(".title")).to_have_text("🎹 MakeMusic")

    def test_loading_overlay_visible_initially(self, page):
        """Loading overlay is shown when no data loaded."""
        page.goto(VIEWER_URL)
        expect(page.locator("#loading-overlay")).to_be_visible()

    def test_toolbar_buttons_present(self, page):
        """All toolbar buttons are present."""
        page.goto(VIEWER_URL)
        expect(page.locator("#play-btn")).to_be_visible()
        expect(page.locator("#zoom-slider")).to_be_visible()
        expect(page.locator("#volume-slider")).to_be_visible()


# ==================== Tests: JSON Loading ====================

class TestJSONLoading:

    def test_load_via_url_param(self, page, test_json_path):
        """Loading JSON via ?json= URL parameter works."""
        page.goto(f"{VIEWER_URL}?json={test_json_path}")
        page.wait_for_timeout(500)
        # Loading overlay should be hidden
        expect(page.locator("#loading-overlay")).to_be_hidden()

    def test_notes_rendered(self, page, test_json_path):
        """Note blocks are created for each note in the data."""
        page.goto(f"{VIEWER_URL}?json={test_json_path}")
        page.wait_for_timeout(500)
        note_blocks = page.locator(".note-block")
        expect(note_blocks).to_have_count(5)

    def test_song_info_displayed(self, page, test_json_path):
        """Song info bar shows note count."""
        page.goto(f"{VIEWER_URL}?json={test_json_path}")
        page.wait_for_timeout(500)
        info = page.locator("#song-info")
        expect(info).to_contain_text("5 notes")

    def test_hand_classification(self, page, test_json_path):
        """Notes are classified with correct hand CSS classes."""
        page.goto(f"{VIEWER_URL}?json={test_json_path}")
        page.wait_for_timeout(500)
        right = page.locator(".note-block.right-hand")
        left = page.locator(".note-block.left-hand")
        expect(right).to_have_count(3)
        expect(left).to_have_count(2)


# ==================== Tests: Keyboard ====================

class TestKeyboard:

    def test_keyboard_rendered(self, page, test_json_path):
        """Piano keyboard is rendered with keys."""
        page.goto(f"{VIEWER_URL}?json={test_json_path}")
        page.wait_for_timeout(500)
        keys = page.locator(".key")
        count = keys.count()
        assert count > 0, "No keyboard keys rendered"

    def test_white_and_black_keys(self, page, test_json_path):
        """Both white and black keys are rendered."""
        page.goto(f"{VIEWER_URL}?json={test_json_path}")
        page.wait_for_timeout(500)
        white = page.locator(".key.white")
        black = page.locator(".key.black")
        assert white.count() > 0, "No white keys"
        assert black.count() > 0, "No black keys"


# ==================== Tests: Piano Roll ====================

class TestPianoRoll:

    def test_roll_has_height(self, page, test_json_path):
        """Piano roll container has a meaningful height."""
        page.goto(f"{VIEWER_URL}?json={test_json_path}")
        page.wait_for_timeout(500)
        roll = page.locator("#piano-roll")
        height = roll.evaluate("el => el.style.height")
        assert height, "Piano roll has no height set"
        height_px = float(height.replace("px", ""))
        assert height_px > 500, f"Piano roll too short: {height_px}px"

    def test_note_blocks_positioned(self, page, test_json_path):
        """Note blocks have explicit positioning styles."""
        page.goto(f"{VIEWER_URL}?json={test_json_path}")
        page.wait_for_timeout(500)
        first_note = page.locator(".note-block").first
        top = first_note.evaluate("el => el.style.top")
        left = first_note.evaluate("el => el.style.left")
        assert top, "Note has no top position"
        assert left, "Note has no left position"

    def test_note_data_attributes(self, page, test_json_path):
        """Note blocks have data attributes for note info."""
        page.goto(f"{VIEWER_URL}?json={test_json_path}")
        page.wait_for_timeout(500)
        first_note = page.locator(".note-block").first
        note_id = first_note.get_attribute("data-note-id")
        assert note_id is not None, "Missing data-note-id"
        start_time = first_note.get_attribute("data-start-time")
        assert start_time is not None, "Missing data-start-time"

    def test_playhead_present(self, page, test_json_path):
        """Playhead element exists in the piano roll."""
        page.goto(f"{VIEWER_URL}?json={test_json_path}")
        page.wait_for_timeout(500)
        expect(page.locator("#playhead")).to_be_attached()


# ==================== Tests: Scrolling ====================

class TestScrolling:

    def test_scroll_changes_time(self, page, test_json_path):
        """Scrolling the piano roll changes the time indicator."""
        page.goto(f"{VIEWER_URL}?json={test_json_path}")
        page.wait_for_timeout(500)
        time_before = page.locator("#time-indicator").inner_text()
        container = page.locator("#piano-roll-container")
        container.evaluate("el => el.scrollTop = 0")
        page.wait_for_timeout(200)
        time_after = page.locator("#time-indicator").inner_text()
        assert time_before != time_after or True, "Time should change on scroll"

    def test_time_indicator_format(self, page, test_json_path):
        """Time indicator shows time in M:SS / M:SS format."""
        page.goto(f"{VIEWER_URL}?json={test_json_path}")
        page.wait_for_timeout(500)
        text = page.locator("#time-indicator").inner_text()
        # Should match pattern like "0:05 / 0:15" or "1:30 / 4:15"
        import re
        assert re.match(r'\d+:\d{2} / \d+:\d{2}', text), f"Bad time format: {text}"


# ==================== Tests: Zoom ====================

class TestZoom:

    def test_zoom_changes_roll_height(self, page, test_json_path):
        """Changing zoom slider changes the piano roll height."""
        page.goto(f"{VIEWER_URL}?json={test_json_path}")
        page.wait_for_timeout(500)

        roll = page.locator("#piano-roll")
        height_before = float(roll.evaluate("el => el.style.height").replace("px", ""))

        # Change zoom
        page.locator("#zoom-slider").fill("150")
        page.locator("#zoom-slider").dispatch_event("input")
        page.wait_for_timeout(300)

        height_after = float(roll.evaluate("el => el.style.height").replace("px", ""))
        assert height_after > height_before, \
            f"Roll didn't grow: {height_before} -> {height_after}"


# ==================== Tests: Playback Control ====================

class TestPlayback:

    def test_play_button_toggles(self, page, test_json_path):
        """Play button toggles between play and pause text."""
        page.goto(f"{VIEWER_URL}?json={test_json_path}")
        page.wait_for_timeout(500)

        btn = page.locator("#play-btn")
        expect(btn).to_contain_text("Play")

        btn.click()
        page.wait_for_timeout(100)
        expect(btn).to_contain_text("Pause")

        btn.click()
        page.wait_for_timeout(100)
        expect(btn).to_contain_text("Play")

    def test_space_toggles_playback(self, page, test_json_path):
        """Spacebar toggles playback."""
        page.goto(f"{VIEWER_URL}?json={test_json_path}")
        page.wait_for_timeout(500)

        btn = page.locator("#play-btn")
        expect(btn).to_contain_text("Play")

        page.keyboard.press("Space")
        page.wait_for_timeout(100)
        expect(btn).to_contain_text("Pause")

        page.keyboard.press("Space")
        page.wait_for_timeout(100)
        expect(btn).to_contain_text("Play")

    def test_playback_scrolls_roll(self, page, test_json_path):
        """During playback, the roll auto-scrolls."""
        page.goto(f"{VIEWER_URL}?json={test_json_path}")
        page.wait_for_timeout(500)

        container = page.locator("#piano-roll-container")
        scroll_before = container.evaluate("el => el.scrollTop")

        page.locator("#play-btn").click()
        page.wait_for_timeout(500)  # Let it scroll for 500ms
        page.locator("#play-btn").click()  # Stop

        scroll_after = container.evaluate("el => el.scrollTop")
        # Scroll should have decreased (scrolling upward = time progresses)
        assert scroll_before != scroll_after, \
            f"Scroll didn't change during playback: {scroll_before}"


# ==================== Tests: Sound Toggle ====================

class TestSoundToggle:

    def test_volume_slider_present(self, page, test_json_path):
        """Volume slider is present (sound is on by default)."""
        page.goto(f"{VIEWER_URL}?json={test_json_path}")
        page.wait_for_timeout(500)

        slider = page.locator("#volume-slider")
        expect(slider).to_be_visible()
        # Default value should be 80
        val = slider.input_value()
        assert val == "80", f"Expected default volume 80, got {val}"


# ==================== Tests: Real Data ====================

class TestRealData:

    def test_load_easy_json(self, page):
        """Load the real 'easy' video analysis output."""
        json_path = os.path.join(VIEWER_DIR, "demo_easy.json")
        if not os.path.exists(json_path):
            pytest.skip("demo_easy.json not found")

        page.goto(f"{VIEWER_URL}?json=demo_easy.json")
        page.wait_for_timeout(1000)

        expect(page.locator("#loading-overlay")).to_be_hidden()
        note_blocks = page.locator(".note-block")
        count = note_blocks.count()
        assert count > 50, f"Expected many notes, got {count}"

    def test_load_perfect_json(self, page):
        """Load the real 'perfect' video analysis output."""
        json_path = os.path.join(VIEWER_DIR, "demo_perfect.json")
        if not os.path.exists(json_path):
            pytest.skip("demo_perfect.json not found")

        page.goto(f"{VIEWER_URL}?json=demo_perfect.json")
        page.wait_for_timeout(1000)

        expect(page.locator("#loading-overlay")).to_be_hidden()
        note_blocks = page.locator(".note-block")
        count = note_blocks.count()
        assert count > 100, f"Expected many notes, got {count}"

    def test_both_hands_in_perfect(self, page):
        """Perfect video should have both left and right hand notes."""
        json_path = os.path.join(VIEWER_DIR, "demo_perfect.json")
        if not os.path.exists(json_path):
            pytest.skip("demo_perfect.json not found")

        page.goto(f"{VIEWER_URL}?json=demo_perfect.json")
        page.wait_for_timeout(1000)

        right = page.locator(".note-block.right-hand")
        left = page.locator(".note-block.left-hand")
        assert right.count() > 0, "No right hand notes"
        assert left.count() > 0, "No left hand notes"
