from ai.quickchat.citation import CitationStreamFilter

TAG = '<cite url="https://example.com" title="Doc">Exact evidence.</cite>'


def test_claim_outside_citation_is_not_duplicated() -> None:
    text, citations = CitationStreamFilter().feed(f"Visible claim. {TAG}")

    assert text == "Visible claim. [1]"
    assert citations[0]["quote"] == "Exact evidence."


def test_bare_bullet_citation_preserves_quote_as_visible_text() -> None:
    text, citations = CitationStreamFilter().feed(f"* {TAG}")

    assert text == "* Exact evidence. [1]"
    assert citations[0]["quote"] == "Exact evidence."
