# Log uploads
Main interaction with the tooling is through .cmd's. These can be run from the windows file explorer.

## run_logs_today.cmd
Easiest way to proces todays logs. 

## upload_from_url.cmd
To add already uploaded logs to the database, paste the dps.report urls to `bin\urls.txt`. Each report should be on a new line, dont add comma's space or other characters than the urls. Finally, run the .cmd.

## copy_logs.cmd
Copy all logs of selected date from the `DPS_LOGS_DIR` (default arcdps output) to the `EXTRA_LOGS_DIR`. Setup the dirs in the `.env`. This makes it easier to share them. We have a onedrive setup for this.

# Encounters
For specific encounters (LCM Cerus), navigate to the encounters folder.

# Utilities

## update_elite_insights_parser.cmd
Update to EI parser to the latest version. Will download it from github and install it in the `GW2EI_parser` folder.

## django_runserver.cmd
Start a django server to get access to the admin interface. http://127.0.0.1:8000/admin/ (admin username=`wiwi` and password=`wiwi-bot`)

## python.cmd
Activate the python environment. This uses `activate_conda.cmd` to activate the env specified in `.env`.