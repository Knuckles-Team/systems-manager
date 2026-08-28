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


def test_write_managed_file_rejects_raced_symlink(tmp_path, monkeypatch):
    """BUG-CX-082: `_write_managed_file` re-resolves the target after
    creating parent directories (the comment says "to catch a raced
    symlink") but never actually checked the re-resolved result -- unlike
    the near-identical `atomic_write_managed_text`. Simulate the race with
    a mock (a real concurrent symlink swap can't be produced deterministically
    in-process): the re-resolve call returns a stand-in for "the path a
    concurrent attacker just replaced with a symlink". `_write_managed_file`
    must refuse before ever reaching a write primitive."""
    import systems_manager.systems_manager as sm

    target = tmp_path / "target.txt"

    class _RacedSymlink:
        """Stands in for what `resolve_managed_path` would return if the
        path had just been swapped for a symlink."""

        def is_symlink(self) -> bool:
            return True

    monkeypatch.setattr(sm, "resolve_managed_path", lambda *a, **k: _RacedSymlink())

    def _must_not_be_called(*_a, **_k):
        raise AssertionError(
            "a raced symlink must never reach a write primitive unchecked"
        )

    monkeypatch.setattr(sm, "_create_exclusive_managed_file", _must_not_be_called)
    monkeypatch.setattr(sm, "_replace_managed_file", _must_not_be_called)

    with pytest.raises(PermissionError, match="Symbolic-link"):
        sm.FileSystemManager._write_managed_file("update", target, "malicious")


def test_replace_managed_file_refuses_an_actual_symlink(tmp_path):
    """`_replace_managed_file` -- the "update" write primitive -- already
    re-checks `target.is_symlink()` immediately before `os.replace()`,
    independent of `_write_managed_file`'s own (previously missing) guard.
    This is why the BUG-CX-082 gap was hardening rather than an
    independently-exploitable write-through-symlink hole for "update": a
    real symlink at the target is refused here even with no caller-side
    check at all, and POSIX `rename()` never dereferences the destination
    name in the first place, so even a same-instant swap can only clobber
    the symlink, never write through it."""
    from systems_manager.systems_manager import _replace_managed_file

    victim = tmp_path / "victim.txt"
    victim.write_text("do-not-touch", encoding="utf-8")
    target = tmp_path / "target.txt"
    target.symlink_to(victim)

    with pytest.raises(PermissionError, match="Symbolic-link"):
        _replace_managed_file(target, "attacker payload")

    assert victim.read_text(encoding="utf-8") == "do-not-touch"


def test_create_exclusive_managed_file_refuses_existing_symlink(tmp_path):
    """The "create" action's write primitive is O_CREAT|O_EXCL|O_NOFOLLOW --
    already refuses a symlink (or anything else) sitting at the target,
    independent of `_write_managed_file`'s own guard. Confirms the other
    half of the BUG-CX-082 "not independently exploitable" finding."""
    from systems_manager.systems_manager import _create_exclusive_managed_file

    victim = tmp_path / "victim.txt"
    victim.write_text("do-not-touch", encoding="utf-8")
    target = tmp_path / "target.txt"
    target.symlink_to(victim)

    with pytest.raises(OSError):
        _create_exclusive_managed_file(target, "attacker payload")

    assert victim.read_text(encoding="utf-8") == "do-not-touch"
