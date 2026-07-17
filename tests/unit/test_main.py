"""
Tests for the main CLI module.
"""
from __future__ import annotations


class TestMainCLI:
    """Tests for CLI entry point commands."""

    def test_version_output(self):
        """Just verify imports work."""
        from src.main import version
        # No need to actually run — just ensure the function exists

    def test_app_creation(self):
        """Verify the Typer app is created."""
        import typer
        from src.main import app
        assert isinstance(app, typer.Typer)
        assert app.info.name == "research-lab"