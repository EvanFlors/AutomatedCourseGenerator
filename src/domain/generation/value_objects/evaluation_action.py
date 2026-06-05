from enum import Enum


class EvaluationAction(str, Enum):
    """What the evaluator recommends the generator should do."""

    APPROVE = "approve"
    REVISE_MODULE = "revise_module"
    ADD_MODULE = "add_module"
    REMOVE_MODULE = "remove_module"
    REVISE_TOPIC = "revise_topic"
    ADD_TOPIC = "add_topic"
    REMOVE_TOPIC = "remove_topic"
    REVISE_BLOCK = "revise_block"
    ADD_BLOCK = "add_block"
    REMOVE_BLOCK = "remove_block"
    REVISE_TITLE = "revise_title"
    REVISE_LEVEL = "revise_level"
