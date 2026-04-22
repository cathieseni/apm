"""Tests for ``apm compile --check`` drift verification flag."""

import os
import shutil
import tempfile
from pathlib import Path

import pytest
from click.testing import CliRunner

from apm_cli.cli import cli


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def runner():
    """CliRunner for CLI tests."""
    return CliRunner()


@pytest.fixture
def project_dir():
    """Create a minimal APM project in a temp directory."""
    tmp = tempfile.mkdtemp()
    tmp_path = Path(tmp)

    # Minimal apm.yml
    (tmp_path / "apm.yml").write_text(
        "name: test-project\nversion: 0.1.0\n", encoding="utf-8"
    )

    yield tmp_path
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture
def project_with_instruction(project_dir):
    """Project with a single root-scoped instruction (no applyTo)."""
    inst_dir = project_dir / ".apm" / "instructions"
    inst_dir.mkdir(parents=True)
    (inst_dir / "coding.instructions.md").write_text(
        "---\ndescription: Coding standards\n---\nUse type hints.\n",
        encoding="utf-8",
    )
    # Ensure .github dir exists for copilot-instructions target detection.
    (project_dir / ".github").mkdir(exist_ok=True)
    return project_dir


@pytest.fixture
def project_with_scoped_instruction(project_dir):
    """Project with a scoped instruction (has applyTo)."""
    inst_dir = project_dir / ".apm" / "instructions"
    inst_dir.mkdir(parents=True)
    (inst_dir / "python.instructions.md").write_text(
        '---\ndescription: Python standards\napplyTo: "**/*.py"\n---\nFollow PEP 8.\n',
        encoding="utf-8",
    )
    # Ensure .github dir exists.
    (project_dir / ".github").mkdir(exist_ok=True)
    return project_dir


def _invoke(runner, args, cwd):
    """Invoke CLI in the given cwd and return the result."""
    original = os.getcwd()
    try:
        os.chdir(cwd)
        return runner.invoke(cli, ["compile"] + args, catch_exceptions=False)
    finally:
        os.chdir(original)


# =====================================================================
# Exit code 0 -- clean state
# =====================================================================


class TestCheckCleanState:
    def test_no_drift_exits_zero(self, runner, project_with_instruction):
        """When on-disk matches expected, exit 0."""
        cwd = project_with_instruction

        # First compile to create the outputs.
        _invoke(runner, ["--local-only"], cwd)

        # Now check -- should be clean.
        result = _invoke(runner, ["--check"], cwd)
        assert result.exit_code == 0

    def test_no_drift_verbose_exits_zero(self, runner, project_with_instruction):
        """With --verbose and no drift, exit 0, output has up-to-date message."""
        cwd = project_with_instruction
        _invoke(runner, ["--local-only"], cwd)

        result = _invoke(runner, ["--check", "--verbose"], cwd)
        assert result.exit_code == 0
        assert "up to date" in result.output


# =====================================================================
# Exit code 1 -- drift detected
# =====================================================================


