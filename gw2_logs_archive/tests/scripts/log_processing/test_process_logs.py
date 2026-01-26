# %%
if __name__ == "__main__":
    from scripts.utilities import django_setup

    django_setup.run()

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from gw2_logs.models import DpsLog
from scripts.log_processing.log_files import LogFile, LogFilesDate
from scripts.log_processing.logfile_processing import process_logs_once


@pytest.fixture
def mock_logfile():
    log = MagicMock(spec=LogFile)
    log.path = "fake/path/log.zevtc"
    log.local_processed = False
    log.upload_processed = False
    return log


@pytest.fixture
def mock_logsdate(mock_logfile):
    logsdate = MagicMock(spec=LogFilesDate)
    logsdate.refresh_and_get_logs.return_value = pd.DataFrame(
        [{"log": mock_logfile, "local_processed": False, "upload_processed": False}]
    )
    return logsdate


@pytest.fixture
def mock_eiparser():
    return MagicMock()


@patch("scripts.log_processing.logfile_processing._parse_or_upload_log")
@patch("scripts.log_processing.logfile_processing.InstanceClearGroupInteraction")
def test_process_logs_once_fully_mocked(
    mock_parse_or_upload,
    mock_icgi_cls,
    mock_logsdate,
    mock_eiparser,
):
    # Create a fake parsed DpsLog
    fake_parsed_log = MagicMock(spec=DpsLog)
    fake_parsed_log.encounter.instance.instance_group.name = "raid"

    # Mock _parse_or_upload_log to always return this fake log
    mock_parse_or_upload.return_value = fake_parsed_log

    # Mock the InstanceClearGroupInteraction
    icgi_instance = MagicMock()
    icgi_instance.iclear_group.success = True
    icgi_instance.iclear_group.type = "raid"
    mock_icgi_cls.create_from_date.return_value = icgi_instance

    # ---- LOCAL ----
    processed_local = process_logs_once(
        processing_type="local",
        log_files_date_cls=mock_logsdate,
        ei_parser=mock_eiparser,
        y=2026,
        m=1,
        d=22,
    )
    assert processed_local is True

    # ---- UPLOAD ----
    processed_upload = process_logs_once(
        processing_type="upload",
        log_files_date_cls=mock_logsdate,
        ei_parser=mock_eiparser,
        y=2026,
        m=1,
        d=22,
    )
    assert processed_upload is True

    # Ensure our mock was called for every lo


if __name__ == "__main__":
    pytest.main([__file__])
