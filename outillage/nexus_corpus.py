#!/usr/bin/env python3
import os, sys, json, hashlib, argparse
from pathlib import Path

CHUNK_SIZE = 4096

def hash_prefix(path):
    try:
        with open(path, 'rb') as f:
            data = f.read(CHUNK_SIZE)
            return hashlib.sha256(data).hexdigest()
    except OSError:
        return None

def walk_path(root, max_depth, ext_filter):
    start_depth = root.count(os.sep)
    for dirpath, _, filenames in os.walk(root):
        cur_depth = dirpath.count(os.sep) - start_depth
        if max_depth is not None and cur_depth > max_depth:
            continue
        for name in filenames:
            ext = os.path.splitext(name)[1].lower()
            if ext_filter and ext not in ext_filter:
                continue
            yield Path(dirpath) / name, ext

def main():
    parser = argparse.ArgumentParser(description='Inventory large corpus without full read')
    parser.add_argument('paths', nargs='+', help='paths to scan')
    parser.add_argument('-e', '--extensions', help='comma separated list of extensions to include')
    parser.add_argument('-d', '--max-depth', type=int, help='maximum directory depth')
    parser.add_argument('-j', '--json', action='store_true', help='output json')
    args = parser.parse_args()

    ext_set = set()
    if args.extensions:
        ext_set = {('.' + e if not e.startswith('.') else e).lower() for e in args.extensions.split(',')}

    ext_stats = {}
    dup_groups = {}
    unreadable = 0
    empty = 0

    for path_arg in args.paths:
        root = Path(path_arg).resolve()
        if not root.exists():
            print(f'Path not found: {root}', file=sys.stderr)
            continue
        for file_path, ext in walk_path(str(root), args.max_depth, ext_set):
            try:
                size = file_path.stat().st_size
            except OSError:
                unreadable += 1
                continue
            if size == 0:
                empty += 1
            ext_stats.setdefault(ext, {'count':0, 'size':0})
            ext_stats[ext]['count'] += 1
            ext_stats[ext]['size'] += size
            h = hash_prefix(file_path)
            if h is None:
                unreadable += 1
                continue
            key = (size, h)
            dup_groups.setdefault(key, []).append(str(file_path.relative_to(root)))

    dup_report = []
    saved_bytes = 0
    for (size, _), files in dup_groups.items():
        if len(files) > 1:
            dup_report.append({'files': files, 'size': size})
            saved_bytes += size * (len(files) - 1)

    report = {
        'extensions': [{'extension': ext, 'count': data['count'], 'total_bytes': data['size']} for ext, data in ext_stats.items()],
        'duplicates': dup_report,
        'saved_bytes': saved_bytes,
        'unreadable': unreadable,
        'empty': empty
    }

    if args.json:
        json.dump(report, sys.stdout, ensure_ascii=False, indent=2)
    else:
        for e in report['extensions']:
            print(f"{e['extension'] or '[no ext]'}: {e['count']} files, {e['total_bytes']} bytes")
        print(f"Duplicate groups: {len(report['duplicates'])}")
        print(f"Potentially saved bytes if duplicates removed: {report['saved_bytes']}")
        print(f"Unreadable files: {report['unreadable']}")
        print(f"Empty files: {report['empty']}")

    sys.exit(1 if report['duplicates'] else 0)

if __name__ == '__main__':
    main()
