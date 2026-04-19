#!/usr/bin/env python3
"""Build base_repo/T01..T50 task directories from capbench_sampled.csv.

For each task:
  1. Resolve the local source repo clone in source_repos/
  2. Use `gh` to fetch the PR merge-commit SHA (ground truth)
  3. Clone to base_repo/<TNN>/repo/, checkout base_commit, prune GT
  4. Produce eval/ artefacts: gt_diff.patch, gt_files.txt, etc.
  5. Write placeholder prompts

Usage:
  ./build_capbench_tasks.sh                # all tasks
  python _build_capbench_tasks.py --start 3 --end 7
  python _build_capbench_tasks.py --dry-run
  python _build_capbench_tasks.py --skip-existing
"""
from __future__ import annotations

import argparse
import csv
import re
import shutil
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
CSV_FILE = SCRIPT_DIR / "capbench_sampled.csv"
SOURCE_REPOS = SCRIPT_DIR / "source_repos"
BASE_REPO = SCRIPT_DIR / "base_repo"

# ---------------------------------------------------------------------------
# Auto-generated file patterns (matched against GT diff paths)
# ---------------------------------------------------------------------------
_AG = [re.compile(p) for p in [
    r"zz_generated",
    r"generated\.pb\.go$",
    r"generated\.proto$",
    r"generated\.protomessage",
    r"generated\.protodevel",
    r"\.pb\.(go|h|cc|py|java)$",
    r"_pb2(_grpc)?\.py$",
    r"_generated\.go$",
    r"types_swagger_doc_generated",
    r"openapi-spec/",
    r"swagger\.json$",
    r"/testdata/",
    r"(^|/)vendor/",
    r"applyconfigurations/",
    r"clientset/",
    r"informers/",
    r"listers/",
    r"generated-sources/",
    r"package-lock\.json$",
    r"yarn\.lock$",
    r"Cargo\.lock$",
    r"go\.sum$",
    r"\.snap$",
    r"versioned_feature_list",
]]


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
def log(msg: str) -> None:
    print(f"\033[1;34m[INFO]\033[0m {msg}", file=sys.stderr, flush=True)

def warn(msg: str) -> None:
    print(f"\033[1;33m[WARN]\033[0m {msg}", file=sys.stderr, flush=True)

def err(msg: str) -> None:
    print(f"\033[1;31m[ERR ]\033[0m {msg}", file=sys.stderr, flush=True)


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------
def _is_bare(repo: Path) -> bool:
    return (repo / "HEAD").is_file() and not (repo / ".git").exists()


def sgit(repo: Path, *args: str) -> subprocess.CompletedProcess:
    """Run git against a possibly-bare repo."""
    if _is_bare(repo):
        cmd = ["git", "--git-dir", str(repo)] + list(args)
    else:
        cmd = ["git", "-C", str(repo)] + list(args)
    return subprocess.run(cmd, capture_output=True, text=True)


def find_source(url: str) -> Path | None:
    """Map a GitHub URL to a local clone in SOURCE_REPOS/."""
    name = url.rstrip("/").split("/")[-1]
    for suffix in ("", ".git"):
        p = SOURCE_REPOS / f"{name}{suffix}"
        if p.exists():
            return p
    return None


def get_merge_sha(pr_link: str) -> str | None:
    """Get the merge commit SHA for a PR URL via gh."""
    m = re.match(r"https://github\.com/([^/]+/[^/]+)/pull/(\d+)", pr_link)
    if not m:
        return None
    owner_repo, pr_num = m.group(1), m.group(2)

    # gh pr view
    r = subprocess.run(
        ["gh", "pr", "view", pr_num, "--repo", owner_repo,
         "--json", "mergeCommit", "--jq", ".mergeCommit.oid"],
        capture_output=True, text=True, timeout=30,
    )
    sha = r.stdout.strip()
    if sha and sha != "null" and len(sha) >= 7:
        return sha

    # gh api fallback
    r = subprocess.run(
        ["gh", "api", f"repos/{owner_repo}/pulls/{pr_num}",
         "--jq", ".merge_commit_sha"],
        capture_output=True, text=True, timeout=30,
    )
    sha = r.stdout.strip()
    if sha and sha != "null" and len(sha) >= 7:
        return sha

    return None


def get_pr_title(pr_link: str) -> str | None:
    """Get the PR title via gh."""
    m = re.match(r"https://github\.com/([^/]+/[^/]+)/pull/(\d+)", pr_link)
    if not m:
        return None
    owner_repo, pr_num = m.group(1), m.group(2)

    r = subprocess.run(
        ["gh", "pr", "view", pr_num, "--repo", owner_repo,
         "--json", "title", "--jq", ".title"],
        capture_output=True, text=True, timeout=30,
    )
    title = r.stdout.strip()
    if title and title != "null":
        return title

    r = subprocess.run(
        ["gh", "api", f"repos/{owner_repo}/pulls/{pr_num}", "--jq", ".title"],
        capture_output=True, text=True, timeout=30,
    )
    title = r.stdout.strip()
    if title and title != "null":
        return title

    return None


