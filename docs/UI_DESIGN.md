# MakeMusic UI Design — Complete Overhaul

## Design Philosophy

The current UI suffers from mode-fragmentation: editing, lyrics, playback, and viewing
all operate as separate bolt-on systems with conflicting interaction models. The new UI
is designed from first principles around **flow states** — the user should be able to do
anything from anywhere without first switching into a special mode.

### Core Principles

1. **No hidden modes** — Edit, lyrics, and view are not separate states. Selection is
   always possible. Editing actions appear contextually when something is selected.
2. **Progressive disclosure** — Default view is clean. Panels and tools appear when needed.
3. **One interaction model** — Same gestures work everywhere: click to select, drag to
   move, double-click to edit inline. Context menus are always available. Keyboard
   shortcuts always work.
4. **Mobile-native, not adapted** — Touch interactions are designed independently, not
   as mappings of desktop patterns.
5. **Visual coherence** — A minimal design system with consistent spacing, typography,
   color usage, and animation timing across all components.

---

## Data Model (unchanged)

```
{
  metadata: { title, source },
  notes: [{ id, note_name, start_time, duration, hand, key_index, center_x, color_rgb, lyric }],
  markers: [{ id, time, label }],
  summary: { total_notes, right_hand_notes, left_hand_notes, duration_range, key_range }
}
```

---

## Layout Architecture

### Desktop (>768px)

```
┌─────────────────────────────────────────────────────┐
│ Header Bar                                           │
│ [Logo] [Title] [spacer] [RH|LH] [Transport] [Menu] │
├──────────────────────────────────────┬───────────────┤
│                                      │ Inspector     │
│     Piano Roll                       │ Panel         │
│     (scrollable, zoomable)           │ (contextual)  │
│                                      │               │
│                                      │               │
├──────────────────────────────────────┴───────────────┤
│ Progress Bar                                         │
├─────────────────────────────────────────────────────┤
│ Piano Keyboard                                       │
└─────────────────────────────────────────────────────┘
```

- **Header Bar**: Compact, always visible. Contains: logo/title, hand toggles, transport
  controls (play/pause, speed), and a hamburger/menu for less-used actions.
- **Piano Roll**: The main canvas. Notes are always interactive (hoverable, clickable,
  right-clickable). No mode switch needed.
- **Inspector Panel**: Right side panel that appears contextually:
  - Nothing selected → Song overview (note counts, duration)
  - Note selected → Note properties (name, time, duration, hand, lyric)
  - Marker selected → Marker editing
  - Can also switch to Lyrics view, Settings view
- **Progress Bar**: Clickable timeline with markers shown as ticks.
- **Piano Keyboard**: Bottom, highlighting active notes.
- **Minimap**: Integrated into the right edge of the piano roll as a thin strip.

### Mobile (<768px)

```
┌────────────────────────┐
│ Header (compact)       │
├────────────────────────┤
│                        │
│   Piano Roll           │
│   (full width)         │
│                        │
├────────────────────────┤
│ Progress Bar           │
├────────────────────────┤
│ Piano Keyboard         │
├────────────────────────┤
│ Bottom Sheet (sliding) │
│ ─────────────────────  │
│ [View] [Play] [Edit]   │
│ [Lyrics] [More]        │
└────────────────────────┘
```

- Bottom sheet slides up to reveal transport controls, inspector, or settings.
- Tap on a note to select it; action bar appears at top of bottom sheet.
- Long-press for context menu (action sheet).
- Two-finger pinch to zoom.

---

## User Flows

### Flow 1: First-Time User — Loading & Exploring

**Desktop:**
1. User arrives at homepage. Clean centered card with:
   - "Open File" drop zone (drag & drop or click)
   - "Load Example" button
   - "Start Empty" button
   - GitHub sign-in (secondary)
2. User drops a JSON file onto the zone or clicks "Open File".
3. Homepage fades out. Piano roll fades in with notes rendered.
4. Playhead sits at the first note position. Time indicator shows `0:00 / 3:42`.
5. User scrolls through the roll — notes pass the playhead line. Keyboard keys
   light up to show which notes are at the playhead position.
6. User hovers over a note — tooltip appears showing: note name, hand, start time,
   duration, and lyric (if any).
7. User clicks a note — note plays its sound. Piano roll scrolls to center that note  
   at the playhead. The inspector panel slides in from the right showing note details.

