# %%
if __name__ == "__main__":
    from scripts.utilities import django_setup

    django_setup.run()


import logging

from scripts.discord_interaction.build_embeds import create_discord_embeds
from scripts.discord_interaction.build_message import create_discord_message
from scripts.leaderboards import *
from scripts.log_helpers import replace_dps_links

logger = logging.getLogger(__name__)

# %%


def test_leaderboard():
    # Test refactor on the go. Dont touch the code below.
    y, m, d = 2025, 12, 18
    itype_group = "raid"
    icgi = InstanceClearGroupInteraction.create_from_date(y=y, m=m, d=d, itype_group=itype_group)

    # Discord messsage testing
    titles, descriptions = create_discord_message(icgi)
    descriptions = replace_dps_links(descriptions)
    # %%
    assert titles == {
        "Spirit Vale": "Spirit Vale",
        "Salvation Pass": "Salvation Pass",
        "Stronghold of the Faithful": "Stronghold of the Faithful",
        "Bastion of the Penitent": "Bastion of the Penitent",
        "Hall of Chains": "Hall of Chains",
        "Mythwright Gambit": "Mythwright Gambit",
        "The Key of Ahdashim": "The Key of Ahdashim",
        "Mount Balrior": "Mount Balrior",
    }

    assert descriptions == {
        "Spirit Vale": "<:spirit_vale:1185639755464060959><:r1_of84_faster14_3s:1338196307239632956>`16:00` <:r2_of84_slower14_3s:1338196308686798858>`16:14` <:r3_of84_slower22_5s:1338196304924250273>`16:22` <:median:1200576359018266714>`17:33`\n\n<:vale_guardian:1206250717401063605>[<:r1_of84_faster2_0s:1338196307239632956>](https://example.com/hidden)` 2:06` [<:r2_of84_slower2_0s:1338196308686798858>](https://example.com/hidden)` 2:08` [<:r3_of84_slower3_7s:1338196304924250273>](https://example.com/hidden)` 2:10` <:median:1200576359018266714>` 2:24`\n<:gorseval_the_multifarious:1206250719074721813>[<:r1_of85_faster1_1s:1338196307239632956>](https://example.com/hidden)` 2:00` [<:r2_of85_slower1_1s:1338196308686798858>](https://example.com/hidden)` 2:01` [<:r3_of85_slower2_1s:1338196304924250273>](https://example.com/hidden)` 2:02` <:median:1200576359018266714>` 2:13`\n<:sabetha_the_saboteur:1206250720483872828>[<:r1_of85_faster3_3s:1338196307239632956>](https://example.com/hidden)` 2:53` [<:r2_of85_slower3_3s:1338196308686798858>](https://example.com/hidden)` 2:56` [<:r3_of85_slower5_8s:1338196304924250273>](https://example.com/hidden)` 2:58` <:median:1200576359018266714>` 3:22`\n",
        "Salvation Pass": "<:salvation_pass:1185642016776913046><:r1_of87_faster5_7s:1338196307239632956>`13:59` <:r2_of87_slower5_7s:1338196308686798858>`14:05` <:r3_of87_slower5_9s:1338196304924250273>`14:05` <:median:1200576359018266714>`15:42`\n\n<:slothasor:1206250721880576081>[<:r1_of87_faster2_1s:1338196307239632956>](https://example.com/hidden)` 2:01` [<:r2_of87_slower2_1s:1338196308686798858>](https://example.com/hidden)` 2:03` [<:r3_of87_slower4_1s:1338196304924250273>](https://example.com/hidden)` 2:05` <:median:1200576359018266714>` 2:21`\n<:bandit_trio:1206250723550175283>[<:r1_of87_faster0_2s:1338196307239632956>](https://example.com/hidden)` 6:27` [<:r2_of87_slower0_2s:1338196308686798858>](https://example.com/hidden)` 6:27` [<:r3_of87_slower0_9s:1338196304924250273>](https://example.com/hidden)` 6:28` <:median:1200576359018266714>` 6:34`\n<:matthias_gabrel:1206250724879503410>[<:r1_of87_faster10_3s:1338196307239632956>](https://example.com/hidden)` 2:04` [<:r2_of87_slower10_3s:1338196308686798858>](https://example.com/hidden)` 2:14` [<:r3_of87_slower11_8s:1338196304924250273>](https://example.com/hidden)` 2:16` <:median:1200576359018266714>` 2:45`\n",
        "Stronghold of the Faithful": "<:stronghold_of_the_faithful:1185642019163471982><:r1_of78_faster24_6s:1338196307239632956>`14:24` <:r2_of78_slower24_6s:1338196308686798858>`14:48` <:r3_of78_slower85_0s:1338196304924250273>`15:49` <:median:1200576359018266714>`20:45`\n\n<:escort:1206250726146441286>[<:r1_of84_faster9_5s:1338196307239632956>](https://example.com/hidden)` 1:17` [<:r2_of84_slower9_5s:1338196308686798858>](https://example.com/hidden)` 1:27` [<:r3_of84_slower13_7s:1338196304924250273>](https://example.com/hidden)` 1:31` <:median:1200576359018266714>` 5:52`\n<:keep_construct:1206251990980763749>[<:r1_of96_faster5_1s:1338196307239632956>](https://example.com/hidden)` 4:27` [<:r2_of96_slower5_1s:1338196308686798858>](https://example.com/hidden)` 4:32` [<:r3_of96_slower5_5s:1338196304924250273>](https://example.com/hidden)` 4:33` <:median:1200576359018266714>` 5:07`\n<:twisted_castle:1206251992272474212>[<:r1_of94_faster1_6s:1338196307239632956>](https://example.com/hidden)` 1:13` [<:r2_of94_slower1_6s:1338196308686798858>](https://example.com/hidden)` 1:15` [<:r3_of94_slower3_8s:1338196304924250273>](https://example.com/hidden)` 1:17` <:median:1200576359018266714>` 1:36`\n<:xera:1206251993677439027>[<:r1_of96_faster0_1s:1338196307239632956>](https://example.com/hidden)` 4:16` [<:r2_of96_slower0_1s:1338196308686798858>](https://example.com/hidden)` 4:16` [<:r3_of96_slower2_3s:1338196304924250273>](https://example.com/hidden)` 4:18` <:median:1200576359018266714>` 4:40`\n",
        "Bastion of the Penitent": "<:bastion_of_the_penitent:1185642020484698132><:r1_of103_faster6_3s:1338196307239632956>`18:07` <:r2_of103_slower6_3s:1338196308686798858>`18:13` <:r3_of103_slower15_1s:1338196304924250273>`18:22` <:median:1200576359018266714>`20:52`\n\n<:cairn:1206251996680556544>[<:r1_of103_faster0_2s:1338196307239632956>](https://example.com/hidden)` 1:15` [<:r2_of103_slower0_2s:1338196308686798858>](https://example.com/hidden)` 1:15` [<:r3_of103_slower1_3s:1338196304924250273>](https://example.com/hidden)` 1:16` <:median:1200576359018266714>` 1:27`\n<:mursaat_overseer:1206252000229199932>[<:r1_of103_faster1_2s:1338196307239632956>](https://example.com/hidden)` 1:33` [<:r2_of103_slower1_2s:1338196308686798858>](https://example.com/hidden)` 1:34` [<:r3_of103_slower3_7s:1338196304924250273>](https://example.com/hidden)` 1:37` <:median:1200576359018266714>` 1:52`\n<:samarog:1206256460120457277>[<:r1_of103_faster24_7s:1338196307239632956>](https://example.com/hidden)` 4:27` [<:r2_of103_slower24_7s:1338196308686798858>](https://example.com/hidden)` 4:52` [<:r3_of103_slower39_0s:1338196304924250273>](https://example.com/hidden)` 5:06` <:median:1200576359018266714>` 5:46`\n<:deimos:1206256463031304253>[<:r1_of103_faster3_1s:1338196307239632956>](https://example.com/hidden)` 5:04` [<:r2_of103_slower3_1s:1338196308686798858>](https://example.com/hidden)` 5:07` [<:r3_of103_slower16_5s:1338196304924250273>](https://example.com/hidden)` 5:20` <:median:1200576359018266714>` 6:04`\n",
        "Hall of Chains": "<:hall_of_chains:1185642022019792976><:r1_of97_faster12_1s:1338196307239632956>`20:16` <:r2_of97_slower12_1s:1338196308686798858>`20:28` <:r3_of97_slower21_6s:1338196304924250273>`20:37` <:median:1200576359018266714>`27:01`\n\n<:soulless_horror:1206256465635966996>[<:r1_of99_faster3_6s:1338196307239632956>](https://example.com/hidden)` 2:14` [<:r2_of99_slower3_6s:1338196308686798858>](https://example.com/hidden)` 2:18` [<:r3_of99_slower7_6s:1338196304924250273>](https://example.com/hidden)` 2:22` <:median:1200576359018266714>` 2:38`\n<:river_of_souls:1206263997163372574>[<:r1_of101_faster0_5s:1338196307239632956>](https://example.com/hidden)` 2:34` [<:r2_of101_slower0_5s:1338196308686798858>](https://example.com/hidden)` 2:34` [<:r3_of101_slower0_6s:1338196304924250273>](https://example.com/hidden)` 2:34` <:median:1200576359018266714>` 2:36`\n<:statue_of_death:1206263999042428928>[<:r1_of100_faster1_6s:1338196307239632956>](https://example.com/hidden)` 1:41` [<:r2_of100_slower1_6s:1338196308686798858>](https://example.com/hidden)` 1:42` [<:r3_of100_slower2_2s:1338196304924250273>](https://example.com/hidden)` 1:43` <:median:1200576359018266714>` 1:49`\n<:statue_of_darkness:1206264000715690045>[<:r1_of101_faster2_0s:1338196307239632956>](https://example.com/hidden)` 0:43` [<:r2_of101_slower2_0s:1338196308686798858>](https://example.com/hidden)` 0:45` [<:r3_of101_slower2_5s:1338196304924250273>](https://example.com/hidden)` 0:46` <:median:1200576359018266714>` 1:11`\n<:statue_of_ice:1206263994260922378>[<:r1_of100_faster0_7s:1338196307239632956>](https://example.com/hidden)` 1:45` [<:r2_of100_slower0_7s:1338196308686798858>](https://example.com/hidden)` 1:46` [<:r3_of100_slower2_6s:1338196304924250273>](https://example.com/hidden)` 1:48` <:median:1200576359018266714>` 2:07`\n<:dhuum:1206264003228213248>[<:r1_of97_faster0_3s:1338196307239632956>](https://example.com/hidden)` 6:15` [<:r2_of97_slower0_3s:1338196308686798858>](https://example.com/hidden)` 6:16` [<:r3_of97_slower6_2s:1338196304924250273>](https://example.com/hidden)` 6:21` <:median:1200576359018266714>` 7:16`\n",
        "Mythwright Gambit": "<:mythwright_gambit:1185642030764920883><:r1_of101_faster0_4s:1338196307239632956>`18:43` <:r2_of101_slower0_4s:1338196308686798858>`18:44` <:r3_of101_slower25_3s:1338196304924250273>`19:08` <:median:1200576359018266714>`22:30`\n\n<:conjured_amalgamate:1206264146086207528>[<:r1_of100_faster0_9s:1338196307239632956>](https://example.com/hidden)` 2:07` [<:r2_of100_slower0_9s:1338196308686798858>](https://example.com/hidden)` 2:08` [<:r3_of100_slower1_7s:1338196304924250273>](https://example.com/hidden)` 2:08` <:median:1200576359018266714>` 2:22`\n<:twin_largos:1206264148661637140>[<:r1_of101_faster3_6s:1338196307239632956>](https://example.com/hidden)` 4:09` [<:r2_of101_slower3_6s:1338196308686798858>](https://example.com/hidden)` 4:12` [<:r3_of101_slower5_1s:1338196304924250273>](https://example.com/hidden)` 4:14` <:median:1200576359018266714>` 4:37`\n<:qadim:1206264151580876841>[<:r1_of100_faster5_0s:1338196307239632956>](https://example.com/hidden)` 6:12` [<:r2_of100_slower5_0s:1338196308686798858>](https://example.com/hidden)` 6:17` [<:r3_of100_slower5_2s:1338196304924250273>](https://example.com/hidden)` 6:17` <:median:1200576359018266714>` 6:59`\n",
        "The Key of Ahdashim": "<:the_key_of_ahdashim:1185642032073543780><:r1_of104_faster33_4s:1338196307239632956>`15:37` <:r2_of104_slower33_4s:1338196308686798858>`16:10` <:r3_of104_slower34_4s:1338196304924250273>`16:11` <:median:1200576359018266714>`20:07`\n\n<:cardinal_adina:1206264154634326116>[<:r1_of104_faster0_5s:1338196307239632956>](https://example.com/hidden)` 3:19` [<:r2_of104_slower0_5s:1338196308686798858>](https://example.com/hidden)` 3:19` [<:r3_of104_slower4_3s:1338196304924250273>](https://example.com/hidden)` 3:23` <:median:1200576359018266714>` 4:26`\n<:cardinal_sabir:1206264157519741019>[<:r1_of104_faster6_6s:1338196307239632956>](https://example.com/hidden)` 3:19` [<:r2_of104_slower6_6s:1338196308686798858>](https://example.com/hidden)` 3:26` [<:r3_of104_slower12_4s:1338196304924250273>](https://example.com/hidden)` 3:32` <:median:1200576359018266714>` 3:54`\n<:qadim_the_peerless:1206264288768036918>[<:r1_of101_faster1_3s:1338196307239632956>](https://example.com/hidden)` 4:59` [<:r2_of101_slower1_3s:1338196308686798858>](https://example.com/hidden)` 5:00` [<:r3_of101_slower2_5s:1338196304924250273>](https://example.com/hidden)` 5:01` <:median:1200576359018266714>` 5:51`\n",
        "Mount Balrior": "<:mount_balrior:1311064236486688839><:r1_of39_faster15_2s:1338196307239632956>`19:22` <:r2_of39_slower15_2s:1338196308686798858>`19:38` <:r3_of39_slower26_1s:1338196304924250273>`19:48` <:median:1200576359018266714>`23:36`\n\n<:greer:1310742326548762664>[<:r1_of42_faster5_0s:1338196307239632956>](https://example.com/hidden)` 7:13` [<:r2_of42_slower5_0s:1338196308686798858>](https://example.com/hidden)` 7:19` [<:r3_of42_slower5_9s:1338196304924250273>](https://example.com/hidden)` 7:19` <:median:1200576359018266714>` 8:00`\n<:decima:1310742355644776458>[<:r1_of40_faster0_1s:1338196307239632956>](https://example.com/hidden)` 4:18` [<:r2_of40_slower0_1s:1338196308686798858>](https://example.com/hidden)` 4:18` [<:r3_of40_slower0_8s:1338196304924250273>](https://example.com/hidden)` 4:19` <:median:1200576359018266714>` 5:01`\n<:ura:1310742374665683056>[<:r1_of40_faster1_5s:1338196307239632956>](https://example.com/hidden)` 4:08` [<:r2_of40_slower1_5s:1338196308686798858>](https://example.com/hidden)` 4:10` [<:r3_of40_slower9_3s:1338196304924250273>](https://example.com/hidden)` 4:18` <:median:1200576359018266714>` 4:50`\n",
    }
    # %%

    # Embeds testing
    embeds = create_discord_embeds(titles=titles, descriptions=descriptions)

    embeds[
        "raid_0"
    ].title == "Thu 18 Dec 2025⠀⠀⠀⠀<:r20_of45_slower1804_9s:1240399925502545930> **3:12:00** <:r20_of45_slower1804_9s:1240399925502545930> \n"

    expected_field_name = [
        "**__<:spirit_vale:1185639755464060959><:r46_of82_slower108_8s:1240799615763222579>Spirit Vale (17:49)__**\n",
        "**__<:salvation_pass:1185642016776913046><:r23_of84_slower55_9s:1240399925502545930>Salvation Pass (14:55)__**\n",
        "**__<:bastion_of_the_penitent:1185642020484698132><:r73_of99_slower319_4s:1240799615763222579>Bastion of the Penitent (23:26)__**\n",
        "**__<:mount_balrior:1311064236486688839><:r14_of39_slower175_0s:1240399925502545930>Mount Balrior (22:17)__**\n",
    ]

    expected_field_value = [
        "<:vale_guardian:1206250717401063605><:r55_of82_slower22_6s:1240799615763222579>[Vale Guardian](https://example.com/hidden) (**2:31**)_+0:00_\n<:gorseval_the_multifarious:1206250719074721813><:r29_of83_slower10_7s:1240399925502545930>[Gorseval the Multifarious](https://example.com/hidden) (**2:10**)_+7:33_\n<:sabetha_the_saboteur:1206250720483872828><:r68_of83_slower49_0s:1240798628596027483>[Sabetha the Saboteur](https://example.com/hidden) (**3:42**)_+1:51_\n",
        "<:slothasor:1206250721880576081><:r8_of84_slower9_5s:1240399924198379621>[Slothasor](https://example.com/hidden) (**2:10**)_+2:58_\n<:bandit_trio:1206250723550175283><:r26_of84_slower4_6s:1240399925502545930>[Bandit Trio](https://example.com/hidden) (**6:31**)_+0:22_\n<:matthias_gabrel:1206250724879503410><:r72_of84_slower66_0s:1240798628596027483>[Matthias Gabrel](https://example.com/hidden) (**3:10**)_+2:40_\n",
        "<:cairn:1206251996680556544><:r6_of99_slower3_6s:1240399924198379621>[Cairn CM](https://example.com/hidden) (**1:18**)_+3:44_\n<:mursaat_overseer:1206252000229199932><:r3_of99_slower3_7s:1338196304924250273>[Mursaat Overseer CM](https://example.com/hidden) (**1:37**)_+1:35_\n<:samarog:1206256460120457277><:r4_of99_slower41_2s:1240399924198379621>[Samarog CM](https://example.com/hidden) (**5:08**)_+1:19_\n<:deimos:1206256463031304253><:r5_of99_slower19_9s:1240399924198379621>[Deimos CM](https://example.com/hidden) (**5:23**)_+7:03_ [<:wipe_at_14:1199739670641258526>](https://example.com/hidden)\n",
        "<:greer:1310742326548762664><:r21_of42_slower45_4s:1240799615763222579>[Greer, the Blightbringer](https://example.com/hidden) (**7:59**)_+4:13_\n<:decima:1310742355644776458><:r17_of40_slower39_0s:1240399925502545930>[Decima, the Stormsinger](https://example.com/hidden) (**4:57**)_+2:41_\n<:ura:1310742374665683056><:r21_of40_slower42_1s:1240799615763222579>[Ura](https://example.com/hidden) (**4:50**)_+1:48_\n",
    ]

    for idx, field in enumerate(embeds["raid_0"].fields):
        assert field.name == expected_field_name[idx]

        field_value = replace_dps_links(field.value, "https://example.com/hidden")

        assert field_value == expected_field_value[idx]


if __name__ == "__main__":
    test_discord_message()

# %%
