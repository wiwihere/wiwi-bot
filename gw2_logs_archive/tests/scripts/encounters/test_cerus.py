# %%
if __name__ == "__main__":
    from scripts.utilities import django_setup

    django_setup.run()


import logging

from gw2_logs.models import InstanceClearGroup
from scripts.encounters.cerus import build_cerus_discord_message
from scripts.log_helpers import replace_dps_links, zfill_y_m_d

logger = logging.getLogger(__name__)

# %%


def test_cerus_progression_message():
    # Test refactor on the go. Dont touch the code below.

    y, m, d = 2024, 3, 16
    CLEAR_GROUP_BASE_NAME = "cerus_cm__"  # followed by y_m_d; e.g. cerus_cm__20240406

    iclear_group, created = InstanceClearGroup.objects.update_or_create(
        name=f"{CLEAR_GROUP_BASE_NAME}{zfill_y_m_d(y, m, d)}", type="strike"
    )

    titles, descriptions = build_cerus_discord_message(iclear_group=iclear_group)
    descriptions = replace_dps_links(descriptions)

    # Testing
    assert titles == {
        "cerus_cm": {
            "main": "Sat 16 Mar 2024",
            "field_0": "\n`##`<:8_legendary:1218314286783533157>**★** ` health |  80% |  50% |  10% `+_delay_⠀⠀\n\n",
            "field_1": "\n`##`<:8_legendary:1218314286783533157>**★** ` health |  80% |  50% |  10% `+_delay_⠀⠀\n\n",
        }
    }

    assert descriptions == {
        "cerus_cm": {
            "main": "<:cerus:1198740269806395402> **Cerus CM**\n<t:1710614288:t> - <t:1710625194:t> \n<a:core:1203309561293840414><a:core:1203309561293840414><a:friend:1282336810487517195><a:pug:1206367130509905931><a:pug:1206367130509905931> <a:pug:1206367130509905931><a:pug:1206367130509905931><a:pug:1206367130509905931><a:pug:1206367130509905931><a:pug:1206367130509905931>\n\n",
            "field_0": "`01`<:1_junk:1218317392627765450>[☆](https://example.com/hidden) ` 83.73% |  --  |  --  |  --  `\n`02`<:4_masterwork:1218309092477767810>[☆](https://example.com/hidden) ` 41.47% | 8:05 | 4:36 |  --  `\n`03`<:1_junk:1218317392627765450>[☆](https://example.com/hidden) ` 98.74% |  --  |  --  |  --  `\n`04`<:2_basic:1218317391260287006>[☆](https://example.com/hidden) ` 78.84% | 8:14 |  --  |  --  `\n`05`<:2_basic:1218317391260287006>[☆](https://example.com/hidden) ` 65.74% | 8:16 |  --  |  --  `\n`06`<:3_fine:1218307650580647976>[☆](https://example.com/hidden) ` 57.47% | 8:16 |  --  |  --  `\n`07`<:2_basic:1218317391260287006>[☆](https://example.com/hidden) ` 79.28% | 8:11 |  --  |  --  `_+4:11_\n`08`<:3_fine:1218307650580647976>[☆](https://example.com/hidden) ` 57.99% | 8:14 |  --  |  --  `\n`09`<:2_basic:1218317391260287006>[☆](https://example.com/hidden) ` 65.26% | 8:12 |  --  |  --  `_+4:48_\n`10`<:2_basic:1218317391260287006>[☆](https://example.com/hidden) ` 79.15% | 8:14 |  --  |  --  `\n`11`<:1_junk:1218317392627765450>[☆](https://example.com/hidden) ` 99.99% |  --  |  --  |  --  `\n`12`<:3_fine:1218307650580647976>[☆](https://example.com/hidden) ` 58.45% | 8:17 |  --  |  --  `\n`13`<:2_basic:1218317391260287006>[☆](https://example.com/hidden) ` 62.77% | 8:13 |  --  |  --  `\n`14`<:2_basic:1218317391260287006>[☆](https://example.com/hidden) ` 77.13% | 8:17 |  --  |  --  `\n`15`<:3_fine:1218307650580647976>[☆](https://example.com/hidden) ` 53.11% | 8:19 |  --  |  --  `\n`16`<:1_junk:1218317392627765450>[☆](https://example.com/hidden) ` 95.24% |  --  |  --  |  --  `\n`17`<:4_masterwork:1218309092477767810>[☆](https://example.com/hidden) ` 49.28% | 8:14 | 4:57 |  --  `\n`18`<:2_basic:1218317391260287006>[☆](https://example.com/hidden) ` 78.64% | 8:16 |  --  |  --  `_+5:00_\n`19`<:2_basic:1218317391260287006>[☆](https://example.com/hidden) ` 79.45% | 8:13 |  --  |  --  `\n`20`<:4_masterwork:1218309092477767810>[☆](https://example.com/hidden) ` 40.14% | 8:17 | 4:56 |  --  `\n`21`<:2_basic:1218317391260287006>[☆](https://example.com/hidden) ` 77.79% | 8:16 |  --  |  --  `_+18:08_\n`22`<:5_rare:1218309546636742727>[☆](https://example.com/hidden) ` 38.77% | 8:18 | 5:06 |  --  `<:r{}_of{}_slower{}s:1338196308686798858>\n`23`<:3_fine:1218307650580647976>[☆](https://example.com/hidden) ` 53.66% | 8:10 |  --  |  --  `_+5:07_\n`24`<:2_basic:1218317391260287006>[☆](https://example.com/hidden) ` 78.96% | 8:18 |  --  |  --  `\n`25`<:3_fine:1218307650580647976>[☆](https://example.com/hidden) ` 52.08% | 8:08 |  --  |  --  `\n`26`<:2_basic:1218317391260287006>[☆](https://example.com/hidden) ` 79.53% | 8:21 |  --  |  --  `\n`27`<:3_fine:1218307650580647976>[☆](https://example.com/hidden) ` 57.47% | 8:18 |  --  |  --  `\n`28`<:2_basic:1218317391260287006>[☆](https://example.com/hidden) ` 65.68% | 8:15 |  --  |  --  `\n`29`<:5_rare:1218309546636742727>[☆](https://example.com/hidden) ` 39.08% | 8:19 | 5:08 |  --  `<:r{}_of{}_slower{}s:1338196304924250273>\n`30`<:4_masterwork:1218309092477767810>[☆](https://example.com/hidden) ` 41.45% | 8:20 | 5:05 |  --  `_+2:33_\n",
            "field_1": "`31`<:2_basic:1218317391260287006>[☆](https://example.com/hidden) ` 78.71% | 8:10 |  --  |  --  `_+3:31_\n`32`<:5_rare:1218309546636742727>[☆](https://example.com/hidden) ` 37.74% | 8:17 | 5:03 |  --  `<:r{}_of{}_faster{}s:1338196307239632956>\n",
        }
    }

    # for line in descriptions["cerus_cm"]["field_0"].split("\n"):
    #     print(line)


if __name__ == "__main__":
    test_cerus_progression_message()
