import logging
import os


# Quiet by default; set OIL_LOG_LEVEL=DEBUG (or INFO) to see internals such as
# raw Ollama responses or embedding-model fallbacks.
_LEVEL = os.environ.get("OIL_LOG_LEVEL", "WARNING").upper()


def get_logger(name):

    logger = logging.getLogger(name)

    if not logger.handlers:

        handler = logging.StreamHandler()

        handler.setFormatter(
            logging.Formatter("[%(levelname)s] %(name)s: %(message)s")
        )

        logger.addHandler(handler)

        logger.setLevel(
            getattr(logging, _LEVEL, logging.WARNING)
        )

        logger.propagate = False

    return logger
