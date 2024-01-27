# %%
import requests
import settings
from discord import SyncWebhook

webhook = SyncWebhook.from_url(settings.WEBHOOK_BOT_CHANNEL)
mess = webhook.send(
    " <:samarog_is_Here:600304962584444951> :skull_crossbones: [Arkk log](https://dps.report/cDnQ-20231210-193611_arkk)",
    wait=True,
)

# <:hypers:503327022869905430>
# %%

# %%


base_url = "https://dps.report/uploadContent"

data = {
    "json": 1,
    "generator": "ei",
    "userToken": settings.DPS_REPORT_USERTOKEN,
    "anonymous": False,
    "detailedwvw": False,
}
files = {
    "file": open(
        r"C:\Users\\Documents\Guild Wars 2\addons\arcdps\arcdps.cbtlogs\Arkk\Wiwi Memi\20231210-193611.zevtc",
        "rb",
    )
}

r = requests.post(base_url, files=files, data=data)

print(r)
# %%


a = webhook.send("", wait=True)
# a.edit(content="sdfg")
