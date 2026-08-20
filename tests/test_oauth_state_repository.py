import asyncio

from backend.application.connectors.oauth_state import InMemoryOAuthStateRepository


def test_oauth_state_is_consumed_exactly_once() -> None:
    repository = InMemoryOAuthStateRepository(token_factory=lambda _size: "state-1")

    state = asyncio.run(repository.create())

    assert asyncio.run(repository.consume(state)) is True
    assert asyncio.run(repository.consume(state)) is False


def test_expired_oauth_state_is_rejected() -> None:
    now = [1_000.0]
    repository = InMemoryOAuthStateRepository(
        ttl_seconds=300,
        clock=lambda: now[0],
        token_factory=lambda _size: "state-1",
    )
    state = asyncio.run(repository.create())
    now[0] += 301

    assert asyncio.run(repository.consume(state)) is False


def test_create_purges_expired_states() -> None:
    now = [1_000.0]
    tokens = iter(["old-state", "new-state"])
    repository = InMemoryOAuthStateRepository(
        ttl_seconds=300,
        clock=lambda: now[0],
        token_factory=lambda _size: next(tokens),
    )
    asyncio.run(repository.create())
    now[0] += 301

    assert asyncio.run(repository.create()) == "new-state"
    assert asyncio.run(repository.consume("old-state")) is False
