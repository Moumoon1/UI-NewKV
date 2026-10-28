#!/usr/bin/env python3
"""Split frozen revision operations by both count and serialized payload size."""

import argparse
import json
from pathlib import Path


def encoded_size(operations):
    return len(json.dumps(operations, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def split_operations(operations, max_items=60, max_json_bytes=36000):
    if max_items < 1 or max_json_bytes < 2:
        raise ValueError("positive batch limits required")
    if not isinstance(operations, list):
        raise ValueError("operations must be a JSON array")
    batches = []
    current = []
    for operation in operations:
        candidate = current + [operation]
        if current and (len(candidate) > max_items or encoded_size(candidate) > max_json_bytes):
            batches.append(current)
            current = [operation]
        else:
            current = candidate
        if encoded_size(current) > max_json_bytes:
            raise ValueError("single operation exceeds JSON byte limit")
    if current:
        batches.append(current)
    return batches


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("operations")
    parser.add_argument("prefix")
    parser.add_argument("--size", type=int, default=60)
    parser.add_argument("--max-json-bytes", type=int, default=36000,
                        help="Reserve room below the Figma code limit for JS helpers")
    args = parser.parse_args()
    source = Path(args.operations)
    operations = json.loads(source.read_text())
    batches = split_operations(operations, args.size, args.max_json_bytes)
    sizes = []
    for index, batch in enumerate(batches):
        path = source.parent / f"{args.prefix}-{index}.json"
        payload = json.dumps(batch, ensure_ascii=False, separators=(",", ":"))
        path.write_text(payload)
        sizes.append(len(payload.encode("utf-8")))
    print({"operations": len(operations), "batches": len(batches),
           "batchBytes": sizes, "maxItems": args.size,
           "maxJsonBytes": args.max_json_bytes})


if __name__ == "__main__":
    main()
