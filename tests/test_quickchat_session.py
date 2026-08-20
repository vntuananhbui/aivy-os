from ai.quickchat.session import _citation_with_trusted_source, _recursion_limit_for_effort


def test_recursion_limit_scales_with_effort() -> None:
    limits = [_recursion_limit_for_effort(level) for level in ("low", "medium", "high", "max")]

    assert limits == sorted(limits)
    assert len(set(limits)) == len(limits)
    assert _recursion_limit_for_effort("unknown") == _recursion_limit_for_effort("medium")


def test_citation_uses_exact_tool_url_when_title_matches() -> None:
    citation = {
        "url": "https://tenant/my/file-cu%CC%80ng.pdf",
        "title": "Tài liệu.pdf",
        "quote": "bằng chứng",
    }
    trusted = [
        {
            "url": "https://tenant/my?id=file-cu%CC%9B%CC%80ng.pdf",
            "title": "Tài liệu.pdf",
        }
    ]

    assert _citation_with_trusted_source(citation, trusted) == {
        "url": trusted[0]["url"],
        "title": trusted[0]["title"],
        "quote": "bằng chứng",
    }
