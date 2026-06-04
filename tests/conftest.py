import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture
def sample_course_title() -> str:
    return "Introduction to Machine Learning"


@pytest.fixture
def sample_module_title() -> str:
    return "Foundations"


@pytest.fixture
def sample_topic_title() -> str:
    return "What is supervised learning?"


@pytest.fixture
def sample_block_payload() -> dict:
    return {"text": "Supervised learning uses labeled data."}
