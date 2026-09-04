import logging

from dotenv import load_dotenv


load_dotenv()


def setup_logging(level: int = logging.INFO):
    """
    Configure the application-wide logging setup.
    Idempotent so multiple imports are safe.
    """

    root = logging.getLogger()

    # Avoid re-adding handlers on repeated calls.
    if any(
        isinstance(h, logging.StreamHandler)
        and not isinstance(h, logging.FileHandler)
        for h in root.handlers
    ):
        return root

    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s "
        "%(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    stream = logging.StreamHandler()
    stream.setFormatter(formatter)

    root.setLevel(level)
    root.addHandler(stream)

    # Keep third-party library logs from flooding output.
    for noisy in (
        "sentence_transformers",
        "chromadb",
        "httpx",
        "urllib3",
    ):
        logging.getLogger(noisy).setLevel(
            logging.WARNING
        )

    return root


def get_logger(name: str) -> logging.Logger:
    """
    Return a configured logger for the given module.
    """
    setup_logging()
    return logging.getLogger(name)
