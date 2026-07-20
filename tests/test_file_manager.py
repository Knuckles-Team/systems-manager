from pathlib import Path

import pytest

from systems_manager.systems_manager import detect_and_create_manager


@pytest.fixture
def file_manager(temp_home, monkeypatch):
    """Return a manager confined to an explicitly selected test root."""
    temp_home.chmod(0o700)
    monkeypatch.setenv("SYSTEMS_MANAGER_FILESYSTEM_ROOT", str(temp_home))
    return detect_and_create_manager(silent=True).fs_manager


@pytest.mark.usefixtures("mock_linux_platform")
def test_file_system_manager_list_files(file_manager, temp_home):
    assert file_manager.list_files("missing") == {
        "success": False,
        "error": "Operation failed",
    }

    directory = temp_home / "dir1"
    nested = directory / "dir2"
    nested.mkdir(parents=True)
    (directory / "file1.txt").write_text("hello", encoding="utf-8")
    (nested / "file2.txt").write_text("world", encoding="utf-8")

    shallow = file_manager.list_files("dir1")
    assert shallow["success"] is True
    assert {item["name"] for item in shallow["items"]} == {"dir2", "file1.txt"}
    assert str(temp_home) not in repr(shallow)

    recursive = file_manager.list_files("dir1", recursive=True, depth=2)
    assert recursive["success"] is True
    assert {item["path"] for item in recursive["items"]} == {
        "dir1/dir2",
        "dir1/file1.txt",
        "dir1/dir2/file2.txt",
    }
    assert str(temp_home) not in repr(recursive)


@pytest.mark.usefixtures("mock_linux_platform")
def test_file_system_manager_search_files(file_manager, temp_home):
    directory = temp_home / "search"
    directory.mkdir()
    (directory / "matching_file.py").write_text("print('test')", encoding="utf-8")
    (directory / "other.txt").write_text("hello", encoding="utf-8")

    result = file_manager.search_files("search", "matching")
    assert result["success"] is True
    assert result["matches"] == ["search/matching_file.py"]
    assert str(temp_home) not in repr(result)
    assert file_manager.search_files("../outside", "matching")["error"] == (
        "Operation failed"
    )


@pytest.mark.usefixtures("mock_linux_platform")
def test_file_system_manager_grep_files(file_manager, temp_home):
    directory = temp_home / "grep"
    directory.mkdir()
    (directory / "matched.txt").write_text(
        "first line\nmatched content\n", encoding="utf-8"
    )
    (directory / "other.txt").write_text("nothing", encoding="utf-8")

    result = file_manager.grep_files("grep", "matched", recursive=True)
    assert result["success"] is True
    assert "grep/matched.txt:2:matched content" in result["matches"]
    assert str(temp_home) not in repr(result)
    assert file_manager.grep_files("grep", "bad\npattern")["error"] == (
        "Operation failed"
    )


@pytest.mark.usefixtures("mock_linux_platform")
def test_file_system_manager_manage_file(file_manager, temp_home):
    created = file_manager.manage_file("create", "documents/test.txt", "content")
    assert created["success"] is True
    assert str(temp_home) not in repr(created)
    assert (temp_home / "documents" / "test.txt").stat().st_mode & 0o777 == 0o600

    assert file_manager.manage_file("read", "documents/test.txt") == {
        "success": True,
        "content": "content",
    }
    assert (
        file_manager.manage_file("update", "documents/test.txt", "updated")["success"]
        is True
    )
    assert (temp_home / "documents" / "test.txt").read_text(
        encoding="utf-8"
    ) == "updated"
    assert file_manager.manage_file("delete", "documents/test.txt")["success"] is True
    assert file_manager.manage_file("delete", "documents/test.txt") == {
        "success": False,
        "error": "Managed file not found",
    }
    assert file_manager.manage_file("unknown", "documents/test.txt") == {
        "success": False,
        "error": "Unknown action: unknown",
    }
    assert file_manager.manage_file(
        "read", str(Path(temp_home).parent / "outside")
    ) == {
        "success": False,
        "error": "Operation failed",
    }
