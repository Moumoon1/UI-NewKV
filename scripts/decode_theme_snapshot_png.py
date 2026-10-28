#!/usr/bin/env python3
"""Decode complete KVSS1/LZ or KVSS2/zlib snapshots; fail closed on loss."""
import argparse
import os
import select
import base64
import json
from pathlib import Path
import sys
import termios
import tty
import zlib


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
    if isinstance(snapshot,dict) and snapshot.get('transportDocument'):
        raise ValueError('partial transport document is not a complete snapshot')
    if not isinstance(snapshot, dict) or not isinstance(snapshot.get('nodes'), list):
        raise ValueError('not a complete snapshot')
    if snapshot.get('errors'):
        raise ValueError('source capture reported read errors')
    if len({row['id'] for row in snapshot['nodes']}) != len(snapshot['nodes']):
        raise ValueError('duplicate node IDs in snapshot')
    if snapshot.get('rootId') not in {row['id'] for row in snapshot['nodes']}:
        raise ValueError('source root missing from snapshot')
    return snapshot


def unpack_transport(data):
    if not data.startswith(PNG_PREFIX):
        raise ValueError('image bytes changed or transport prefix missing')
    header = data[len(PNG_PREFIX):len(PNG_PREFIX) + 21]
    if len(header) != 21 or header[:5] not in (MAGIC, b'KVSS2'):
        raise ValueError('KVSS payload missing; image channel may have stripped it')
    raw_size = int.from_bytes(header[5:9], 'big')
    packed_size = int.from_bytes(header[9:13], 'big')
    expected = (int.from_bytes(header[13:17], 'big'), int.from_bytes(header[17:21], 'big'))
    packed = data[len(PNG_PREFIX) + 21:]
    if len(packed) != packed_size:
        raise ValueError('missing or extra packed bytes')
    if header[:5] == MAGIC:
        raw = unpack_theme_bytes(raw_size, packed, expected)
    else:
        if raw_size > 100_000_000 or packed_size > 100_000_000:
            raise ValueError('transport exceeds size limit')
        decoder = zlib.decompressobj()
        raw = decoder.decompress(packed, raw_size + 1)
        if (not decoder.eof or decoder.unused_data or decoder.unconsumed_tail
                or len(raw) != raw_size or _hash(raw) != expected):
            raise ValueError('snapshot length, stream or checksum mismatch')
    return raw


def decode_transport(data):
    return validate_snapshot(unpack_transport(data))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('input', type=Path, help='raw image bytes or a base64 text file')
    parser.add_argument('output', type=Path)
    parser.add_argument('--base64', action='store_true')
    parser.add_argument('--stdin-base64', action='store_true',
                        help='read one base64 image line from stdin')
    parser.add_argument('--stdin-base64-length', type=int,
                        help='read exactly this many base64 bytes from a raw TTY')
    parser.add_argument('--expected-root')
    parser.add_argument('--expected-nodes', type=int)
    parser.add_argument('--part-manifest',type=Path)
    parser.add_argument('--part-index',type=int)
    args = parser.parse_args()
    if args.stdin_base64_length is not None:
        if not sys.stdin.isatty() or args.stdin_base64_length <= 0:
            raise ValueError('positive length and a TTY are required')
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            print('KVSS1_READY', flush=True)
            chunks = []
            remaining = args.stdin_base64_length
            while remaining:
                if not select.select([fd], [], [], 15)[0]:
                    raise ValueError('snapshot input timed out; reuse cached capture')
                chunk = os.read(fd, min(65536, remaining))
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
    if args.part_manifest is not None:
        if args.part_index is None:
            raise ValueError('part index required')
        from snapshot_chunk_audit import validate_part
        snapshot = validate_part(json.loads(unpack_transport(data).decode('utf-8')),
                                 json.loads(args.part_manifest.read_text()),args.part_index)
    else:
        if args.part_index is not None:
            raise ValueError('part manifest required')
        snapshot = decode_transport(data)
    if args.expected_root is not None and snapshot['rootId'] != args.expected_root:
        raise ValueError('snapshot root does not match requested frame')
    if args.expected_nodes is not None and len(snapshot['nodes']) != args.expected_nodes:
        raise ValueError('snapshot node count does not match capture receipt')
    temporary = args.output.with_name(args.output.name + '.partial')
    temporary.write_text(json.dumps(snapshot, ensure_ascii=False, separators=(',', ':')))
    temporary.replace(args.output)
    print(json.dumps({'rootId': snapshot['rootId'], 'nodes': len(snapshot['nodes']),
                      'capturedAt': snapshot.get('capturedAt')}))


if __name__ == '__main__':
    main()