**Mobile:**
1. Same homepage but laid out vertically. "Open File" button (no drop zone).
2. After loading, piano roll appears. Bottom nav shows [View][Play][Edit][Lyrics][More].
3. User scrolls with finger. Keyboard highlights work identically.
4. User taps a note — note plays, scrolls to it. Bottom sheet slides up showing
   note info.
5. User taps away — sheet dismisses.

### Flow 2: Playback

**Desktop:**
1. User presses Space (or clicks ▶ in header).
2. Play button changes to ⏸. Piano roll auto-scrolls upward.
3. Notes crossing the playhead line glow/highlight. Audio plays via Tone.js.
4. Keyboard keys light up in real-time.
5. User scrolls with mouse wheel → playback pauses momentarily, resumes when
   user stops scrolling (200ms debounce).
6. User clicks on progress bar → playback jumps to that time.
7. User presses Space → playback stops. Playhead stays at current position.
8. User changes speed dropdown (0.25x, 0.5x, 0.75x, 1x, 1.5x, 2x) — speed
   changes immediately, even during playback.
9. User presses L → loop icon toggles. At end of song, playback wraps to start.
10. User presses Home → jumps to first note. Press End → jumps to end.
11. Volume slider in header adjusts audio level.
12. Arrow keys ↑/↓ scroll through the roll.

**Mobile:**
1. User taps [Play] in bottom nav → transport controls appear in bottom sheet
   (play/pause, skip-to-start, loop toggle, speed picker, volume slider).
2. User taps ▶. Piano roll auto-scrolls. Same highlighting behavior.
3. User can scrub the progress bar with finger.
4. User taps ⏸ to stop.

### Flow 3: Note Selection & Inspection

**Desktop:**
1. User clicks any note → note gets selection ring (border highlight).
   Inspector panel opens on right side showing: Note name (e.g. "C#4"),
   Hand (RH/LH with color dot), Start time, Duration, Lyric field.
2. User can edit the lyric directly in the inspector panel's input field.
   Changes apply live to the note (lyric text appears on the note block).
3. User can change the hand by clicking the hand toggle in the inspector.
4. User can nudge time/duration with small +/- buttons in inspector.
5. User clicks on empty space → note deselects. Inspector shows song overview.
6. User presses Tab → selects next note (by time). Shift+Tab → previous note.
7. User presses Delete → selected note is deleted (with undo support).
8. User presses H → toggles selected note's hand assignment.
9. Right-click on a note → context menu appears: Toggle Hand, Duplicate,
   Edit Lyric, Delete. (Same menu in edit mode and view mode.)

**Mobile:**
1. User taps a note → bottom sheet slides up showing note info + action buttons
   (Toggle Hand, Duplicate, Edit Lyric, Delete).
2. User taps "Edit Lyric" → keyboard appears, lyric input in bottom sheet.
3. User swipes bottom sheet down → closes it, deselects note.
4. Long-press on note → action sheet with same options.

### Flow 4: Editing Notes (Create, Move, Resize, Delete)

**Desktop:**
1. User presses E (or clicks ✏️ in header) to enter edit mode. A subtle visual
   indicator appears (thin colored bar along top, or badge in header). Edit mode
   enables: note creation, drag-to-move, resize handles, right-click context menus.
2. **Creating notes**: Click on empty space in the piano roll, hold, and drag
   vertically to set duration. A preview ghost note shows where the note will be
   placed. Release to create the note. The note lane (horizontal position) is
   determined by the mouse X position (snaps to nearest key lane). Minimum drag
   threshold prevents accidental creation.
3. **Moving notes**: Click and drag a note. The note follows the cursor. Horizontal
   movement changes the key. Vertical movement changes the start time. Snap lines
   appear when the note edge aligns with another note's start/end.
4. **Resizing notes**: Top and bottom edges of selected notes show resize handles
   (cursor changes). Drag to change duration. Snap-to-edge works here too.
5. **Deleting notes**: Select note, press Delete. Or right-click → Delete.
6. **Duplicating notes**: Right-click → Duplicate. New note placed immediately after
   the original.
7. **Toggle hand**: Select note, press H. Or right-click → Toggle Hand.
8. **Hand selector**: Small RH/LH toggle in header (or inspector) controls which
   hand new notes are assigned to. Press R to toggle.
9. All edits support undo (Cmd+Z) and redo (Cmd+Shift+Z / Cmd+Y).
10. Edit mode can be exited with E or Escape.

**Mobile:**
1. User taps [Edit] in bottom nav → edit mode activates. Visual indicator shows.
2. **Creating notes**: Tap on empty space → creates a 1-second note. User can then
   adjust via the bottom sheet inspector.