def get_first_parent(repo: Path, sha: str) -> str | None:
    """Get the first parent of a commit."""
    r = sgit(repo, "rev-parse", f"{sha}^1")
    if r.returncode == 0:
        parent = r.stdout.strip()
        if parent:
            return parent
    return None


def get_origin_url(repo: Path) -> str | None:
    """Get remote.origin.url from a repo."""
    r = sgit(repo, "config", "--get", "remote.origin.url")
    if r.returncode == 0:
        url = r.stdout.strip()
        if url:
            return url
    return None


def find_openjdk_landed_sha(repo: Path, pr_title: str, preferred_parent: str | None = None) -> str | None:
    """Resolve the landed mainline commit for an OpenJDK PR title."""
    title = pr_title.strip()
    bugid_match = re.match(r"^(\d+):", title)

    args = ["log", "--all", "--format=%H%x00%s"]
    if bugid_match:
        args.extend(["--grep", bugid_match.group(1)])

    r = sgit(repo, *args)
    if r.returncode != 0:
        return None

    exact: list[str] = []
    prefix: list[str] = []
    bugid = bugid_match.group(1) if bugid_match else None

    for line in r.stdout.splitlines():
        if "\x00" not in line:
            continue
        sha, subject = line.split("\x00", 1)
        subject = subject.strip()
        if subject == title:
            exact.append(sha)
        if bugid and subject.startswith(f"{bugid}:"):
            prefix.append(sha)

    if preferred_parent:
        preferred_exact = [sha for sha in exact if get_first_parent(repo, sha) == preferred_parent]
        if len(preferred_exact) == 1:
            return preferred_exact[0]

        preferred_prefix = [sha for sha in prefix if get_first_parent(repo, sha) == preferred_parent]
        if not exact and len(preferred_prefix) == 1:
            return preferred_prefix[0]

    if len(exact) == 1:
        return exact[0]
    if not exact and len(prefix) == 1:
        return prefix[0]
    return None


