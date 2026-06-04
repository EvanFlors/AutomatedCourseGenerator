# Sprint 3 — Pipeline de generación de cursos (TEXT + URL)

> Estado: **completado**. El pipeline síncrono en proceso toma fuentes
> `TEXT` y `URL`, las divide en chunks, extrae conceptos y relaciones
> con un LLM pluggable (Gemini o Fake), calcula embeddings, y persiste
> el resultado en Neo4j. El estado del job se persiste en Postgres
> para monitoreo y recuperación.

## Resumen ejecutivo

| Métrica                              | Valor     |
| ------------------------------------ | --------- |
| Tests rápidos (sin Docker)           | **391**   |
| Tests reales (Docker, Neo4j)         | **20**    |
| **Total**                            | **411**   |
| Archivos de dominio (nuevos)         | 11        |
| Archivos de aplicación (nuevos)      | 1         |
| Archivos de infraestructura (nuevos) | 7         |
| Archivos de tests (nuevos)           | 9         |
| Migración Alembic                    | 1         |

> **Verificación rápida:**
> - `pytest -m "not requires_docker"` → 391 passed en ~2 s
> - `pytest -m requires_docker tests/integration/persistence/test_neo4j_real.py`
>   → 20 passed en ~30 s (incluye arranque de Neo4j)

## Arquitectura del pipeline

```
CourseGenerationService.run(job)            [application/services/]
  │
  ├─ 1. _stage_text_extraction(sources)    → TextExtractionRepository
  │       (TEXT: trimea; URL: httpx + trafilatura)
  │
  ├─ 2. _stage_chunking(sources)            → ChunkingService
  │       (SimpleChunker: char-based con detección de frontera oracional)
  │
  ├─ 3. _stage_concept_extraction(chunks)   → ConceptExtractionAgent
  │       (Pasa 1: extrae SOLO conceptos)
  │       gather(sem=concurrency) por chunk
  │       dedup por nombre.lower()
  │
  ├─ 4. _stage_relation_classification(...) → RelationClassificationAgent
  │       (Pasa 2: para cada chunk, filtra los conceptos cuyo
  │        nombre aparece en el texto y pide las relaciones
  │        entre ellos; dedup por (source, target, type) conservando
  │        el peso más alto)
  │
  ├─ 5. _stage_embeddings(concepts)        → EmbeddingService
  │       (embed_many en un solo call; mapea por nombre.lower())
  │
  └─ 6. _stage_persist(job, concepts, relations, embeddings)
          → KnowledgeGraphRepository
              (upsert_concepts + create_relations en lote vía UNWIND)
              metadata embebido: job_id, confidence, rationale
```

## 5 decisiones clave de Sprint 3

### 1. Orquestador síncrono en proceso, no cola

El servicio ejecuta los 6 stages dentro de un único `await
service.run(job)`. Es un *stateless orchestrator* — no hay worker,
no hay broker, no hay retries automáticos. La razón: para MVP
single-user, una cola es sobre-ingeniería. Si en Sprint 4+
necesitamos escalar, el JobRepository ya persiste el estado
(`PENDING → RUNNING → COMPLETED/FAILED`) y un worker externo puede
recoger jobs huérfanos con `find_orphaned_jobs()`.

**Trade-off:** si la API recibe muchos jobs concurrentes, cada
`run()` bloquea su event loop. Aceptable para MVP; no para producción.

### 2. LLM en dos pasadas con agentes enchufables

- **Pasa 1** (`ConceptExtractionAgent.extract_from_chunk`): solo
  nombres y descripciones. El prompt es específico al modelo.
- **Pasa 2** (`RelationClassificationAgent.classify_relations(chunk,
  concepts)`): recibe el chunk **y** los conceptos ya extraídos, y
  devuelve las aristas. El servicio filtra el chunk a los conceptos
  cuyo nombre aparece, evitando gastar tokens del LLM.

Ambos agentes son ports (Protocols); las implementaciones
`GeminiConceptExtractionAgent` y `GeminiRelationClassificationAgent`
viven en `src/infrastructure/integrations/llm/gemini_agents.py`.
Los tests del servicio usan `FakeConceptAgent` /
`FakeRelationAgent` (en `tests/integration/application/generation_fakes.py`)
que devuelven `ExtractionResult` deterministas.

**¿Por qué dos pasadas y no una sola?** En pruebas informales
(sin tests automatizados), un solo prompt que pide conceptos *y*
relaciones tiende a generar conceptos "fantasma" en las aristas
que no coinciden con los conceptos declarados, obligando a un
paso de post-procesado ruidoso. Separar las pasadas hace el
servicio responsable del *merge* limpio vía `ExtractionResult.merge()`.

### 3. Job persistido como JSON-serialized, no relacional

`CourseGenerationJob` se guarda en `course_generation_jobs` con
`sources_json TEXT` (la lista de `CourseSource` serializada). No
hay tabla `course_generation_job_sources`. Razón: las fuentes son
inmutables una vez que el job arranca, y no se consultan
individualmente (solo se ven como parte del job).

