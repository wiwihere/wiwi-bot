# %%
import os
import sys
from pathlib import Path

import django
from dotenv import load_dotenv

load_dotenv(Path(__file__).parents[2] / ".env")
if os.environ["PYTHONPATH"].lower() not in sys.path:
    sys.path.insert(0, os.environ["PYTHONPATH"].lower())

django.setup()
