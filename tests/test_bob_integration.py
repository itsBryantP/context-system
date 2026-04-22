"""Tests for Bob Shell integration."""

from pathlib import Path
import pytest
from ctx.integrations.claude_code import install_module, remove_module, _resolve_tools


def test_bob_detection_with_bob_dir(tmp_path):
    """Test Bob Shell project detection via .bob directory."""
    bob_dir = tmp_path / ".bob"
    bob_dir.mkdir()
    
    tools = _resolve_tools(None, tmp_path)
    assert "bob" in tools
    assert "claude" in tools  # Always included


def test_bob_detection_with_bob_md(tmp_path):
    """Test Bob Shell project detection via BOB.md file."""
    (tmp_path / "BOB.md").write_text("# Project Context")
    
    tools = _resolve_tools(None, tmp_path)
    assert "bob" in tools


def test_bob_detection_without_indicators(tmp_path):
    """Test that Bob Shell is not detected without indicators."""
    tools = _resolve_tools(None, tmp_path)
    assert "bob" not in tools
    assert "claude" in tools  # Always included


def test_bob_explicit_tool_selection(tmp_path):
    """Test explicit Bob Shell tool selection."""
    tools = _resolve_tools(["bob"], tmp_path)
    assert "bob" in tools
    assert "claude" not in tools  # Not included when explicit


def test_bob_installation(tmp_path):
    """Test installing a module with Bob Shell files."""
    module_path = Path(__file__).parent / "fixtures" / "bob-test-module"
    
    result = install_module(module_path, tmp_path, tools=["bob"])
    
    # Check BOB.md symlink
    bob_md = tmp_path / "BOB.md"
    assert bob_md.is_symlink()
    assert bob_md.resolve() == (module_path / "BOB.md").resolve()
    
    # Check mode symlink
    mode_link = tmp_path / ".bob" / "modes" / "test-mode.yaml"
    assert mode_link.is_symlink()
    assert mode_link.resolve() == (module_path / "bob" / "modes" / "test-mode.yaml").resolve()
    
    # Check tool symlink
    tool_link = tmp_path / ".bob" / "tools" / "test-tool.yaml"
    assert tool_link.is_symlink()
    assert tool_link.resolve() == (module_path / "bob" / "tools" / "test-tool.yaml").resolve()
    
    # Check server symlink
    server_link = tmp_path / ".bob" / "servers" / "test-server.json"
    assert server_link.is_symlink()
    assert server_link.resolve() == (module_path / "bob" / "servers" / "test-server.json").resolve()
    
    # Check result tracking
    assert "BOB.md" in result.tool_files
    assert ".bob/modes/test-mode.yaml" in result.tool_files
    assert ".bob/tools/test-tool.yaml" in result.tool_files
    assert ".bob/servers/test-server.json" in result.tool_files


def test_bob_removal(tmp_path):
    """Test removing Bob Shell integration."""
    module_path = Path(__file__).parent / "fixtures" / "bob-test-module"
    
    # Install first
    install_module(module_path, tmp_path, tools=["bob"])
    
    # Verify installation
    assert (tmp_path / "BOB.md").exists()
    assert (tmp_path / ".bob" / "modes" / "test-mode.yaml").exists()
    
    # Remove
    result = remove_module(module_path, tmp_path, tools=["bob"])
    
    # Check files are removed
    assert not (tmp_path / "BOB.md").exists()
    assert not (tmp_path / ".bob" / "modes" / "test-mode.yaml").exists()
    assert not (tmp_path / ".bob" / "tools" / "test-tool.yaml").exists()
    assert not (tmp_path / ".bob" / "servers" / "test-server.json").exists()
    
    # Check result tracking
    assert "BOB.md" in result.tool_files_removed
    assert ".bob/modes/test-mode.yaml" in result.tool_files_removed
    assert ".bob/tools/test-tool.yaml" in result.tool_files_removed
    assert ".bob/servers/test-server.json" in result.tool_files_removed


def test_bob_installation_creates_directories(tmp_path):
    """Test that Bob Shell installation creates necessary directories."""
    module_path = Path(__file__).parent / "fixtures" / "bob-test-module"
    
    # Ensure .bob directory doesn't exist
    assert not (tmp_path / ".bob").exists()
    
    install_module(module_path, tmp_path, tools=["bob"])
    
    # Check directories were created
    assert (tmp_path / ".bob").is_dir()
    assert (tmp_path / ".bob" / "modes").is_dir()
    assert (tmp_path / ".bob" / "tools").is_dir()
    assert (tmp_path / ".bob" / "servers").is_dir()


