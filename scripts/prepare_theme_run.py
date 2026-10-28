#!/usr/bin/env python3
"""Compile reviewed inputs and run the existing static gates in one local call.

Does not author roles, freeze an unreviewed ledger, access Figma, or grant visual
approval. Relative input paths resolve against the input spec's directory.
"""
import argparse
import json
import time
from pathlib import Path

from compile_color_mutation_plan import build
from preflight_full import run as preflight
from theme_audit import digest

INPUTS = ('sourceBefore', 'kvSource', 'manifest', 'options', 'ruleLedger',
          'visualUnits', 'colorRelations', 'materialRelations')


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def prepare(spec_path, out_dir):
    spec_path, out_dir = Path(spec_path).resolve(), Path(out_dir).resolve()
    if out_dir.exists() and any(out_dir.iterdir()):
        raise ValueError('output directory must be empty; use a fresh projection directory')
    out_dir.mkdir(parents=True, exist_ok=True)
    receipt = {'status': 'fail', 'steps': [], 'inputs': {}}

    def step(name, callback):
        started = time.monotonic()
        row = {'name': name, 'status': 'fail'}
        receipt['steps'].append(row)
        try:
            result = callback()
            row['status'] = 'pass'
            return result
        finally:
            row['seconds'] = round(time.monotonic() - started, 4)

    try:
        spec = json.loads(spec_path.read_text())
        paths, values = {}, {}
        for key in INPUTS:
            path = (spec_path.parent / spec[key]).resolve()
            values[key] = json.loads(path.read_text())
            # Copy exact inputs so later edits cannot silently change this projection.
            frozen_path = out_dir / (key + '.json')
            save(frozen_path, values[key])
            paths[key] = str(frozen_path)
            receipt['inputs'][key] = {'path': str(path), 'hash': digest(values[key])}
        compiled = step('compile', lambda: build(values['sourceBefore'], values['kvSource'],
                                                  values['manifest'], values['options']))
        for key in ('expectedClone', 'writePlan', 'policy', 'nodeMap'):
            paths[key] = str(out_dir / (key + '.json'))
            save(Path(paths[key]), compiled[key])
        (out_dir / 'apply.js').write_text(compiled['applyJs'])
        save(out_dir / 'preflight-spec.json', paths)
        report = step('static-preflight', lambda: preflight(paths, 'static'))
        save(out_dir / 'static-preflight.json', report)
        receipt.update(status=report['status'], failedChecks=report.get('failedChecks', []),
                       summary=compiled['summary'], preflightSpec=str(out_dir / 'preflight-spec.json'))
        receipt['steps'][-1]['status'] = 'pass' if report['status'] == 'ready-for-preview' else 'fail'
    except (ValueError, KeyError, TypeError, OSError) as exc:
        receipt['error'] = str(exc)
    finally:
        save(out_dir / 'prepare-receipt.json', receipt)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('spec', type=Path)
    parser.add_argument('--out-dir', type=Path, required=True)
    args = parser.parse_args()
    result = prepare(args.spec, args.out_dir)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result['status'] == 'ready-for-preview' else 1


if __name__ == '__main__':
    raise SystemExit(main())