3. **Moving notes**: Tap to select, then drag. Drag threshold is higher on touch
   to prevent accidental moves.
4. **Deleting/duplicating**: Long-press → action sheet with options.
5. **Undo/Redo**: Undo/Redo buttons appear in the bottom action bar on mobile.

### Flow 5: Lyrics Mode

**Desktop:**
1. User presses W (or clicks Lyrics in header) → Lyrics panel opens as a right-side
   panel (replaces/overlays inspector). Shows all notes in time order with inline
   lyric input fields.
2. If a note is selected, the corresponding row in the lyrics panel is highlighted
   and auto-scrolled into view. Input field is focused.
3. User types lyric text → text appears on the note block in the piano roll in
   real-time.
4. User presses Tab → focus advances to next note's input. Shift+Tab → previous.
5. User presses Enter → same as Tab (moves to next).
6. User presses Escape → exits lyrics mode.
7. **Hand filter buttons** at top of lyrics panel: [RH] [LH] [All]. Clicking one
   filters the list to show only that hand's notes.
8. When a hand filter is active, Tab/Shift+Tab only navigates within that hand's
   notes.
9. Clicking a row in the lyrics panel:
   - Selects that note in the piano roll (highlight ring)
   - Scrolls the piano roll to center that note at the playhead
   - Focuses the lyric input for that row
10. Notes with existing lyrics show a small music note icon (🎵) on the note block.
11. The lyric text on the note block is truncated with ellipsis if too long.

**Lyrics + Playback interaction:**
12. User can start playback during lyrics mode. As the playhead advances, the
    current note's lyrics panel row auto-scrolls to stay visible. This lets the
    user review lyrics while listening.
13. User can type lyrics while playback is paused, then play to review.

**Lyrics + Hand visibility:**
14. If the user hides a hand (press 1/2), lyrics panel respects the visibility
    and hides notes from the hidden hand.

**Mobile:**
1. User taps [Lyrics] in bottom nav → lyrics panel occupies the bottom sheet
   (full height). Piano roll shrinks to show only the top portion.
2. User taps a row → piano roll scrolls to that note. Inline input becomes active.
3. User types lyric → updates in real time on the note block.
4. Tab navigates to next lyric. Keyboard stays open.
5. User taps [View] or swipes down → exits lyrics mode.

### Flow 6: Markers (Section Labels)

**Desktop:**
1. In edit mode, user presses M → inline input appears at the playhead position
   asking for a label (e.g. "Verse 1", "Chorus"). User types and presses Enter.
2. A horizontal marker line appears across the piano roll at that time position.
   The label shows on the left edge.
3. On the progress bar, a small tick mark appears at the marker's position.
4. Clicking a marker label in view mode → scrolls to that time.
5. Clicking a marker label in edit mode → opens inline edit for the label.
6. Right-clicking or Ctrl+clicking a marker label → delete confirmation.
7. Markers appear in the inspector panel as a list. User can click any to jump.
8. Markers are included in the JSON export.

**Mobile:**
1. In edit mode, user taps "Add Marker" in the action bar → inline input appears.
2. Markers appear as horizontal lines. Tapping a marker label scrolls to it.
3. Long-press on a marker → action sheet with Edit/Delete options.

### Flow 7: Hand Visibility & Filtering

**Desktop:**
1. Header shows two hand toggle buttons: [● RH] [● LH] with colored dots.
2. Click RH → toggles right hand visibility. Notes with hand=right_hand show/hide.
   Drop lines also show/hide. Keyboard highlighting ignores hidden notes.
3. Playback audio also mutes hidden hand's notes (important UX improvement!).
4. Both hands can be hidden simultaneously — empty roll is shown.
5. Press 1 → toggles RH. Press 2 → toggles LH.
6. When editing, note creation uses the currently selected edit hand (R to toggle).
7. In lyrics panel, hand filter buttons are independent of note visibility.
   User can hide RH notes in the roll but still see/edit RH lyrics.

**Mobile:**
1. Hand toggles are in the bottom sheet transport controls.
2. Same toggle behavior. Visual dots reflect state.

### Flow 8: Zoom & Navigation

**Desktop:**
1. Ctrl+scroll zooms in/out centered on mouse position. Zoom range: 20px/s to 300px/s.
2. Zoom slider in header provides direct control. Dragging updates live.
3. Mouse wheel (no Ctrl) scrolls vertically through time.
4. Arrow keys ↑/↓ scroll with smooth animation.
5. Home → jump to first note. End → jump to last note.
6. Click on minimap (right edge strip) → jump to position in song.
7. Click on progress bar → jump to time position.
8. When zooming, the playhead position (relative to the visible notes) is preserved.