def test_bob_multi_tool_installation(tmp_path):
    """Test installing for both Claude and Bob."""
    module_path = Path(__file__).parent / "fixtures" / "bob-test-module"
    
    result = install_module(module_path, tmp_path, tools=["claude", "bob"])
    
    # Bob files should be installed
    assert (tmp_path / "BOB.md").is_symlink()
    assert (tmp_path / ".bob" / "modes" / "test-mode.yaml").is_symlink()
    
    # Check result includes Bob files
    assert "BOB.md" in result.tool_files
    assert ".bob/modes/test-mode.yaml" in result.tool_files


def test_bob_installation_with_existing_bob_dir(tmp_path):
    """Test installing when .bob directory already exists."""
    # Create existing .bob directory
    bob_dir = tmp_path / ".bob"
    bob_dir.mkdir()
    (bob_dir / "existing.txt").write_text("existing file")
    
    module_path = Path(__file__).parent / "fixtures" / "bob-test-module"
    install_module(module_path, tmp_path, tools=["bob"])
    
    # Existing file should still be there
    assert (bob_dir / "existing.txt").exists()
    
    # New files should be installed
    assert (bob_dir / "modes" / "test-mode.yaml").is_symlink()


def test_bob_removal_preserves_other_files(tmp_path):
    """Test that removal only removes module's files."""
    module_path = Path(__file__).parent / "fixtures" / "bob-test-module"
    
    # Create .bob directory with other files
    bob_dir = tmp_path / ".bob"
    bob_dir.mkdir()
    modes_dir = bob_dir / "modes"
    modes_dir.mkdir()
    (modes_dir / "other-mode.yaml").write_text("other: mode")
    
    # Install module
    install_module(module_path, tmp_path, tools=["bob"])
    
    # Remove module
    remove_module(module_path, tmp_path, tools=["bob"])
    
    # Other files should still exist
    assert (modes_dir / "other-mode.yaml").exists()
    
    # Module files should be removed
    assert not (modes_dir / "test-mode.yaml").exists()


def test_bob_installation_without_bob_files(tmp_path):
    """Test installing a module that has no Bob Shell files."""
    # Use sample-module which doesn't have bob/ directory
    module_path = Path(__file__).parent / "fixtures" / "sample-module"
    
    result = install_module(module_path, tmp_path, tools=["bob"])
    
    # Should not create .bob directory if module has no Bob files
    # (BOB.md might still be symlinked if it exists)
    assert result.module_name == "sample-module"


def test_bob_auto_detection_with_multiple_tools(tmp_path):
    """Test auto-detection with multiple tool indicators."""
    # Create indicators for multiple tools
    (tmp_path / ".bob").mkdir()
    (tmp_path / ".cursor").mkdir()
    (tmp_path / ".github").mkdir()
    
    tools = _resolve_tools(None, tmp_path)
    
    assert "claude" in tools  # Always included
    assert "bob" in tools
    assert "cursor" in tools
    assert "copilot" in tools


def test_bob_symlink_replacement(tmp_path):
    """Test that reinstalling replaces existing symlinks."""
    module_path = Path(__file__).parent / "fixtures" / "bob-test-module"
    
    # Install once
    install_module(module_path, tmp_path, tools=["bob"])
    original_target = (tmp_path / "BOB.md").resolve()
    
    # Install again (should replace symlink)
    install_module(module_path, tmp_path, tools=["bob"])
    new_target = (tmp_path / "BOB.md").resolve()
    
    # Should point to same target
    assert original_target == new_target
    assert (tmp_path / "BOB.md").is_symlink()


def test_bob_removal_with_missing_files(tmp_path):
    """Test removal when some files are already missing."""
    module_path = Path(__file__).parent / "fixtures" / "bob-test-module"
    
    # Install
    install_module(module_path, tmp_path, tools=["bob"])
    
    # Manually remove one file
    (tmp_path / ".bob" / "modes" / "test-mode.yaml").unlink()
    
    # Removal should still work
    result = remove_module(module_path, tmp_path, tools=["bob"])
    
    # Should report removal of files that existed
    assert "BOB.md" in result.tool_files_removed
    assert ".bob/tools/test-tool.yaml" in result.tool_files_removed
