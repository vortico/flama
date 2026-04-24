import pathlib
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest
from click.testing import CliRunner

from flama.cli.commands.get import command


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def mock_download():
    with patch("flama.cli.commands.get._download_model", new_callable=AsyncMock) as m:
        m.return_value = "text-generation"
        yield m


@pytest.fixture
def mock_package():
    with patch("flama.cli.commands.get._package_model") as m:
        yield m


class TestCaseGetCommand:
    def test_get_huggingface(self, runner, mock_download, mock_package):
        result = runner.invoke(command, ["my-org/my-model", "--source", "huggingface"])

        assert result.exit_code == 0, result.output
        assert "my-org_my-model.flm" in result.output

        assert mock_download.await_count == 1
        dl_args = mock_download.call_args
        assert dl_args.args[0] == "my-org/my-model"
        assert isinstance(dl_args.args[1], pathlib.Path)

        assert mock_package.call_count == 1
        pkg_kwargs = mock_package.call_args.kwargs
        assert pkg_kwargs["task"] == "text-generation"
        assert pkg_kwargs["model_name"] == "my-org/my-model"
        assert pkg_kwargs["engine"] == "transformers"

    def test_get_huggingface_with_task(self, runner, mock_download, mock_package):
        result = runner.invoke(
            command,
            ["my-org/my-model", "--source", "huggingface", "--task", "summarization"],
        )

        assert result.exit_code == 0, result.output
        assert mock_package.call_args.kwargs["task"] == "summarization"

    def test_get_huggingface_with_output(self, runner, mock_download, mock_package, tmp_path):
        output = str(tmp_path / "custom.flm")
        result = runner.invoke(
            command,
            ["my-org/my-model", "--source", "huggingface", "-o", output],
        )

        assert result.exit_code == 0, result.output
        assert mock_package.call_args.args[1] == pathlib.Path(output)

    def test_get_huggingface_with_engine_vllm(self, runner, mock_download, mock_package):
        result = runner.invoke(
            command,
            ["my-org/my-model", "--source", "huggingface", "--engine", "vllm"],
        )

        assert result.exit_code == 0, result.output
        assert mock_package.call_args.kwargs["engine"] == "vllm"

    def test_get_task_auto_detected_from_download(self, runner, mock_download, mock_package):
        mock_download.return_value = "image-classification"

        result = runner.invoke(command, ["my-org/my-model", "--source", "huggingface"])

        assert result.exit_code == 0, result.output
        assert mock_package.call_args.kwargs["task"] == "image-classification"

    def test_get_missing_source(self, runner):
        result = runner.invoke(command, ["my-org/my-model"])
        assert result.exit_code != 0

    def test_get_invalid_source(self, runner):
        result = runner.invoke(command, ["my-org/my-model", "--source", "unknown"])
        assert result.exit_code != 0


class TestCaseDownloadModel:
    @pytest.mark.anyio
    async def test_download_model(self, tmp_path):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "pipeline_tag": "text-generation",
            "siblings": [{"rfilename": "config.json"}, {"rfilename": "model.safetensors"}],
            "usedStorage": 1024,
        }
        mock_response.raise_for_status = MagicMock()

        chunks = [b"fake-content"]

        mock_stream = AsyncMock()
        mock_stream.__aenter__ = AsyncMock(return_value=mock_stream)
        mock_stream.__aexit__ = AsyncMock(return_value=False)
        mock_stream.raise_for_status = MagicMock()

        async def aiter_bytes(chunk_size=None):
            for c in chunks:
                yield c

        mock_stream.aiter_bytes = aiter_bytes

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.stream = MagicMock(return_value=mock_stream)

        with patch("flama.cli.commands.get._BaseClient", return_value=mock_client):
            from flama.cli.commands.get import _download_model

            pipeline_tag = await _download_model("my-org/my-model", tmp_path)

        assert pipeline_tag == "text-generation"
        assert mock_client.get.await_args_list == [call("/api/models/my-org/my-model")]
        assert mock_client.stream.call_count == 2
        assert (tmp_path / "config.json").exists()
        assert (tmp_path / "model.safetensors").exists()


class TestCasePackageModel:
    def test_package_model(self, tmp_path):
        local_dir = tmp_path / "model"
        local_dir.mkdir()
        (local_dir / "config.json").write_text("{}")

        output_path = tmp_path / "output.flm"

        mock_serializer = MagicMock()
        mock_serializer.dump.return_value = b"fake-tar-bytes"

        with (
            patch("flama.cli.commands.get.ModelSerializer") as mock_ms,
            patch("flama.cli.commands.get.Compression") as mock_compression_cls,
            patch("flama.cli.commands.get.ModelArtifact") as mock_artifact_cls,
            patch("flama.cli.commands.get.encode_json", return_value=b'{"meta": "data"}'),
            patch("flama.cli.commands.get.console"),
        ):
            mock_ms.from_lib.return_value = mock_serializer

            mock_compression = MagicMock()
            mock_compression.compress.side_effect = lambda b: b
            mock_compression.format = 4
            mock_compression_cls.return_value = mock_compression

            mock_artifact = MagicMock()
            mock_artifact.meta.to_dict.return_value = {"meta": "data"}
            mock_artifact_cls.from_model.return_value = mock_artifact

            from flama.cli.commands.get import _package_model

            _package_model(
                local_dir,
                output_path,
                task="text-generation",
                model_name="my-org/my-model",
                engine="transformers",
            )

        assert output_path.exists()
        assert mock_ms.from_lib.call_args_list == [call("transformers")]
        assert mock_serializer.dump.call_args_list == [call(local_dir)]
        assert mock_compression.compress.call_count == 2

        content = output_path.read_bytes()
        assert len(content) > 0
