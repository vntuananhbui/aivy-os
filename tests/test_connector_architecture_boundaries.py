import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_connector_http_routes_do_not_import_provider_or_persistence_implementations() -> None:
    route_dir = ROOT / "backend" / "api" / "routes" / "connectors"
    forbidden_prefixes = (
        "api.settings_store",
        "api.settings_views",
        "backend.infrastructure.connectors",
        "httpx",
    )

    violations = {
        path.name: sorted(
            module
            for module in _imports(path)
            if module.startswith(forbidden_prefixes)
        )
        for path in route_dir.glob("*.py")
    }

    assert not {name: modules for name, modules in violations.items() if modules}


def test_connector_application_services_do_not_import_infrastructure() -> None:
    service_dir = ROOT / "backend" / "application" / "connectors"
    violations = {
        path.name: sorted(
            module
            for module in _imports(path)
            if module.startswith("backend.infrastructure")
        )
        for path in service_dir.glob("*.py")
    }

    assert not {name: modules for name, modules in violations.items() if modules}


def test_connector_ai_executors_do_not_import_persistence_or_provider_clients() -> None:
    executor_paths = [
        ROOT / "ai" / "skills" / "global" / "access" / "sharepoint" / "executor.py",
        ROOT / "ai" / "skills" / "global" / "access" / "jira" / "executor.py",
    ]
    forbidden_prefixes = (
        "api.settings_store",
        "backend.infrastructure.connectors.sharepoint",
        "backend.infrastructure.connectors.jira",
    )
    violations = {
        str(path.relative_to(ROOT)): sorted(
            module
            for module in _imports(path)
            if module.startswith(forbidden_prefixes)
        )
        for path in executor_paths
    }
    assert not {name: modules for name, modules in violations.items() if modules}


def test_connector_packages_do_not_own_langchain_tool_definitions() -> None:
    tool_paths = [
        ROOT / "backend" / "infrastructure" / "connectors" / "sharepoint" / "tools.py",
        ROOT / "backend" / "infrastructure" / "connectors" / "jira" / "tools.py",
        ROOT / "backend" / "infrastructure" / "connectors" / "teams" / "tools.py",
    ]
    forbidden_prefixes = (
        "langchain",
        "api.settings_store",
        "backend.infrastructure.connectors.sharepoint.token_store",
        "backend.infrastructure.connectors.jira.token_store",
        "backend.infrastructure.connectors.teams.token_store",
    )
    violations = {
        str(path.relative_to(ROOT)): sorted(
            module
            for module in _imports(path)
            if module.startswith(forbidden_prefixes)
        )
        for path in tool_paths
    }
    assert not {name: modules for name, modules in violations.items() if modules}

    for path in tool_paths:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        decorated = [
            node.name
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.decorator_list
        ]
        assert decorated == []


def test_ai_tool_adapters_depend_on_services_not_persistence_or_provider_clients() -> None:
    adapter_dir = ROOT / "ai" / "adapters" / "connectors"
    forbidden_prefixes = (
        "api.settings_store",
        "backend.infrastructure.connectors.sharepoint",
        "backend.infrastructure.connectors.jira",
        "backend.infrastructure.connectors.teams",
        "backend.infrastructure.connectors.microsoft_graph",
    )
    violations = {
        path.name: sorted(
            module
            for module in _imports(path)
            if module.startswith(forbidden_prefixes)
        )
        for path in adapter_dir.glob("*.py")
    }
    assert not {name: modules for name, modules in violations.items() if modules}


def test_legacy_ai_adapter_package_is_removed() -> None:
    assert not (ROOT / "ai_adapters").exists()


def test_legacy_top_level_agents_package_is_removed() -> None:
    assert not (ROOT / "agents").exists()


def test_legacy_top_level_tools_package_is_removed() -> None:
    assert not (ROOT / "tools").exists()


def test_legacy_root_skills_directory_is_removed() -> None:
    assert not (ROOT / "skills").exists()
    assert not list((ROOT / "ai" / "skills").rglob(".staging_*"))


def test_dynamic_skills_are_written_outside_packaged_ai_skills() -> None:
    source = (
        ROOT / "ai" / "skills" / "evolution" / "dynamic_builder.py"
    ).read_text(encoding="utf-8")
    assert "searchos_workspace/generated_skills" in source
    assert 'Path("ai/skills/deepresearch/access")' not in source


