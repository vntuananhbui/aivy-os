from urllib.parse import parse_qs, unquote, urlsplit

from backend.infrastructure.connectors.sharepoint.connector import browser_url


def test_graph_direct_url_becomes_onedrive_ui_url() -> None:
    direct = (
        "https://tenant-my.sharepoint.com/personal/user/Documents/folder/"
        "Men%20vi%20sinh%20ta%CC%86ng.pdf"
    )

    result = urlsplit(browser_url(direct))
    query = parse_qs(result.query)

    assert result.path == "/my"
    assert unquote(query["id"][0]) == "/personal/user/Documents/folder/Men vi sinh tăng.pdf"
    assert unquote(query["parent"][0]) == "/personal/user/Documents/folder"


def test_non_personal_sharepoint_url_is_unchanged() -> None:
    url = "https://tenant.sharepoint.com/sites/team/Documents/report.pdf"

    assert browser_url(url) == url
