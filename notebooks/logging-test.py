import sys 
from pathlib import Path

current_file = Path(__file__)
current_folder = current_file.parent
project_root = current_folder.parent

sys.path.insert(0, str(project_root))

from src.config.logging import configure_logging, get_logger, set_request_id, set_user_id, set_project_id, clear_context

configure_logging()

logger = get_logger(__name__)

# no context yet
logger.info("before_context", note="should have no request/user id")

# simulate what middleware and auth do
set_request_id("test-req-123")
set_user_id("test-user-456")
logger.info("with_Context", note="should have request_id and user_id")

clear_context()
logger.info("after_clear", note="context should be gone again")
