# %%

"""
Restore a backup file to a PostgreSQL database using pg_restore.
Drops and creates the database before restoring.

Make sure you have postgresql17 installed and pg_restore, createdb and dropdb are in your PATH.
This is only used in development.
"""

import datetime
import logging
import os
import subprocess
from pathlib import Path
from typing import Literal

from bot_settings.env_settings import BaseEnvSettings, EnvSettings
from bot_settings.log_settings import get_create_log_config
from pydantic import validate_call

# Load .env settings
base_settings = BaseEnvSettings.load()
dev_env_settings = EnvSettings.load(app_env="DEV")
prd_env_settings = EnvSettings.load(app_env="PRD")

logging.config.dictConfig(get_create_log_config(debug=dev_env_settings.DEBUG, loglevel=dev_env_settings.LOGLEVEL))
logger = logging.getLogger(__name__)

DJANGO_BACKUP_DIR = prd_env_settings.DJANGO_BACKUP_DIR
assert DJANGO_BACKUP_DIR.exists()

PROJECT_DIR = Path(__file__).resolve().parents[3]  # git repo
LOCAL_BACKUP_DIR = PROJECT_DIR / "data" / "db_backups"
assert LOCAL_BACKUP_DIR.exists()


def get_postgres_credentials(env_key: Literal["DEV", "PRD"]) -> dict:
    """Get Postgres database from environment variables."""

    database = {}
    if env_key == "DEV":
        env_settings = dev_env_settings
    else:
        env_settings = prd_env_settings

    for param in ["NAME", "ENGINE", "USER", "PASSWORD", "HOST", "PORT"]:
        database[param] = getattr(env_settings, f"DJANGO_DATABASE_{param}")

    return database


class PostgresDatabase:
    def __init__(self, database: dict, dryrun: bool = False):
        """
        Interaction with a Postgres database to create and restore backups.

        Parameters
        ----------
        database :
            from .env
        backup_dir : Path, optional
            Directory where backups are stored
        """
        self.database = database
        self.dryrun = dryrun

    @classmethod
    def from_env(cls, dryrun: bool = False) -> "PostgresDatabase":
        """Initialize PostgresDatabase from environment variables.
        Either connect to DEV or PRD, depending on ENVIRONMENT variable.
        """
        database = get_postgres_credentials(env_key="DEV")
        return cls(database=database, dryrun=dryrun)

    @property
    def default_args(self) -> list[str]:
        """Default arguments for pg commands."""
        db_user = self.database["USER"]
        db_host = self.database["HOST"]
        db_port = self.database["PORT"]
        return ["-h", str(db_host), "-p", str(db_port), "-U", str(db_user)]

    def create_backup_of_prd(self, backup_dir: Path = LOCAL_BACKUP_DIR) -> Path:
        """Create a backup of the database using pg_dump."""

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = backup_dir / f"pgsql_{self.database['NAME']}_{timestamp}.sql"

        logger.info(f"Creating backup at: {backup_file}")
        # Run pg_dump
        args = (
            ["pg_dump"]
            + self.default_args
            + [
                "-F",
                "c",  # custom format
                "-f",
                str(backup_file),
                prd_env_settings.DJANGO_DATABASE_NAME,
            ]
        )
        self._run_postgres_cmd(args=args)

        return backup_file

    def _run_postgres_cmd(self, args: list[str], raise_error: bool = True):
        """Run pg command"""

        # Set PG database password as env variable, it cannot be passed as argument.
        env = os.environ.copy()
        env["PGPASSWORD"] = self.database["PASSWORD"].get_secret_value()

        try:
            logger.debug(f"Running command: {args}")
            if self.dryrun:
                logger.info("Dry run enabled. Command execution skipped")
                return None
            result = subprocess.run(args, env=env, capture_output=True, text=True)
            if result.returncode != 0:
                stderr = result.stderr.strip()
                logger.error(f"{args} failed with exit code {result.returncode}")
                logger.error(f"stderr: {stderr}")
                if raise_error:
                    raise RuntimeError(f"Command {args} failed: {stderr}")

        except FileNotFoundError:
            raise FileNotFoundError(
                f"{args[0]}.exe not found. Make sure PostgreSQL bin directory (e.g. C:\\Program Files\\PostgreSQL\\17\\bin) is in your PATH (System Environment Variables)."
            )
        except Exception as e:
            raise Exception(f"Unexpected error during execution of {args[0]}.exe: {e}") from e
        logger.debug("cmd run succes")
        return result

    @validate_call
    def restore_backup(self, backup_file: Path) -> None:
        """Restore a backup file to a PostgreSQL database using pg_restore.
        Drops and creates the database before restoring.

        Parameters
        ----------
        backup_file : Path, optional, default is None
            Path to the backup file to restore. When None it will search the latest backup in BACKUP_DIR.
        """
        db_name = self.database["NAME"]

        if "test" not in db_name:
            raise RuntimeError("Refusing to overwrite database without 'test' in name.")

        logger.info(f"Dropping existing postgresdb if exists: {db_name}")

        args = ["dropdb"] + self.default_args + [str(db_name)]
        self._run_postgres_cmd(args=args, raise_error=False)

        logger.info(f"Creating new postgresdb: {db_name}")
        args = ["createdb"] + self.default_args + ["--template=template0", str(db_name)]
        self._run_postgres_cmd(args=args)

        logger.info(f"Restoring backup from: {backup_file}")
        args = ["pg_restore"] + self.default_args + ["--dbname", str(db_name), "--verbose", str(backup_file)]
        self._run_postgres_cmd(args=args, raise_error=False)

        logger.info(f"Finished restore of {db_name}")

    def backup_prd_and_restore_on_dev(self) -> None:
        """Create a backup of the database and optionally restore it."""
        backup_file = self.create_backup_of_prd()

        self.restore_backup(backup_file=backup_file)


# %%
if __name__ == "__main__":
    self = postgres_db = PostgresDatabase.from_env(dryrun=False)
    self.backup_prd_and_restore_on_dev()

# %%
