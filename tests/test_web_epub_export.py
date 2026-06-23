"""Tests for the secondary EPUB export from completed lip-sync jobs."""

from types import SimpleNamespace
from unittest.mock import Mock
import sys
import uuid

from screencastgen.pipelines.types import PipelineRunResult
from web.backend.models import JobStatus, PipelineType, UploadedFile
from web.backend.tasks import pipelines


class _Session:
    def __init__(self, job, uploaded):
        self.job = job
        self.uploaded = uploaded
        self.commits = 0

    def get(self, model, _record_id):
        return self.uploaded if model is UploadedFile else self.job

    def commit(self):
        self.commits += 1

    def close(self):
        pass


def test_epub_export_reuses_job_and_records_output(monkeypatch, tmp_path):
    job_id = uuid.uuid4()
    upload_id = uuid.uuid4()
    job = SimpleNamespace(
        id=job_id,
        pipeline_type=PipelineType.lipsync,
        status=JobStatus.completed,
        uploaded_file_id=upload_id,
        config_json={},
    )
    uploaded = SimpleNamespace(stored_path="uploads/document.pdf")
    session = _Session(job, uploaded)
    output = tmp_path / "document_lipsync.epub"
    output.write_bytes(b"epub")
    request = SimpleNamespace(format="epub")
    upload_output = Mock()

    monkeypatch.setitem(
        sys.modules,
        "web.backend.database",
        SimpleNamespace(get_sync_session=lambda: session),
    )
    monkeypatch.setattr(pipelines, "get_upload_abs_path", lambda _path: "/tmp/document.pdf")
    monkeypatch.setattr(pipelines, "get_output_dir", lambda _job_id: str(tmp_path))
    monkeypatch.setattr(pipelines, "_build_lipsync_request", lambda *args, **kwargs: request)
    monkeypatch.setattr(
        pipelines,
        "run_lipsync_pipeline",
        lambda _request: PipelineRunResult(
            exit_code=0,
            output_name=output.name,
            output_path=str(output),
        ),
    )
    monkeypatch.setattr(pipelines, "upload_output", upload_output)

    result = pipelines.run_lipsync_epub_export_task.run(str(job_id))

    assert result == {"export_status": "done"}
    assert job.config_json["epub_export_status"] == "done"
    assert job.config_json["epub_export_output"] == output.name
    assert job.config_json["epub_export_error"] is None
    upload_output.assert_called_once_with(job_id, output.name)
