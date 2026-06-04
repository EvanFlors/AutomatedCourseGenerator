# Sprint 2 — Notas de arquitectura: knowledge graph

Documento de referencia del bounded context `knowledge_graph` y su adaptador
Neo4j. Cubre las decisiones de diseño que no son obvias mirando el código,
los trade-offs conocidos y los comandos de test.

## Resumen ejecutivo

- Se introdujo el bounded context `knowledge_graph` (nodos `Concept`,
  aristas tipadas `ConceptRelation`) en `src/domain/knowledge_graph/`.
- Se implementó el port `KnowledgeGraphRepository` y su adaptador
  `Neo4jKnowledgeGraphRepository` con Cypher en
  `src/infrastructure/persistence/neo4j/`.
- Se endureció el fake driver (`tests/integration/persistence/neo4j_fakes.py`)
  con matching exacto, colas de respuestas, modo estricto y helpers
  `find_call` / `find_calls`.
- Se añadieron 25+ tests nuevos cubriendo edge cases (unicode, weights,
  multi-curso, bulk ops, round-trip de metadata).
- Tests E2E contra Neo4j real vía testcontainers, gated por
  `@pytest.mark.requires_docker`.

## Capas

### Dominio (`src/domain/knowledge_graph/`)

Sin dependencias de infraestructura. Solo importa de `domain.shared`.

- `value_objects/relation_type.py`: enum `str` con 4 tipos
  (`BELONGS_TO`, `PREREQUISITE_OF`, `RELATED_TO`, `EXTENDS`).
- `entities/concept.py`: nodo con `id`, `name`, `description`, `embedding`,
  refs opcionales a topic/curso, `metadata`. Validaciones:
  - `name` no puede ser vacío.
  - `embedding` no puede ser una lista vacía.
- `entities/concept_relation.py`: arista dirigida con `id`, `source`,
  `target`, `type`, `weight>=0`, `metadata`. Validaciones:
  - `source` y `target` no pueden ser idénticos (no self-loops).
  - `weight` no puede ser negativo.
  - `relation_type` debe ser un `RelationType`.
- `repositories/knowledge_graph_repository.py`: port con 7 métodos:
  `upsert_concept`, `find_concept_by_id`, `list_concepts_by_course`,
  `delete_concept`, `create_relation`, `delete_relations_for_concept`,
  `get_graph_for_course`.

### Infraestructura (`src/infrastructure/persistence/neo4j/`)

- `driver.py`: factoría del `AsyncDriver` oficial de `neo4j`. Expone
  `create_driver()`, `get_driver()` (lazy singleton), `reset_driver()`,
  `verify_connectivity()`. La configuración viene de `Settings` en
  `src/bootstrap/settings.py`.
- `neo4j_knowledge_graph_repository.py`: adaptador que implementa el port.
  Crea el schema lazily: 1 `CREATE CONSTRAINT` + 2 `CREATE INDEX`
  (course_id y topic_id), idempotentes con `IF NOT EXISTS`.

## Decisiones de diseño

### 1. Metadata como `metadata_json` (string JSON)

**Problema.** Neo4j solo permite tipos primitivos y arrays como
propiedades de nodo. Un `dict` Python con tipos anidados (listas,
dicts anidados) lanza `CypherTypeError`.

**Solución.** Serializar como string JSON en escritura y deserializar
en lectura. El dominio sigue trabajando con `dict` Python; el mapeo
es 100% responsabilidad del adaptador.

```python
await session.run("...", metadata_json=_json_dumps(concept.metadata))
# ...
metadata=_json_loads(record.get("metadata_json"))
```

**Trade-off conocido.** No se puede hacer query Cypher sobre campos
de metadata (ej. `WHERE c.metadata.category = 'video'`). Si lo
necesitamos en el futuro: cambiar a nodos hijos
`(c:Concept)-[:HAS_METADATA]->(m:Meta)` o usar Neo4j 5.x map types
(experimental).

### 2. Schema setup lazy y singleton por repositorio

`_ensure_schema()` corre en cada operación pero solo ejecuta los 3
`CREATE CONSTRAINT/INDEX` la primera vez (flag `self._initialized`).

