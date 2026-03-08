"""
Track notes across frames to build a timeline of musical events.

Takes per-frame note detections and links them into unique notes
with start times and durations.

Key features:
- Per-frame box coordinate tracking for each note
- Precise scroll speed measurement from observed note movement
- Accurate start time = when note's bottom edge reaches keyboard_y
- Duration = note height / scroll speed (with partial-visibility handling)
- Correct ordering by play time (keyboard crossing)
- Handles notes clipped at top of screen (extrapolates full height)
- Handles same-note adjacency via position prediction
"""
import numpy as np
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from .note_detector import DetectedNote
from .calibrator import CalibrationResult

import logging
logger = logging.getLogger(__name__)


@dataclass
class FrameObservation:
    """One observation of a note in a single frame."""
    frame_index: int
    timestamp: float
    x: int
    y: int
    width: int
    height: int
    center_x: int
    center_y: int
    is_clipped_top: bool = False
    is_clipped_bottom: bool = False


@dataclass
class TrackedNote:
    """A unique note tracked across multiple frames."""
    id: int
    note_name: str  # e.g., 'C4', 'F#3'
    hand: str  # 'left_hand', 'right_hand', 'unknown'
    color_idx: int

    # Timing
    start_time: float  # When the note is played (bottom edge reaches keyboard_y)
    duration: float  # How long the note is held

    # Position (average across detections)
    center_x: float
    key_index: int = -1  # Piano key index (0-87) or MIDI number

    # Detection info
    first_frame: int = 0
    last_frame: int = 0
    detection_count: int = 0

    # Visual properties
    mean_bgr: Tuple[int, int, int] = (0, 0, 0)
    note_height_px: float = 0  # Best estimate of true note height in pixels

    # OCR
    ocr_text: str = ''
    ocr_confidence: float = 0.0

    # Tracking confidence
    confidence: float = 0.0  # 0-1 confidence score


@dataclass
class ActiveTrack:
    """An in-progress track being built from detections."""
    id: int
    observations: List[FrameObservation] = field(default_factory=list)
    detections: List[DetectedNote] = field(default_factory=list)
    last_seen_frame: int = 0
    color_idx: int = 0
    hand: str = 'unknown'

    # Per-frame coordinates
    center_x_history: List[float] = field(default_factory=list)
    center_y_history: List[float] = field(default_factory=list)
    timestamps: List[float] = field(default_factory=list)

    # Height tracking
    height_history: List[float] = field(default_factory=list)
    top_clipped_count: int = 0  # Frames where top was clipped (y<=2)
    first_unclipped_height: float = 0  # First height when fully visible

    @property
    def mean_center_x(self) -> float:
        return float(np.median(self.center_x_history)) if self.center_x_history else 0

    @property
    def best_height(self) -> float:
        """Best estimate of true note height."""
        if self.first_unclipped_height > 0:
            return self.first_unclipped_height
        if self.height_history:
            return float(np.max(self.height_history))
        return 0


