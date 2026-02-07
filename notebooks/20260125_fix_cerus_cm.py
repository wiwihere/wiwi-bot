# %%

if __name__ == "__main__":
    from scripts.utilities import django_setup

    django_setup.run()


import logging
from gw2_logs.models import (
    DpsLog,
    Encounter,
    InstanceClear,
    InstanceClearGroup,
)
from scripts.log_helpers import zfill_y_m_d,

logger = logging.getLogger(__name__)



CLEAR_GROUP_BASE_NAME = "cerus_cm__"  # followed by y_m_d; e.g. cerus_cm__20240406

if __name__ == "__main__":
    y, m, d = 2024, 3, 16
    clear_name = f"{CLEAR_GROUP_BASE_NAME}{zfill_y_m_d(y, m, d)}"

    # Building instance clears. havent been used before for this.
    encounter = Encounter.objects.get(name="Temple of Febe")
    iclear_group, created = InstanceClearGroup.objects.get_or_create(name=clear_name, type="strike")
    iclear, created = InstanceClear.objects.get_or_create(
        defaults={
            "instance": encounter.instance,
            "instance_clear_group": iclear_group,
        },
        name=clear_name,
    )

    cm_logs = DpsLog.objects.filter(
        encounter__name="Temple of Febe",
        start_time__year=y,
        start_time__month=m,
        start_time__day=d,
        cm=True,
        # final_health_percentage__lt=100,
    ).order_by("start_time")

    # Set start time
    log0 = cm_logs[0]
    log0.start_time
    if iclear.start_time != log0.start_time:
        logger.info(f"Updating start time for {iclear.name} from {iclear.start_time} to {log0.start_time}")
        iclear.start_time = log0.start_time
        iclear.save()

    # Set duration
    last_log = cm_logs.order_by("start_time").last()
    calculated_duration = last_log.start_time + last_log.duration - iclear.start_time
    if iclear.duration != calculated_duration:
        logger.info(f"Updating duration for {iclear.name} from {iclear.duration} to {calculated_duration}")
        iclear.duration = calculated_duration
        iclear.save()

    for dpslog in cm_logs:
        if dpslog.instance_clear != iclear:
            logger.info(f"Updating instance clear for log {dpslog.id} to {iclear.name}")
            dpslog.instance_clear = iclear
            dpslog.save()