**Por qué no en `__init__`?** La creación de constraints es async.
Hacerlo en el constructor bloquearía hasta que el driver esté
conectado. Lazy es más limpio y permite tests que construyen
repositorios sin driver real.

**Por qué no por sesión?** Cada llamada al port abre una sesión
nueva (igual que el driver oficial). Si el setup corriera por
sesión, serían 3 queries extra por cada `upsert` / `find` / etc.
Con el flag de instancia, las queries solo se ejecutan la primera
vez en toda la vida del repositorio.

### 3. `MERGE` con tipo de relación dinámico

```cypher
MATCH (a:Concept {id: $source_id})
MATCH (b:Concept {id: $target_id})
MERGE (a)-[r:PREREQUISITE_OF]->(b)
SET r.id = $id,
    r.weight = $weight,
    r.metadata_json = $metadata_json
```

`r:RELATION_TYPE` se interpola en Python (no es parámetro) porque
Cypher no acepta tipos de relación como `$param`. Esto es seguro
porque `RelationType` es un enum cerrado (4 valores), no input de
usuario.

### 4. `get_graph_for_course` en dos queries

1. Conceptos del curso:
   `MATCH (c:Concept {source_course_id: $course_id}) RETURN c`.
2. Relaciones internas:
   `MATCH (a)-[r]->(b) WHERE a.id IN $ids AND b.id IN $ids`
   con los IDs del paso 1.

Si no hay conceptos, se evita la segunda query
(devuelve `([], [])` directamente).

**Trade-off.** Dos round-trips a la base. Si tenemos 10k conceptos
por curso, considerar una sola query con `OPTIONAL MATCH`:

```cypher
MATCH (c:Concept {source_course_id: $id})
OPTIONAL MATCH (c)-[r]->(b:Concept)
WHERE b.source_course_id = $id
RETURN c, r, b
```

Por ahora (MVP) los cursos típicos tienen <200 conceptos, así que
dos round-trips es aceptable.

### 5. `_collect_records` con doble compatibilidad

Función helper que maneja los dos modos (fake y real):

```python
if hasattr(result, "fetch_all"):
    records = await result.fetch_all()  # fake
else:
    async for record in result:          # real driver
        ...
```

`AsyncResult` del driver oficial **no** expone `fetch_all`. La única
API es `async for`, `await .single()`, `await .consume()`. Esta fue
la causa del fallo en el primer run de tests reales (ya corregido).

## Fake driver (`tests/integration/persistence/neo4j_fakes.py`)

### Modos de uso

1. **Recording-only (default).** Crea el driver sin respuestas.
   Cada `session.run()` registra en `session.calls` y devuelve un
   resultado vacío. Útil para tests que solo verifican qué queries
   se enviaron.
2. **Respuestas estáticas.** Pasa
   `responses={"substring": [record1, record2]}` para devolver esos
   records cuando una query contenga ese substring. Se devuelve el
   mismo batch en cada match (lookup: exact match primero, luego
   substring en orden de inserción).
3. **Cola de respuestas.** Pasa
   `responses={"substring": [[...batch1], [...batch2]]}` para
   devolver batches diferentes en llamadas sucesivas. Cada call hace
   pop del primer batch.
4. **Strict mode.** Pasa `strict=True` y cualquier query sin
   respuesta programada lanza `RuntimeError` con mensaje claro
   (`Programmed keys: [...]`). Útil para tests que quieren asegurar
   que el repository llama exactamente las queries esperadas.

### Helpers de la sesión

- `session.find_call(substring=..., query=..., params=...)`
  Primera call que matchea. Falla con mensaje útil si no encuentra.
- `session.find_calls(substring=..., query=...)`
  Todas las calls que matchean.
- `session.calls` Lista cruda de `(query, params)`.

### Helpers del driver

- `driver.find_session(index=0)` Sesión por índice.
- `driver.sessions` Lista de todas las sesiones creadas.
- `FakeNeo4jDriver(responses=..., strict=...)` Parametriza el
  comportamiento por defecto para todas las sesiones nuevas.

### Cobertura del fake

- `run(query, **params)`, `single()`, `fetch_all()`, `consume()`,
  `close()`.
- Context manager (`async with self._driver.session() as session:`).
- Cero dependencias externas (no usa el driver oficial de neo4j).

## Tests

### Totales

