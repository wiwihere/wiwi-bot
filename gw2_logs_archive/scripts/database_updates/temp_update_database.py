# %%

if __name__ == "__main__":
    from scripts.utilities import django_setup

    django_setup.run()


from gw2_logs.models import (
    DiscordMessage,
    Encounter,
    InstanceClearGroup,
)
from scripts.log_instance_interaction import InstanceClearGroupInteraction

# %%

icgs = InstanceClearGroup.objects.filter(name__contains="raids")

for icg in icgs:
    if icg.discord_message_id_old is not None:
        print(icg.name)
        disc_mess, _ = DiscordMessage.objects.update_or_create(message_id=icg.discord_message_id_old)
        icg.discord_message = disc_mess
        icg.save()

        # Create strike counterpart
        icgi = InstanceClearGroupInteraction.create_from_date(
            y=icg.start_time.year, m=icg.start_time.month, d=icg.start_time.day, itype_group="strike"
        )
        icgi.clear_group


# %% Update ei_encounter_id for each encounter
ei_ids = {
    "Vale Guardian": 131329,
    "Gorseval the Multifarious": 131330,
    "Sabetha the Saboteur": 131331,
    "Slothasor": 131585,
    "Bandit Trio": 131586,
    "Matthias Gabrel": 131587,
    "Escort": 131841,
    "Keep Construct": 131842,
    "Twisted Castle": 131843,
    "Xera": 131844,
    "Cairn": 132097,
    "Mursaat Overseer": 132098,
    "Samarog": 132099,
    "Deimos": 132100,
    "Soulless Horror": 132353,
    "River of Souls": 132354,
    "Broken King": 132355,
    "Eater of Souls": 132356,
    "Eye of Fate": 132357,
    "Dhuum": 132358,
    "Conjured Amalgamate": 132609,
    "Twin Largos": 132610,
    "Qadim": 132611,
    "Cardinal Adina": 132865,
    "Cardinal Sabir": 132866,
    "Qadim the Peerless": 132867,
    "Mama": 196865,
    "Siax the Corrupted": 196866,
    "Ensolyss": 196867,
    "Skorvald the Shattered": 197121,
    "Artsariiv": 197122,
    "Arkk": 197123,
    "Elemental Ai": 197378,
    "Dark Ai": 197379,
    "Kanaxai": 197633,
    "Freezie": 262401,
    "Icebrood Construct": 262657,
    "Fraenir of Jormag": 262658,
    "The Voice and the Claw": 262659,
    "Boneskinner": 262660,
    "Whisper of Jormag": 262661,
    # "Varinia Stormsounder": 262662,
    "Aetherblade Hideout": 262913,
    "Xunlai Jade Junkyard": 262914,
    "Kaineng Overlook": 262915,
    "Harvest Temple": 262916,
    "Old Lion's Court": 262917,
    "Cosmic Observatory": 263425,
    "Temple of Febe": 263426,
    "Standard Kitty Golem": 524550,
    "Large Kitty Golem": 524553,
    "Medium Kitty Golem": 524554,
}

for key, val in ei_ids.items():
    print(key)
    encounter = Encounter.objects.get(name=key)

    encounter.ei_encounter_id = val

    encounter.save()
# %%