**Mobile:**
1. Two-finger pinch to zoom. Single finger scrolls.
2. Zoom slider in bottom sheet transport controls.
3. Progress bar is tappable/scrubbable.

### Flow 9: Command Palette

**Desktop:**
1. User presses Cmd+P → command palette appears (centered modal with search input).
2. User types to filter commands. Fuzzy matching highlights results.
3. Arrow keys navigate the list. Enter executes the selected command. Escape closes.
4. Commands include all actions: playback controls, view toggles, file operations,
   edit operations, zoom, speed, volume, etc.
5. Each command shows its keyboard shortcut on the right side.
6. Command palette should also allow searching for notes by name (e.g. typing "C#4"
   shows all C#4 notes and selecting one jumps to it).

**Mobile:**
1. Command palette can be triggered from [More] → "Command Palette" or by a
   swipe-down gesture on the header.

### Flow 10: Settings

**Desktop:**
1. Click ⚙️ in header menu → Settings panel opens as a modal.
2. Settings grouped into sections:
   - **Display**: Drop lines (toggle), Note labels (toggle), Density heatmap (toggle),
     Dark/Light theme (toggle)
   - **Colors**: Right hand color (color picker), Left hand color (color picker)
   - **Playback**: Scroll speed, Keyboard height
3. Settings persist in localStorage.
4. "Reset Defaults" button restores all settings.
5. Changing colors applies immediately to all notes and hand indicators.

**Mobile:**
1. Settings accessible from [More] menu → "Settings".
2. Settings open as a full-screen sheet with the same options.
3. Color pickers use native mobile color inputs.

### Flow 11: File Operations

**Desktop:**
1. Cmd+O or File → Open → native file picker for JSON files.
2. Drag & drop a JSON file onto the window → loads it.
3. Cmd+S or File → Save → downloads the current state as JSON.
4. Title input in header → user can rename the song.
5. GitHub cloud storage → modal with sign-in, save/load from repo.

**Mobile:**
1. [More] → Open File / Save File / Cloud Storage.
2. Same functionality, adapted layout.

### Flow 12: Theme Toggle

1. Press T → toggles dark/light theme. All colors, backgrounds, borders update.
2. Theme preference is remembered in settings.
3. Dark theme is the default.
4. Both themes should have good contrast ratios (WCAG AA).

### Flow 13: Editing + Playback Interaction

1. User can start playback while in edit mode. Notes still scroll and play.
2. Selected note keeps its selection ring during playback.
3. User can pause, edit a note (move/resize), then resume playback.
4. If a note is being dragged when playback is active, playback pauses until
   the drag completes, then resumes.
5. Creating a note during playback → playback pauses, note is created, playback
   can be resumed.

### Flow 14: Editing + Lyrics Interaction

1. When lyrics panel is open, selecting a note in the piano roll auto-scrolls
   the lyrics panel to that note and focuses the input.
2. When editing a note's lyric in the lyrics panel, the note block updates in
   real-time (lyric text appears on the note).
3. Moving a note in the piano roll reorders the lyrics panel (since it sorts
   by time).
4. Deleting a note removes its row from the lyrics panel.
5. Duplicating a note adds a new row to the lyrics panel.
6. Changing a note's hand updates the lyrics panel's color dot and potentially
   filters it out if a hand filter is active.

### Flow 15: Editing + Markers Interaction

1. Markers are visible in both view and edit modes. Only editable in edit mode.
2. Notes can snap to marker positions during drag (in addition to snapping to
   other note edges).
3. When editing a marker label, the inline input appears near the marker.
4. Deleting a marker removes it from the progress bar and the roll.

### Flow 16: Hidden Hand Notes + Editing

1. If RH is hidden, RH notes cannot be selected or interacted with.
2. New notes are always created with the current edit hand, regardless of visibility.
3. If the current edit hand is hidden, a warning appears when trying to create notes.
4. Context menus only show for visible notes.
5. Lyrics panel can show notes from hidden hands (hand filter is independent).

### Flow 17: Hidden Hand Notes + Playback

1. Hidden notes do not play audio during playback. This allows the user to
   practice one hand at a time.
2. Hidden notes do not highlight on the keyboard.
3. The progress bar still reflects total song timeline (including hidden notes).

### Flow 18: Keyboard Navigation (Accessibility)

1. Tab moves focus between header controls → piano roll → inspector → keyboard.
2. In the piano roll, arrow keys move selection between notes (← → for pitch,
   ↑ ↓ for time).
3. Enter on a selected note opens the inspector for it.
4. Escape closes any open panel/modal and deselects.
5. All interactive elements have visible focus rings.
6. Screen reader labels on all buttons and controls.

### Flow 19: Undo/Redo System

1. All editing operations are undoable: create note, delete note, move note,
   resize note, toggle hand, edit lyric, add/edit/delete marker.
2. Undo stack holds up to 100 items.
3. Cmd+Z → undo. Cmd+Shift+Z or Cmd+Y → redo.
4. Undo/redo works across mode transitions (e.g. undo from view mode undoes
   an edit made in edit mode).
5. Undo restores the selection state if a note was involved.

### Flow 20: Empty Project

1. User clicks "Start Empty" → blank piano roll appears.
2. User must enter edit mode to create notes.
3. Progress bar, time display, minimap are hidden when empty.
4. First note creates the timeline.

---

## Component Design Details

### Header Bar

- Height: 48px (desktop), 44px (mobile).
- Background: semi-transparent with backdrop blur.
- Layout: flex with gap=8px.
- Items left-to-right (desktop):
  1. Logo icon (🎹) + "MakeMusic" text (clickable → homepage)
  2. Song title (editable inline input, underline on hover)
  3. Spacer
  4. Hand toggle buttons [● RH] [● LH] — small, inline
  5. Transport: [⏮][▶/⏸][🔁] — compact icon buttons
  6. Speed selector (dropdown, compact)
  7. Volume icon + mini slider
  8. Zoom slider (compact, labeled)
  9. Menu button (☰) → dropdown with: Open, Save, Cloud, Edit Mode,
     Settings, Help, Theme toggle
- Mobile: Logo, Title, spacer, Menu button only. All else in bottom sheet.

### Piano Roll

- Full viewport height minus header (48px), progress bar (4px), keyboard.
- CSS Grid layout for note positioning.
- Notes use absolute positioning within the roll.
- Playhead: fixed horizontal line at 70% from top of viewport.
- Track lines: subtle vertical lines aligned with keyboard keys.
- Density heatmap: 1px-wide canvas showing note density.
- Minimap: 40px-wide strip on the right edge showing song overview with
  draggable viewport indicator.

### Note Blocks

- Rounded corners (4px).
- Background: gradient using hand color. Sharps are slightly darker.
- Border: 1px semi-transparent darker.
- On hover: subtle glow/brightness increase.
- Selected: ring outline (2px) in bright color.
- Playing (crossing playhead): pulsing glow animation.
- Resize handles: invisible 8px zones at top and bottom edges. Cursor changes.
- Note label: small text inside (note name). Hidden if note is too small.
- Lyric label: smaller text below note name. Truncated with ellipsis.
- Drop lines: very faint vertical lines from note bottom to keyboard.

### Inspector Panel

- Width: 280px (desktop). Slides in from right.
- Sections:
  - **Song Overview** (default when nothing selected):
    - Note counts (RH/LH)
    - Song duration
    - Marker list (clickable → jump to time)
  - **Note Inspector** (when note selected):
    - Note name (readonly badge)
    - Hand (toggle switch: RH/LH)
    - Start time (number input with +/- buttons)
    - Duration (number input with +/- buttons)
    - Lyric (text input, live preview)
    - Actions: Duplicate, Delete (buttons)
  - **Lyrics Panel** (in lyrics mode):
    - Filter bar: [RH][LH][All]
    - Note list with inline lyric inputs
    - Each row: hand color dot, note name, time, lyric input
  - **Settings Panel** (when opened):
    - All settings with toggles/sliders/colors

### Progress Bar

- Height: 4px, full width. Expands to 8px on hover.
- Fill color: accent color (blue).
- Marker ticks: small vertical lines at marker positions.
- Clickable/scrubbable for seeking.
- Shows current progress as filled portion.

### Keyboard

- Height: configurable (default 100px desktop, 60px mobile).
- White and black keys with proper piano layout.
- Active notes highlighted with hand color.
- Keys labeled with note names (small text).

### Context Menu

- Appears on right-click (desktop) or long-press (mobile).
- Consistent menu items regardless of mode:
  - Note context: [Toggle Hand] [Duplicate] [Edit Lyric] [—] [Delete]
  - Empty space context: [Add Note Here] [Add Marker Here]
- Keyboard navigable (arrow keys, Enter to select).
- Dismisses on click outside or Escape.

### Command Palette

- Full-width modal, top-centered (like VS Code).
- Search input with fuzzy matching.
- Shows all available commands with icons and keyboard shortcuts.
- Arrow key navigation, Enter to execute.
- Cmd+P to toggle.

### Modals

- Settings modal, Help modal, GitHub modal.
- Centered overlay with backdrop blur.
- Escape to close.
- Click outside to close.

---

## Keyboard Shortcuts (Complete)

| Action                   | Desktop Shortcut | Mobile Equivalent     |
|--------------------------|------------------|-----------------------|
| Play/Pause               | Space            | Play tab → ▶          |
| Toggle Loop              | L                | Play tab → 🔁         |
| Jump to Start            | Home             | Play tab → ⏮          |
| Jump to End              | End              | —                     |
| Scroll Up                | ↑                | Swipe                 |
| Scroll Down              | ↓                | Swipe                 |
| Zoom In                  | Ctrl+Scroll↑     | Pinch out             |
| Zoom Out                 | Ctrl+Scroll↓     | Pinch in              |
| Toggle Right Hand        | 1                | Play tab → RH toggle  |
| Toggle Left Hand         | 2                | Play tab → LH toggle  |
| Toggle Theme             | T                | More → Settings       |
| Toggle Edit Mode         | E                | Edit tab              |
| Delete Note              | Delete/Backspace | Action sheet → Delete |
| Toggle Note Hand         | H                | Action sheet → Toggle |
| Switch Edit Hand         | R                | —                     |
| Add Marker               | M                | Edit bar → Marker     |
| Toggle Lyrics Mode       | W                | Lyrics tab            |
| Navigate Lyrics Forward  | Tab              | Tab (with keyboard)   |
| Navigate Lyrics Backward | Shift+Tab        | Shift+Tab             |
| Undo                     | Cmd+Z            | Edit bar → Undo       |
| Redo                     | Cmd+Shift+Z/Y    | Edit bar → Redo       |
| Open File                | Cmd+O            | More → Open           |
| Save/Export              | Cmd+S            | More → Save           |
| Command Palette          | Cmd+P            | More → Commands       |
| Show Help                | ?                | More → Help           |
| Escape                   | Esc              | Swipe down / Back     |
| Select Next Note         | Tab (in roll)    | Tap next note         |
| Select Previous Note     | Shift+Tab        | Tap previous note     |

---

## Animation & Transitions

- Panel slide-in: 200ms ease-out (inspector, lyrics, mobile sheets).
- Modal fade-in: 150ms ease-out.
- Note selection ring: 100ms.
- Note playing glow: continuous pulse (2s cycle).
- Theme toggle: 200ms CSS transition on all color properties.
- Progress bar hover expand: 100ms.
- Button hover/active states: 100ms.
- Playhead (during playback): requestAnimationFrame smooth scroll.

---

## Color System

### Dark Theme (default)
```
--bg-primary: #1a1a2e
--bg-secondary: #16213e
--bg-surface: #1f2940
--bg-hover: #273350
--text-primary: #e0e0e0
--text-secondary: #a0a0b0
--text-muted: #666680
--border: #2a2a4a
--accent: #6c63ff
--accent-hover: #7b73ff
--danger: #ff4757
--success: #2ed573
--rh-default: #6495ED (cornflower blue)
--lh-default: #48BF91 (emerald)
--playhead: #ff6b6b
```

### Light Theme
```
--bg-primary: #f5f5f5
--bg-secondary: #ffffff
--bg-surface: #ffffff
--bg-hover: #eeeef2
--text-primary: #1a1a2e
--text-secondary: #555570
--text-muted: #999
--border: #ddd
--accent: #5a52d5
--accent-hover: #4a42c5
--danger: #e74c3c
--success: #27ae60
--rh-default: #4a7fd4
--lh-default: #3aa87a
--playhead: #e74c3c
```

---

## Tooltip Design

- Background: dark semi-transparent (both themes).
- Border radius: 6px.
- Padding: 8px 12px.
- Content: Note name (bold, larger), Hand (with color dot), Time, Duration.
- If lyric is present: shown below other info.
- Position: follows mouse, 14px offset. Stays within viewport.
- Mobile: shows as a small toast or bottom sheet header instead.

---

## Test Coverage Plan

### Unit / Component Tests

Each major UI component should have thorough tests:

#### Basic Load & Rendering
- Page loads without JS errors
- Correct number of notes rendered
- Song info displays correctly
- Note count badge shows RH/LH
- Title contains app name
- Loading overlay hides after data loads
- Empty project shows empty state

#### Keyboard
- Keyboard renders at bottom
- White and black keys present
- Keys have note name labels
- Keyboard height matches settings
- Keys span correct range based on data

#### Note Blocks
- RH and LH notes have correct counts
- Notes have position styles
- Notes have gradient backgrounds
- Notes have data attributes
- Tall notes show labels
- Short notes hide labels
- Notes with lyrics show lyric text
- Sharp notes have darker color
- Lyric text truncates when too long

#### Tooltips
- Tooltip appears on hover
- Tooltip shows note name, hand, time, duration
- Tooltip shows lyric if present
- Tooltip follows mouse within viewport
- Tooltip hides on mouse leave
- No tooltip on mobile (uses action sheet)

#### Selection
- Clicking a note selects it (visual ring)
- Clicking elsewhere deselects
- Tab cycles through notes by time
- Shift+Tab goes to previous note
- Inspector panel opens when note selected
- Inspector shows correct note info

#### Inspector Panel
- Shows song overview when nothing selected
- Shows note details when selected
- Lyric input updates note in real-time
- Hand toggle changes note hand
- Duplicate button works
- Delete button works
- Panel closes when nothing selected

#### Playback
- Space toggles play/pause
- Play button icon changes
- Piano roll scrolls during playback
- Progress bar updates
- Time indicator updates
- Speed changes apply during playback
- Loop mode wraps at end
- Home/End keys work
- Scroll pauses playback temporarily
- Keyboard keys highlight during playback
- Notes glow when playing

#### Playhead
- Playhead is at 70% viewport height
- Playhead position updates on scroll
- Playhead is a horizontal line

#### Zoom
- Ctrl+scroll zooms
- Zoom slider works
- Zoom preserves playhead position
- Zoom range is 20-300

#### Progress Bar
- Progress bar updates on scroll
- Clicking progress bar seeks
- Progress fill reflects position
- Markers show as ticks

#### Hand Toggles
- Pressing 1 toggles RH visibility
- Pressing 2 toggles LH visibility
- Hidden notes not visible
- Hidden notes not played
- Hidden notes not highlightable
- Toggle button visual state updates
- Can restore hidden notes

#### Minimap
- Minimap shows note positions
- Minimap viewport indicator moves
- Clicking minimap seeks
- Minimap updates on zoom

#### Theme
- T toggles theme
- Dark theme applied by default
- Light theme changes colors
- Theme persists in settings

#### Edit Mode
- E toggles edit mode
- Edit indicator shows
- Creating notes by drag works
- Moving notes by drag works
- Resizing notes by drag works
- Snap-to-edge works
- Snap indicator shows during snap
- Minimum drag prevents accidental creation
- Context menu on right-click
- Empty space context menu
- Edit hand selector works
- R toggles edit hand

#### Undo/Redo
- Cmd+Z undoes note creation
- Cmd+Z undoes note deletion
- Cmd+Z undoes note move
- Cmd+Z undoes note resize
- Cmd+Z undoes hand toggle
- Cmd+Z undoes lyric edit
- Cmd+Z undoes marker operations
- Cmd+Shift+Z redoes
- 100-item undo stack limit

#### Lyrics Mode
- W toggles lyrics panel
- Lyrics panel shows all notes sorted by time
- Hand filter buttons work (RH, LH, All)
- Clicking row selects note and scrolls
- Tab advances to next note
- Shift+Tab goes to previous
- Enter advances to next note
- Escape exits lyrics mode
- Typing updates note lyric in real-time
- Lyric edits are undoable
- Filtering by hand works
- Notes from hidden hands respect filter

#### Markers
- M adds marker at current position
- Marker line appears on roll
- Marker label is editable
- Marker can be deleted
- Markers appear on progress bar
- Click marker → scroll to time
- Markers sort by time
- Markers survive undo/redo

#### Command Palette
- Cmd+P opens palette
- Search filters commands
- Arrow keys navigate
- Enter executes command
- Escape closes
- All commands are listed

#### Settings
- Settings modal opens/closes
- Toggles work (drop lines, labels, density)
- Color pickers change hand colors
- Keyboard height slider works
- Reset defaults works
- Settings persist in localStorage

#### File Operations
- Open file loads JSON
- Drag & drop loads JSON
- Export downloads JSON
- Invalid JSON shows error
- Song title is editable

### Integration / Cross-Feature Tests

#### Editing + Playback
- Start playback in edit mode
- Pause playback, edit note, resume
- Creating note pauses playback
- Selected note maintains selection during playback

#### Editing + Lyrics
- Select note in roll → lyrics panel scrolls to it
- Edit lyric in panel → note block updates
- Delete note → row removed from lyrics panel
- Duplicate note → row added to lyrics panel
- Toggle hand → color dot updates in lyrics panel
- Move note → lyrics panel reorders

#### Editing + Markers
- Notes snap to marker times
- Delete marker → removed from progress bar
- Edit marker label → updates on roll

#### Lyrics + Playback
- Playing with lyrics panel open → auto-scrolls lyrics
- Typing lyric doesn't interfere with playback

#### Hidden Hands + Editing
- Cannot select hidden notes
- New notes use edit hand regardless of visibility
- Warning when creating notes with hidden edit hand

#### Hidden Hands + Playback
- Hidden notes don't play audio
- Hidden notes don't highlight keyboard
- Progress bar still shows full timeline

#### Hidden Hands + Lyrics
- Lyrics panel filter is independent of note visibility
- Can see hidden hand notes in lyrics panel if filter allows

#### Zoom + Selection
- Zoom preserves selected note
- Zoom recalculates note positions

#### Keyboard Navigation Flow
- Tab through all interactive elements
- Arrow keys within piano roll
- Escape dismissal cascade

### Mobile-Specific Tests

#### Layout
- Header is compact on mobile
- Bottom nav appears below 768px
- Desktop toolbar hidden on mobile
- Touch targets are ≥44px

#### Bottom Navigation
- All 5 tabs present
- Tapping tab activates it
- Active tab is highlighted
- View tab exits edit/lyrics

#### Touch Interactions
- Tap note selects it
- Long-press shows action sheet
- Pinch-to-zoom works
- Swipe scrolls
- Tap empty space in edit mode creates note

#### Bottom Sheet
- Transport controls in play sheet
- Note info in bottom sheet on select
- Speed/volume controls in play sheet

#### Action Sheet
- Shows on long-press
- Cancel button works
- Actions execute correctly
- Overlay click dismisses

#### Mobile Edit Bar
- Shows when note selected in edit mode
- Action buttons work (toggle, duplicate, delete, undo, redo)
- Hides when note deselected

#### Responsive Viewports
- 320x568 (iPhone SE)
- 375x667 (iPhone 6/7/8)
- 390x844 (iPhone 12/13)
- 768x1024 (iPad)
- 1024x768 (iPad landscape)
- 1280x800 (desktop)

### Performance Tests

#### Large File
- Load 200+ note file (examples/perfect_lyrics.json)
- Scroll performance stays smooth
- Zoom performance stays smooth
- Playback doesn't stutter
- Edit mode works with many notes

#### Rapid Operations
- Rapid undo/redo
- Rapid zoom
- Rapid play/pause
- Multiple notes created quickly

---

## Implementation Notes

### File Structure (new)

```
viewer/
  index.html                   — Semantic HTML structure
  css/
    variables.css              — CSS custom properties / design tokens
    base.css                   — Reset, typography, layout primitives
    components.css             — Header, buttons, inputs, badges
    piano-roll.css             — Note blocks, playhead, track lines
    panels.css                 — Inspector, lyrics, modals
    mobile.css                 — Mobile overrides and bottom nav
  js/
    constants.js               — Piano keys, utilities (unchanged)
    state.js                   — Global state (unchanged)
    audio.js                   — Tone.js audio (unchanged)
    keyboard.js                — Piano keyboard (unchanged)
    rendering.js               — Piano roll rendering (updated for new layout)
    playback.js                — Playback engine (unchanged)
    editor.js                  — Edit operations (updated for unified model)
    file-io.js                 — File I/O (unchanged)
    github.js                  — GitHub integration (unchanged)
    ui.js                      — UI components (rewritten for new design)
    events.js                  — Event handlers (rewritten)
    touch.js                   — Touch support (rewritten)
    app.js                     — App init (updated)
```

### CSS Architecture

Use CSS custom properties exclusively for theming. All colors reference variables.
Mobile-first media queries (`min-width`) for responsive design.
No px breakpoints in component CSS — use semantic container queries where possible.

### Accessibility

- All interactive elements: `role`, `aria-label`, `tabindex`
- Focus visible styles on all controls
- High contrast ratios
- Keyboard-navigable menus, modals, panels
- Screen reader announcements for state changes

### Performance

- Virtual scrolling for lyrics panel when note count > 100
- Debounced renders on zoom/scroll
- requestAnimationFrame for playback
- Canvas-based density heatmap
- DOM-based notes with direct style updates during drag (no re-render)
