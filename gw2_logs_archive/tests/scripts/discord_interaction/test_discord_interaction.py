# %%
if __name__ == "__main__":
    from scripts.utilities import django_setup

    django_setup.run()


import logging

from scripts.discord_interaction.build_embeds import create_discord_embeds
from scripts.discord_interaction.build_message import create_discord_message
from scripts.log_helpers import replace_dps_links
from scripts.model_interactions.instance_clear_group import InstanceClearGroupInteraction

logger = logging.getLogger(__name__)

# %%


def test_discord_message():
    # Test refactor on the go. Dont touch the code below.
    y, m, d = 2025, 12, 18
    itype_group = "raid"

    icgi = InstanceClearGroupInteraction.create_from_date(y=y, m=m, d=d, itype_group=itype_group)
    titles, descriptions = create_discord_message(icgi)
    descriptions = replace_dps_links(descriptions)
    assert titles == {
        "raid": {
            "main": "Thu 18 Dec 2025⠀⠀⠀⠀<:r20_of45_slower1804_9s:1240399925502545930> **3:12:00** <:r20_of45_slower1804_9s:1240399925502545930> \n",
            "spirit_vale__20251218": "**__<:spirit_vale:1185639755464060959><:r46_of82_slower108_8s:1240799615763222579>Spirit Vale (17:49)__**\n",
            "salvation_pass__20251218": "**__<:salvation_pass:1185642016776913046><:r23_of84_slower55_9s:1240399925502545930>Salvation Pass (14:55)__**\n",
            "bastion_of_the_penitent__20251218": "**__<:bastion_of_the_penitent:1185642020484698132><:r73_of99_slower319_4s:1240799615763222579>Bastion of the Penitent (23:26)__**\n",
            "mount_balrior__20251218": "**__<:mount_balrior:1311064236486688839><:r14_of39_slower175_0s:1240399925502545930>Mount Balrior (22:17)__**\n",
        }
    }

    assert descriptions == {
        "raid": {
            "main": "<t:1766083791:t> - <t:1766089156:t> \n<a:core:1203309561293840414><a:core:1203309561293840414><a:core:1203309561293840414><a:core:1203309561293840414><a:core:1203309561293840414> <a:core:1203309561293840414><a:core:1203309561293840414><a:core:1203309561293840414><a:core:1203309561293840414><a:pug:1206367130509905931>\n\n",
            "spirit_vale__20251218": "<:vale_guardian:1206250717401063605><:r55_of82_slower22_6s:1240799615763222579>[Vale Guardian](https://example.com/hidden) (**2:31**)_+0:00_\n<:gorseval_the_multifarious:1206250719074721813><:r29_of83_slower10_7s:1240399925502545930>[Gorseval the Multifarious](https://example.com/hidden) (**2:10**)_+7:33_\n<:sabetha_the_saboteur:1206250720483872828><:r68_of83_slower49_0s:1240798628596027483>[Sabetha the Saboteur](https://example.com/hidden) (**3:42**)_+1:51_\n",
            "salvation_pass__20251218": "<:slothasor:1206250721880576081><:r8_of84_slower9_5s:1240399924198379621>[Slothasor](https://example.com/hidden) (**2:10**)_+2:58_\n<:bandit_trio:1206250723550175283><:r26_of84_slower4_6s:1240399925502545930>[Bandit Trio](https://example.com/hidden) (**6:31**)_+0:22_\n<:matthias_gabrel:1206250724879503410><:r72_of84_slower66_0s:1240798628596027483>[Matthias Gabrel](https://example.com/hidden) (**3:10**)_+2:40_\n",
            "bastion_of_the_penitent__20251218": "<:cairn:1206251996680556544><:r6_of99_slower3_6s:1240399924198379621>[Cairn CM](https://example.com/hidden) (**1:18**)_+3:44_\n<:mursaat_overseer:1206252000229199932><:r3_of99_slower3_7s:1338196304924250273>[Mursaat Overseer CM](https://example.com/hidden) (**1:37**)_+1:35_\n<:samarog:1206256460120457277><:r4_of99_slower41_2s:1240399924198379621>[Samarog CM](https://example.com/hidden) (**5:08**)_+1:19_\n<:deimos:1206256463031304253><:r5_of99_slower19_9s:1240399924198379621>[Deimos CM](https://example.com/hidden) (**5:23**)_+7:03_ [<:wipe_at_14:1199739670641258526>](https://example.com/hidden)\n",
            "mount_balrior__20251218": "<:greer:1310742326548762664><:r21_of42_slower45_4s:1240799615763222579>[Greer, the Blightbringer](https://example.com/hidden) (**7:59**)_+4:13_\n<:decima:1310742355644776458><:r17_of40_slower39_0s:1240399925502545930>[Decima, the Stormsinger](https://example.com/hidden) (**4:57**)_+2:41_\n<:ura:1310742374665683056><:r21_of40_slower42_1s:1240799615763222579>[Ura](https://example.com/hidden) (**4:50**)_+1:48_\n",
        }
    }

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
