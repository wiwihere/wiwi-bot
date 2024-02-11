# Gw2 Log Manager
This log manager is specifically geared towards tracking clears within a raid static. It will upload logs to [dps.report](https://dps.report) and create a discord message using webhooks with the run times. 
It also compares the runs with previous results and shows how you did on the leaderboard.
For any questions or feature requests feel free to slide into the discord server
[Wiwi's Corner](https://discord.gg/C6sNvPq3dK).

# Features
It is a local tool that uses dps logs from arc-dps and uploads them to dps.report. The log manager will create a discord message for a raiding or fractal session. It will post new logs while raiding every time there is one available. Or just upload the full run afterwards.

### Static clears
![Raid message](img/raid_message.png)
![Fractal message](img/fractal_message.png)

(**4:41**) cleartime of the encounter\
_+1:07_ Time between the end of the previous kill run and the start of the current kill run. If its the first log in the session it will be 0:00, unless there is a fail log. \
<img src="gw2_database/img/medal/first.png" width="20"/> Medals indicate position on leaderboard, comparing the speed of that run with all historic runs.\
<img src="gw2_database/img/medal/first_invalid.png" width="20"/> Invalid medals mean that there were more pugs than allowed (check settings).\
<img src="gw2_database/img/medal/below_average.png" alt="below average" width="20"/> 5s slower than average\
<img src="gw2_database/img/medal/above_average.png" alt="above average" width="20"/> 5s faster than average, but not in top 3\
<img src="gw2_database/img/wipe_50.png" alt="wipe_50%" width="20"/> Wipe, red indicates how much health left. More red = lower boss health.\
<img src="img/click_wipe.png" alt="click_wipe%" width=""/>\
Clicking the skull icon will also open the log of that run. Does sadly not work on phone.\
<img src="gw2_database/img/core.gif" width="20"/> Amount of core members in the run.\
<img src="gw2_database/img/pug.gif" width="20"/> Amount of pugs in the run.\
<img src="gw2_database/img/medal/below_average.png" width="20"/>**2:47:15**<img src="gw2_database/img/medal/below_average.png" width="20"/> Total runtime of combined runs. Only shows when all encounters have been successfully killed. Works for fractals and raids. For raids the whole week is checked. Fractals need to be cleared on the same day.\
<img src="gw2_database/img/emboldened.png" width="20"/> Emboldened runs will not count towards leaderboards.
### Leaderboards
<img src="img/leaderboard_message.png" width=""/>\
<img src="gw2_database/img/medal/first.png" width="20"/> Click the medal to go to the dps report.

# Installation
The log manager is built on a django framework with a local sqlite database, only tested on Windows. All we need is a local python environment to run the scripts. Below installation is done with miniforge, but feel free
to use any other python distribution to your liking.

## Software
<!-- 1. <s>Download the latest [release](https://github.com/wiwihere/wiwi-bot/releases)<\s> and place it anywhere. Unpack the zip. -->
1. Download this github page as zip (Code -> Download ZIP) and place it anywhere. Unpack the zip.
2. Install the python environment. Download [miniforge](https://github.com/conda-forge/miniforge). Make sure to tick the option to add python 3.10 to system path.
3. Run `Miniforge Prompt` as **admin**. And run the following code;
```
mamba env create -f "C:\Users\Wiwi\Documents\github\wiwi-bot\environment.yml" #Change to download location
```
4. Use the IDE of your choice if you need to debug errors or want a bit more control. I use [vs-code-insiders](https://code.visualstudio.com/insiders):\
    a. Install the python and jupyter extensions.\
    b. File -> Open Folder ->  select the folder with the unpacked zip from 1.\
    c. Open the file `wiwi-bot/gw2_database/scripts/import_dps_report.py`\
    d. On the bottom right click the python interpreter ![select interpreter](img/vscode_select_interpreter.png) and select the python env we installed at step 2; ![python env](img/vscode_python_env.png).\
    e. Run the code with `shift+enter` or by pressing ![alt text](img/vscode_runcell.png) above the code blocks.
5. Enable logging to file in [arcdps](https://www.deltaconnected.com/arcdps/), can be done in-game `alt+shift+t`.\
![activate logging](img/activate_logging.png)

## Initial setup
A couple tokens and keys need to be set so the results can be posted to discord.
1. Rename `bot_settings\.env-example` to `bot_settings\.env`.
    - .env\CONDA_DIR -> rename `C:\Users\Wiwi\miniforge3` to your own conda or mamba installation (step 2 in software)
    - .env\DPS_REPORT_USERTOKEN -> place userToken from https://dps.report/getUserToken after = sign.
    - .env\CORE_MINIMUM_RAID -> [0 to 10] Minimum core members in run for leaderboard
    - .env\CORE_MINIMUM_FRACTAL -> [0 to 5] Minimum core members in run for leaderboard
    - .env\INCLUDE_NON_CORE_LOGS -> [True or False] When True non core runs are still posted on leaderboard, but they get a red background emote (e.g. <img src="gw2_database/img/medal/first_invalid.png" width="20"/>)

2. In discord we have 3 channels running. Create a webhook for each and copy the webhook URL into the env. 

    ![discord_channels](img/discord_channel.png)\
    Make sure to tick the option:\
    ![discord_use_emoji](img/discord_use_emoji.png)

    discord Server Setttings -> integrations -> Webhooks -> Copy Webhook URL
3. Within the leaderboards channel create threads for: `raids`, `strikes` and `fractals`.
- Get the thread id by right click -> copy link or  -> paste only the last 18 digit number in the .env.
4. Setup the database. Copy `gw2_datase/db-empty.sqlite3` to `gw2_datase/db.sqlite3`.
5. Add core members to the database, see [Add a core member](#add-a-core-member).

## Usage
For runs on the same day just run `bin\run_logs_today.cmd` from the file-explorer.

To import history run `bin\run_logs_date.cmd` from the file-explorer. Then enter the date \
![run_logs_date](img/run_logs_date.png)

## Customization
Everything can be customized. Easiest way to make edits to the database is by firing up Django.

- Run `bin/django_runserver.cmd.`
- Open http://127.0.0.1:8000/admin/
- user: wiwi, pw: wiwi-bot


#### Add a core member:
Add members to the players list to have them appear as a core member. 

- Go to the Guilds page and make a guild; http://127.0.0.1:8000/admin/gw2_logs/guild/
- Go to the Players page; http://127.0.0.1:8000/admin/gw2_logs/player/ and add a new player:\
<img src="img/add_player.png" width="400"/>


#### Add new encounter
When parsing a log from an encounter that is not in the database yet, the script will throw
a warning and ignore it. If .env/DEBUG is set to True an error will be raised instead. \
![missing_bossid](img/missing_bossid.png)

The encounter will have to be added to the database if you want it to show up on discord.
- Add encounter to http://127.0.0.1:8000/admin/gw2_logs/encounter/
- Use the boss id from error message.


#### Removing logs
To remove logs or a clear you need to look at these three tables.
- http://127.0.0.1:8000/admin/gw2_logs/instancecleargroup/
- http://127.0.0.1:8000/admin/gw2_logs/instanceclear/
- http://127.0.0.1:8000/admin/gw2_logs/dpslog/

![remove_logs](img/remove_logs.png)


#### Showing non-cm encounters on leaderboard
We are not showing all enounters in the leaderboard because we are not interested in non-CM runs.
Which encounters are shown is configured in the LB and LB CM options per encounter.\
See http://127.0.0.1:8000/admin/gw2_logs/encounter/ \
![leaderboard_selection](img/leaderboard_selection.png)