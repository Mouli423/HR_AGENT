import os
import requests
from urllib.parse import urlparse
from src.hr_agent.config.settings import GITHUB_API, GITHUB_HEADERS, RELEVANT_EXTENSIONS, SKIP_DIRS


def extract_github_username(github_url: str) -> str:
    path = urlparse(github_url).path.strip("/")
    return path.split("/")[0]


def get_all_repos(username: str) -> list:
    """Fetches all original (non-fork, non-archived, non-empty) repos."""
    repos, page = [], 1
    while True:
        resp = requests.get(
            f"{GITHUB_API}/users/{username}/repos",
            headers=GITHUB_HEADERS,
            params={"per_page": 100, "page": page},
            timeout=15,
        )
        if resp.status_code != 200:
            break
        batch = resp.json()
        if not batch:
            break
        filtered = [
            r for r in batch
            if not r.get("fork",     False)
            and not r.get("archived", False)
            and r.get("size", 0) > 0
        ]
        repos.extend(filtered)
        page += 1
    return repos


def traverse_repo(owner: str, repo: str, path: str = ""):
    """Yields relevant files from a repo, skipping irrelevant dirs."""
    url  = f"{GITHUB_API}/repos/{owner}/{repo}/contents/{path}"
    resp = requests.get(url, headers=GITHUB_HEADERS, timeout=15)
    if resp.status_code != 200:
        return
    for item in resp.json():
        if item["type"] == "file":
            filename = item["name"].lower()
            ext      = os.path.splitext(filename)[1]
            if ext in RELEVANT_EXTENSIONS or filename in ("dockerfile", "makefile"):
                yield item
        elif item["type"] == "dir":
            if item["name"].lower() not in SKIP_DIRS:
                yield from traverse_repo(owner, repo, item["path"])


def fetch_file_content(url: str, timeout: int = 15) -> str:
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    return resp.text