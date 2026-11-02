import gc
import io
import os
import pathlib
import stat
from unittest.mock import patch

import pytest

from flama._io import AtomicFile


class TestCaseAtomicFile:
    @pytest.fixture
    def path(self, tmp_path: pathlib.Path) -> pathlib.Path:
        return tmp_path / "out.bin"

    def test_is_binary_file(self, path: pathlib.Path) -> None:
        with AtomicFile(path) as f:
            assert isinstance(f, io.BufferedWriter)
            f.write(b"0000body")
            end = f.tell()
            f.seek(0)
            f.write(b"head")
            f.seek(end)

        assert path.read_bytes() == b"headbody"

    @pytest.mark.parametrize("existing", [pytest.param(False, id="new"), pytest.param(True, id="existing")])
    def test_commit_on_exit(self, path: pathlib.Path, existing: bool) -> None:
        if existing:
            path.write_bytes(b"previous")

        with AtomicFile(path) as f:
            f.write(b"content")
            assert path.exists() is existing

        assert path.read_bytes() == b"content"
        assert [p.name for p in path.parent.iterdir()] == ["out.bin"]

    def test_commit(self, path: pathlib.Path) -> None:
        f = AtomicFile(path)
        f.write(b"content")

        f.commit()
        f.commit()
        f.close()

        assert f.closed
        assert path.read_bytes() == b"content"
        assert [p.name for p in path.parent.iterdir()] == ["out.bin"]

    @pytest.mark.parametrize("existing", [pytest.param(False, id="new"), pytest.param(True, id="existing")])
    def test_discard_on_error(self, path: pathlib.Path, existing: bool) -> None:
        if existing:
            path.write_bytes(b"previous")

        with pytest.raises(RuntimeError, match="boom"), AtomicFile(path) as f:
            f.write(b"partial")
            raise RuntimeError("boom")

        assert path.exists() is existing
        if existing:
            assert path.read_bytes() == b"previous"
        assert [p.name for p in path.parent.iterdir()] == (["out.bin"] if existing else [])

    def test_discard_on_close(self, path: pathlib.Path) -> None:
        f = AtomicFile(path)
        f.write(b"partial")

        f.close()

        assert f.closed
        assert not path.exists()
        assert list(path.parent.iterdir()) == []

    def test_discard_on_garbage_collection(self, path: pathlib.Path) -> None:
        f = AtomicFile(path)
        f.write(b"partial")

        del f
        gc.collect()

        assert not path.exists()
        assert list(path.parent.iterdir()) == []

    def test_discard_when_commit_fails(self, path: pathlib.Path) -> None:
        f = AtomicFile(path)
        f.write(b"content")

        with patch("flama._io.os.replace", side_effect=OSError("cross-device")), pytest.raises(OSError):
            f.commit()

        assert f.closed
        assert not path.exists()
        assert list(path.parent.iterdir()) == []

    @pytest.mark.parametrize(
        ["durable", "expected"],
        [pytest.param(True, ["fsync", "replace"], id="durable"), pytest.param(False, ["replace"], id="not_durable")],
    )
    def test_durable(self, path: pathlib.Path, durable: bool, expected: list[str]) -> None:
        calls: list[str] = []
        replace = os.replace

        def recording_replace(src, dst):
            calls.append("replace")
            replace(src, dst)

        with (
            patch("flama._io.os.fsync", side_effect=lambda fd: calls.append("fsync")),
            patch("flama._io.os.replace", side_effect=recording_replace),
            AtomicFile(path, durable=durable) as f,
        ):
            f.write(b"content")

        assert calls == expected

    def test_keeps_permissions(self, path: pathlib.Path) -> None:
        path.write_bytes(b"previous")
        path.chmod(0o640)

        with AtomicFile(path) as f:
            f.write(b"content")

        assert stat.S_IMODE(path.stat().st_mode) == 0o640

    def test_writes_through_symlink(self, tmp_path: pathlib.Path) -> None:
        real = tmp_path / "real.bin"
        real.write_bytes(b"previous")
        link = tmp_path / "link.bin"
        link.symlink_to(real)

        with AtomicFile(link) as f:
            f.write(b"content")

        assert link.is_symlink()
        assert real.read_bytes() == b"content"
        assert sorted(p.name for p in tmp_path.iterdir()) == ["link.bin", "real.bin"]
