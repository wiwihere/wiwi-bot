# %%

if __name__ == "__main__":
    from scripts.utilities import django_setup

    django_setup.run()


import logging

from django.conf import settings
from scripts.discord_interaction.build_message_progression import send_progression_discord_message
from scripts.encounter_progression.cerus_service import CerusProgressionService
from scripts.encounter_progression.decima_service import DecimaProgressionService
from scripts.log_helpers import (
    create_folder_names,
    today_y_m_d,
    zfill_y_m_d,
)
from scripts.log_processing.ei_parser import EliteInsightsParser
from scripts.log_processing.log_files import LogFilesDate
from scripts.model_interactions.dpslog_service import DpsLogService

logger = logging.getLogger(__name__)


# %%
if __name__ == "__main__":
    y, m, d = today_y_m_d()
    y, m, d = 2025, 11, 27
    # y, m, d = 2025, 12, 8

    clear_group_base_name = "decima_cm"
    processing_type = "local"
    force_update = True

    # Initialize local parser
    ei_parser = EliteInsightsParser()
    ei_parser.create_settings(out_dir=settings.EI_PARSED_LOGS_DIR.joinpath(zfill_y_m_d(y, m, d)), create_html=False)

    progression_service = DecimaProgressionService(clear_group_base_name=clear_group_base_name, y=y, m=m, d=d)

    log_files_date_cls = LogFilesDate(
        y=y, m=m, d=d, allowed_folder_names=progression_service.encounter.folder_names.split(";")
    )
    logfiles = log_files_date_cls.get_unprocessed_logs(processing_type="local")

    # %%
    for logfile in logfiles:
        log_path = logfile.path

        parsed_path = ei_parser.parse_log(log_path=log_path)
        if parsed_path is not None:
            detailed_parsed_log = EliteInsightsParser.load_parsed_json(parsed_path=parsed_path)
            dpslog = DpsLogService().get_update_create_from_ei_parsed_log(
                detailed_parsed_log=detailed_parsed_log, log_path=log_path, force_update=True
            )

            if dpslog.instance_clear != progression_service.iclear:
                if dpslog.cm:
                    logger.info(f"Updating instance clear for log {dpslog} with log path {log_path}")
                    dpslog.instance_clear = progression_service.iclear
                    dpslog.save()
                else:
                    logger.info(
                        f"Not updating instance clear for log {dpslog} with log path {log_path} because it is not cm"
                    )

    # %%

    progression_service.update_instance_clear()
    send_progression_discord_message(progression_service)
