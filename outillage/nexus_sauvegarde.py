#!/usr/bin/env python3
"""Local git repository backup script.

This script creates a local git bundle that captures the entire history of the
repository. It does NOT push the bundle, does NOT replace a remote repository,
and does NOT leave the machine. The bundle is verified after creation because
an unverified bundle may be corrupted and unusable.

The script:
- determines the repository root from its own location,
- creates a directory ".nexus/sauvegardes" inside the root,
- creates a timestamped bundle with a 120 second timeout,
- verifies the bundle,
- reports the bundle path, size and number of commits,
- keeps only the most recent N bundles (default 5) unless --no-delete is used.
"""

import argparse
import datetime
import pathlib
import subprocess
import sys

def run_git_command(args, cwd, timeout):
    """Run a git command with given arguments, cwd and timeout."""
    result = subprocess.run(
        ["git"] + args,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout,
    )
    return result

def create_bundle(repo_root, dest_dir):
    """Create a git bundle and return its path, or raise RuntimeError."""
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    bundle_name = f"backup_{timestamp}.bundle"
    bundle_path = dest_dir / bundle_name

    # git bundle create <path> --all
    result = run_git_command(
        ["bundle", "create", str(bundle_path), "--all"],
        cwd=repo_root,
        timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git bundle create failed: {result.stderr.strip()}")
    return bundle_path

def verify_bundle(repo_root, bundle_path):
    """Verify the git bundle, raise RuntimeError if verification fails."""
    result = run_git_command(
        ["bundle", "verify", str(bundle_path)],
        cwd=repo_root,
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git bundle verify failed: {result.stderr.strip()}")

def count_commits(repo_root):
    """Return the total number of commits in the repository."""
    result = run_git_command(
        ["rev-list", "--count", "--all"],
        cwd=repo_root,
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git rev-list failed: {result.stderr.strip()}")
    return int(result.stdout.strip())

def manage_retention(sauveg_dir, keep, no_delete):
    """Delete old bundles keeping only the most recent `keep` files."""
    bundles = sorted(
        sauveg_dir.glob("*.bundle"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    to_delete = bundles[keep:]
    if not to_delete:
        return
    if no_delete:
        for p in to_delete:
            print(f"Would delete old bundle (no-delete option): {p}")
        return
    for p in to_delete:
        try:
            p.unlink()
            print(f"Deleted old bundle: {p}")
        except Exception as e:
            print(f"Failed to delete {p}: {e}", file=sys.stderr)

def main():
    parser = argparse.ArgumentParser(description="Local git backup script")
    parser.add_argument(
        "--keep",
        type=int,
        default=5,
        help="Number of recent bundles to keep (default 5)",
    )
    parser.add_argument(
        "--no-delete",
        action="store_true",
        help="Do not delete old bundles",
    )
    args = parser.parse_args()

    try:
        script_path = pathlib.Path(__file__).resolve()
        # parent of the directory that contains this script
        repo_root = script_path.parent.parent
        if not (repo_root / ".git").is_dir():
            raise RuntimeError("Repository root not found (no .git directory)")

        # destination directory: .nexus/sauvegardes inside repo root
        nexus_dir = repo_root / ".nexus"
        sauveg_dir = nexus_dir / "sauvegardes"
        sauveg_dir.mkdir(parents=True, exist_ok=True)

        bundle_path = create_bundle(repo_root, sauveg_dir)
        verify_bundle(repo_root, bundle_path)

        size = bundle_path.stat().st_size
        commit_count = count_commits(repo_root)

        print(f"Bundle path: {bundle_path}")
        print(f"Size: {size} bytes")
        print(f"Commits: {commit_count}")

        manage_retention(sauveg_dir, args.keep, args.no_delete)

        sys.exit(0)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        # optional: uncomment next line to see traceback for debugging
        # traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()