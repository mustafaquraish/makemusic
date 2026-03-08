"""Frame extraction from video files using ffmpeg and OpenCV."""
import subprocess
import os
import cv2
import numpy as np
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class FrameInfo:
    """Information about an extracted frame."""
    path: str
    index: int
    timestamp: float  # seconds


def get_video_info(video_path: str) -> dict:
    """Get video metadata using ffprobe."""
    cmd = [
        'ffprobe', '-v', 'quiet', '-print_format', 'json',
        '-show_format', '-show_streams', video_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr}")
    
    import json
    data = json.loads(result.stdout)
    
    video_stream = None
    for stream in data.get('streams', []):
        if stream.get('codec_type') == 'video':
            video_stream = stream
            break
    
    if not video_stream:
        raise RuntimeError("No video stream found")
    
    # Parse FPS
    fps_str = video_stream.get('avg_frame_rate', '30/1')
    if '/' in fps_str:
        num, den = fps_str.split('/')
        fps = float(num) / float(den) if float(den) != 0 else 30.0
    else:
        fps = float(fps_str)
    
    # Parse duration - try multiple sources
    duration = None
    if 'duration' in video_stream:
        duration = float(video_stream['duration'])
    elif 'tags' in video_stream and 'DURATION' in video_stream['tags']:
        dur_str = video_stream['tags']['DURATION']
        parts = dur_str.split(':')
        duration = float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
    elif 'duration' in data.get('format', {}):
        duration = float(data['format']['duration'])
    
    return {
        'width': int(video_stream['width']),
        'height': int(video_stream['height']),
        'fps': fps,
        'duration': duration,
        'codec': video_stream.get('codec_name', 'unknown'),
    }


def extract_frames(video_path: str, output_dir: str, fps: float = 10.0,
                   start_time: float = 0.0, end_time: Optional[float] = None) -> List[FrameInfo]:
    """
    Extract frames from a video at the specified FPS.
    
    Args:
        video_path: Path to the video file
        output_dir: Directory to save extracted frames
        fps: Frames per second to extract
        start_time: Start extraction at this time (seconds)
        end_time: Stop extraction at this time (seconds), None for full video
    
    Returns:
        List of FrameInfo objects for extracted frames
    """
    os.makedirs(output_dir, exist_ok=True)
    
    cmd = ['ffmpeg', '-y']
    
    if start_time > 0:
        cmd.extend(['-ss', str(start_time)])
    
    cmd.extend(['-i', video_path])
    
    if end_time is not None:
        duration = end_time - start_time
        cmd.extend(['-t', str(duration)])
    
    cmd.extend([
        '-vf', f'fps={fps}',
        os.path.join(output_dir, 'frame_%06d.png')
    ])
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr}")
    
    # Collect frame info
    frames = []
    frame_files = sorted([f for f in os.listdir(output_dir) if f.startswith('frame_') and f.endswith('.png')])
    
    for i, fname in enumerate(frame_files):
        frames.append(FrameInfo(
            path=os.path.join(output_dir, fname),
            index=i,
            timestamp=start_time + i / fps
        ))
    
    return frames


def load_frame(frame_path: str) -> np.ndarray:
    """Load a frame as a numpy array (BGR)."""
    img = cv2.imread(frame_path)
    if img is None:
        raise FileNotFoundError(f"Could not load frame: {frame_path}")
    return img


def load_frame_rgb(frame_path: str) -> np.ndarray:
    """Load a frame as RGB numpy array."""
    img = load_frame(frame_path)
    return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)


def extract_frames_opencv(video_path: str, fps: float = 10.0,
                          start_time: float = 0.0, 
                          end_time: Optional[float] = None) -> List[tuple]:
    """
    Extract frames directly using OpenCV (no temp files).
    
    Returns list of (timestamp, frame_bgr) tuples.
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video: {video_path}")
    
    video_fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    frame_interval = int(video_fps / fps) if fps < video_fps else 1
    start_frame = int(start_time * video_fps)
    end_frame = int(end_time * video_fps) if end_time else total_frames
    
    frames = []
    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
    
    current_frame = start_frame
    while current_frame < end_frame:
        ret, frame = cap.read()
        if not ret:
            break
        
        if (current_frame - start_frame) % frame_interval == 0:
            timestamp = current_frame / video_fps
            frames.append((timestamp, frame.copy()))
        
        current_frame += 1
    
    cap.release()
    return frames