- 44 tests fake-driver
  (`tests/integration/persistence/test_neo4j_knowledge_graph_repository.py`):
  deterministas, ~0.1s total.
- 11 tests real-Neo4j
  (`tests/integration/persistence/test_neo4j_real.py`):
  container start ~10s + tests ~5s, gated por
  `@pytest.mark.requires_docker`.
- 71 tests unitarios de dominio
  (`tests/unit/domain/knowledge_graph/`).
- Total proyecto: 262 tests pasan sin Docker, 273 con Docker.

### Markers

- `@pytest.mark.asyncio` (auto por `asyncio_mode = "auto"`).
- `@pytest.mark.requires_docker` — registrado en `pyproject.toml` con
  `--strict-markers`. Los tests que lo usan se saltan automáticamente
  si Docker no está disponible.

### Comandos

```bash
# Solo tests rápidos (sin Docker)
pytest -m "not requires_docker"

# Solo tests reales (requiere Docker)
pytest -m requires_docker tests/integration/persistence/test_neo4j_real.py -v

# Todos (incluye Docker si está disponible)
pytest
```

## Estructura de archivos

```
src/
├── domain/knowledge_graph/
│   ├── entities/
│   │   ├── concept.py
│   │   └── concept_relation.py
│   ├── value_objects/
│   │   └── relation_type.py
│   └── repositories/
│       └── knowledge_graph_repository.py
└── infrastructure/persistence/neo4j/
    ├── driver.py
    └── neo4j_knowledge_graph_repository.py

tests/
├── unit/domain/knowledge_graph/
│   ├── test_concept.py
│   ├── test_concept_relation.py
│   └── test_relation_type.py
└── integration/persistence/
    ├── neo4j_fakes.py
    ├── test_neo4j_knowledge_graph_repository.py
    └── test_neo4j_real.py
```

## Conocidos / Trabajo futuro

- **Sin constraint en `Concept.source_course_id`** (solo índice). Si
  dos cursos crean conceptos con IDs iguales habría conflicto — la
  uniqueness constraint en `id` lo previene. Considerar índice
  compuesto `(source_course_id, name)` para queries por nombre dentro
  de un curso.
- **`get_graph_for_course` no pagina.** Cursos con >1000 conceptos
  pueden ser lentos. Añadir `LIMIT $skip, $limit` si hace falta.
- **No hay operaciones en batch** (`upsert_concepts(list)`). Si en
  Sprint 3 necesitamos insertar cientos de conceptos a la vez,
  añadir `UNWIND $batch AS row MERGE ...` para reducir round-trips.
- **El fake driver no valida** que los tipos de los records
  programados coincidan con lo que el repositorio espera. Si el test
  programa mal, el fallo aparece lejos. Considerar Pydantic schemas
  en el fake (ej. `ConceptRecord`) para validación temprana.
- **No hay tests de concurrencia** (múltiples `upsert_concept` en
  paralelo). El driver oficial es thread-safe; el repositorio
  debería serlo también, pero no está probado.
- **El embedding se almacena como lista cruda** en Neo4j. Cuando
  llegue el Sprint de embeddings reales, considerar usar el tipo
  vectorial nativo de Neo4j 5.x (si está disponible en la versión
  community) para poder hacer ANN search con
  `db.index.vector.queryNodes`.

## Lecciones aprendidas

1. **Neo4j `AsyncResult` no tiene `fetch_all`.** Documentado en
   `_collect_records` y en commit history. Cualquier helper nuevo
   que itere sobre resultados debe usar `async for` + `consume()`.
2. **`MERGE` con tipo dinámico solo es seguro si el tipo viene de
   un enum cerrado**, no de input de usuario. Si en el futuro
   `RelationType` se vuelve dinámico, parametrizar el tipo vía
   `apoc.create.relationship` (procedimiento APOC).
3. **El primer test E2E real casi siempre falla por una API sutil
   del driver.** Vale la pena invertir en tests reales aunque los
   fakes sean muy completos — capturan errores que el fake no
   puede anticipar.
4. **El fake driver creció de 89 a 178 líneas** durante el polish.
   Es una inversión que paga: tests más legibles, errores más
   claros, y un fixture reutilizable para futuros adaptadores
   (Redis, Elasticsearch, etc.).
