## ADDED Requirements

### Requirement: Rate-limit error classification
The system SHALL classify LLM error responses as rate-limit errors when the error content contains rate-limit markers (429 status, "rate limit", "quota exceeded", "resource exhausted"). This classification SHALL be exposed as a `is_rate_limited` boolean on `AgentRunResult`.

#### Scenario: Standard rate-limit error detected
- **WHEN** the LLM provider returns a 429 error and retries are exhausted
- **THEN** `AgentRunResult.is_rate_limited` SHALL be `True` and `stop_reason` SHALL be `"rate_limited"`

#### Scenario: Non-rate-limit error not classified as rate-limited
- **WHEN** the LLM provider returns a 500 server error or connection timeout after retries
- **THEN** `AgentRunResult.is_rate_limited` SHALL be `False` and `stop_reason` SHALL be `"error"`

#### Scenario: Quota exceeded classified as rate-limited
- **WHEN** the error content contains "quota exceeded" or "usage quota"
- **THEN** `AgentRunResult.is_rate_limited` SHALL be `True`

---

### Requirement: Rate-limit checkpoint save
When the agent loop encounters a terminal rate-limit error, the system SHALL save a checkpoint to session metadata containing the original user message, channel routing info, and timestamp. The error SHALL NOT be saved as a normal conversation turn.

#### Scenario: Checkpoint saved on rate-limit error
- **WHEN** `AgentRunResult.is_rate_limited` is `True`
- **THEN** the system SHALL save a `rate_limit_checkpoint` entry to `session.metadata` with keys: `original_message`, `timestamp`, `channel`, `chat_id`, `session_key`, `error_summary`
- **AND** the error SHALL NOT appear in session message history
- **AND** a notification SHALL be sent to the user's channel

#### Scenario: Normal error does not save checkpoint
- **WHEN** `AgentRunResult.is_rate_limited` is `False`
- **THEN** no `rate_limit_checkpoint` SHALL be written to session metadata
- **AND** the error SHALL be saved to session history as a normal turn

#### Scenario: Overwrite previous checkpoint
- **WHEN** a rate-limit error occurs on a session that already has a `rate_limit_checkpoint`
- **THEN** the new checkpoint SHALL overwrite the previous one

---

### Requirement: Rate-limit checkpoint expiry
Checkpoints SHALL expire 14 days after their `timestamp`. Expired checkpoints SHALL be silently deleted during resume scanning.

#### Scenario: Checkpoint within TTL is valid
- **WHEN** a checkpoint's `timestamp` is within 14 days of the current time
- **THEN** the checkpoint SHALL be considered valid and eligible for resume

#### Scenario: Checkpoint past TTL is expired
- **WHEN** a checkpoint's `timestamp` is more than 14 days in the past
- **THEN** the checkpoint SHALL be deleted from session metadata without resuming

---

### Requirement: Proactive resume on startup
When `nanobot gateway` or `nanobot agent` starts, the system SHALL scan all sessions for pending rate-limit checkpoints and resume each valid one by replaying the original message through the normal agent loop.

#### Scenario: Gateway startup with pending checkpoint
- **WHEN** the gateway starts and session "telegram:123456" has a valid `rate_limit_checkpoint`
- **THEN** the system SHALL send a proactive notification to the telegram channel: "Back online — resuming your earlier task..."
- **AND** the original message SHALL be replayed through the agent loop
- **AND** the checkpoint SHALL be cleared from session metadata
- **AND** the result SHALL be delivered to the channel

#### Scenario: CLI startup with pending checkpoint
- **WHEN** `nanobot agent` starts interactively and a session has a valid `rate_limit_checkpoint`
- **THEN** the system SHALL print a notification to the terminal
- **AND** replay the original message through the agent loop
- **AND** display the result

#### Scenario: No pending checkpoints
- **WHEN** no sessions have a `rate_limit_checkpoint`
- **THEN** startup SHALL proceed normally with no delay or notification

#### Scenario: Multiple sessions with checkpoints
- **WHEN** multiple sessions have valid checkpoints
- **THEN** all SHALL be resumed concurrently, subject to the existing concurrency gate

---

### Requirement: Session metadata scanning
`SessionManager` SHALL provide a `scan_metadata(key)` method that discovers sessions containing a specific metadata key without loading full session histories.

#### Scenario: Scan discovers sessions with checkpoint
- **WHEN** `scan_metadata("rate_limit_checkpoint")` is called
- **THEN** it SHALL return a list of `(session_key, checkpoint_data)` tuples for all sessions that have the key

#### Scenario: Scan finds no matching sessions
- **WHEN** no sessions contain the requested metadata key
- **THEN** `scan_metadata()` SHALL return an empty list
