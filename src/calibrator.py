"""
Auto-calibration for falling notes videos.

Detects:
- Keyboard position (play line)
- Note colors (left/right hand)
- Scroll speed (pixels per second)
- Intro end time (when notes first appear)
- Static elements (watermarks, UI)
"""
import cv2
import numpy as np
from dataclasses import dataclass, field
from typing import List, Tuple, Optional
from sklearn.cluster import KMeans, DBSCAN


@dataclass
class NoteColor:
    """A detected note color with HSV range."""
    center_hsv: Tuple[int, int, int]
    center_bgr: Tuple[int, int, int]
    label: str  # 'right_hand', 'left_hand', 'unknown'
    h_range: Tuple[int, int] = (0, 180)
    s_range: Tuple[int, int] = (0, 255)
    v_range: Tuple[int, int] = (0, 255)


@dataclass 
class CalibrationResult:
    """Result of video calibration."""
    keyboard_y: int  # Y position of the top of the keyboard / play line
    keyboard_height: int  # Height of keyboard region
    note_area_top: int  # Top of the note falling area
    note_area_bottom: int  # Bottom of the note falling area (= keyboard_y)
    note_colors: List[NoteColor] = field(default_factory=list)
    scroll_speed: float = 0.0  # pixels per second
    intro_end_frame: int = 0  # Frame index where notes start
    intro_end_time: float = 0.0  # Time in seconds where notes start
    static_mask: Optional[np.ndarray] = None  # Mask of static UI elements
    frame_width: int = 1920
    frame_height: int = 1080


