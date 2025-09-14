from __future__ import annotations

import os
from dotenv import load_dotenv


def load_env() -> None:
    if not os.getenv("ENV_LOADED"):
        load_dotenv(override=False)
        os.environ["ENV_LOADED"] = "1"