def is_auto_generated(path: str) -> bool:
    for p in _AG:
        if p.search(path):
            return True
    return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description="Build CapBench task directories")
    ap.add_argument("--start", type=int, default=1)
    ap.add_argument("--end", type=int, default=999)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--skip-existing", action="store_true")
    ap.add_argument("range", nargs="*", type=int, help="positional start [end]")
    args = ap.parse_args()

    # Positional overrides
    if len(args.range) >= 1:
        args.start = args.range[0]
    if len(args.range) >= 2:
        args.end = args.range[1]
    elif len(args.range) == 1:
        args.end = args.range[0]

    if not CSV_FILE.exists():
        sys.exit(f"CSV not found: {CSV_FILE}")
    if not SOURCE_REPOS.is_dir():
        sys.exit(f"source_repos/ not found: {SOURCE_REPOS}")

    with open(CSV_FILE, newline="") as f:
        rows = list(csv.DictReader(f))
    log(f"Loaded {len(rows)} tasks from {CSV_FILE.name}")

    BASE_REPO.mkdir(exist_ok=True)
    ok = skip = fail = 0

    for idx, row in enumerate(rows, start=1):
        if idx < args.start or idx > args.end:
            continue

        tid = f"T{idx:02d}"
        project = row["project_name"]
        github_url = row["project_github_link"].strip()
        pr_link = row["pr_link"].strip()
        base_commit = row["base_commit"].strip()
        req_doc = row["requirement_doc_link"].strip()
        lang = row["primary_language"].strip()

        task_dir = BASE_REPO / tid
        repo_dir = task_dir / "repo"
        eval_dir = task_dir / "eval"
        prompt_dir = task_dir / "prompts"

        log(f"=== {tid}: {project} [{lang}] ===")
        log(f"  PR: {pr_link}")
        log(f"  Base: {base_commit[:12]}")

        # Skip if already built
        if args.skip_existing and repo_dir.exists() and (eval_dir / "gt_files.txt").exists():
            log(f"  Already built — skipping")
            skip += 1
            continue

        # Find source repo
        src = find_source(github_url)
        if src is None:
            err(f"  Source repo not found for {github_url}")
            fail += 1
            continue
        log(f"  Source: {src.name}")

        # Check base_commit exists
        r = sgit(src, "cat-file", "-t", base_commit)
        if r.returncode != 0:
            err(f"  base_commit {base_commit[:12]} not in source")
            fail += 1
            continue

        # Parse PR
        pr_match = re.match(r"https://github\.com/([^/]+/[^/]+)/pull/(\d+)", pr_link)
        if not pr_match:
            err(f"  Cannot parse PR link: {pr_link}")
            fail += 1
            continue
        owner_repo, pr_num = pr_match.group(1), pr_match.group(2)

        pr_title = get_pr_title(pr_link)

        # Get merge commit
        merge_sha = get_merge_sha(pr_link)
        if owner_repo == "openjdk/jdk" and pr_title:
            # OpenJDK's GitHub PR merge refs are synthetic and can differ from the
            # single landed commit on mainline. Resolve the landed commit locally.
            landed_sha = find_openjdk_landed_sha(src, pr_title, preferred_parent=base_commit)
            if landed_sha:
                merge_sha = landed_sha
                log(f"  OpenJDK landed commit: {merge_sha[:12]}")
                parent_sha = get_first_parent(src, merge_sha)
                if parent_sha and parent_sha != base_commit:
                    warn(
                        f"  base_commit {base_commit[:12]} != landed^1 {parent_sha[:12]} "
                        f"— using landed^1"
                    )
                    base_commit = parent_sha
            else:
                warn("  Could not resolve OpenJDK landed commit locally; falling back to PR merge SHA")

        if not merge_sha:
            err(f"  Could not get merge commit for {owner_repo}#{pr_num}")
            fail += 1
            continue
        log(f"  Merge: {merge_sha[:12]}")

        # Check merge commit in source
        r = sgit(src, "cat-file", "-t", merge_sha)
        if r.returncode != 0:
            warn(f"  Merge commit not in repo — trying PR ref fetch...")
            # Try fetching the specific PR merge ref
            sgit(src, "fetch", "origin", f"refs/pull/{pr_match}/{pr_num}/merge:refs/pull/{pr_num}/merge" if False else "")
            # Fetch via pull ref
            fetch_ok = False
            for ref in [f"refs/pull/{pr_num}/merge", f"refs/pull/{pr_num}/head"]:
                r2 = sgit(src, "fetch", "origin", f"+{ref}:refs/pull/{pr_num}/fetched")
                if r2.returncode == 0:
                    fetch_ok = True
                    break
            if not fetch_ok:
                sgit(src, "fetch", "--all")
            r = sgit(src, "cat-file", "-t", merge_sha)
            if r.returncode != 0:
                # Last resort: try PR head SHA
                try:
                    import subprocess as sp2
                    hr = sp2.run(["gh", "api", f"repos/{owner_repo}/pulls/{pr_num}", "--jq", ".head.sha"],
                                 capture_output=True, text=True, timeout=30)
                    head_sha = hr.stdout.strip()
                    if head_sha:
                        r3 = sgit(src, "cat-file", "-t", head_sha)
                        if r3.returncode == 0:
                            warn(f"  Using PR head SHA {head_sha[:10]} instead of merge SHA")
                            merge_sha = head_sha
                        else:
                            err(f"  Merge commit still not found after fetch")
                            fail += 1
                            continue
                    else:
                        err(f"  Merge commit still not found after fetch")
                        fail += 1
                        continue
                except Exception:
                    err(f"  Merge commit still not found after fetch")
                    fail += 1
                    continue

        if args.dry_run:
            log(f"  [DRY RUN] {task_dir}")
            ok += 1
            continue

        # ── eval/ artifacts ──
        eval_dir.mkdir(parents=True, exist_ok=True)

        # GT diff
        r = sgit(src, "diff", base_commit, merge_sha)
        (eval_dir / "gt_diff.patch").write_text(r.stdout)

        # GT file list
        r = sgit(src, "diff", "--name-only", base_commit, merge_sha)
        gt_files = sorted(f for f in r.stdout.splitlines() if f.strip())
        (eval_dir / "gt_files.txt").write_text(
            "\n".join(gt_files) + ("\n" if gt_files else ""))

        hw = sorted(f for f in gt_files if not is_auto_generated(f))
        ag = sorted(f for f in gt_files if is_auto_generated(f))
        (eval_dir / "handwritten_files.txt").write_text(
            "\n".join(hw) + ("\n" if hw else ""))
        (eval_dir / "auto_generated_files.txt").write_text(
            "\n".join(ag) + ("\n" if ag else ""))
        log(f"  GT files: {len(gt_files)} ({len(hw)} HW, {len(ag)} AG)")

        # ── Clone + sanitise repo ──
        if repo_dir.exists():
            shutil.rmtree(repo_dir)

        log(f"  Cloning repo...")
        # Use --no-local to handle bare repos; fall back to regular clone,
        # then fall back to origin URL for incomplete/promisor local mirrors.
        try:
            subprocess.run(
                ["git", "clone", "--no-local", str(src), str(repo_dir)],
                check=True, capture_output=True, text=True,
            )
        except subprocess.CalledProcessError:
            try:
                if repo_dir.exists():
                    shutil.rmtree(repo_dir)
                subprocess.run(
                    ["git", "clone", str(src), str(repo_dir)],
                    check=True, capture_output=True, text=True,
                )
            except subprocess.CalledProcessError:
                origin_url = get_origin_url(src)
                if not origin_url:
                    raise
                warn(f"  Local clone failed — fetching base commit directly from origin URL {origin_url}")
                if repo_dir.exists():
                    shutil.rmtree(repo_dir)
                subprocess.run(
                    ["git", "init", str(repo_dir)],
                    check=True, capture_output=True, text=True,
                )
                subprocess.run(
                    ["git", "-C", str(repo_dir), "remote", "add", "origin", origin_url],
                    check=True, capture_output=True, text=True,
                )
                subprocess.run(
                    ["git", "-C", str(repo_dir), "fetch", "--filter=blob:none",
                     "--depth=1", "origin", base_commit],
                    check=True, capture_output=True, text=True,
                )
                subprocess.run(
                    ["git", "-C", str(repo_dir), "checkout", base_commit],
                    check=True, capture_output=True, text=True,
                )
        subprocess.run(
            ["git", "-C", str(repo_dir), "checkout", base_commit],
            check=True, capture_output=True, text=True,
        )
        subprocess.run(
            ["git", "-C", str(repo_dir), "remote", "remove", "origin"],
            capture_output=True, text=True,
        )
        # Delete remote-tracking refs left by clone; otherwise future GT commits
        # on the default branch can remain reachable even after origin is removed.
        r = subprocess.run(
            ["git", "-C", str(repo_dir), "for-each-ref",
             "--format=%(refname)", "refs/remotes/"],
            capture_output=True, text=True,
        )
        for ref in r.stdout.strip().splitlines():
            if ref:
                subprocess.run(
                    ["git", "-C", str(repo_dir), "update-ref", "-d", ref],
                    capture_output=True, text=True,
                )
        # Delete branches
        r = subprocess.run(
            ["git", "-C", str(repo_dir), "for-each-ref",
             "--format=%(refname:short)", "refs/heads/"],
            capture_output=True, text=True,
        )
        for branch in r.stdout.strip().splitlines():
            if branch:
                subprocess.run(
                    ["git", "-C", str(repo_dir), "branch", "-D", branch],
                    capture_output=True, text=True,
                )
        # Delete tags
        r = subprocess.run(
            ["git", "-C", str(repo_dir), "tag", "-l"],
            capture_output=True, text=True,
        )
        for tag in r.stdout.strip().splitlines():
            if tag:
                subprocess.run(
                    ["git", "-C", str(repo_dir), "tag", "-d", tag],
                    capture_output=True, text=True,
                )
        # Prune & gc
        subprocess.run(
            ["git", "-C", str(repo_dir), "reflog", "expire",
             "--expire=now", "--all"],
            capture_output=True, text=True,
        )
        subprocess.run(
            ["git", "-C", str(repo_dir), "gc", "--prune=now", "--aggressive"],
            capture_output=True, text=True,
        )

        # Verify GT removed
        r = subprocess.run(
            ["git", "-C", str(repo_dir), "cat-file", "-t", merge_sha],
            capture_output=True, text=True,
        )
        if r.returncode == 0:
            warn(f"  GT commit still reachable after GC!")
        else:
            log(f"  GT commit verified unreachable")

        # History depth
        r = subprocess.run(
            ["git", "-C", str(repo_dir), "rev-list", "--count", "HEAD"],
            capture_output=True, text=True,
        )
        if r.returncode == 0:
            log(f"  History: {r.stdout.strip()} commits")

        # ── Prompts ──
        prompt_dir.mkdir(parents=True, exist_ok=True)
        (prompt_dir / f"{tid}-short.md").write_text(
            f"# {tid}: {project}\n\n"
            f"Implement the changes described in the requirement document.\n\n"
            f"Requirement: {req_doc}\n"
        )
        (prompt_dir / f"{tid}-long.md").write_text(
            f"# {tid}: {project}\n\n"
            f"TODO: detailed implementation instructions.\n\n"
            f"## Requirement\n{req_doc}\n\n"
            f"## PR Reference\n{pr_link}\n"
        )

        ok += 1
        log(f"  Done")

    log(f"\nResults: {ok} built, {skip} skipped, {fail} failed")


if __name__ == "__main__":
    main()
