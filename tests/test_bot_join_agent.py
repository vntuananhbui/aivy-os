from ai.agents.bot_join import bot_join
from ai.quickchat.commands.catalog import COMMAND_CATALOG


def test_bot_join_accepts_microsoft_teams_url() -> None:
    url = "https://teams.microsoft.com/l/meetup-join/abc?context=123"
    assert bot_join.invoke({"teams_join_url": url}) == f"Bot đã vào link {url}"


def test_bot_join_rejects_non_teams_url() -> None:
    result = bot_join.invoke({"teams_join_url": "https://example.com/meeting"})
    assert result.startswith("Lỗi:")


def test_bot_join_agent_is_registered() -> None:
    assert "bot_join" in COMMAND_CATALOG
