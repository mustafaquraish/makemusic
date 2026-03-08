"""
OCR reader for note labels on falling note rectangles.

Uses EasyOCR to read the note letter labels (A-G, with sharps/flats)
that are often printed on the colored note rectangles.
"""
import cv2
import numpy as np
from typing import List, Optional, Tuple
from dataclasses import dataclass

# Lazy-load EasyOCR to avoid slow import at module level
_reader = None


def get_reader():
    """Get or create the EasyOCR reader (lazy initialization)."""
    global _reader
    if _reader is None:
        import easyocr
        _reader = easyocr.Reader(['en'], gpu=False, verbose=False)
    return _reader


@dataclass
class OCRResult:
    """Result of OCR on a note region."""
    text: str
    confidence: float
    bbox: Tuple[int, int, int, int]  # x, y, w, h within the note region


def read_note_label(frame_bgr: np.ndarray, 
                    note_x: int, note_y: int, 
                    note_w: int, note_h: int,
                    padding: int = 2) -> Optional[OCRResult]:
    """
    Read the text label on a single note rectangle.
    
    Args:
        frame_bgr: Full frame image
        note_x, note_y: Top-left corner of the note
        note_w, note_h: Width and height of the note
        padding: Extra pixels around the note to include
    
    Returns:
        OCRResult if text was found, None otherwise
    """
    h, w = frame_bgr.shape[:2]
    
    # Extract note region with padding
    x1 = max(0, note_x - padding)
    y1 = max(0, note_y - padding)
    x2 = min(w, note_x + note_w + padding)
    y2 = min(h, note_y + note_h + padding)
    
    roi = frame_bgr[y1:y2, x1:x2]
    
    if roi.shape[0] < 10 or roi.shape[1] < 10:
        return None
    
    # Preprocess: increase contrast, resize if too small
    # Scale up small regions for better OCR
    scale = 1.0
    if roi.shape[0] < 40 or roi.shape[1] < 40:
        scale = max(40 / roi.shape[0], 40 / roi.shape[1])
        roi = cv2.resize(roi, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    
    # Convert to grayscale and threshold for better OCR
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    
    # Try to enhance text contrast
    # The text is usually white or dark on a colored background
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    # Run OCR
    reader = get_reader()
    
    try:
        results = reader.readtext(roi, allowlist='ABCDEFGabcdefg#b♯♭0123456789',
                                  paragraph=False, min_size=5)
    except Exception:
        return None
    
    if not results:
        # Try with binary image
        try:
            binary_bgr = cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)
            results = reader.readtext(binary_bgr, allowlist='ABCDEFGabcdefg#b♯♭0123456789',
                                      paragraph=False, min_size=5)
        except Exception:
            return None
    
    if not results:
        return None
    
    # Filter results: keep only plausible note labels
    valid_results = []
    for bbox, text, conf in results:
        text = text.strip().upper()
        # Valid note labels: single letter A-G, optionally followed by # or b, and octave
        if len(text) >= 1 and text[0] in 'ABCDEFG':
            valid_results.append((text, conf, bbox))
    
    if not valid_results:
        return None
    
    # Pick highest confidence
    best = max(valid_results, key=lambda r: r[1])
    text, conf, bbox = best
    
    return OCRResult(
        text=text,
        confidence=conf,
        bbox=(x1, y1, x2 - x1, y2 - y1),
    )


def batch_read_labels(frame_bgr: np.ndarray,
                      notes: List[dict]) -> List[Optional[OCRResult]]:
    """
    Read labels for multiple notes in a single frame.
    
    More efficient than calling read_note_label individually because
    we can batch the OCR calls.
    
    Args:
        frame_bgr: Full frame image
        notes: List of dicts with 'x', 'y', 'width', 'height' keys
    
    Returns:
        List of OCRResult (or None) for each note
    """
    results = []
    for note in notes:
        result = read_note_label(
            frame_bgr,
            note['x'], note['y'],
            note['width'], note['height']
        )
        results.append(result)
    return results


def read_all_frame_labels(frame_bgr: np.ndarray,
                          allow_list: str = 'ABCDEFGabcdefg#b♯♭0123456789') -> List[OCRResult]:
    """
    Read all text in the note area of a frame.
    
    Useful for initial calibration to find all visible labels.
    
    Args:
        frame_bgr: Full frame image
        allow_list: Characters to allow in OCR
    
    Returns:
        List of OCRResult for all detected text
    """
    reader = get_reader()
    
    try:
        results = reader.readtext(frame_bgr, allowlist=allow_list,
                                  paragraph=False, min_size=10)
    except Exception:
        return []
    
    ocr_results = []
    for bbox, text, conf in results:
        text = text.strip().upper()
        if len(text) >= 1 and text[0] in 'ABCDEFG':
            # Get bounding box as x, y, w, h
            pts = np.array(bbox)
            x = int(pts[:, 0].min())
            y = int(pts[:, 1].min())
            w = int(pts[:, 0].max() - x)
            h = int(pts[:, 1].max() - y)
            
            ocr_results.append(OCRResult(
                text=text,
                confidence=conf,
                bbox=(x, y, w, h),
            ))
    
    return ocr_results
