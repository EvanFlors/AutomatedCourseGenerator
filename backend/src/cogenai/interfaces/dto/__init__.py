from cogenai.interfaces.dto.contract import JSONOutputContract
from cogenai.interfaces.dto.course import CourseDTO
from cogenai.interfaces.dto.generation import GenerationMetadataDTO
from cogenai.interfaces.dto.generation_request import GenerationRequestDTO


def create_contract(
    course,
    job_id: str,
    provider: str = "gemini",
    model: str = "gemini-2.5-pro",
) -> JSONOutputContract:
    return JSONOutputContract(
        schema_version="1.0.0",
        course=CourseDTO.from_domain(course),
        generation=GenerationMetadataDTO(
            job_id=job_id,
            provider=provider,
            model=model,
        ),
    )