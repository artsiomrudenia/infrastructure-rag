from pathlib import Path

import pytest

from app.rag.service import RAGService


def test_context_keeps_multiple_chunks_from_one_source_with_sections(tmp_path: Path) -> None:
    checks_heading = "\n## Checks\n"
    symptoms = "# Storage runbook\n\n## Symptoms\n" + (
        "IO latency remains elevated while capacity is available.\n" * 9
    )
    checks = checks_heading + (
        "Measure queue depth and compare IOPS with provisioned throughput.\n" * 8
    )
    (tmp_path / "storage.md").write_text(symptoms + checks, encoding="utf-8")
    service = RAGService(tmp_path, candidate_multiplier=5)

    result = service.build_context("IO latency queue IOPS", max_chunks=4, max_chars=4000)

    assert len(result.sources) >= 2
    assert len({source.path for source in result.sources}) == 1
    assert {source.section for source in result.sources} == {"Symptoms", "Checks"}
    assert [source.source_id for source in result.sources] == [
        f"S{index}" for index in range(1, len(result.sources) + 1)
    ]
    assert all(f"[{source.source_id}]" in result.context for source in result.sources)
    assert len(result.context) <= 4000


def test_context_hard_character_budget_and_marks_truncation(tmp_path: Path) -> None:
    (tmp_path / "runbook.md").write_text(
        "# Runbook\n## Checks\n" + ("Investigate storage latency.\n" * 40),
        encoding="utf-8",
    )
    service = RAGService(tmp_path)

    result = service.build_context("storage latency", max_chunks=5, max_chars=128)

    assert result.context
    assert len(result.context) <= 128
    assert result.truncated is True
    assert result.sources


def test_context_empty_and_invalid_limits(tmp_path: Path) -> None:
    (tmp_path / "runbook.md").write_text("# Runbook\nNo matching terms.\n", encoding="utf-8")
    service = RAGService(tmp_path)

    empty = service.build_context("quantum entanglement", max_chunks=3, max_chars=100)
    assert empty.context == ""
    assert empty.sources == []
    assert empty.truncated is False
    with pytest.raises(ValueError, match="max_chunks"):
        service.build_context("query", max_chunks=0)
    with pytest.raises(ValueError, match="max_chars"):
        service.build_context("query", max_chars=31)