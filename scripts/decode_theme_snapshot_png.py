#!/usr/bin/env python3
"""Decode a complete KVSS1 Figma snapshot image artifact; fail closed on loss."""
import argparse
import base64
import json
from pathlib import Path
import sys
import termios
import tty


PNG_PREFIX = base64.b64decode(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/lXcAAAAASUVORK5CYII='
)
MAGIC = b'KVSS1'


def _hash(data):
    a, b = 2166136261, 5381
    for byte in data:
        a = ((a ^ byte) * 16777619) & 0xffffffff
        b = ((b * 33) ^ byte) & 0xffffffff
    return a, b


def unpack_theme_bytes(raw_size, packed, expected):
    if raw_size > 100_000_000 or len(packed) > 100_000_000:
        raise ValueError('transport exceeds size limit')
    out = bytearray()
    i = 0
    while i < len(packed):
        byte = packed[i]
        if byte:
            out.append(byte)
            i += 1
        else:
            if i + 4 > len(packed):
                raise ValueError('truncated backreference')
            distance = (packed[i + 1] << 8) | packed[i + 2]
            length = packed[i + 3]
            if not distance and not length:
                out.append(0)
            else:
                if not 0 < distance <= len(out) or length < 7:
                    raise ValueError('invalid backreference')
                for _ in range(length):
                    out.append(out[-distance])
            i += 4
        if len(out) > raw_size:
            raise ValueError('decompressed payload exceeds declared size')
    if len(out) != raw_size or _hash(out) != expected:
        raise ValueError('snapshot length or checksum mismatch')
    return bytes(out)


def validate_snapshot(raw):
    snapshot = json.loads(raw.decode('utf-8'))
    if not isinstance(snapshot, dict) or not isinstance(snapshot.get('nodes'), list):
        raise ValueError('not a complete snapshot')
    if snapshot.get('errors'):
        raise ValueError('source capture reported read errors')
    if len({row['id'] for row in snapshot['nodes']}) != len(snapshot['nodes']):
        raise ValueError('duplicate node IDs in snapshot')
    if snapshot.get('rootId') not in {row['id'] for row in snapshot['nodes']}:
        raise ValueError('source root missing from snapshot')
    return snapshot


def decode_transport(data):
    if not data.startswith(PNG_PREFIX):
        raise ValueError('image bytes changed or transport prefix missing')
    header = data[len(PNG_PREFIX):len(PNG_PREFIX) + 21]
    if len(header) != 21 or header[:5] != MAGIC:
        raise ValueError('KVSS1 payload missing; image channel may have stripped it')
    raw_size = int.from_bytes(header[5:9], 'big')
    packed_size = int.from_bytes(header[9:13], 'big')
    expected = (int.from_bytes(header[13:17], 'big'), int.from_bytes(header[17:21], 'big'))
    packed = data[len(PNG_PREFIX) + 21:]
    if len(packed) != packed_size:
        raise ValueError('missing or extra packed bytes')
    return validate_snapshot(unpack_theme_bytes(raw_size, packed, expected))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('input', type=Path, help='raw image bytes or a base64 text file')
    parser.add_argument('output', type=Path)
    parser.add_argument('--base64', action='store_true')
    parser.add_argument('--stdin-base64', action='store_true',
                        help='read one base64 image line from stdin')
    parser.add_argument('--stdin-base64-length', type=int,
                        help='read exactly this many base64 bytes from a raw TTY')
    args = parser.parse_args()
    if args.stdin_base64_length is not None:
        if not sys.stdin.isatty() or args.stdin_base64_length <= 0:
            raise ValueError('positive length and a TTY are required')
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            chunks = []
            remaining = args.stdin_base64_length
            while remaining:
                chunk = sys.stdin.buffer.read(min(65536, remaining))
                if not chunk:
                    raise ValueError('truncated base64 snapshot input')
                chunks.append(chunk)
                remaining -= len(chunk)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
        data = base64.b64decode(b''.join(chunks), validate=True)
    elif args.stdin_base64:
        data = base64.b64decode(sys.stdin.buffer.readline().strip(), validate=True)
    else:
        data = args.input.read_bytes()
    if args.base64 and not args.stdin_base64:
        data = base64.b64decode(b''.join(data.split()), validate=True)
    snapshot = decode_transport(data)
    args.output.write_text(json.dumps(snapshot, ensure_ascii=False, separators=(',', ':')))
    print(json.dumps({'rootId': snapshot['rootId'], 'nodes': len(snapshot['nodes']),
                      'capturedAt': snapshot.get('capturedAt')}))


if __name__ == '__main__':
    main()
