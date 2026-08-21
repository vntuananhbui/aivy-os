GitHub Repository Metadata Skill

This skill extracts structured metadata from public GitHub repository pages on **github.com** using HTML parsing (no GitHub API tokens required).

## Supported function

### `repo_metadata`

Fetch core metadata and root directory files for a repository.

**Inputs**
- `function`: `"repo_metadata"`
- Either:
  - `owner`: repository owner or organization name
  - `repo`: repository name
- Or:
  - `url`: full GitHub repository URL, e.g. `https://github.com/owner/repo`

**Output**

A JSON object:
```json
{
  "error": null,
  "data": {
    "full_name": "owner/repo",
    "owner": "owner",
    "name": "repo",
    "description": "Repository description if present",
    "stars": 1234,
    "topics": ["agents", "llm", "tooling"],
    "files": [
      {"name": "README.md", "type": "file"},
      {"name": "src", "type": "directory"}
    ],
    "languages": [
      {"name": "Python", "percentage": "80%"},
      {"name": "Shell", "percentage": "20%"}
    ]
  }
}
```

If an error occurs, `error` will be a short string such as `"missing_params"`, `"invalid_repo"`, `"http_error"`, or `"internal_error"`, and a human-readable `message` may be included.

## Notes
- Works only on public repositories accessible without authentication.
- Parsing relies on GitHub's HTML structure; fields that cannot be located will be omitted or set to `null`.
