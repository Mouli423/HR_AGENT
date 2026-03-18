from src.hr_agent.core.state import GraphState
from src.hr_agent.tools.github_client import extract_github_username, get_all_repos, traverse_repo
from src.hr_agent.config.settings import MAX_FILES_PER_REPO, MAX_TOTAL_FILES
from src.hr_agent.tools.logger import get_logger, NodeTimer

def profile_extractor(state: GraphState) -> dict:
    print("--- PROFILE EXTRACTOR ---")

    candidate  = state.get("candidate_name", "")
    github_url = state.get("github_url")
    log        = get_logger("profile_extractor")
 
    if not github_url:
        print("  No GitHub URL found — skipping.")
        log.warning("no_github_url", candidate=candidate)
        return {"routed_files": [], "analyzed_repos": []}
 
    urls           = []
    analyzed_repos = []

    with NodeTimer("profile_extractor", candidate=candidate):
        username       = extract_github_username(github_url)
        repos          = get_all_repos(username)

        print(f"  Found {len(repos)} original repos (forks excluded)")
        log.info("repos_fetched",
            candidate=candidate,
            username=username,
            repo_count=len(repos),
        )
        for r in repos:
            print(f"    → {r['name']} "
                f"(⭐{r.get('stargazers_count', 0)}, "
                f"updated: {r.get('updated_at', '')[:10]})")

        for repo in repos:
            if len(urls) >= MAX_TOTAL_FILES:
                print(f"  Total file cap ({MAX_TOTAL_FILES}) reached.")
                break
            try:
                repo_count = 0
                for file in traverse_repo(username, repo["name"]):
                    if file.get("download_url"):
                        urls.append(file["download_url"])
                        repo_count += 1
                        if repo_count >= MAX_FILES_PER_REPO:
                            break
                if repo_count > 0:
                    analyzed_repos.append(repo["name"])
            except Exception as e:
                print(f"  Skipping repo '{repo['name']}': {e}")
                continue

        print(f"  Analyzed repos: {analyzed_repos}")
        print(f"  Found {len(urls)} relevant files")
        log.info("profile_extraction_complete",
            candidate=candidate,
            repos_analyzed=len(analyzed_repos),
            files_found=len(urls),
        )
        return {"routed_files": urls, "analyzed_repos": analyzed_repos}