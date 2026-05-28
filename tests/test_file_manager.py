import os
from unittest.mock import patch

import pytest

from systems_manager.systems_manager import (
    detect_and_create_manager,
)


@pytest.mark.usefixtures("mock_linux_platform")
def test_file_system_manager_list_files(temp_home):
    """Test list_files method in FileSystemManager under Linux."""
    manager = detect_and_create_manager(silent=True)
    fs = manager.fs_manager

    # Test path not found
    res = fs.list_files(path="non_existent_dir")
    assert res.success is False
    assert res.error is not None and "Path not found" in res.error

    # Create test directory structure
    dir1 = temp_home / "dir1"
    dir1.mkdir()
    file1 = dir1 / "file1.txt"
    file1.write_text("hello")

    dir2 = dir1 / "dir2"
    dir2.mkdir()
    file2 = dir2 / "file2.txt"
    file2.write_text("world")

    # Non-recursive scan
    res_non_rec = fs.list_files(path=str(dir1), recursive=False)
    assert res_non_rec.success is True
    assert res_non_rec.get("total") == 2
    items = res_non_rec.get("items")
    assert items is not None
    names = {item["name"] for item in items}
    assert "file1.txt" in names
    assert "dir2" in names

    # Recursive walk up to depth 2 (excluding dir2's files if depth exceeded, but here depth=2 includes everything)
    res_rec = fs.list_files(path=str(dir1), recursive=True, depth=2)
    assert res_rec.success is True
    # Should include: dir2, file1.txt, file2.txt (depth of file2.txt is 1 relative to dir1, which is < depth=2)
    # Let's verify we get items from subdirectories
    items_rec = res_rec.get("items")
    assert items_rec is not None
    item_paths = {item["path"] for item in items_rec}
    assert str(file2) in item_paths

    # Test depth constraint (depth=1 should not include file2.txt since root is dir1/dir2, depth from root is 1)
    res_depth_1 = fs.list_files(path=str(dir1), recursive=True, depth=1)
    assert res_depth_1.success is True
    items_depth_1 = res_depth_1.get("items")
    assert items_depth_1 is not None
    item_paths_depth_1 = {item["path"] for item in items_depth_1}
    assert str(file2) not in item_paths_depth_1

    # Test list_files exception handling
    with patch("os.scandir", side_effect=OSError("Read error")):
        res_err = fs.list_files(path=str(dir1), recursive=False)
        assert res_err.success is False
        assert res_err.error is not None and "Read error" in res_err.error


@pytest.mark.usefixtures("mock_linux_platform")
def test_file_system_manager_search_files(temp_home):
    """Test search_files method in FileSystemManager."""
    manager = detect_and_create_manager(silent=True)
    fs = manager.fs_manager

    # Create dummy files
    dir1 = temp_home / "search_dir"
    dir1.mkdir()
    (dir1 / "matching_file.py").write_text("print('test')")
    (dir1 / "other.txt").write_text("hello")

    res = fs.search_files(path=str(dir1), pattern="matching")
    assert res.success is True
    assert res.get("total") == 1
    matches = res.get("matches")
    assert matches is not None
    assert "matching_file.py" in matches[0]

    # Test error handling
    with patch("os.walk", side_effect=Exception("Walk failed")):
        res_err = fs.search_files(path=str(dir1), pattern="test")
        assert res_err.success is False
        assert res_err.error is not None and "Walk failed" in res_err.error


@pytest.mark.usefixtures("mock_linux_platform")
def test_file_system_manager_grep_files():
    """Test grep_files method in FileSystemManager."""
    manager = detect_and_create_manager(silent=True)
    fs = manager.fs_manager

    with patch.object(manager, "run_command") as mock_run:
        mock_run.return_value = {
            "success": True,
            "stdout": "file.txt:1:matched content",
            "stderr": "",
        }
        res = fs.grep_files(path=".", pattern="matched", recursive=True)
        assert res.success is True
        matches = res.get("matches")
        assert matches is not None
        assert "matched content" in matches
        mock_run.assert_called_with(["grep", "-rn", "matched", "."])

    # Test non-recursive grep
    with patch.object(manager, "run_command") as mock_run:
        mock_run.return_value = {
            "success": True,
            "stdout": "file.txt:1:matched content",
            "stderr": "",
        }
        res = fs.grep_files(path="file.txt", pattern="matched", recursive=False)
        assert res.success is True
        mock_run.assert_called_with(["grep", "-n", "matched", "file.txt"])

    # Test exception handling
    with patch.object(manager, "run_command", side_effect=Exception("Grep failed")):
        res_err = fs.grep_files(path=".", pattern="matched")
        assert res_err.success is False
        assert res_err.error is not None and "Grep failed" in res_err.error


