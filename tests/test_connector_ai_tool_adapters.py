from ai.adapters.connectors.jira import get_jira_tools as get_new_jira_tools
from ai.adapters.connectors.sharepoint import get_sharepoint_tools as get_new_sharepoint_tools
from backend.infrastructure.connectors.jira.tools import get_jira_tools as get_legacy_jira_tools
from backend.infrastructure.connectors.sharepoint.tools import get_sharepoint_tools as get_legacy_sharepoint_tools


def test_legacy_sharepoint_tool_imports_reexport_ai_adapter_objects() -> None:
    current = get_new_sharepoint_tools()
    legacy = get_legacy_sharepoint_tools()

    assert legacy == current
    assert [tool.name for tool in current] == ["sharepoint_search", "sharepoint_read"]
    assert set(current[0].args_schema.model_fields) == {"query"}
    assert set(current[1].args_schema.model_fields) == {"item_id", "offset"}


def test_legacy_jira_tool_imports_reexport_ai_adapter_objects() -> None:
    current = get_new_jira_tools()
    legacy = get_legacy_jira_tools()

    assert legacy == current
    assert [tool.name for tool in current] == [
        "jira_search",
        "jira_read",
        "jira_create_issue",
        "jira_update_issue",
        "jira_add_comment",
        "jira_transition_issue",
    ]
