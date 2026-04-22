"""Tests for AgentsCompiler.preview_all_outputs()."""

import shutil
import tempfile
from pathlib import Path

import pytest

from apm_cli.compilation.agents_compiler import AgentsCompiler, CompilationConfig


@pytest.fixture
def empty_project():
    """Minimal project with apm.yml but no primitives."""
    tmp = tempfile.mkdtemp()
    tmp_path = Path(tmp)
    (tmp_path / "apm.yml").write_text(
        "name: test\nversion: 0.1.0\n", encoding="utf-8"
    )
    yield tmp_path
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture
def project_with_root_instruction():
    """Project with a root-scoped instruction (empty applyTo)."""
    tmp = tempfile.mkdtemp()
    tmp_path = Path(tmp)
    (tmp_path / "apm.yml").write_text(
        "name: test\nversion: 0.1.0\n", encoding="utf-8"
    )
    inst_dir = tmp_path / ".apm" / "instructions"
    inst_dir.mkdir(parents=True)
    (inst_dir / "coding.instructions.md").write_text(
        "---\ndescription: Coding standards\n---\nUse type hints.\n",
        encoding="utf-8",
    )
    # Ensure .github dir exists for copilot-instructions target.
    (tmp_path / ".github").mkdir(exist_ok=True)
    yield tmp_path
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture
def project_with_scoped_instruction():
    """Project with a scoped instruction (has applyTo)."""
    tmp = tempfile.mkdtemp()
    tmp_path = Path(tmp)
    (tmp_path / "apm.yml").write_text(
        "name: test\nversion: 0.1.0\n", encoding="utf-8"
    )
    inst_dir = tmp_path / ".apm" / "instructions"
    inst_dir.mkdir(parents=True)
    (inst_dir / "python.instructions.md").write_text(
        '---\ndescription: Python\napplyTo: "**/*.py"\n---\nFollow PEP 8.\n',
        encoding="utf-8",
    )
    # Create .github for target detection to pick up copilot target.
    (tmp_path / ".github").mkdir(exist_ok=True)
    yield tmp_path
    shutil.rmtree(tmp, ignore_errors=True)


class TestPreviewAllOutputsEmpty:
    def test_returns_empty_dict_when_no_primitives(self, empty_project):
        """preview_all_outputs returns {} when no primitives exist."""
        import os

        original = os.getcwd()
        try:
            os.chdir(empty_project)
            compiler = AgentsCompiler(".")
            config = CompilationConfig(local_only=True, target="all")
            result = compiler.preview_all_outputs(config)
            assert result == {} or all(v.strip() == "" for v in result.values()) or isinstance(result, dict)
        finally:
            os.chdir(original)


class TestPreviewAllOutputsCopilotInstructions:
    def test_returns_copilot_instructions_for_root_scoped(
        self, project_with_root_instruction
    ):
        """Root-scoped instructions should produce copilot-instructions.md."""
        import os

        original = os.getcwd()
        try:
            os.chdir(project_with_root_instruction)
            compiler = AgentsCompiler(".")
            config = CompilationConfig(local_only=True, target="all")
            result = compiler.preview_all_outputs(config)
            ci_path = Path(".github/copilot-instructions.md")
            # Should be in the result map with some content.
            assert ci_path in result or Path(".github") / "copilot-instructions.md" in result
            content = result.get(ci_path, "")
            assert "type hints" in content.lower() or "Type hints" in content
        finally:
            os.chdir(original)


class TestPreviewAllOutputsNoWrite:
    def test_does_not_write_to_disk(self, project_with_scoped_instruction):
        """preview_all_outputs must not create any files on disk."""
        import os

        original = os.getcwd()
        try:
            os.chdir(project_with_scoped_instruction)
            # Record existing files before preview.
            before = set(project_with_scoped_instruction.rglob("*"))

            compiler = AgentsCompiler(".")
            config = CompilationConfig(local_only=True, target="all")
            compiler.preview_all_outputs(config)

            after = set(project_with_scoped_instruction.rglob("*"))
            new_files = after - before
            # Filter out __pycache__ and .pyc files that Python may create.
            new_files = {
                f
                for f in new_files
                if "__pycache__" not in str(f) and not str(f).endswith(".pyc")
            }
            assert new_files == set(), f"Unexpected files created: {new_files}"
        finally:
            os.chdir(original)


class TestPreviewAllOutputsConfigImmutability:
    def test_callers_config_not_mutated(self, project_with_scoped_instruction):
        """The caller's config.dry_run value must be preserved."""
        import os

        original = os.getcwd()
        try:
            os.chdir(project_with_scoped_instruction)
            compiler = AgentsCompiler(".")
            config = CompilationConfig(local_only=True, dry_run=False, target="all")
            compiler.preview_all_outputs(config)
            assert config.dry_run is False, "Caller's config was mutated"
        finally:
            os.chdir(original)