@pytest.mark.usefixtures("mock_linux_platform")
def test_file_system_manager_manage_file(temp_home):
    """Test manage_file method in FileSystemManager."""
    manager = detect_and_create_manager(silent=True)
    fs = manager.fs_manager

    file_path = str(temp_home / "test.txt")

    # Create file
    res = fs.manage_file(action="create", path=file_path, content="test content")
    assert res.success is True
    assert os.path.exists(file_path)

    # Read file
    res_read = fs.manage_file(action="read", path=file_path)
    assert res_read.success is True
    assert res_read.get("content") == "test content"

    # Read non-existent file
    res_read_fail = fs.manage_file(action="read", path="missing.txt")
    assert res_read_fail.success is False
    assert res_read_fail.error is not None and "File not found" in res_read_fail.error

    # Update file
    res_up = fs.manage_file(action="update", path=file_path, content="updated content")
    assert res_up.success is True
    with open(file_path) as f:
        assert f.read() == "updated content"

    # Delete file
    res_del = fs.manage_file(action="delete", path=file_path)
    assert res_del.success is True
    assert not os.path.exists(file_path)

    # Delete non-existent file
    res_del_fail = fs.manage_file(action="delete", path=file_path)
    assert res_del_fail.success is False
    assert res_del_fail.error is not None and "File not found" in res_del_fail.error

    # Unknown action
    res_unknown = fs.manage_file(action="unknown", path=file_path)
    assert res_unknown.success is False
    assert res_unknown.error is not None and "Unknown action" in res_unknown.error

    # Exception handling
    with patch("builtins.open", side_effect=PermissionError("Permission denied")):
        res_err = fs.manage_file(action="create", path=file_path, content="test")
        assert res_err.success is False
        assert res_err.error is not None and "Permission denied" in res_err.error


@pytest.mark.usefixtures("mock_linux_platform")
def test_shell_profile_manager(temp_home):
    """Test ShellProfileManager on Linux platform."""
    manager = detect_and_create_manager(silent=True)
    sh = manager.shell_manager

    # Test profile paths
    assert sh.get_profile_path("bash") == os.path.join(str(temp_home), ".bashrc")
    assert sh.get_profile_path("zsh") == os.path.join(str(temp_home), ".zshrc")
    assert sh.get_profile_path("fish") == os.path.join(
        str(temp_home), ".config/fish/config.fish"
    )
    assert sh.get_profile_path("unknown") == os.path.join(str(temp_home), ".profile")

    # Test add_alias (new file creation)
    res = sh.add_alias(name="ll", command="ls -la", shell="bash")
    assert res.success is True
    profile = sh.get_profile_path("bash")
    assert os.path.exists(profile)
    with open(profile) as f:
        assert 'alias ll="ls -la"' in f.read()

    # Test add_alias (already exists)
    res_dup = sh.add_alias(name="ll", command="ls -la", shell="bash")
    assert res_dup.success is True
    assert res_dup.message is not None and "already exists" in res_dup.message

    # Test add_alias exception handling
    with patch("builtins.open", side_effect=Exception("Disk full")):
        res_err = sh.add_alias(name="la", command="ls -a", shell="bash")
        assert res_err.success is False
        assert res_err.error is not None and "Disk full" in res_err.error


@pytest.mark.usefixtures("mock_windows_platform")
def test_shell_profile_manager_windows(temp_home):
    """Test ShellProfileManager on Windows platform."""
    manager = detect_and_create_manager(silent=True)
    sh = manager.shell_manager

    profile = sh.get_profile_path("powershell")
    assert "WindowsPowerShell" in profile

    # Add PowerShell alias (creates a function instead of alias keyword)
    res = sh.add_alias(name="ll", command="ls -la", shell="powershell")
    assert res.success is True
    assert os.path.exists(profile)
    with open(profile) as f:
        assert "function ll { ls -la }" in f.read()
