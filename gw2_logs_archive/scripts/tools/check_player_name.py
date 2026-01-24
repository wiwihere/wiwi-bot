"""Check how often a player has joined runs.
Creates a dataframe with a count of all the logs for each day they were there.
"""

# %%
if __name__ == "__main__":
    from scripts.utilities import django_setup

    django_setup.run()
import numpy as np
import pandas as pd
from gw2_logs.models import DpsLog

player_name = "Wiwiwar"  # Fill gw2 account name

x = [a.date() for a in DpsLog.objects.filter(players__icontains=player_name).values_list("start_time", flat=True)]

data = np.unique(x, return_counts=True)
pd.DataFrame(data)