def detect_keyboard_region(frame_bgr: np.ndarray) -> Tuple[int, int]:
    """
    Detect the piano keyboard region in a frame.
    
    The keyboard is typically at the bottom, characterized by:
    - High number of vertical transitions (black/white keys)
    - Consistent horizontal pattern
    - Located in the bottom portion of the frame
    
    Returns:
        (keyboard_y, keyboard_height) — top y-coordinate and height of keyboard
    """
    h, w = frame_bgr.shape[:2]
    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    
    # Scan horizontal rows from bottom up
    # Count the number of intensity transitions per row
    transition_counts = []
    for y in range(h - 1, h // 3, -1):
        row = gray[y].astype(np.int16)
        transitions = np.sum(np.abs(np.diff(row)) > 30)
        transition_counts.append((y, transitions))
    
    if not transition_counts:
        return h - 100, 100
    
    # Find the region with consistently high transitions (this is the keyboard)
    # Group consecutive rows with high transition counts
    threshold = max(t for _, t in transition_counts) * 0.3
    threshold = max(threshold, 20)  # At least 20 transitions
    
    keyboard_rows = []
    for y, tc in transition_counts:
        if tc >= threshold:
            keyboard_rows.append(y)
    
    if not keyboard_rows:
        # Fallback: assume keyboard is bottom 20%
        return int(h * 0.8), int(h * 0.2)
    
    keyboard_top = min(keyboard_rows)
    keyboard_bottom = max(keyboard_rows)
    
    return keyboard_top, keyboard_bottom - keyboard_top + 1


def detect_note_colors(frames_bgr: List[np.ndarray], keyboard_y: int,
                       note_area_top: int = 0) -> List[NoteColor]:
    """
    Detect the distinct note colors used in the video.
    
    Strategy:
    1. Collect all non-background, non-keyboard colored pixels from the note area
    2. Cluster them to find dominant colors
    3. Classify as left/right hand based on position tendency
    
    Args:
        frames_bgr: List of frames to analyze
        keyboard_y: Y position of keyboard (notes are above this)
        note_area_top: Top of the note area
    
    Returns:
        List of detected NoteColor objects
    """
    all_colored_pixels_hsv = []
    all_colored_pixels_bgr = []
    all_colored_x_positions = []
    
    for frame in frames_bgr:
        h, w = frame.shape[:2]
        # Only look at the note area (above keyboard)
        note_region = frame[note_area_top:keyboard_y, :]
        note_hsv = cv2.cvtColor(note_region, cv2.COLOR_BGR2HSV)
        
        # Filter: non-dark (V > 60) and somewhat saturated (S > 50)
        mask = (note_hsv[:, :, 2] > 60) & (note_hsv[:, :, 1] > 50)
        
        if np.sum(mask) == 0:
            continue
        
        # Collect colored pixel info
        ys, xs = np.where(mask)
        pixels_hsv = note_hsv[mask]
        pixels_bgr = note_region[mask]
        
        # Subsample if too many pixels (deterministic)
        if len(pixels_hsv) > 5000:
            rng = np.random.RandomState(42)
            indices = rng.choice(len(pixels_hsv), 5000, replace=False)
            pixels_hsv = pixels_hsv[indices]
            pixels_bgr = pixels_bgr[indices]
            xs = xs[indices]
        
        all_colored_pixels_hsv.append(pixels_hsv)
        all_colored_pixels_bgr.append(pixels_bgr)
        all_colored_x_positions.append(xs)
    
    if not all_colored_pixels_hsv:
        return []
    
    all_hsv = np.vstack(all_colored_pixels_hsv)
    all_bgr = np.vstack(all_colored_pixels_bgr)
    all_x = np.concatenate(all_colored_x_positions)
    
    if len(all_hsv) < 10:
        return []
    
    # Cluster by hue primarily
    # Use hue (circular) and saturation for clustering
    # Convert hue to cartesian for better clustering
    hue_rad = all_hsv[:, 0].astype(np.float64) * np.pi / 90  # OpenCV hue is 0-180
    hue_x = np.cos(hue_rad)
    hue_y = np.sin(hue_rad)
    sat = all_hsv[:, 1].astype(np.float64) / 255.0
    
    features = np.column_stack([hue_x * 2, hue_y * 2, sat])
    
    # Try 2 and 3 clusters, pick the best
    best_n = 1
    best_score = -1
    
    for n_clusters in [2, 3]:
        if len(features) < n_clusters:
            continue
        try:
            kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
            labels = kmeans.fit_predict(features)
            
            # Score: silhouette-like — how well-separated are the clusters?
            cluster_sizes = [np.sum(labels == i) for i in range(n_clusters)]
            min_size = min(cluster_sizes)
            
            # Reject if any cluster is too small (< 5% of total)
            if min_size < len(features) * 0.05:
                continue
            
            # Calculate inter-cluster distance in hue space
            centers = kmeans.cluster_centers_
            min_dist = float('inf')
            for i in range(n_clusters):
                for j in range(i + 1, n_clusters):
                    dist = np.linalg.norm(centers[i] - centers[j])
                    min_dist = min(min_dist, dist)
            
            if min_dist > best_score:
                best_score = min_dist
                best_n = n_clusters
        except Exception:
            continue
    
    # If clusters aren't well-separated, use 1 color
    if best_score < 0.5:
        best_n = 1
    
    if best_n == 1:
        # Single color
        mean_hsv = np.mean(all_hsv, axis=0).astype(int)
        mean_bgr = np.mean(all_bgr, axis=0).astype(int)
        std_hsv = np.std(all_hsv, axis=0)
        
        color = NoteColor(
            center_hsv=tuple(mean_hsv),
            center_bgr=tuple(mean_bgr),
            label='right_hand',
            h_range=(max(0, int(mean_hsv[0] - std_hsv[0] * 2)), min(180, int(mean_hsv[0] + std_hsv[0] * 2))),
            s_range=(max(0, int(mean_hsv[1] - std_hsv[1] * 2)), min(255, int(mean_hsv[1] + std_hsv[1] * 2))),
            v_range=(max(0, int(mean_hsv[2] - std_hsv[2] * 2)), min(255, int(mean_hsv[2] + std_hsv[2] * 2))),
        )
        return [color]
    
    # Multi-color clustering
    kmeans = KMeans(n_clusters=best_n, random_state=42, n_init=10)
    labels = kmeans.fit_predict(features)
    
    colors = []
    for i in range(best_n):
        cluster_mask = labels == i
        cluster_hsv = all_hsv[cluster_mask]
        cluster_bgr = all_bgr[cluster_mask]
        cluster_x = all_x[cluster_mask]
        
        mean_hsv = np.mean(cluster_hsv, axis=0).astype(int)
        mean_bgr = np.mean(cluster_bgr, axis=0).astype(int)
        std_hsv = np.std(cluster_hsv, axis=0)
        mean_x = np.mean(cluster_x)
        
        color = NoteColor(
            center_hsv=tuple(mean_hsv),
            center_bgr=tuple(mean_bgr),
            label='unknown',
            h_range=(max(0, int(mean_hsv[0] - std_hsv[0] * 2.5)), min(180, int(mean_hsv[0] + std_hsv[0] * 2.5))),
            s_range=(max(0, int(mean_hsv[1] - std_hsv[1] * 2.5)), min(255, int(mean_hsv[1] + std_hsv[1] * 2.5))),
            v_range=(max(0, int(mean_hsv[2] - std_hsv[2] * 2.5)), min(255, int(mean_hsv[2] + std_hsv[2] * 2.5))),
        )
        colors.append((color, mean_x))
    
    # Label hands: left hand tends to be on the left (lower x), right hand on right
    # Also, in most videos, right hand = warmer color, left hand = cooler
    if len(colors) >= 2:
        # Sort by mean x position
        colors.sort(key=lambda c: c[1])
        colors[0][0].label = 'left_hand'
        colors[-1][0].label = 'right_hand'
        if len(colors) > 2:
            for c in colors[1:-1]:
                c[0].label = 'unknown'
    elif len(colors) == 1:
        colors[0][0].label = 'right_hand'
    
    return [c[0] for c in colors]


def detect_intro_end(frames_data: List[Tuple[float, np.ndarray]], 
                     keyboard_y: int) -> Tuple[int, float]:
    """
    Detect when the intro ends and actual note playing begins.
    
    Strategy:
    - Track the number of discrete colored blob regions in the note area
    - During intros, we see either: a full-screen title card OR a blank dark screen
    - During playing, we see: discrete note rectangles on a dark background
    - Also check for motion (notes moving) and scene transitions
    
    Key insight: an intro frame might have LOTS of colored pixels (title card) or
    none (blank). Playing frames have a moderate number in discrete regions.
    
    Args:
        frames_data: List of (timestamp, frame_bgr) tuples
        keyboard_y: Y position of keyboard
    
    Returns:
        (frame_index, timestamp) of intro end
    """
    if not frames_data:
        return 0, 0.0
    
    h0, w0 = frames_data[0][1].shape[:2]
    total_pixels = keyboard_y * w0
    
    # For each frame, compute:
    # 1. Colored pixel percentage
    # 2. Number of discrete colored blobs (contours)
    # 3. Motion score (frame diff)
    # 4. Whether the frame looks like "playing" (dark bg + note blobs)
    
    frame_stats = []
    prev_gray = None
    
    for i, (ts, frame) in enumerate(frames_data):
        h, w = frame.shape[:2]
        note_region = frame[0:keyboard_y, :]
        hsv = cv2.cvtColor(note_region, cv2.COLOR_BGR2HSV)
        gray = cv2.cvtColor(note_region, cv2.COLOR_BGR2GRAY)
        
        # Count colored pixels
        colored_mask = (hsv[:, :, 2] > 60) & (hsv[:, :, 1] > 50)
        colored_pct = np.sum(colored_mask) / total_pixels if total_pixels > 0 else 0
        
        # Count dark pixels (background)
        dark_pct = np.sum(hsv[:, :, 2] < 40) / total_pixels if total_pixels > 0 else 0
        
        # Count discrete colored blobs
        colored_uint8 = colored_mask.astype(np.uint8) * 255
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        colored_uint8 = cv2.morphologyEx(colored_uint8, cv2.MORPH_OPEN, kernel)
        contours, _ = cv2.findContours(colored_uint8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        big_blobs = [c for c in contours if cv2.contourArea(c) > 500]
        
        # Motion
        motion = 0
        if prev_gray is not None and prev_gray.shape == gray.shape:
            diff = cv2.absdiff(gray, prev_gray)
            motion = np.mean(diff)
        prev_gray = gray
        
        # A "playing" frame has: dark background (>40%), moderate colored pixels (1-20%),
        # and at least 1 discrete blob
        is_playing_like = (
            dark_pct > 0.40 and 
            0.005 < colored_pct < 0.25 and 
            len(big_blobs) >= 1
        )
        
        frame_stats.append({
            'colored_pct': colored_pct,
            'dark_pct': dark_pct,
            'blob_count': len(big_blobs),
            'motion': motion,
            'is_playing_like': is_playing_like,
        })
    
    # Strategy 1: Find first frame that looks like "playing" AND has motion
    # Use a small window to avoid false positives
    window = 3
    for i in range(len(frame_stats)):
        window_end = min(i + window, len(frame_stats))
        window_stats = frame_stats[i:window_end]
        
        playing_count = sum(1 for s in window_stats if s['is_playing_like'])
        has_motion = any(s['motion'] > 0.3 for s in window_stats)
        
        if playing_count >= min(2, len(window_stats)) and has_motion:
            return i, frames_data[i][0]
    
    # Strategy 2: Look for significant scene change followed by playing-like frames
    for i in range(1, len(frame_stats)):
        if frame_stats[i]['motion'] > 5.0:
            future = frame_stats[i:min(i + window + 1, len(frame_stats))]
            if any(s['is_playing_like'] for s in future):
                return i, frames_data[i][0]
    
    # Strategy 3: Find first frame with discrete blobs on dark background
    for i, stats in enumerate(frame_stats):
        if stats['is_playing_like']:
            return i, frames_data[i][0]
    
    # Fallback: if colored percentage drops significantly (title → dark scene)
    for i in range(1, len(frame_stats)):
        if (frame_stats[i-1]['colored_pct'] > 0.3 and 
            frame_stats[i]['colored_pct'] < 0.1):
            return i, frames_data[i][0]
    
    return 0, 0.0


def estimate_scroll_speed(frames_data: List[Tuple[float, np.ndarray]],
                          note_colors: List[NoteColor],
                          keyboard_y: int) -> float:
    """
    Estimate the scroll speed of falling notes in pixels per second.
    
    Strategy:
    - Find a prominent note rectangle in one frame
    - Track it across consecutive frames
    - Measure vertical displacement / time
    
    Args:
        frames_data: List of (timestamp, frame_bgr) tuples
        note_colors: Detected note colors
        keyboard_y: Y position of keyboard
    
    Returns:
        Scroll speed in pixels per second
    """
    if len(frames_data) < 3 or not note_colors:
        return 300.0  # Default fallback
    
    speeds = []
    
    for frame_idx in range(len(frames_data) - 1):
        ts1, frame1 = frames_data[frame_idx]
        ts2, frame2 = frames_data[frame_idx + 1]
        dt = ts2 - ts1
        
        if dt <= 0:
            continue
        
        # Create masks for note colors in both frames
        for note_color in note_colors:
            mask1 = create_color_mask(frame1, note_color, keyboard_y)
            mask2 = create_color_mask(frame2, note_color, keyboard_y)
            
            # Find contours in both frames
            contours1, _ = cv2.findContours(mask1, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            contours2, _ = cv2.findContours(mask2, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            # Filter to significant contours
            rects1 = []
            for c in contours1:
                area = cv2.contourArea(c)
                if area > 1000:
                    x, y, w, h_r = cv2.boundingRect(c)
                    if h_r > 20:  # Notes have some vertical extent
                        rects1.append((x, y, w, h_r, x + w // 2))
            
            rects2 = []
            for c in contours2:
                area = cv2.contourArea(c)
                if area > 1000:
                    x, y, w, h_r = cv2.boundingRect(c)
                    if h_r > 20:
                        rects2.append((x, y, w, h_r, x + w // 2))
            
            # Match rectangles between frames by x-center position
            for r1 in rects1:
                x1, y1, w1, h1, cx1 = r1
                best_match = None
                best_dist = float('inf')
                
                for r2 in rects2:
                    x2, y2, w2, h2, cx2 = r2
                    # Must be at similar x position (same key)
                    if abs(cx1 - cx2) < 20 and abs(w1 - w2) < 20:
                        # And moved downward
                        dy = y2 - y1
                        if 0 < dy < 200:  # Moved down but not too far
                            dist = abs(cx1 - cx2) + abs(w1 - w2)
                            if dist < best_dist:
                                best_dist = dist
                                best_match = r2
                
                if best_match is not None:
                    dy = best_match[1] - y1
                    speed = dy / dt
                    if 50 < speed < 2000:  # Sanity check
                        speeds.append(speed)
    
    if speeds:
        # Use median to be robust against outliers
        return float(np.median(speeds))
    
    return 300.0  # Default fallback


def create_color_mask(frame_bgr: np.ndarray, note_color: NoteColor,
                      keyboard_y: int, margin: int = 0) -> np.ndarray:
    """
    Create a binary mask for pixels matching a note color.
    
    Args:
        frame_bgr: Input frame
        note_color: Color to match
        keyboard_y: Y of keyboard (mask only above this)
        margin: Additional margin above keyboard to exclude
    
    Returns:
        Binary mask (uint8, 0 or 255)
    """
    h, w = frame_bgr.shape[:2]
    hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
    
    # Create mask for the color range
    lower = np.array([note_color.h_range[0], note_color.s_range[0], note_color.v_range[0]])
    upper = np.array([note_color.h_range[1], note_color.s_range[1], note_color.v_range[1]])
    
    # Handle hue wrapping (e.g., red spans 170-10)
    if note_color.h_range[0] > note_color.h_range[1]:
        mask1 = cv2.inRange(hsv, np.array([note_color.h_range[0], note_color.s_range[0], note_color.v_range[0]]),
                           np.array([180, note_color.s_range[1], note_color.v_range[1]]))
        mask2 = cv2.inRange(hsv, np.array([0, note_color.s_range[0], note_color.v_range[0]]),
                           np.array([note_color.h_range[1], note_color.s_range[1], note_color.v_range[1]]))
        color_mask = mask1 | mask2
    else:
        color_mask = cv2.inRange(hsv, lower, upper)
    
    # Only keep pixels above keyboard
    region_mask = np.zeros((h, w), dtype=np.uint8)
    region_mask[0:max(0, keyboard_y - margin), :] = 255
    
    return color_mask & region_mask


def detect_static_elements(frames_bgr: List[np.ndarray], 
                           keyboard_y: int) -> np.ndarray:
    """
    Detect static UI elements (watermarks, text overlays) that don't move
    across frames.
    
    Strategy:
    - Compare multiple frames
    - Pixels that remain the same across many frames are static
    - Exclude the keyboard area (always static)
    
    Returns:
        Binary mask of static elements (uint8)
    """
    if len(frames_bgr) < 3:
        return np.zeros(frames_bgr[0].shape[:2], dtype=np.uint8)
    
    h, w = frames_bgr[0].shape[:2]
    
    # Sample frames evenly
    indices = np.linspace(0, len(frames_bgr) - 1, min(10, len(frames_bgr)), dtype=int)
    sampled = [frames_bgr[i] for i in indices]
    
    # Count how many frames each pixel stays the same
    static_count = np.zeros((h, w), dtype=np.int32)
    
    for i in range(len(sampled) - 1):
        diff = cv2.absdiff(sampled[i], sampled[i + 1])
        diff_gray = np.max(diff, axis=2)
        static_pixels = diff_gray < 10  # Pixel barely changed
        static_count += static_pixels.astype(np.int32)
    
    # Pixels static in >80% of comparisons are static elements
    threshold = int(len(sampled) * 0.8)
    static_mask = (static_count >= threshold).astype(np.uint8) * 255
    
    # Exclude keyboard area (it's expected to be static)
    static_mask[keyboard_y:, :] = 0
    
    # Also exclude very dark static pixels (just background)
    mean_frame = np.mean([f.astype(np.float32) for f in sampled], axis=0)
    dark_mask = np.max(mean_frame, axis=2) < 40
    static_mask[dark_mask] = 0
    
    return static_mask


def calibrate(frames_data: List[Tuple[float, np.ndarray]]) -> CalibrationResult:
    """
    Run full calibration on a set of frames.
    
    Args:
        frames_data: List of (timestamp, frame_bgr) tuples, should span the intro and 
                     early playing section
    
    Returns:
        CalibrationResult with all detected parameters
    """
    if not frames_data:
        raise ValueError("No frames provided for calibration")
    
    h, w = frames_data[0][1].shape[:2]
    
    # Step 1: Find a frame that's likely during playback (not intro)
    # Use a frame from the middle of the provided frames
    mid_idx = len(frames_data) * 2 // 3  # Use 2/3 through to likely be past intro
    mid_frame = frames_data[mid_idx][1]
    
    # Step 2: Detect keyboard
    keyboard_y, keyboard_height = detect_keyboard_region(mid_frame)
    
    # Step 3: Detect intro end
    intro_idx, intro_time = detect_intro_end(frames_data, keyboard_y)
    
    # Step 4: Get frames after intro for color analysis
    playing_frames = [f for ts, f in frames_data[intro_idx:]]
    if not playing_frames:
        playing_frames = [f for ts, f in frames_data]
    
    # Step 5: Detect note colors
    note_colors = detect_note_colors(playing_frames, keyboard_y)
    
    # Step 6: Detect static elements
    static_mask = detect_static_elements(playing_frames, keyboard_y)
    
    # Step 7: Estimate scroll speed
    playing_data = frames_data[intro_idx:]
    if len(playing_data) >= 2:
        scroll_speed = estimate_scroll_speed(playing_data, note_colors, keyboard_y)
    else:
        scroll_speed = 300.0
    
    return CalibrationResult(
        keyboard_y=keyboard_y,
        keyboard_height=keyboard_height,
        note_area_top=0,
        note_area_bottom=keyboard_y,
        note_colors=note_colors,
        scroll_speed=scroll_speed,
        intro_end_frame=intro_idx,
        intro_end_time=intro_time,
        static_mask=static_mask,
        frame_width=w,
        frame_height=h,
    )
