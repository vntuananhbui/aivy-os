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
        "connector.",
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


def test_connector_application_services_do_not_import_legacy_persistence() -> None:
    service_dir = ROOT / "backend" / "application" / "connectors"
    forbidden = {
        "api.settings_store",
        "connector.cache",
        "connector.teams.token_store",
        "connector.sharepoint.token_store",
        "connector.jira.token_store",
    }

    violations = {
        path.name: sorted(_imports(path) & forbidden)
        for path in service_dir.glob("*.py")
    }

    assert not {name: modules for name, modules in violations.items() if modules}


def test_connector_ai_executors_do_not_import_persistence_or_provider_clients() -> None:
    executor_paths = [
        ROOT / "skills" / "global" / "access" / "sharepoint" / "executor.py",
        ROOT / "skills" / "global" / "access" / "jira" / "executor.py",
    ]
    forbidden_prefixes = (
        "api.settings_store",
        "connector.sharepoint",
        "connector.jira",
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
        ROOT / "connector" / "sharepoint" / "tools.py",
        ROOT / "connector" / "jira" / "tools.py",
        ROOT / "connector" / "teams" / "tools.py",
        ROOT / "agents" / "teams_meeting_action" / "tools.py",
    ]
    forbidden_prefixes = (
        "langchain",
        "api.settings_store",
        "connector.sharepoint.token_store",
        "connector.jira.token_store",
        "connector.teams.token_store",
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
        "connector.sharepoint",
        "connector.jira",
        "connector.teams",
        "connector.microsoft_graph",
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


def test_legacy_ai_adapter_package_contains_only_compatibility_facades() -> None:
    adapter_dir = ROOT / "ai_adapters" / "connectors"
    for path in adapter_dir.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        implementations = [
            node.name
            for node in tree.body
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        assert implementations == []


def test_legacy_teams_agent_package_contains_only_compatibility_facades() -> None:
    for legacy_dir in (
        ROOT / "agents" / "teams_meeting_action",
        ROOT / "agents" / "bot_join",
        ROOT / "agents" / "meeting_assistant",
    ):
        for path in legacy_dir.glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            implementations = [
                node.name
                for node in tree.body
                if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
            ]
            assert implementations == []


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


def test_legacy_shared_ai_helpers_are_compatibility_facades() -> None:
    for path in (
        ROOT / "searchos" / "agents" / "temporal.py",
        ROOT / "searchos" / "agents" / "toolset_render.py",
        ROOT / "searchos" / "agents" / "explore" / "__init__.py",
        ROOT / "searchos" / "agents" / "search" / "__init__.py",
        ROOT / "searchos" / "agents" / "writer" / "__init__.py",
        ROOT / "searchos" / "agents" / "orchestrator" / "prompt.py",
        ROOT / "searchos" / "agents" / "orchestrator" / "post_mortem_prompt.py",
        ROOT / "searchos" / "agents" / "orchestrator" / "catalog.py",
        ROOT / "searchos" / "agents" / "runtime.py",
        ROOT / "searchos" / "agents" / "orchestrator" / "__init__.py",
        ROOT / "searchos" / "agents" / "orchestrator" / "lifecycle.py",
        ROOT / "searchos" / "agents" / "orchestrator" / "scheduler.py",
        ROOT / "searchos" / "agents" / "orchestrator" / "post_mortem.py",
        ROOT / "searchos" / "harness" / "blueprint.py",
        ROOT / "searchos" / "harness" / "repair_planner.py",
        ROOT / "searchos" / "harness" / "middleware" / "_shared.py",
        ROOT / "searchos" / "harness" / "middleware" / "__init__.py",
        ROOT / "searchos" / "harness" / "middleware" / "context" / "__init__.py",
        ROOT / "searchos" / "harness" / "middleware" / "context" / "control_middleware.py",
        ROOT / "searchos" / "harness" / "middleware" / "context" / "dynamic_trim.py",
        ROOT / "searchos" / "harness" / "middleware" / "context" / "layered_context.py",
    ):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        implementations = [
            node.name
            for node in tree.body
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        assert implementations == []


def test_legacy_research_runtime_reuses_canonical_context_objects() -> None:
    from ai.research.agents import runtime as canonical
    from searchos.agents import runtime as legacy

    assert legacy._ctx is canonical._ctx
    assert legacy._scheduler_var is canonical._scheduler_var


def test_legacy_research_extraction_package_contains_only_facades() -> None:
    legacy_dir = ROOT / "searchos" / "harness" / "middleware" / "extraction"
    for path in legacy_dir.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        implementations = [
            node.name
            for node in tree.body
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        assert implementations == []


def test_legacy_research_sensor_package_contains_only_facades() -> None:
    legacy_dir = ROOT / "searchos" / "harness" / "middleware" / "sensor"
    for path in legacy_dir.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        implementations = [
            node.name
            for node in tree.body
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        assert implementations == []


def test_legacy_research_session_and_report_are_compatibility_facades() -> None:
    paths = [
        ROOT / "searchos" / "harness" / "session.py",
        ROOT / "searchos" / "harness" / "report" / "__init__.py",
        ROOT / "searchos" / "harness" / "report" / "synthesis.py",
        ROOT / "searchos" / "harness" / "report" / "eval_table_export.py",
        ROOT / "searchos" / "harness" / "telemetry" / "trajectory.py",
        ROOT / "searchos" / "harness" / "telemetry" / "conversation.py",
        ROOT / "searchos" / "harness" / "telemetry" / "episodic.py",
        ROOT / "searchos" / "harness" / "telemetry" / "conversation_context.py",
        ROOT / "searchos" / "socm" / "workspace.py",
    ]
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        implementations = [
            node.name
            for node in tree.body
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        assert implementations == []


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


def test_search_http_route_is_backend_owned_and_legacy_route_is_facade() -> None:
    canonical = ROOT / "backend" / "api" / "routes" / "search.py"
    forbidden_prefixes = ("api.", "web.api")
    assert not {
        module
        for module in _imports(canonical)
        if module.startswith(forbidden_prefixes)
    }

    legacy = ROOT / "web" / "api" / "routes" / "search.py"
    tree = ast.parse(legacy.read_text(encoding="utf-8"), filename=str(legacy))
    implementations = [
        node.name
        for node in tree.body
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    assert implementations == []


def test_legacy_research_web_dependencies_are_compatibility_facades() -> None:
    for path in (
        ROOT / "web" / "api" / "deps.py",
        ROOT / "web" / "api" / "skills_catalog.py",
    ):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        implementations = [
            node.name
            for node in tree.body
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        assert implementations == []


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

        legacy = ROOT / "web" / "api" / "routes" / name
        tree = ast.parse(
            legacy.read_text(encoding="utf-8"), filename=str(legacy)
        )
        implementations = [
            node.name
            for node in tree.body
            if isinstance(
                node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
            )
        ]
        assert implementations == []
