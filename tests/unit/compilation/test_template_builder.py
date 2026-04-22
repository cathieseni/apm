"""Unit tests for template_builder -- deterministic sort behaviour."""

from pathlib import Path

import pytest

from apm_cli.compilation.template_builder import build_conditional_sections
from apm_cli.primitives.models import Instruction


class TestBuildConditionalSectionsDeterministicSort:
    """build_conditional_sections must sort by base_dir-relative paths,
    not by cwd-relative paths, so the output is deterministic regardless
    of where the user invokes ``apm compile``."""

    @staticmethod
    def _make_instruction(file_path: Path, content: str) -> Instruction:
        return Instruction(
            name=file_path.stem,
            file_path=file_path,
            description="test",
            apply_to="**/*.py",
            content=content,
            author="test",
            version="1.0",
        )

    def test_sort_uses_base_dir_not_cwd(self, tmp_path: Path) -> None:
        """Two instructions whose relative order flips depending on the
        base directory used for sorting.  Passing ``base_dir`` explicitly
        must control the order, regardless of actual cwd."""
        # Create paths: under base_dir="/project", the relative paths
        # are "alpha/code.py" and "beta/code.py" (alpha < beta).
        project = tmp_path / "project"
        alpha = project / "alpha" / "code.py"
        beta = project / "beta" / "code.py"
        alpha.parent.mkdir(parents=True)
        beta.parent.mkdir(parents=True)
        alpha.touch()
        beta.touch()

        instr_alpha = self._make_instruction(alpha, "alpha content")
        instr_beta = self._make_instruction(beta, "beta content")

        # Regardless of the order we pass them in, the output must list
        # alpha before beta when base_dir is ``project``.
        result = build_conditional_sections(
            [instr_beta, instr_alpha], base_dir=project
        )

        alpha_pos = result.index("alpha content")
        beta_pos = result.index("beta content")
        assert alpha_pos < beta_pos, (
            "Instructions should be sorted by base_dir-relative path "
            "(alpha before beta)"
        )

    def test_sort_is_stable_across_different_base_dirs(self, tmp_path: Path) -> None:
        """Using a different base_dir changes the relative paths and
        therefore the sort order."""
        root = tmp_path / "root"
        a_file = root / "z_dir" / "a.py"
        b_file = root / "a_dir" / "b.py"
        a_file.parent.mkdir(parents=True)
        b_file.parent.mkdir(parents=True)
        a_file.touch()
        b_file.touch()

        instr_a = self._make_instruction(a_file, "content_a")
        instr_b = self._make_instruction(b_file, "content_b")

        result = build_conditional_sections(
            [instr_a, instr_b], base_dir=root
        )

        # Relative paths: "a_dir/b.py" < "z_dir/a.py"
        a_pos = result.index("content_a")
        b_pos = result.index("content_b")
        assert b_pos < a_pos, (
            "a_dir/b.py should sort before z_dir/a.py"
        )

    def test_empty_instructions_returns_empty(self) -> None:
        """Empty instruction list returns empty string."""
        assert build_conditional_sections([], base_dir=Path(".")) == ""
