import asyncio
from typing import Any, Dict

import httpx
from bs4 import BeautifulSoup

BASE_WEB_URL = "https://github.com"


class GitHubSkillError(Exception):
    pass


async def fetch_html(client: httpx.AsyncClient, path: str) -> str:
    url = path if path.startswith("http") else f"{BASE_WEB_URL.rstrip('/')}/{path.lstrip('/')}"
    resp = await client.get(url, follow_redirects=True, headers={
        "User-Agent": "SearchOS-GitHubSkill/1.0",
        "Accept": "text/html,application/xhtml+xml",
    })
    resp.raise_for_status()
    return resp.text


def parse_repo_page(html: str) -> Dict[str, Any]:
    soup = BeautifulSoup(html, "html.parser")

    title_el = soup.find("strong", {"itemprop": "name"})
    owner_el = soup.find("span", {"class": "author"}) or soup.find("a", {"rel": "author"})

    full_name = None
    owner = owner_el.get_text(strip=True) if owner_el else None
    repo_name = title_el.get_text(strip=True) if title_el else None
    if owner and repo_name:
        full_name = f"{owner}/{repo_name}".strip()

    description_el = soup.find("p", {"class": "f4 my-3"}) or soup.find("p", {"itemprop": "description"})
    description = description_el.get_text(strip=True) if description_el else None

    # stars
    stars = None
    st_el = soup.find("a", {"href": lambda x: x and x.endswith("/stargazers")})
    if st_el:
        stars_text = st_el.get_text(strip=True).replace(",", "")
        try:
            # Handle shorthand like 1.2k
            if stars_text.lower().endswith("k"):
                stars = int(float(stars_text[:-1]) * 1000)
            elif stars_text.lower().endswith("m"):
                stars = int(float(stars_text[:-1]) * 1_000_000)
            else:
                stars = int(stars_text)
        except ValueError:
            stars = None

    # topics
    topics = []
    topics_container = soup.find("div", class_="topic-tags-container") or soup.find("div", class_="BorderGrid-row")
    if topics_container:
        for a in topics_container.find_all("a", class_=lambda c: c and "topic-tag" in c.split()):
            t = a.get_text(strip=True)
            if t:
                topics.append(t)

    # file list (root)
    files = []
    table = soup.find("div", {"role": "grid"}) or soup.find("table", class_="files")
    if table:
        for row in table.find_all("div", {"role": "row"}):
            name_el = row.find("a", {"data-testid": "tree-list-item"}) or row.find("a", class_="js-navigation-open")
            if not name_el:
                continue
            file_name = name_el.get_text(strip=True)
            type_badge = row.find("svg", {"aria-label": ["Directory", "File"]})
            kind = None
            if type_badge and type_badge.get("aria-label"):
                kind = type_badge["aria-label"].lower()
            files.append({"name": file_name, "type": kind})

    # language stats if present
    languages = []
    lang_container = soup.find("ul", class_="list-style-none")
    if lang_container:
        for li in lang_container.find_all("li"):
            lang_name_el = li.find("span", class_="color-fg-default")
            percent_el = li.find("span", class_="color-fg-muted")
            if lang_name_el:
                languages.append({
                    "name": lang_name_el.get_text(strip=True),
                    "percentage": percent_el.get_text(strip=True) if percent_el else None,
                })

    return {
        "full_name": full_name,
        "owner": owner,
        "name": repo_name,
        "description": description,
        "stars": stars,
        "topics": topics,
        "files": files,
        "languages": languages,
    }


async def get_repo_metadata(owner: str, repo: str) -> Dict[str, Any]:
    async with httpx.AsyncClient(timeout=20.0) as client:
        html = await fetch_html(client, f"/{owner}/{repo}")
    return parse_repo_page(html)


async def execute(params: Dict[str, Any], ctx: Any) -> Dict[str, Any]:
    """Entry point for SearchOS.

    Params:
      - function: which capability to run. Supported:
          - repo_metadata: fetch core metadata and root file listing for a repository.
      - owner: repo owner/org (repo_metadata)
      - repo: repo name (repo_metadata)
      - url: full GitHub repo URL (alternative to owner+repo)
    """
    fn = params.get("function")

    if fn == "repo_metadata":
        owner = params.get("owner")
        repo = params.get("repo")
        url = params.get("url")

        if not (owner and repo) and not url:
            return {"error": "missing_params", "message": "Provide either owner+repo or url."}

        if url and not (owner and repo):
            # parse url like https://github.com/owner/repo[...]
            try:
                from urllib.parse import urlparse

                parsed = urlparse(url)
                parts = parsed.path.strip("/").split("/")
                if len(parts) >= 2:
                    owner, repo = parts[0], parts[1]
            except Exception:
                pass

        if not (owner and repo):
            return {"error": "invalid_repo", "message": "Could not determine owner and repo from inputs."}

        try:
            data = await get_repo_metadata(owner, repo)
            return {
                "error": None,
                "data": data,
            }
        except httpx.HTTPStatusError as e:
            return {"error": "http_error", "status_code": e.response.status_code, "message": str(e)}
        except Exception as e:  # unexpected
            return {"error": "internal_error", "message": str(e)}

    return {"error": "unknown_function", "message": f"Unsupported function: {fn}"}
