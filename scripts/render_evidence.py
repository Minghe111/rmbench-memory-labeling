#!/usr/bin/env python3
"""Render selected raw RMBench HDF5 frames and optional RGB checksums.

The published JPEG format is documented by RMBench's reference codec:
https://github.com/RoboTwin-Platform/RMBench/blob/7d1cdfc7661c273a7a5c5f6126e2d1a7f0a3f4b7/data/decode_image_bit.py
"""

from argparse import ArgumentParser
from hashlib import file_digest, sha256
import json
from pathlib import Path
from tempfile import NamedTemporaryFile

import cv2
import h5py
import numpy as np
from PIL import Image, ImageDraw


CAMERAS = {
    'head': 'head_camera',
    'left_wrist': 'left_camera',
    'right_wrist': 'right_camera',
}
RGB_COMMENT = b'XPL-RGB1'


def marked_rgb_jpeg(data: memoryview) -> bool:
    """Recognize a complete XPL-RGB1 comment in the JPEG header."""
    if data[:2] != b'\xff\xd8':
        return False
    offset = 2
    while offset < len(data) and data[offset] == 0xff:
        while offset < len(data) and data[offset] == 0xff:
            offset += 1
        if offset == len(data):
            return False
        tag = data[offset]
        offset += 1
        if tag in (0, 0xd9, 0xda):
            return False
        if tag == 1 or 0xd0 <= tag <= 0xd8:
            continue
        length = int.from_bytes(data[offset:offset + 2], 'big')
        end = offset + length
        if length < 2 or end > len(data):
            return False
        if tag == 0xfe and data[offset + 2:end] == RGB_COMMENT:
            return True
        offset = end
    return False


def decode_rgb(frame: bytes | np.ndarray) -> np.ndarray:
    """Return the published RMBench camera frame as uint8 HWC RGB."""
    if isinstance(frame, bytes):
        bytes_view = memoryview(frame)
    elif isinstance(frame, np.ndarray) and frame.dtype == np.uint8:
        if frame.ndim == 3 and frame.shape[-1] == 3:
            return np.ascontiguousarray(frame)
        if frame.ndim != 1:
            raise ValueError(f'Unsupported uint8 camera frame shape {frame.shape}')
        bytes_view = memoryview(np.ascontiguousarray(frame))
    else:
        raise ValueError(f'Unsupported camera frame type {type(frame).__name__}')
    if not bytes_view:
        raise ValueError('Empty camera frame')
    rgb = cv2.imdecode(np.frombuffer(bytes_view, dtype=np.uint8), cv2.IMREAD_COLOR)
    if rgb is None:
        raise ValueError('Camera frame could not be decoded')
    # RMBench's fixed-width HDF5 buffers may have NUL padding after the JPEG.
    # OpenCV stops at the image end, and the marker check visits only the header.
    # Untagged legacy frames were encoded by passing RGB straight to imencode.
    return cv2.cvtColor(rgb, cv2.COLOR_BGR2RGB) if marked_rgb_jpeg(bytes_view) else rgb


def collect(episode: Path, frames: list[int], roles: list[str]) -> list[tuple]:
    tiles = []
    with h5py.File(episode, 'r') as h5:
        for role in roles:
            dataset = f'observation/{CAMERAS[role]}/rgb'
            if dataset not in h5 or not isinstance(h5[dataset], h5py.Dataset):
                raise ValueError(f'Missing camera stream {dataset}')
        streams = {role: h5[f'observation/{CAMERAS[role]}/rgb'] for role in roles}
        if any(stream.ndim == 0 for stream in streams.values()):
            raise ValueError('Camera streams must have a frame axis')
        lengths = {len(stream) for stream in streams.values()}
        if len(lengths) != 1:
            raise ValueError('Selected camera streams have different frame counts')
        count = lengths.pop()
        if frames[0] < 0 or frames[-1] >= count:
            raise ValueError(f'Request raw frames in [0, {count})')
        for frame in frames:
            for role, stream in streams.items():
                try:
                    rgb = decode_rgb(stream[frame])
                except (ValueError, cv2.error) as exc:
                    raise ValueError(f'{role} frame {frame}: {exc}') from exc
                tiles.append((frame, role, rgb))
    return tiles


