from enum import Enum

class BlockType(str, Enum):
    HEADING = "heading"
    TEXT = "text"
    CODE = "code"
    IMAGE = "image"
    QUOTE = "quote"
    DIVIDER = "divider"