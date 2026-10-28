#!/usr/bin/env python3
"""Project guarded region operations onto a clone baseline for compact live proof.

This is a transport optimization, never evidence that Figma actually changed.
The projected tree must be verified by a fresh full-tree Figma fingerprint.
"""
import argparse
import copy
import json
from pathlib import Path

from snapshot_fingerprint import row_fingerprint


def _pointer(value, path, replacement):
    if path == '':
        return copy.deepcopy(replacement)
    if not path.startswith('/'):
        raise ValueError('invalid property pointer')
    keys = [part.replace('~1', '/').replace('~0', '~') for part in path[1:].split('/')]
    out = copy.deepcopy(value)
    cursor = out
    for key in keys[:-1]:
        cursor = cursor[int(key)] if isinstance(cursor, list) else cursor[key]
    key = keys[-1]
    if isinstance(replacement, dict) and replacement.get('$missing') is True:
        if isinstance(cursor, list):
            raise ValueError('array deletion needs a full property replacement')
        del cursor[key]
    elif isinstance(cursor, list):
        cursor[int(key)] = copy.deepcopy(replacement)
    else:
        cursor[key] = copy.deepcopy(replacement)
    return out


def _update_text_run(row, change):
    runs = row['props'].get('textRuns', {}).get('fills')
    if not isinstance(runs, list):
        raise ValueError('TEXT fill runs missing from clone baseline')
    start, end = change['start'], change['end']
    if not isinstance(start, int) or not isinstance(end, int) or start >= end:
        raise ValueError('invalid text range')
    overlaps = [run for run in runs if run['end'] > start and run['start'] < end]
    if not overlaps or overlaps[0]['start'] > start or overlaps[-1]['end'] < end:
        raise ValueError('text range not fully covered')
    cursor = start
    for run in overlaps:
        if run['start'] > cursor:
            raise ValueError('text range contains a coverage gap')
        cursor = max(cursor, run['end'])
    values = [run['value'] for run in overlaps]
    if any(value != values[0] for value in values[1:]):
        raise ValueError('mixed before fills need a full clone readback')
    current_hash = row_fingerprint(values[0])
    after_hash = row_fingerprint(change['value'])
    if current_hash == after_hash:
        return
    if current_hash != change['beforeHash']:
        raise ValueError('text before hash conflict')
    replacement = copy.deepcopy(change['value'])
    result = []
    for run in runs:
        if run['end'] <= start or run['start'] >= end:
            result.append(run)
            continue
        if run['start'] < start:
            result.append({**run, 'end': start})
        result.append({'start': max(run['start'], start), 'end': min(run['end'], end), 'value': replacement})
        if run['end'] > end:
            result.append({**run, 'start': end})
    merged = []
    for run in result:
        if merged and merged[-1]['end'] == run['start'] and merged[-1]['value'] == run['value']:
            merged[-1]['end'] = run['end']
        else:
            merged.append(run)
    row['props']['textRuns']['fills'] = merged
    if all(run['value'] == merged[0]['value'] for run in merged):
        row['props']['fills'] = copy.deepcopy(merged[0]['value'])
    else:
        row['props']['fills'] = {'$mixed': True}


def project(baseline, region_plans):
    if baseline.get('errors'):
        raise ValueError('clone baseline has read errors')
    out = copy.deepcopy(baseline)
    rows = {row['id']: row for row in out['nodes']}
    if len(rows) != len(out['nodes']):
        raise ValueError('duplicate clone node IDs')
    count = 0
    for plan in region_plans:
        if plan.get('schemaVersion') != 1 or not isinstance(plan.get('operations'), list):
            raise ValueError('invalid region plan')
        for op in plan['operations']:
            row = rows.get(op.get('cloneId'))
            if not row:
                raise ValueError('clone node missing: ' + str(op.get('cloneId')))
            if op['property'] == 'textRuns':
                for change in op['runs']:
                    _update_text_run(row, change)
            else:
                prop = op['property']
                if prop not in row['props']:
                    raise ValueError('clone property missing: ' + prop)
                current = row['props'][prop]
                current_hash = row_fingerprint(current)
                if current_hash != op['afterHash']:
                    if current_hash != op['beforeHash']:
                        raise ValueError('before hash conflict: ' + op['cloneId'] + ' ' + prop)
                    for change in op['changes']:
                        current = _pointer(current, change['path'], change['value'])
                    if row_fingerprint(current) != op['afterHash']:
                        raise ValueError('after hash mismatch: ' + op['cloneId'] + ' ' + prop)
                    row['props'][prop] = current
            count += 1
    return out, count


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('baseline', type=Path)
    parser.add_argument('plans', type=Path, nargs='+')
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    out, count = project(json.loads(args.baseline.read_text()),
                         [json.loads(path.read_text()) for path in args.plans])
    args.out.write_text(json.dumps(out, ensure_ascii=False, separators=(',', ':')))
    print(json.dumps({'rootId': out['rootId'], 'nodes': len(out['nodes']), 'projectedOperations': count}))


if __name__ == '__main__':
    main()
