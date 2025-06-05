import logging

logging.basicConfig(
    level=logging.INFO,
    filename="Api.log",
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)