def test_legacy_top_level_connector_package_is_removed() -> None:
    assert not (ROOT / "connector").exists()


def test_conversation_route_and_service_do_not_import_quickchat_persistence() -> None:
    paths = [
        ROOT / "backend" / "api" / "routes" / "chat.py",
        ROOT / "backend" / "api" / "routes" / "conversations.py",
        ROOT / "backend" / "application" / "chat_runs" / "service.py",
        ROOT / "backend" / "application" / "chat_runs" / "gateways.py",
        ROOT / "backend" / "application" / "conversations" / "service.py",
        ROOT / "backend" / "application" / "conversations" / "repositories.py",
    ]
    forbidden_prefixes = (
        "quickchat",
        "sqlite3",
        "langgraph",
        "api.routes",
    )
    violations = {
        str(path.relative_to(ROOT)): sorted(
            module
            for module in _imports(path)
            if module.startswith(forbidden_prefixes)
        )
        for path in paths
    }
    assert not {name: modules for name, modules in violations.items() if modules}


def test_ai_quickchat_runtime_does_not_import_backend_infrastructure_or_legacy_runtime() -> None:
    forbidden_prefixes = ("backend.infrastructure", "quickchat")
    violations = {
        str(path.relative_to(ROOT)): sorted(
            module
            for module in _imports(path)
            if module.startswith(forbidden_prefixes)
        )
        for path in (ROOT / "ai" / "quickchat").rglob("*.py")
    }
    assert not {name: modules for name, modules in violations.items() if modules}


def test_legacy_top_level_quickchat_package_is_removed() -> None:
    assert not (ROOT / "quickchat").exists()


def test_legacy_searchos_ai_trees_are_removed() -> None:
    assert not (ROOT / "searchos" / "agents").exists()
    assert not (ROOT / "searchos" / "harness").exists()


def test_research_ai_does_not_import_legacy_or_backend_telemetry() -> None:
    forbidden_prefixes = (
        "backend.infrastructure",
        "searchos.harness.telemetry",
    )
    violations = {
        str(path.relative_to(ROOT)): sorted(
            module
            for module in _imports(path)
            if module.startswith(forbidden_prefixes)
        )
        for path in (ROOT / "ai" / "research").rglob("*.py")
    }
    assert not {name: modules for name, modules in violations.items() if modules}


def test_search_session_does_not_resolve_models_or_backend_adapters() -> None:
    imports = _imports(ROOT / "ai" / "research" / "orchestration" / "session.py")
    assert "searchos.config.models" not in imports
    assert "searchos.config.settings" not in imports
    assert not any(module.startswith("backend.") for module in imports)


def test_search_http_route_is_backend_owned() -> None:
    canonical = ROOT / "backend" / "api" / "routes" / "search.py"
    forbidden_prefixes = ("api.", "web.api")
    assert not {
        module
        for module in _imports(canonical)
        if module.startswith(forbidden_prefixes)
    }

def test_legacy_web_api_package_is_removed() -> None:
    assert not (ROOT / "web" / "api").exists()


def test_research_run_application_layer_does_not_import_infrastructure() -> None:
    application_dir = ROOT / "backend" / "application" / "research_runs"
    violations = {
        path.name: sorted(
            module
            for module in _imports(path)
            if module.startswith("backend.infrastructure")
        )
        for path in application_dir.glob("*.py")
    }
    assert not {name: modules for name, modules in violations.items() if modules}


def test_canonical_search_route_uses_run_service_not_legacy_sessions() -> None:
    path = ROOT / "backend" / "api" / "routes" / "search.py"
    source = path.read_text(encoding="utf-8")
    assert "research_run_service" in source
    assert "sessions.get" not in source
    assert "sessions[" not in source


def test_research_history_and_stream_routes_are_backend_owned() -> None:
    for name in ("history.py", "stream.py"):
        canonical = ROOT / "backend" / "api" / "routes" / name
        imports = _imports(canonical)
        assert not any(module.startswith("api.") for module in imports)
        source = canonical.read_text(encoding="utf-8")
        assert "research_run_service" in source
        assert "sessions.get" not in source
