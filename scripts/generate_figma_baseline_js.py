#!/usr/bin/env python3
"""Produce the tested single-capture Figma baseline program for use_figma."""
import argparse
import json
from pathlib import Path
from transport_codec import zlib_helper


def build(root_id, file_name, page_id=None):
    directory = Path(__file__).parent
    names = ('figma_snapshot.js', 'snapshot_fingerprint.js',
             'figma_source_preflight.js', 'figma_snapshot_transport.js')
    program = zlib_helper() + '\n'.join((directory / name).read_text() for name in names)
    program += '\nreturn await captureThemeBaseline(figma,' + json.dumps(root_id) + ',' + json.dumps(file_name) + ',' + json.dumps(page_id) + ');\n'
    if len(program) > 45000:
        raise ValueError('generated Figma code exceeds 45,000-character safety budget')
    return program


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('root_id')
    parser.add_argument('--file-name', default='theme-source-snapshot.png')
    parser.add_argument('--page-id')
    parser.add_argument('--out', type=Path, help='save code locally without printing it into context')
    args = parser.parse_args()
    program = build(args.root_id, args.file_name, args.page_id)
    if args.out:
        args.out.write_text(program)
        print(json.dumps({'codePath': str(args.out), 'characters': len(program)}))
    else:
        print(program, end='')


if __name__ == '__main__':
    main()
