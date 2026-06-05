from enum import StrEnum


class BlockType(StrEnum):
    HEADING = "heading"
    TEXT = "text"
    CODE = "code"
    IMAGE = "image"
    QUOTE = "quote"
    DIVIDER = "divider"
