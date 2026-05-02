from dataclasses import dataclass


@dataclass
class DataError:
    source: str
    message: str


__all__ = ["DataError"]
