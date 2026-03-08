"""Frame extraction from video files using ffmpeg and OpenCV."""
import json
import subprocess
import numpy as np
from typing import List, Optional, Generator, Tuple

import cv2


def get_video_info(video_path: str) -> dict:
    """Get video metadata using ffprobe."""
    cmd = [
        'ffprobe', '-v', 'quiet', '-print_format', 'json',
        '-show_format', '-show_streams', video_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr}")

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


def pipe_frames(video_path: str, fps: float, width: int, height: int,
                start_time: float = 0, end_time: Optional[float] = None
                ) -> List[Tuple[float, np.ndarray]]:
    """Extract frames using ffmpeg pipe — fast for low fps / short clips.

    Uses ffmpeg's fps filter for efficient frame decimation; the decoder
    can skip non-reference frames it doesn't need.
    Returns list of (timestamp, frame_bgr) tuples.
    """
    cmd = ['ffmpeg', '-v', 'quiet', '-threads', '0']
    if start_time > 0:
        cmd += ['-ss', str(start_time)]
    cmd += ['-i', video_path]
    if end_time is not None:
        cmd += ['-t', str(end_time - start_time)]
    cmd += ['-vf', f'fps={fps}',
            '-f', 'rawvideo', '-pix_fmt', 'bgr24', 'pipe:1']

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL)
    frame_size = width * height * 3
    frames: list[tuple[float, np.ndarray]] = []
    i = 0
    try:
        while True:
            data = proc.stdout.read(frame_size)
            if len(data) < frame_size:
                break
            frame = np.frombuffer(
                data, dtype=np.uint8,
            ).reshape(height, width, 3).copy()
            timestamp = start_time + i / fps
            frames.append((timestamp, frame))
            i += 1
    finally:
        proc.stdout.close()
        proc.wait()
    return frames


def iter_frames_pipe(video_path: str, fps: float,
                     width: int, height: int,
                     start_time: float = 0,
                     end_time: Optional[float] = None,
                     crop_height: Optional[int] = None,
                     ) -> Generator[Tuple[float, np.ndarray], None, None]:
    """Yield (timestamp, frame_bgr) from ffmpeg pipe — streaming version.

    Each frame is a **view** into a freshly-allocated buffer so it is
    safe to slice without an extra copy.

    If *crop_height* is given, only the top *crop_height* rows of each
    frame are decoded (via ffmpeg's crop filter), reducing pipe
    throughput and memory by up to 40%.
    """
    vf_parts = [f'fps={fps}']
    out_h = height
    if crop_height is not None and crop_height < height:
        vf_parts.append(f'crop={width}:{crop_height}:0:0')
        out_h = crop_height

    cmd = ['ffmpeg', '-v', 'quiet', '-threads', '0']
    if start_time > 0:
        cmd += ['-ss', str(start_time)]
    cmd += ['-i', video_path]
    if end_time is not None:
        cmd += ['-t', str(end_time - start_time)]
    cmd += ['-vf', ','.join(vf_parts),
            '-f', 'rawvideo', '-pix_fmt', 'bgr24', 'pipe:1']

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL)
    frame_size = width * out_h * 3
    i = 0
    try:
        while True:
            data = proc.stdout.read(frame_size)
            if len(data) < frame_size:
                break
            frame = np.frombuffer(
                data, dtype=np.uint8,
            ).reshape(out_h, width, 3)
            timestamp = start_time + i / fps
            yield (timestamp, frame)
            i += 1
    finally:
        proc.stdout.close()
        proc.wait()


def extract_frames_opencv(video_path: str, fps: float = 10.0,
                          start_time: float = 0.0,
                          end_time: Optional[float] = None) -> List[tuple]:
    """Extract frames using OpenCV — kept for backward compatibility.

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
