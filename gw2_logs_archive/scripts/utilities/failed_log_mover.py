import logging
import shutil
from pathlib import Path
from typing import Literal

from django.conf import settings
from scripts.log_helpers import today_y_m_d, zfill_y_m_d

logger = logging.getLogger(__name__)


def move_failed_log(log_path: Path, reason: Literal["failed", "forbidden"]) -> None:
    """Move a failing or forbidden log to a unified location.

    - `failed`: moved to <DPS_LOGS_DIR parent>/failed_logs/<YYYYMMDD>/<last-3-path-parts>
    - `forbidden`: moved to <DPS_LOGS_DIR parent>/forbidden_logs/<YYYYMMDD>/<last-3-path-parts>
    """
    if not log_path:
        return

    base = settings.DPS_LOGS_DIR.parent
    y, m, d = today_y_m_d()
    out_path = base.joinpath(f"{reason}_logs", zfill_y_m_d(y, m, d), *Path(log_path).parts[-3:])

    out_path.parent.mkdir(parents=True, exist_ok=True)
    logger.warning("Moved %s log from %s to", reason, log_path)
    logger.warning(out_path)
    shutil.move(src=log_path, dst=out_path)