La columna `sources_json` se deserializa en
`SqlAlchemyCourseGenerationJobRepository._to_domain()` y se
re-serializa en `_to_orm()`. Tests round-trip en
`test_sqlalchemy_course_generation_job_repository.py` (10 tests).

**Trade-off:** no se puede consultar "todos los jobs que usaron la
fuente X" directamente. Aceptable para MVP; si se necesita,
agregar tabla relacional en Sprint 4.

### 4. Patrón port + Gemini + Fake para LLM y embeddings

`LLMClient` es el port (`abstract class` con `complete()` y
`complete_json()`). `GeminiLLMClient` usa `google-genai` 1.7.0
(`client.aio.models.generate_content`). `FakeLLMClient` registra
respuestas por substring de prompt (no por match exacto, lo que
permite reutilizar la misma respuesta para prompts similares).

```python
fake = FakeLLMClient()
fake.set_response(substring="list 3 concepts", text="ML\nDL\nRL")
result = await fake.complete("Please list 3 concepts related to AI...")
assert result == "ML\nDL\nRL"
```

`complete_json(prompt, PydanticModel, temperature)` parsea la salida
como JSON y la valida contra el modelo Pydantic. Los agentes
Gemini exponen `_ConceptList` / `_RelationList` (internos) que
`GeminiConceptExtractionAgent` y `GeminiRelationClassificationAgent`
usan para garantizar estructura de salida.

`FakeEmbeddingService` produce vectores de 4 dimensiones
deterministas vía hash del texto, lo que permite tests de
similitud coseno reproducibles sin red.

### 5. Estados explícitos del job, no "status" mágico

`CourseGenerationJob` usa una mini-máquina de estados:

```
PENDING ──mark_running──> RUNNING ──mark_completed──> COMPLETED
   │                          │
   │                          └──mark_failed──> FAILED
   │                                              │
   └──── mark_failed ─────────────────────────────┘
   (transición válida: PENDING → FAILED si las
    fuentes fallan al extraerse)
```

Reglas (todas testeadas):
- `add_source` solo funciona en `PENDING`.
- `mark_completed` requiere `RUNNING` y contadores ≥ 0.
- `mark_failed` no funciona en `COMPLETED` (job exitoso es final).
- `mark_running` no funciona en `COMPLETED` ni en `RUNNING`
  (no-op en este último caso, idem­potente).
- `duration_seconds` es `None` mientras el job no haya
  `mark_completed` o `mark_failed`.

## Estructura de carpetas (nueva en Sprint 3)

```
src/
├── application/
│   └── services/
│       └── course_generation_service.py
├── domain/
│   └── generation/
│       ├── __init__.py
│       ├── value_objects/
│       │   ├── job_status.py
│       │   └── source_type.py
│       ├── entities/
│       │   ├── course_generation_job.py
│       │   ├── course_source.py
│       │   ├── extracted_concept.py
│       │   ├── extracted_relation.py
│       │   └── extraction_result.py
│       └── repositories/
│           ├── chunking_service.py
│           ├── concept_extraction_agent.py
│           ├── course_generation_job_repository.py
│           ├── embedding_service.py
│           ├── relation_classification_agent.py
│           └── text_extraction_repository.py
└── infrastructure/
    ├── database/
    │   ├── models/course_generation_job_model.py
    │   └── repositories/
    │       └── sqlalchemy_course_generation_job_repository.py
    └── integrations/
        ├── chunking/simple_chunker.py
        ├── llm/
        │   ├── gemini_agents.py
        │   ├── gemini_embedding_service.py
        │   └── llm_client.py
        └── text_extraction/text_source_extractor.py

migrations/
└── versions/
    └── 8c2a4f9b1d3e_add_course_generation_jobs_table.py
```

## Tests añadidos en Sprint 3

| Archivo                                                          | #  | Tipo        |
| ---------------------------------------------------------------- | -- | ----------- |
| `tests/unit/domain/generation/value_objects/` (2 archivos)      | 28 | unit        |
| `tests/unit/domain/generation/entities/` (5 archivos)            | 56 | unit        |
| `tests/integration/chunking/test_simple_chunker.py`              | 11 | integration |
| `tests/integration/application/test_course_generation_service.py`| 14 | integration |
| `tests/integration/persistence/test_sqlalchemy_course_generation_job_repository.py` | 10 | integration |
| `tests/smoke/test_domain_imports.py` (extendido)                 | 6  | smoke       |
| **Total Sprint 3**                                               |**125** |            |

Adicionalmente, en Sprint 2 polish + futuros:

| Archivo                                                          | #  | Tipo        |
| ---------------------------------------------------------------- | -- | ----------- |
| `tests/integration/persistence/test_neo4j_knowledge_graph_repository.py` (batch + paginación + concurrencia) | +20 | integration |
| `tests/integration/persistence/test_neo4j_real.py` (vector + concurrencia) | +9 | integration |
| **Total Sprint 2 polish + futuros**                              |**29** |            |

## Cómo correr los tests

