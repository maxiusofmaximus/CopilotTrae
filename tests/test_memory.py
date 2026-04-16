from local_ai_agent.memory import ConversationMemory, PersistentConversationMemory


def test_memory_keeps_last_n_non_system_messages():
    memory = ConversationMemory(max_messages=4, system_prompt="Stay helpful.")

    for index in range(6):
        role = "user" if index % 2 == 0 else "assistant"
        memory.add(role=role, content=f"message-{index}")

    visible = memory.recent_messages()

    assert [item.content for item in visible] == [
        "message-2",
        "message-3",
        "message-4",
        "message-5",
    ]


def test_memory_builds_context_with_system_prompt():
    memory = ConversationMemory(max_messages=2, system_prompt="Architect mode.")
    memory.add(role="user", content="First")
    memory.add(role="assistant", content="Reply")

    messages = memory.build_request_messages("Next question")

    assert [item.role for item in messages] == ["system", "user", "assistant", "user"]
    assert messages[0].content == "Architect mode."
    assert messages[-1].content == "Next question"


def test_persistent_memory_survives_restart_and_reconstructs_context(tmp_path):
    storage_path = tmp_path / "session.jsonl"

    first_process = PersistentConversationMemory(
        max_messages=4,
        system_prompt="Architect mode.",
        storage_path=storage_path,
    )
    first_process.add(role="user", content="First")
    first_process.add(role="assistant", content="Reply")

    second_process = PersistentConversationMemory(
        max_messages=4,
        system_prompt="Architect mode.",
        storage_path=storage_path,
    )
    messages = second_process.build_request_messages("Next question")

    assert [item.role for item in second_process.recent_messages()] == ["user", "assistant"]
    assert [item.role for item in messages] == ["system", "user", "assistant", "user"]
    assert [item.content for item in messages] == ["Architect mode.", "First", "Reply", "Next question"]


def test_persistent_memory_applies_trimming_after_restart(tmp_path):
    storage_path = tmp_path / "session.jsonl"
    first_process = PersistentConversationMemory(
        max_messages=3,
        system_prompt="Stay helpful.",
        storage_path=storage_path,
    )

    for index in range(5):
        role = "user" if index % 2 == 0 else "assistant"
        first_process.add(role=role, content=f"message-{index}")

    second_process = PersistentConversationMemory(
        max_messages=3,
        system_prompt="Stay helpful.",
        storage_path=storage_path,
    )

    assert [item.content for item in second_process.recent_messages()] == [
        "message-2",
        "message-3",
        "message-4",
    ]
    assert len(storage_path.read_text(encoding="utf-8").splitlines()) == 5
