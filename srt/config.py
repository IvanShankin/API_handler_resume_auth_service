from datetime import timedelta
import logging
from pathlib import Path

MAX_ACTIVE_SESSIONS = 5
MAX_ATTEMPTS_ENTER = 5
LOGIN_BLOCK_TIME = timedelta(seconds=300)  # Период блокировки

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "auth_service.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)