import re, common
def test_skill_md_frontmatter_and_references():
    md = (common.SKILL_DIR / "SKILL.md").read_text()
    assert md.startswith("---\nname: job-search\n") and "description:" in md
    assert "!`${CLAUDE_SKILL_DIR}/scripts/runtime_probe.py`" in md
    # allowed-tools entries are comma-separated; a space-separated list parses as one rule
    tools = [t.strip() for t in md.split("allowed-tools:", 1)[1].splitlines()[0].split(",")]
    assert tools == ["Bash(${CLAUDE_SKILL_DIR}/scripts/runtime_probe.py)", "Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/*)"]
    for s in ["parse_args.py", "doctor.py", "resume_ingest.py", "boards.py", "jd_extract.py", "jobs_db.py", "fit_score.py", "rank.py",
              "report.py", "html2pdf.py", "canary_check.py", "apply_guard.py", "notion_sync.py", "disinterest.py"]:
        assert s in md, s
    for r in ["references/commands.md", "references/search-strategy.md", "references/scoring-rubric.md", "references/memory-model.md",
              "references/tailoring.md", "references/apply-flow.md", "references/notion-mirror.md", "references/headless.md", "references/report-format.md"]:
        assert r in md, r
    assert "never" in md.lower() and "auto_submit" in md and "prompt injection" in md.lower()
    assert len(md.encode()) < 40_000