def make_sheet(tiles: list[tuple], columns: int) -> tuple[Image.Image, list[dict]]:
    width = max(rgb.shape[1] for _, _, rgb in tiles) + 6
    height = max(rgb.shape[0] for _, _, rgb in tiles) + 25
    rows = (len(tiles) + columns - 1) // columns
    sheet = Image.new('RGB', (columns * width, rows * height), '#f0f2f4')
    caption = ImageDraw.Draw(sheet)
    metadata = []
    for index, (frame, role, rgb) in enumerate(tiles):
        row, column = divmod(index, columns)
        x, y = column * width, row * height
        caption.text((x + 4, y + 4), f'{frame}  {role}', fill='#1c2833')
        sheet.paste(Image.fromarray(rgb), (x + 3, y + 20))
        metadata.append({
            'frame': frame,
            'camera': role,
            'shape': list(rgb.shape),
            'sha256': sha256(rgb.tobytes()).hexdigest(),
            'tile_xy': [x + 3, y + 20],
        })
    return sheet, metadata


def write_atomic(path: Path, write) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=path.parent, prefix=f'.{path.name}.', delete=False) as temp:
        scratch = Path(temp.name)
    try:
        write(scratch)
        scratch.replace(path)
    finally:
        scratch.unlink(missing_ok=True)


def main() -> None:
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('episode', type=Path, help='Raw RMBench episode HDF5')
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument('--frames', type=int, nargs='+', help='Zero-based raw frame indices')
    selection.add_argument(
        '--window-end', type=int,
        help='Render the four consecutive raw frames ending at this index (fewer at episode start)',
    )
    parser.add_argument('--cameras', nargs='+', choices=tuple(CAMERAS), default=list(CAMERAS))
    parser.add_argument('--output', type=Path, required=True, help='Evidence PNG path')
    parser.add_argument('--metadata', type=Path, help='Optional JSON with per-frame RGB checksums')
    args = parser.parse_args()
    episode = args.episode.expanduser().resolve()
    output = args.output.expanduser()
    metadata = args.metadata.expanduser() if args.metadata is not None else None
    if output.suffix.lower() != '.png':
        parser.error('--output must end in .png')
    if metadata is not None and metadata.suffix.lower() != '.json':
        parser.error('--metadata must end in .json')
    paths = [episode, output.resolve()]
    if metadata is not None:
        paths.append(metadata.resolve())
    if len(set(paths)) != len(paths):
        parser.error('Input HDF5, output PNG, and metadata paths must be distinct')

    if args.window_end is None:
        frames = sorted(set(args.frames))
    else:
        if args.window_end < 0:
            parser.error('--window-end must be a nonnegative raw frame index')
        frames = list(range(max(0, args.window_end - 3), args.window_end + 1))
    roles = list(dict.fromkeys(args.cameras))
    try:
        tiles = collect(episode, frames, roles)
        columns = len(roles) if len(roles) > 1 else min(4, len(tiles))
        sheet, checksums = make_sheet(tiles, columns)
        if metadata is not None:
            with episode.open('rb') as data_file:
                episode_sha256 = file_digest(data_file, 'sha256').hexdigest()
        write_atomic(output, lambda path: sheet.save(path, format='PNG'))
        if metadata is not None:
            with output.open('rb') as png_file:
                sheet_sha256 = file_digest(png_file, 'sha256').hexdigest()
            report = {
                'format': 'rmbench-evidence-v1',
                'episode_file': episode.name,
                'episode_sha256': episode_sha256,
                'sheet_sha256': sheet_sha256,
                'opencv_version': cv2.__version__,
                'tiles': checksums,
            }
            write_atomic(metadata, lambda path: path.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8'))
    except (ValueError, OSError) as exc:
        parser.error(str(exc))


if __name__ == '__main__':
    main()
