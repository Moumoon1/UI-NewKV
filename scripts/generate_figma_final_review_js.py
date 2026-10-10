#!/usr/bin/env python3
"""Generate one final review call with exactly two output image blocks."""
import argparse
import json
from pathlib import Path


def build(source_id, clone_id, kv_clone_id, source_fingerprint):
    directory = Path(__file__).parent
    names = ('figma_snapshot.js', 'snapshot_fingerprint.js',
             'figma_snapshot_transport.js', 'figma_final_review.js')
    program = '\n'.join((directory / name).read_text() for name in names)
    args = ','.join(json.dumps(value) for value in
                    (source_id, clone_id, kv_clone_id, source_fingerprint))
    program += '\nreturn await captureThemeFinalReview(figma,' + args + ');\n'
    if len(program) > 45000:
        raise ValueError('generated Figma code exceeds 45,000-character safety budget')
    return program


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('source_id')
    parser.add_argument('clone_id')
    parser.add_argument('kv_clone_id')
    parser.add_argument('source_fingerprint')
    args = parser.parse_args()
    print(build(args.source_id, args.clone_id, args.kv_clone_id,
                args.source_fingerprint), end='')


if __name__ == '__main__':
    main()
