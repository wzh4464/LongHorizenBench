#!/usr/bin/env python3
"""Build base_repo task directories from capbench_sampled.csv.

For each task:
1. Clone/checkout repo at parent commit
2. Generate GT diff from parent..GT
3. Create handwritten/auto-generated file lists
4. Copy prompts (placeholder)
"""

import csv, os, subprocess, sys, json, shutil
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE = Path("/Users/zihanwu/Public/codes/huawei-eval")
CSV_FILE = BASE / "capbench_sampled.csv"
SOURCE_REPOS = BASE / "source_repos"
BASE_REPO = BASE / "base_repo"

# Map project name -> clone URL
CLONE_URLS = {
    "apache/kafka": "https://github.com/apache/kafka.git",
    "python/cpython": "https://github.com/python/cpython.git",
    "apache/airflow": "https://github.com/apache/airflow.git",
    "llvm/llvm-project": "https://github.com/llvm/llvm-project.git",
    "godotengine/godot": "https://github.com/godotengine/godot.git",
    "openjdk/jdk": "https://github.com/openjdk/jdk.git",
    "microsoft/TypeScript": "https://github.com/microsoft/TypeScript.git",
    "hashicorp/consul": "https://github.com/hashicorp/consul.git",
    "astral-sh/ruff": "https://github.com/astral-sh/ruff.git",
    "nickel-org/vitess": "https://github.com/vitessio/vitess.git",
    "grpc/grpc": "https://github.com/grpc/grpc.git",
    "envoyproxy/envoy": "https://github.com/envoyproxy/envoy.git",
    "electron/electron": "https://github.com/electron/electron.git",
    "kubernetes/kubernetes": "https://github.com/kubernetes/kubernetes.git",
    "prestodb/presto": "https://github.com/prestodb/presto.git",
    "vitessio/vitess": "https://github.com/vitessio/vitess.git",
}

def get_repo_url(github_url):
    """Extract clone URL from project URL."""
    return github_url.rstrip('/') + '.git'

def get_pr_merge_commit(repo_path, pr_url):
    """Find the merge commit for a PR from git log."""
    pr_num = pr_url.rstrip('/').split('/')[-1]
    # Try to find merge commit referencing this PR
    result = subprocess.run(
        ['git', '-C', str(repo_path), 'log', '--all', '--grep', f'#{pr_num}', '--format=%H', '-1'],
        capture_output=True, text=True
    )
    return result.stdout.strip() if result.stdout.strip() else None

def build_task(task_id, row, source_repo_path):
    """Build one task directory."""
    task_dir = f"/Users/zihanwu/Public/codes/huawei-eval/base_repo/{task_id}"
    # ... implementation
    pass

if __name__ == '__main__':
    print("Script template ready. Will be called by agents.")
