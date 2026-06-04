from enum import Enum


class SourceType(str, Enum):
    """The kind of input a `CourseSource` represents.

    The MVP of the generation pipeline supports TEXT (raw text pasted
    by the user) and URL (a web page whose content is extracted).
    YOUTUBE and PDF are planned for follow-up sprints.
    """

    TEXT = "text"
    URL = "url"
    YOUTUBE = "youtube"
    PDF = "pdf"
