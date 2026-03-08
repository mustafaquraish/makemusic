"""Command-line interface for MakeMusic."""
import argparse
import os
import sys


def main():
    parser = argparse.ArgumentParser(
        description='MakeMusic - Convert falling notes videos to interactive HTML'
    )
    subparsers = parser.add_subparsers(dest='command', help='Command')
    
    # analyze command
    analyze_parser = subparsers.add_parser('analyze', help='Analyze a video')
    analyze_parser.add_argument('video', help='Path to video file')
    analyze_parser.add_argument('-o', '--output', default='output',
                              help='Output directory (default: output)')
    analyze_parser.add_argument('--fps', type=float, default=10.0,
                              help='Analysis FPS (default: 10)')
    analyze_parser.add_argument('--no-ocr', action='store_true',
                              help='Disable OCR')
    analyze_parser.add_argument('--ocr-rate', type=int, default=5,
                              help='Run OCR every N frames (default: 5)')
    analyze_parser.add_argument('--keyboard-map', type=str, default=None,
                              help='Path to pre-built keyboard map JSON')
    analyze_parser.add_argument('--octave-offset', type=int, default=None,
                              help='Absolute octave for first visible C (default: auto)')
    analyze_parser.add_argument('-v', '--verbose', action='store_true',
                              help='Verbose output')
    
    args = parser.parse_args()
    
    if args.command == 'analyze':
        from .pipeline import analyze_video
        analyze_video(
            video_path=args.video,
            output_dir=args.output,
            analysis_fps=args.fps,
            ocr_enabled=not args.no_ocr,
            ocr_sample_rate=args.ocr_rate,
            keyboard_map_json=args.keyboard_map,
            octave_offset=args.octave_offset,
            verbose=True,
        )
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
