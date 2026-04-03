"""Tests for rate-limit checkpoint: save, resume, TTL, and classification."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nanobot.providers.base import LLMProvider, LLMResponse
from nanobot.bus.events import InboundMessage, OutboundMessage
from nanobot.session.manager import Session, SessionManager


def _get_key():
    from nanobot.agent.loop import AgentLoop
    return AgentLoop._RATE_LIMIT_CHECKPOINT_KEY


# ---------------------------------------------------------------------------
# 5.1 Rate-limit error classification
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("content", [
    "Error: 429 Too Many Requests",
    "rate limit exceeded",
    "Quota exceeded for model",
    "Resource Exhausted: usage quota met",
    "Your API key has exceeded the usage quota",
])
def test_is_rate_limit_error_true(content):
    assert LLMProvider.is_rate_limit_error(content) is True


@pytest.mark.parametrize("content", [
    "Error: 500 Internal Server Error",
    "connection timed out",
    "Error calling LLM: Connection refused",
    "502 Bad Gateway",
    "server error: overloaded",
    None,
    "",
])
def test_is_rate_limit_error_false(content):
    assert LLMProvider.is_rate_limit_error(content) is False


# ---------------------------------------------------------------------------
# 5.2 AgentRunResult.is_rate_limited
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_runner_sets_is_rate_limited_on_429():
    from nanobot.agent.runner import AgentRunSpec, AgentRunner
    from nanobot.config.schema import AgentDefaults

    provider = MagicMock()
    provider.chat_with_retry = AsyncMock(return_value=LLMResponse(
        content="Error: 429 Rate limit exceeded",
        finish_reason="error",
        tool_calls=[],
    ))
    tools = MagicMock()
    tools.get_definitions.return_value = []

    runner = AgentRunner(provider)
    result = await runner.run(AgentRunSpec(
        initial_messages=[{"role": "user", "content": "hello"}],
        tools=tools,
        model="test-model",
        max_iterations=1,
        max_tool_result_chars=AgentDefaults().max_tool_result_chars,
    ))

    assert result.is_rate_limited is True
    assert result.stop_reason == "rate_limited"


@pytest.mark.asyncio
async def test_runner_does_not_set_is_rate_limited_on_500():
    from nanobot.agent.runner import AgentRunSpec, AgentRunner
    from nanobot.config.schema import AgentDefaults

    provider = MagicMock()
    provider.chat_with_retry = AsyncMock(return_value=LLMResponse(
        content="Error: 500 Internal Server Error",
        finish_reason="error",
        tool_calls=[],
    ))
    tools = MagicMock()
    tools.get_definitions.return_value = []

    runner = AgentRunner(provider)
    result = await runner.run(AgentRunSpec(
        initial_messages=[{"role": "user", "content": "hello"}],
        tools=tools,
        model="test-model",
        max_iterations=1,
        max_tool_result_chars=AgentDefaults().max_tool_result_chars,
    ))

    assert result.is_rate_limited is False
    assert result.stop_reason == "error"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_loop(tmp_path, *, sessions=None):
    from nanobot.agent.loop import AgentLoop
    from nanobot.bus.queue import MessageBus

    bus = MessageBus()
    provider = MagicMock()
    provider.get_default_model.return_value = "test-model"

    with patch("nanobot.agent.loop.ContextBuilder"), \
         patch("nanobot.agent.loop.SubagentManager") as MockSubMgr:
        MockSubMgr.return_value.cancel_by_session = AsyncMock(return_value=0)
        kwargs = dict(bus=bus, provider=provider, workspace=tmp_path)
        if sessions is not None:
            kwargs["session_manager"] = sessions
        loop = AgentLoop(**kwargs)
    return loop


# ---------------------------------------------------------------------------
# 5.3 Checkpoint save
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_checkpoint_saved_on_rate_limit(tmp_path):
    key = _get_key()
    sessions = SessionManager(tmp_path)

    loop = _make_loop(tmp_path, sessions=sessions)
    loop.provider.chat_with_retry = AsyncMock(return_value=LLMResponse(
        content="Error: 429 rate limit exceeded",
        finish_reason="error",
        tool_calls=[],
    ))

    msg = InboundMessage(channel="telegram", sender_id="user1", chat_id="123", content="hello")
    result = await loop._process_message(msg)

    assert result is not None
    assert "Rate limit" in result.content
    session = sessions.get_or_create("telegram:123")
    assert key in session.metadata
    checkpoint = session.metadata[key]
    assert checkpoint["original_message"] == "hello"
    assert checkpoint["channel"] == "telegram"
    assert checkpoint["chat_id"] == "123"
    assert "timestamp" in checkpoint


# ---------------------------------------------------------------------------
# 5.6 Non-rate-limit errors produce no checkpoint
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_no_checkpoint_on_non_rate_limit_error(tmp_path):
    key = _get_key()
    sessions = SessionManager(tmp_path)

    loop = _make_loop(tmp_path, sessions=sessions)
    loop.provider.chat_with_retry = AsyncMock(return_value=LLMResponse(
        content="Error: 500 Internal Server Error",
        finish_reason="error",
        tool_calls=[],
    ))

    msg = InboundMessage(channel="cli", sender_id="user1", chat_id="direct", content="hello")
    result = await loop._process_message(msg)

    session = sessions.get_or_create("cli:direct")
    assert key not in session.metadata
    assert result is not None


# ---------------------------------------------------------------------------
# 5.4 Checkpoint resume via scan_metadata
# ---------------------------------------------------------------------------

def test_scan_metadata_finds_checkpoints(tmp_path):
    key = _get_key()
    sessions = SessionManager(tmp_path)

    session_with_checkpoint = Session(key="telegram:123", metadata={
        key: {
            "original_message": "hello",
            "timestamp": datetime.now().isoformat(),
        },
    })
    sessions.save(session_with_checkpoint)

    session_without = Session(key="telegram:456")
    sessions.save(session_without)

    results = sessions.scan_metadata(key)
    assert len(results) == 1
    assert results[0][0] == "telegram:123"
    assert results[0][1]["original_message"] == "hello"


def test_scan_metadata_returns_empty_when_none(tmp_path):
    key = _get_key()
    sessions = SessionManager(tmp_path)
    session = Session(key="telegram:789")
    sessions.save(session)

    results = sessions.scan_metadata(key)
    assert results == []


# ---------------------------------------------------------------------------
# 5.5 TTL expiry (2 weeks)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_expired_checkpoint_deleted_without_replay(tmp_path):
    key = _get_key()
    sessions = SessionManager(tmp_path)

    old_ts = (datetime.now() - timedelta(days=15)).isoformat()
    session = Session(key="telegram:expired", metadata={
        key: {
            "original_message": "old msg",
            "timestamp": old_ts,
            "channel": "telegram",
            "chat_id": "expired",
        },
    })
    sessions.save(session)

    loop = _make_loop(tmp_path, sessions=sessions)
    bus = loop.bus

    bus.publish_outbound = AsyncMock()
    await loop._resume_rate_limit_checkpoints()

    bus.publish_outbound.assert_not_called()
    reloaded = sessions._load("telegram:expired")
    assert reloaded is not None
    assert key not in reloaded.metadata


@pytest.mark.asyncio
async def test_valid_checkpoint_is_resumed(tmp_path):
    key = _get_key()
    sessions = SessionManager(tmp_path)

    session = Session(key="telegram:valid", metadata={
        key: {
            "original_message": "resume me",
            "timestamp": datetime.now().isoformat(),
            "channel": "telegram",
            "chat_id": "valid",
        },
    })
    sessions.save(session)

    loop = _make_loop(tmp_path, sessions=sessions)
    bus = loop.bus

    loop._dispatch = AsyncMock()
    bus.publish_outbound = AsyncMock()
    await loop._resume_rate_limit_checkpoints()

    bus.publish_outbound.assert_awaited_once()
    notification = bus.publish_outbound.call_args[0][0]
    assert "Back online" in notification.content

    loop._dispatch.assert_awaited_once()
    synthetic_msg = loop._dispatch.call_args[0][0]
    assert synthetic_msg.content == "resume me"
    assert synthetic_msg.channel == "telegram"

    reloaded = sessions._load("telegram:valid")
    assert reloaded is not None
    assert key not in reloaded.metadata
