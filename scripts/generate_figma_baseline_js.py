#!/usr/bin/env python3
"""Produce the tested single-capture Figma baseline program for use_figma."""
import argparse
import json
from pathlib import Path


def build(root_id, file_name, page_id=None):
    directory = Path(__file__).parent
    names = ('figma_snapshot.js', 'snapshot_fingerprint.js',
             'figma_source_preflight.js', 'figma_snapshot_transport.js')
    program = '\n'.join((directory / name).read_text() for name in names)
    program += '\nreturn await captureThemeBaseline(figma,' + json.dumps(root_id) + ',' + json.dumps(file_name) + ',' + json.dumps(page_id) + ');\n'
    if len(program) > 45000:
        raise ValueError('generated Figma code exceeds 45,000-character safety budget')
    return program


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('root_id')
    parser.add_argument('--file-name', default='theme-source-snapshot.png')
    parser.add_argument('--page-id')
    args = parser.parse_args()
    print(build(args.root_id, args.file_name, args.page_id), end='')


if __name__ == '__main__':
    main()