```bash
# Solo rápidos (sin Docker) — loop interno, < 5 s
pytest -m "not requires_docker"

# Solo los reales con Neo4j — requiere Docker corriendo
pytest -m requires_docker

# Solo el orquestador
pytest tests/integration/application/test_course_generation_service.py -v

# Solo el chunker
pytest tests/integration/chunking/test_simple_chunker.py -v

# Solo el job repository
pytest tests/integration/persistence/test_sqlalchemy_course_generation_job_repository.py -v
```

## Bug del test de vector index (resuelto)

En la primera corrida completa de los tests reales, `TestVectorIndex`
colgaba de forma intermitente. La causa raíz fue una **incompatibilidad
de dimensiones** entre el `vector.dimensions: 1536` hard-codeado en
el schema y los embeddings de prueba de 3 dimensiones.

Neo4j 5.26-community **valida las dimensiones en el momento del
SET** cuando hay un vector index sobre la propiedad. Cuando la
propiedad se escribe con dimensiones distintas a las del index,
Neo4j encola la escritura y el test `SHOW INDEXES` queda esperando.

**Fix aplicado:**
- El repositorio ahora acepta `vector_dimensions` en el constructor
  (default 768, alineado con `text-embedding-004` de Gemini).
- Los tests reales crean el repo con `vector_dimensions=3` para
  coincidir con sus fixtures pequeñas.
- `GeminiEmbeddingService.DIMENSIONS = 768` se mantiene como la
  única fuente de verdad para producción.

## Lecciones aprendidas (a recordar en Sprint 4)

1. **`ExtractionResult._unsafe`**: el `merge()` necesita saltarse la
   validación del constructor porque los componentes ya fueron
   validados individualmente. Sin el bypass, un test que construye
   `result.relations.append(orphan)` y luego `merge()` no puede
   verificar la lógica de "dropear huérfanos". La forma idiomática
   es usar `__new__` + atributos directos; la validación se delega
   a los componentes.

2. **`InMemoryJobRepository._snapshot`**: el repo fake debe copiar
   el job en cada `save()` para preservar el historial de
   transiciones. Sin la copia, todas las entradas en `history`
   apuntan al mismo objeto mutado, y `mark_running` /
   `mark_completed` colapsan en un solo estado final.

3. **Servicio: chunks con conceptos**: `_stage_relation_classification`
   filtra los chunks a los que contienen al menos un concepto
   extraído. Si el texto de prueba no contiene los nombres
   literales de los conceptos, la lista filtrada queda vacía y no
   se generan relaciones — **los tests deben usar texto que
   contenga los nombres**.

4. **Concurrencia con `asyncio.gather` + `asyncio.Semaphore`**: el
   orquestador limita la concurrencia a un valor configurable
   (default 4) usando un semáforo por gather. Esto evita agotar
   las cuotas de la API del LLM con jobs grandes.

5. **Service wrappea `save()` en try/except**: durante los stages,
   un fallo al guardar el job no debe enmascarar el error real del
   stage. `_safe_save()` traga excepciones del repo y deja que la
   excepción original se propague.

6. **Test fixture text debe mencionar conceptos**: en
   `test_course_generation_service.py::test_relations_are_persisted`,
   el texto de las fuentes debe incluir los nombres de los
   conceptos extraídos (e.g. `"ML and DL are related"`), si no, la
   pasa 2 no genera relaciones y el test falla sin error claro.

## Trabajo futuro (backlog)

### Sprint 4: HTTP layer
- Endpoints REST: `POST /courses/{id}/generate`, `GET /jobs/{id}`,
  `GET /jobs?course_id=...`.
- Middleware de error que serializa `ValidationError` → 400,
  `NotFoundError` → 404, `GenerationError` → 500.
- Inyección de dependencias: factory de FastAPI que arma el grafo
  de servicios (ServiceContainer).

### Sprint 4: WebSocket / SSE
- Stream de progreso del job (por stage) para que el viewer React
  muestre una barra de progreso en tiempo real.

### Backlog técnico
- **YouTube y PDF sources**: agregar extractores en
  `infrastructure/integrations/text_extraction/`, extender
  `SourceType` con sus validadores.
- **Retry con backoff exponencial** en el orquestador para fallos
  transitorios del LLM.
- **Rate limiting** en la capa de aplicación (token bucket).
- **Pydantic schemas en el fake driver** (item #6 de SPRINT2_NOTES):
  agregar `ConceptRecord` / `RelationRecord` para que el fake
  valide la forma de las respuestas al construirlas, no solo al
  recibirlas. Útil cuando se hagan tests de "el adapter nunca
  emite un query que devuelva `None` en un campo obligatorio".
- **Vector search real** (e.g. `db.index.vector.queryNodes`): una
  vez que tengamos ≥ 100 conceptos por curso, agregar endpoint
  de búsqueda semántica.
- **Migración de jobs huérfanos**: un job en `RUNNING` por más de
  N minutos se considera muerto y se puede reintentar.
- **Observabilidad**: logging estructurado con `structlog`,
  tracing con OpenTelemetry, métricas Prometheus.
- **Persistencia del resultado del job**: actualmente solo se
  guardan contadores. Agregar tabla `job_results` con los
  conceptos/relaciones extraídos para auditoría.
