#!/usr/bin/env python3
"""Generate the exact staged Figma preview start or cleanup program."""
import argparse
import json
from pathlib import Path


def build_start(source_id, fingerprint, plan_hash, apply_js):
    directory = Path(__file__).parent
    names = ('figma_snapshot.js', 'snapshot_fingerprint.js', 'figma_staged_preview.js')
    program = '\n'.join((directory / name).read_text() for name in names)
    program += '\n' + Path(apply_js).read_text() + '\n'
    program += ('return await startStagedThemePreview(figma,' + ','.join(map(json.dumps,
                (source_id, fingerprint, plan_hash))) + ',applyThemeWriteToClone);\n')
    if len(program) > 45000:
        raise ValueError('preview start exceeds 45,000-character safety budget')
    return program


def build_finish(source_id, clone_id, fingerprint, plan_hash, child_ids):
    directory = Path(__file__).parent
    names = ('figma_snapshot.js', 'snapshot_fingerprint.js', 'figma_staged_preview.js')
    program = '\n'.join((directory / name).read_text() for name in names)
    args = (source_id, clone_id, fingerprint, plan_hash, child_ids)
    program += '\nreturn await finishStagedThemePreview(figma,' + \
               ','.join(map(json.dumps, args)) + ');\n'
    if len(program) > 45000:
        raise ValueError('preview cleanup exceeds 45,000-character safety budget')
    return program


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='mode', required=True)
    start = sub.add_parser('start')
    start.add_argument('source_id'); start.add_argument('source_fingerprint')
    start.add_argument('plan_hash'); start.add_argument('--apply-js', type=Path, required=True)
    finish = sub.add_parser('finish')
    finish.add_argument('source_id'); finish.add_argument('clone_id')
    finish.add_argument('source_fingerprint'); finish.add_argument('plan_hash')
    finish.add_argument('--child-ids-json', required=True)
    args = parser.parse_args()
    if args.mode == 'start':
        print(build_start(args.source_id, args.source_fingerprint, args.plan_hash, args.apply_js), end='')
    else:
        print(build_finish(args.source_id, args.clone_id, args.source_fingerprint,
                           args.plan_hash, json.loads(args.child_ids_json)), end='')


if __name__ == '__main__':
    main()
