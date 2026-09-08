from unittest.mock import MagicMock, patch

from app.generator import build_messages, generate_code
from app.memory import build_memory_context, retrieve_similar_failures


def test_build_messages_injects_memory_into_system_prompt():
    """Assert that memory context is explicitly embedded inside the system message."""
    sample_context = (
        "PAST FAILURES TO AVOID (learn from these mistakes):\n"
        "[Memory 1 — similarity: 0.82]\n"
        "Task: Reverse a linked list\n"
        "What was tried:\nnode.next = prev\n"
        "What went wrong: AttributeError: NoneType has no attribute next\n"
        "Do not repeat this approach.\n"
    )

    messages = build_messages(
        task="Reverse a singly linked list in Python",
        attempt=1,
        memory_context=sample_context,
    )

    assert len(messages) >= 2
    system_msg = messages[0]["content"]

    # Hard gate assertion: memory must appear in system prompt
    assert "PAST FAILURES TO AVOID" in system_msg
    assert "AttributeError: NoneType has no attribute next" in system_msg
    assert "Do not repeat this approach." in system_msg


def test_generate_code_constructs_prompt_with_retrieved_memory():
    """
    Assert that generate_code queries memory and passes the retrieved failure
    into the actual messages payload sent to Groq client.chat.completions.create.
    """
    mock_memories = [
        {
            "task": "Find prime factors",
            "code": "def factors(n): return [i for i in range(2, n) if n % i == 0]",
            "error": "TimeLimitExceeded: loop ran too long on large integer",
            "similarity": 0.88,
        }
    ]

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value.choices = [
        MagicMock(message=MagicMock(content="def factors(n): return [2]"))
    ]

    with patch("app.memory.retrieve_similar_failures", return_value=mock_memories):
        generate_code(
            task="Find all prime factors of n",
            attempt=1,
            client=mock_client,
            use_memory=True,
        )

        # Inspect the exact call args passed to the LLM client
        assert mock_client.chat.completions.create.called
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        sent_messages = call_kwargs["messages"]

        system_content = sent_messages[0]["content"]
        # Hard assertion: prompt must contain the specific past error and code
        assert "PAST FAILURES TO AVOID" in system_content
        assert "TimeLimitExceeded: loop ran too long on large integer" in system_content
        assert "def factors(n): return [i for i in range(2, n) if n % i == 0]" in system_content


def test_memory_context_empty_when_no_similar_failures():
    """Ensure prompt remains clean and free of memory headers when no memories meet the threshold."""
    with patch("app.memory.retrieve_similar_failures", return_value=[]):
        context = build_memory_context("Unseen novel task")
        assert context == ""

        messages = build_messages("Unseen novel task", attempt=1, memory_context=context)
        system_content = messages[0]["content"]
        assert "PAST FAILURES TO AVOID" not in system_content


def test_similarity_filtering_below_threshold():
    """Ensure memories below similarity threshold are excluded from retrieval."""
    mock_coll = MagicMock()
    mock_coll.count.return_value = 2
    mock_coll.query.return_value = {
        "metadatas": [[
            {"task": "Sort array", "code": "arr.sort()", "error": "TypeError"},
            {"task": "Unrelated binary tree", "code": "tree.left", "error": "ValueError"},
        ]],
        "distances": [[0.15, 0.45]],  # 1 - 0.15 = 0.85 (>= 0.75), 1 - 0.45 = 0.55 (< 0.75)
    }

    results = retrieve_similar_failures(
        task="Sort array of numbers",
        similarity_threshold=0.75,
        collection=mock_coll,
    )

    assert len(results) == 1
    assert results[0]["task"] == "Sort array"
    assert results[0]["similarity"] == 0.85