class TestCheckDriftDetected:
    def test_content_drift_single_file(self, runner, project_with_instruction):
        """Content drift in one file: exit 1."""
        cwd = project_with_instruction
        _invoke(runner, ["--local-only"], cwd)

        # Tamper with the generated file.
        ci_path = cwd / ".github" / "copilot-instructions.md"
        if ci_path.exists():
            ci_path.write_text("tampered content", encoding="utf-8")

        result = _invoke(runner, ["--check"], cwd)
        assert result.exit_code == 1

    def test_stale_agents_md(self, runner, project_dir):
        """Stale file (on disk, no primitives) triggers stale report."""
        cwd = project_dir
        # Write an AGENTS.md with no primitives to generate it.
        (cwd / "AGENTS.md").write_text("# Stale\n", encoding="utf-8")

        result = _invoke(runner, ["--check"], cwd)
        assert result.exit_code == 1
        assert "Stale files with no matching primitives:" in result.output
        assert "AGENTS.md" in result.output
        assert "apm compile --clean" in result.output

    def test_stale_remediation_is_clean(self, runner, project_dir):
        """When only stale files exist, remediation says --clean."""
        cwd = project_dir
        (cwd / "AGENTS.md").write_text("stale", encoding="utf-8")

        result = _invoke(runner, ["--check"], cwd)
        assert result.exit_code == 1
        assert "apm compile --clean" in result.output

    def test_content_drift_remediation_is_compile(
        self, runner, project_with_instruction
    ):
        """When only content drift exists, remediation is plain compile."""
        cwd = project_with_instruction
        _invoke(runner, ["--local-only"], cwd)

        ci_path = cwd / ".github" / "copilot-instructions.md"
        if ci_path.exists():
            ci_path.write_text("tampered", encoding="utf-8")

        result = _invoke(runner, ["--check"], cwd)
        assert result.exit_code == 1
        # Should have "apm compile" without "--clean" in the remediation.
        lines = result.output.splitlines()
        remediation_lines = [
            ln for ln in lines if ln.strip().startswith("apm compile")
        ]
        assert any("--clean" not in ln for ln in remediation_lines)

    def test_drift_header_pluralisation_singular(self, runner, project_dir):
        """Header says 'file' for 1."""
        cwd = project_dir
        (cwd / "AGENTS.md").write_text("stale", encoding="utf-8")

        result = _invoke(runner, ["--check"], cwd)
        assert "1 generated file." in result.output

    def test_verbose_drift_shows_diff_markers(
        self, runner, project_with_instruction
    ):
        """--verbose with content drift shows unified diff markers."""
        cwd = project_with_instruction
        _invoke(runner, ["--local-only"], cwd)

        ci_path = cwd / ".github" / "copilot-instructions.md"
        if ci_path.exists():
            ci_path.write_text("tampered\n", encoding="utf-8")

        result = _invoke(runner, ["--check", "--verbose"], cwd)
        assert result.exit_code == 1
        # Unified diff markers should appear.
        assert "---" in result.output or "+++" in result.output

    def test_check_failed_hint(self, runner, project_dir):
        """Drift report ends with --check failed hint."""
        cwd = project_dir
        (cwd / "AGENTS.md").write_text("stale", encoding="utf-8")

        result = _invoke(runner, ["--check"], cwd)
        assert result.exit_code == 1
        assert "--check failed" in result.output


# =====================================================================
# Exit code 2 -- unrecoverable error
# =====================================================================


class TestCheckUnrecoverableError:
    def test_no_apm_yml_exits_two(self, runner):
        """Missing apm.yml should exit 2 in --check mode."""
        tmp = tempfile.mkdtemp()
        try:
            result = _invoke(runner, ["--check"], tmp)
            assert result.exit_code == 2
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


# =====================================================================
# Flag incompatibility
# =====================================================================


class TestCheckFlagIncompatibility:
    def test_check_with_validate(self, runner, project_dir):
        result = _invoke(runner, ["--check", "--validate"], project_dir)
        assert result.exit_code == 2

    def test_check_with_watch(self, runner, project_dir):
        result = _invoke(runner, ["--check", "--watch"], project_dir)
        assert result.exit_code == 2

    def test_check_with_dry_run(self, runner, project_dir):
        result = _invoke(runner, ["--check", "--dry-run"], project_dir)
        assert result.exit_code == 2

    def test_check_with_single_agents(self, runner, project_dir):
        result = _invoke(runner, ["--check", "--single-agents"], project_dir)
        assert result.exit_code == 2

    def test_check_with_clean(self, runner, project_dir):
        result = _invoke(runner, ["--check", "--clean"], project_dir)
        assert result.exit_code == 2


# =====================================================================
# Implies --local-only
# =====================================================================


class TestCheckImpliesLocalOnly:
    def test_check_ignores_dependencies(
        self, runner, project_with_scoped_instruction
    ):
        """--check should behave identically to --check --local-only."""
        cwd = project_with_scoped_instruction

        # Compile first with local-only.
        _invoke(runner, ["--local-only"], cwd)

        # Check should pass (no drift) since we compiled local-only.
        result = _invoke(runner, ["--check"], cwd)
        assert result.exit_code == 0