class NoteTracker:
    """
    Tracks note detections across frames to build a timeline.

    Algorithm:
    1. For each new frame, match detected notes to existing active tracks
    2. Matching uses x-position (same piano key), color, and predicted y-position
    3. Scroll speed is measured from actual note movement each frame
    4. Unmatched detections start new tracks
    5. Tracks that haven't been seen for several frames are finalized
    6. Start time = when bottom edge of note crosses keyboard_y
    7. Duration = note height / scroll speed
    """

    def __init__(self, calibration: CalibrationResult,
                 max_gap_frames: int = 2,
                 x_match_threshold: int = 30,
                 y_match_threshold: int = 80):
        """
        Args:
            calibration: Video calibration results
            max_gap_frames: Max frames a note can be missing before track ends
            x_match_threshold: Max x-distance for matching (pixels)
            y_match_threshold: Max y-distance from expected position (pixels)
        """
        self.calibration = calibration
        self.max_gap_frames = max_gap_frames
        self.x_match_threshold = x_match_threshold
        self.y_match_threshold = y_match_threshold

        self.active_tracks: Dict[int, ActiveTrack] = {}
        self.completed_tracks: List[ActiveTrack] = []
        self.next_id = 1
        self.prev_frame_index = -1
        self.prev_timestamp = 0.0

        # Scroll speed tracking
        self.measured_speeds: List[float] = []
        self._current_scroll_speed = calibration.scroll_speed

    @property
    def scroll_speed(self) -> float:
        """Best estimate of scroll speed from measurements."""
        if len(self.measured_speeds) >= 3:
            # Use trimmed mean to remove outliers
            speeds = sorted(self.measured_speeds[-200:])
            trim = max(1, len(speeds) // 5)
            trimmed = speeds[trim:-trim] if trim < len(speeds) // 2 else speeds
            return float(np.median(trimmed))
        return self._current_scroll_speed

    def process_frame(self, detections: List[DetectedNote],
                      frame_index: int, timestamp: float):
        """
        Process detections from a single frame.

        Args:
            detections: Notes detected in this frame
            frame_index: Frame index
            timestamp: Frame timestamp
        """
        global_dt = timestamp - self.prev_timestamp if self.prev_timestamp > 0 else 0.1
        if global_dt <= 0:
            global_dt = 0.001

        # Use calibrated scroll speed (it's reliable); measurements are secondary
        speed = self._current_scroll_speed

        # Predict where each active track should be based on BOTTOM EDGE movement
        # Bottom edge moves at scroll speed for all notes (unlike center_y which
        # moves slower for growing notes)
        # IMPORTANT: Use per-track dt (time since that track's last observation)
        # not global dt, since a track may have missed frames
        predicted_positions = {}
        for track_id, track in self.active_tracks.items():
            if track.observations:
                last_obs = track.observations[-1]
                track_dt = timestamp - last_obs.timestamp
                if track_dt <= 0:
                    track_dt = global_dt
                last_bottom = last_obs.y + last_obs.height
                predicted_bottom = last_bottom + speed * track_dt
                predicted_positions[track_id] = (
                    track.mean_center_x,  # x stays on same key
                    predicted_bottom,     # bottom edge moves at scroll speed
                    last_obs.y + speed * track_dt,  # top edge also moves at scroll speed
                    track_dt,  # store per-track dt for threshold calculation
                )
            else:
                predicted_positions[track_id] = (0, 0, 0, global_dt)

        # Build cost matrix for matching
        matched_tracks = set()
        matched_detections = set()

        # Score each possible (track, detection) pair
        assignments = []
        for track_id, track in self.active_tracks.items():
            pred_x, pred_bottom, pred_top, track_dt = predicted_positions[track_id]

            for det_idx, det in enumerate(detections):
                # Check basic compatibility
                x_dist = abs(det.center_x - pred_x)
                if x_dist > self.x_match_threshold:
                    continue
                if det.color_idx != track.color_idx:
                    continue

                # Compare bottom edges (most reliable for scroll speed matching)
                det_bottom = det.y + det.height
                bottom_dist = abs(det_bottom - pred_bottom)

                # Also check top edge for notes that are growing
                det_top = det.y
                top_dist = abs(det_top - pred_top)

                # Use minimum of bottom/top distances - growing notes may not
                # match on top (it stays at y=0) but should match on bottom
                is_clipped = getattr(det, 'is_clipped_top', False) or det.y <= 2
                if is_clipped:
                    # For top-clipped notes, only use bottom edge
                    y_dist = bottom_dist
                else:
                    y_dist = min(bottom_dist, top_dist)

                # Allow generous y matching - use per-track dt for proper threshold
                # Cap max threshold to prevent matching notes that have drifted far
                max_y_dist = min(speed * track_dt * 2 + 30, 150)
                if y_dist > max_y_dist:
                    continue

                # Score: lower is better
                score = x_dist * 3 + y_dist * 0.3
                assignments.append((score, track_id, det_idx))

        # Greedy matching (sorted by score, best first)
        assignments.sort(key=lambda a: a[0])
        for score, track_id, det_idx in assignments:
            if track_id in matched_tracks or det_idx in matched_detections:
                continue

            det = detections[det_idx]
            track = self.active_tracks[track_id]

            # Update track with new observation
            obs = FrameObservation(
                frame_index=frame_index, timestamp=timestamp,
                x=det.x, y=det.y, width=det.width, height=det.height,
                center_x=det.center_x, center_y=det.center_y,
                is_clipped_top=getattr(det, 'is_clipped_top', False),
                is_clipped_bottom=getattr(det, 'is_clipped_bottom', False),
            )
            track.observations.append(obs)
            track.detections.append(det)
            track.center_x_history.append(det.center_x)
            track.center_y_history.append(det.center_y)
            track.timestamps.append(timestamp)
            track.height_history.append(det.height)
            track.last_seen_frame = frame_index

            # Track clipping
            if getattr(det, 'is_clipped_top', False):
                track.top_clipped_count += 1
            elif track.first_unclipped_height <= 0:
                track.first_unclipped_height = det.height

            # Measure scroll speed from BOTTOM EDGE of fully visible notes only
            if len(track.observations) >= 2:
                prev_obs = track.observations[-2]
                local_dt = timestamp - prev_obs.timestamp
                if local_dt > 0:
                    prev_bottom = prev_obs.y + prev_obs.height
                    curr_bottom = det.y + det.height
                    # Only measure from non-clipped notes (both frames)
                    prev_clipped = prev_obs.is_clipped_top or prev_obs.is_clipped_bottom
                    curr_clipped = obs.is_clipped_top or obs.is_clipped_bottom
                    if not prev_clipped and not curr_clipped:
                        dy = curr_bottom - prev_bottom
                        if dy > 0:
                            measured = dy / local_dt
                            if 50 < measured < 800:
                                self.measured_speeds.append(measured)

            matched_tracks.add(track_id)
            matched_detections.add(det_idx)

        # Start new tracks for unmatched detections
        for det_idx, det in enumerate(detections):
            if det_idx in matched_detections:
                continue

            track = ActiveTrack(
                id=self.next_id,
                observations=[FrameObservation(
                    frame_index=frame_index, timestamp=timestamp,
                    x=det.x, y=det.y, width=det.width, height=det.height,
                    center_x=det.center_x, center_y=det.center_y,
                    is_clipped_top=getattr(det, 'is_clipped_top', False),
                    is_clipped_bottom=getattr(det, 'is_clipped_bottom', False),
                )],
                detections=[det],
                last_seen_frame=frame_index,
                color_idx=det.color_idx,
                hand=det.hand,
                center_x_history=[det.center_x],
                center_y_history=[det.center_y],
                timestamps=[timestamp],
                height_history=[det.height],
                top_clipped_count=1 if getattr(det, 'is_clipped_top', False) else 0,
            )
            if not getattr(det, 'is_clipped_top', False):
                track.first_unclipped_height = det.height
            self.active_tracks[self.next_id] = track
            self.next_id += 1

        # Finalize tracks that haven't been seen recently
        to_remove = []
        for track_id, track in self.active_tracks.items():
            if frame_index - track.last_seen_frame > self.max_gap_frames:
                if len(track.detections) >= 2:  # Require at least 2 detections
                    self.completed_tracks.append(track)
                to_remove.append(track_id)

        for track_id in to_remove:
            del self.active_tracks[track_id]

        self.prev_frame_index = frame_index
        self.prev_timestamp = timestamp

    def finalize(self) -> List[TrackedNote]:
        """
        Finalize all remaining active tracks and convert to TrackedNote objects.

        Returns:
            List of all tracked notes with timing information
        """
        # Move all remaining active tracks to completed
        for track in self.active_tracks.values():
            if len(track.detections) >= 2:
                self.completed_tracks.append(track)
        self.active_tracks.clear()

        logger.info("Measured scroll speed: %.1f px/s (from %d measurements, "
                     "calibrated: %.1f)",
                     self.scroll_speed, len(self.measured_speeds),
                     self.calibration.scroll_speed)

        # Convert to TrackedNote objects
        notes = []
        for track in self.completed_tracks:
            note = self._track_to_note(track)
            if note is not None:
                notes.append(note)

        # Post-process: remove notes with unreasonable timing
        all_timestamps = []
        for track in self.completed_tracks:
            all_timestamps.extend(track.timestamps)
        max_time = max(all_timestamps) if all_timestamps else 300.0

        reasonable_notes = []
        for note in notes:
            if note.start_time > max_time + 10:
                continue
            if note.duration > max_time * 0.5:
                note.duration = min(note.duration, 10.0)
            if note.duration < 0.03:
                continue
            reasonable_notes.append(note)

        # Post-process: merge fragmented same-pitch notes
        reasonable_notes = self._merge_fragments(reasonable_notes)

        # Post-merge: remove very short notes that didn't merge with anything
        # These are typically spurious detections (noise)
        reasonable_notes = [n for n in reasonable_notes
                           if n.duration >= 0.08 or n.detection_count >= 4]

        # Remove ultra-short orphan fragments: notes < 0.12s that have a
        # same-pitch neighbor within 5s (they're fragments that didn't merge
        # due to gap being too large, but are clearly not standalone notes)
        reasonable_notes = self._remove_orphan_fragments(reasonable_notes)

        # Post-process: resolve overlaps on the same key
        reasonable_notes = self._resolve_overlaps(reasonable_notes)

        # Sort by start time (precise play-order)
        reasonable_notes.sort(key=lambda n: (n.start_time, n.center_x))

        # Re-assign IDs
        for i, note in enumerate(reasonable_notes):
            note.id = i + 1

        return reasonable_notes

    def _remove_orphan_fragments(self, notes: List[TrackedNote]) -> List[TrackedNote]:
        """
        Remove ultra-short notes (< 0.08s) that have a same-pitch neighbor nearby.

        These are tracking artifacts: tiny fragment detections that didn't merge
        because the gap was too large, but are clearly not real standalone notes.
        Only remove if a same-pitch neighbor is within 1.5s (close proximity
        suggests it's a fragment of a real note, not a distinct staccato note).
        """
        from collections import defaultdict

        # Group by approximate x-position (same piano key) and hand
        key_groups = defaultdict(list)
        for note in notes:
            group_key = (round(note.center_x / 20) * 20, note.hand)
            key_groups[group_key].append(note)

        to_remove = set()
        for group_key, group_notes in key_groups.items():
            group_notes.sort(key=lambda n: n.start_time)
            for i, note in enumerate(group_notes):
                if note.duration >= 0.08:
                    continue
                # Notes with high detection counts are real notes, not fragments
                # (they were tracked across many frames)
                if note.detection_count >= 10:
                    continue
                # Check if there's a same-pitch neighbor within 1.5s
                # (close proximity = likely a tracking artifact of a real note)
                has_neighbor = False
                for j, other in enumerate(group_notes):
                    if i == j:
                        continue
                    gap = abs(other.start_time - (note.start_time + note.duration))
                    if gap < 1.5 and other.duration >= 0.10:
                        has_neighbor = True
                        break
                if has_neighbor:
                    to_remove.add(id(note))

        return [n for n in notes if id(n) not in to_remove]

    def _merge_fragments(self, notes: List[TrackedNote]) -> List[TrackedNote]:
        """
        Merge consecutive same-pitch notes that are really fragments of the same note.

        Notes on the same key with small gaps between them are almost certainly
        the same physical note that got fragmented during tracking. Merge them
        into a single note spanning the full duration.
        """
        if not notes:
            return notes

        # Group by approximate x-position (same piano key) and hand
        from collections import defaultdict
        key_groups = defaultdict(list)
        for note in notes:
            # Group by rounded center_x (same key) + hand
            group_key = (round(note.center_x / 20) * 20, note.hand)
            key_groups[group_key].append(note)

        merged = []
        for group_key, group_notes in key_groups.items():
            group_notes.sort(key=lambda n: n.start_time)

            i = 0
            while i < len(group_notes):
                current = group_notes[i]
                # Try to absorb subsequent notes
                j = i + 1
                while j < len(group_notes):
                    next_note = group_notes[j]
                    current_end = current.start_time + current.duration
                    gap = next_note.start_time - current_end

                    # Merge if gap is small AND at least one note is a fragment
                    # (short duration suggests a tracking artifact, not a real note)
                    # Don't merge two long notes even if they overlap, as that
                    # means they are separate notes with overlapping play windows
                    #
                    # Use tiered thresholds based on shorter note's duration.
                    # Keep gaps tight to avoid merging distinct repeated notes
                    # (e.g., B B or G G G G in rapid passages).
                    # At 10 fps, a real tracking gap is 0.1-0.2s (1-2 frames).
                    min_dur = min(current.duration, next_note.duration)
                    if min_dur < 0.10:
                        max_gap = 0.35  # very short fragment, merge if close
                    elif min_dur < 0.20:
                        max_gap = 0.20  # short note, conservative merge
                    else:
                        max_gap = -1  # don't merge distinct notes
                    if gap < max_gap:
                        # Extend current to cover the next note
                        new_end = max(current_end,
                                      next_note.start_time + next_note.duration)
                        current.duration = new_end - current.start_time
                        current.detection_count += next_note.detection_count
                        # Keep best confidence
                        current.confidence = max(current.confidence,
                                                 next_note.confidence)
                        # Update height to max
                        current.note_height_px = max(current.note_height_px,
                                                     next_note.note_height_px)
                        j += 1
                    else:
                        break
                merged.append(current)
                i = j

        return merged

    def _resolve_overlaps(self, notes: List[TrackedNote]) -> List[TrackedNote]:
        """
        Resolve overlapping notes on the same key by truncating durations.
        """
        from collections import defaultdict

        key_groups = defaultdict(list)
        for note in notes:
            group_key = round(note.center_x / 25) * 25
            key_groups[group_key].append(note)

        resolved = []
        for group_key, group_notes in key_groups.items():
            group_notes.sort(key=lambda n: n.start_time)

            for i in range(len(group_notes)):
                note = group_notes[i]
                if i + 1 < len(group_notes):
                    next_note = group_notes[i + 1]
                    end_time = note.start_time + note.duration
                    if end_time > next_note.start_time:
                        note.duration = max(0.05, next_note.start_time - note.start_time - 0.01)
                resolved.append(note)

        return resolved

    def _track_to_note(self, track: ActiveTrack) -> Optional[TrackedNote]:
        """Convert an ActiveTrack to a TrackedNote with precise timing."""
        if not track.detections or len(track.observations) < 2:
            return None

        # Use calibrated scroll speed as primary (it's computed from video analysis)
        # Only override with measured speed if we have enough reliable data
        scroll_speed = self.calibration.scroll_speed
        if len(self.measured_speeds) >= 10:
            measured = self.scroll_speed
            # Only use measured speed if it's within 30% of calibrated
            if 0.7 * scroll_speed < measured < 1.3 * scroll_speed:
                scroll_speed = measured

        if scroll_speed <= 0:
            scroll_speed = 200.0  # fallback

        # ---- Compute precise note height ----
        # Best height: from first frame where the note was fully visible
        note_height = track.best_height
        if note_height <= 0:
            note_height = float(np.median(track.height_history)) if track.height_history else 50

        # If the note was ALWAYS clipped at top, estimate unseen portion
        if track.top_clipped_count == len(track.observations):
            # Never saw the full note. Estimate using:
            # The height grew as the note entered. Look at how it changed.
            if len(track.height_history) >= 2:
                # Height decreases as note scrolls (top becomes visible, then bottom exits)
                # Actually for top-clipped: height initially increases (more visible)
                # then stays constant (fully visible) then decreases (exiting)
                max_observed = max(track.height_history)
                # The unseen portion when first detected:
                first_obs = track.observations[0]
                last_obs = track.observations[-1]
                time_clipped = 0
                for obs in track.observations:
                    if obs.is_clipped_top:
                        time_clipped = obs.timestamp - first_obs.timestamp
                    else:
                        break
                if time_clipped > 0:
                    unseen_pixels = scroll_speed * time_clipped
                    note_height = max_observed + unseen_pixels
                else:
                    note_height = max_observed

        # ---- Compute start_time: when bottom edge reaches keyboard_y ----
        keyboard_y = self.calibration.keyboard_y

        # Find the observation closest to when the bottom edge crosses keyboard_y
        # bottom_edge = obs.y + obs.height
        # It crosses keyboard_y when bottom_edge = keyboard_y

        # Method: interpolate from two nearby observations
        bottom_edges = [(obs.timestamp, obs.y + obs.height) for obs in track.observations]

        start_time = None
        for i in range(len(bottom_edges) - 1):
            t1, b1 = bottom_edges[i]
            t2, b2 = bottom_edges[i + 1]
            if b1 <= keyboard_y <= b2:
                # Linear interpolation
                if b2 != b1:
                    frac = (keyboard_y - b1) / (b2 - b1)
                    start_time = t1 + frac * (t2 - t1)
                else:
                    start_time = t1
                break

        if start_time is None:
            # Bottom edge never crossed keyboard_y during tracking.
            # Extrapolate from last observation
            last_obs = track.observations[-1]
            last_bottom = last_obs.y + last_obs.height
            dist_to_keyboard = keyboard_y - last_bottom

            if dist_to_keyboard > 0 and scroll_speed > 0:
                # Note hasn't reached keyboard yet
                time_remaining = dist_to_keyboard / scroll_speed
                start_time = last_obs.timestamp + time_remaining
            elif dist_to_keyboard <= 0:
                # Note already passed keyboard - extrapolate backwards
                first_obs = track.observations[0]
                first_bottom = first_obs.y + first_obs.height
                if first_bottom >= keyboard_y:
                    # Already past keyboard at first observation
                    dist_past = first_bottom - keyboard_y
                    start_time = max(0, first_obs.timestamp - dist_past / scroll_speed)
                else:
                    # Crossed during tracking but we missed it (shouldn't happen often)
                    start_time = track.timestamps[0]

        if start_time is None:
            start_time = track.timestamps[0]

        # ---- Compute duration from note height ----
        if scroll_speed > 0:
            duration = note_height / scroll_speed
            duration = min(duration, 30.0)
        else:
            duration = 0.5

        # ---- Collect OCR texts ----
        ocr_texts = [d.ocr_text for d in track.detections if d.ocr_text]
        if ocr_texts:
            from collections import Counter
            ocr_counts = Counter(ocr_texts)
            # Deterministic tie-breaking: highest count, then alphabetical
            ocr_text = max(ocr_counts.keys(), key=lambda t: (ocr_counts[t], t))
        else:
            ocr_text = ''

        # ---- Mean color ----
        mean_bgr = np.mean([d.mean_bgr for d in track.detections], axis=0)

        # ---- Determine hand ----
        hands = [d.hand for d in track.detections if d.hand != 'unknown']
        if hands:
            from collections import Counter
            hand_counts = Counter(hands)
            # Deterministic tie-breaking: highest count, then alphabetical
            hand = max(hand_counts.keys(), key=lambda h: (hand_counts[h], h))
        else:
            hand = track.hand

        # ---- Confidence score ----
        # Based on: number of observations, consistency of tracking
        obs_conf = min(1.0, len(track.observations) / 10.0)
        x_std = float(np.std(track.center_x_history)) if len(track.center_x_history) > 1 else 0
        x_conf = max(0, 1.0 - x_std / 30.0)
        confidence = obs_conf * 0.6 + x_conf * 0.4

        return TrackedNote(
            id=track.id,
            note_name=ocr_text if ocr_text else 'unknown',
            hand=hand,
            color_idx=track.color_idx,
            start_time=max(0, start_time),
            duration=max(0.05, duration),
            center_x=track.mean_center_x,
            first_frame=track.observations[0].frame_index,
            last_frame=track.observations[-1].frame_index,
            detection_count=len(track.observations),
            mean_bgr=tuple(int(v) for v in mean_bgr),
            note_height_px=note_height,
            ocr_text=ocr_text,
            confidence=confidence,
        )
