# Guía Completa de Pruebas con pytest

> Una guía exhaustiva, de fundamentos a conceptos avanzados, para dominar el framework de pruebas más popular de Python. Cada concepto va acompañado de ejemplos prácticos y ejecutables.

## Tabla de contenidos

1. [Introducción](#1-introducción)
2. [Instalación y configuración](#2-instalación-y-configuración)
3. [Tu primera prueba](#3-tu-primera-prueba)
4. [Aserciones](#4-aserciones)
5. [Organización de tests](#5-organización-de-tests)
6. [Ejecución desde la línea de comandos](#6-ejecución-desde-la-línea-de-comandos)
7. [Fixtures](#7-fixtures)
8. [Parametrización](#8-parametrización)
9. [Markers (marcadores)](#9-markers-marcadores)
10. [Pruebas asíncronas](#10-pruebas-asíncronas)
11. [Mocking y monkeypatching](#11-mocking-y-monkeypatching)
12. [Cobertura de código](#12-cobertura-de-código)
13. [Patrones y mejores prácticas](#13-patrones-y-mejores-prácticas)
14. [Conceptos avanzados](#14-conceptos-avanzados)
15. [Plugins útiles](#15-plugins-útiles)
16. [Integración con CI/CD](#16-integración-con-cicd)
17. [Debugging de tests](#17-debugging-de-tests)
18. [Glosario](#18-glosario)

---

## 1. Introducción

### 1.1 ¿Qué son las pruebas automatizadas?

Las pruebas automatizadas son **piezas de código que ejecutan otros trozos de código** para verificar que se comportan como esperamos. En lugar de abrir la aplicación, escribir datos a mano y comprobar visualmente el resultado, escribimos un programa que lo hace por nosotros y emite un veredicto **PASSED** o **FAILED**.

### 1.2 Tipos de pruebas (pirámide de pruebas)

La **pirámide de pruebas** clasifica los tests en niveles según su velocidad, coste y nivel de detalle:

```
        /\
       /  \         E2E (end-to-end): pocas, lentas, costosas
      /----\        Prueban el sistema completo (UI, HTTP, DB real)
     /      \
    /--------\      Integración: moderadas
   /          \     Prueban varios módulos juntos (DB, API, etc.)
  /------------\
 /              \   Unitarias: muchas, rápidas, baratas
/________________\  Prueban una sola unidad (función, clase) aislada
```

- **Smoke tests**: subtipo rápido que verifica que la aplicación arranca y los imports funcionan. Sirve como "red de seguridad" mínima.
- **Tests unitarios (unit tests)**: prueban **una sola unidad lógica** sin tocar I/O (disco, red, base de datos, tiempo). Son los más rápidos y los más numerosos.
- **Tests de integración (integration tests)**: prueban la interacción entre varios módulos, a menudo con bases de datos reales o en contenedores.
- **Tests E2E (end-to-end)**: prueban el sistema completo desde la perspectiva del usuario (click → resultado).

### 1.3 ¿Por qué pytest?

pytest es el framework de testing más usado en Python. Ventajas frente al `unittest` de la librería estándar:

| Característica | unittest | pytest |
|---|---|---|
| Sintaxis | Clases que heredan de `TestCase` | Funciones simples con `assert` |
| Aserciones | `self.assertEqual(a, b)` | `assert a == b` (con introspección) |
| Fixtures | `setUp` / `tearDown` | Inyección declarativa, composable |
| Parametrización | Verbosa (`subTest`) | `@pytest.mark.parametrize` |
| Plugins | Limitado | Ecosistema enorme (700+ plugins) |
| Output | Básico | Coloreado, traceback mejorado, diff |

> **Regla mnemotécnica**: si puedes escribirlo como una función, hazlo como una función. Las clases en pytest son **opcionales** y se usan solo para agrupar visualmente.

### 1.4 Filosofía de pytest

pytest aplica tres principios:

1. **Las pruebas deben ser fáciles de escribir** → usa `assert` directo, sin boilerplate.
2. **Las pruebas deben ser fáciles de leer** → el nombre del test debe describir el comportamiento.
3. **Las pruebas deben ser fáciles de ejecutar** → un solo comando corre todo.

---

## 2. Instalación y configuración

### 2.1 Instalación

```bash
# Instalación mínima
pip install pytest

# Con plugins comunes
pip install pytest pytest-cov pytest-mock pytest-asyncio
```

En el proyecto `course-automation` ya está declarado en `pyproject.toml`:

```toml
[project.optional-dependencies]
dev = [
    "pytest>=8.3.3",
    "pytest-asyncio>=0.24.0",
    "pytest-cov>=5.0.0",
    ...
]
```

Para instalar todo el entorno de desarrollo:

```bash
pip install -e ".[dev]"
```

> El flag `-e` instala el proyecto en **modo editable**: cualquier cambio en `src/` se refleja sin reinstalar.

### 2.2 Verificar la instalación

```bash
pytest --version
# pytest 8.3.3
```

### 2.3 Configuración en `pyproject.toml`

pytest busca configuración en varios archivos (`pytest.ini`, `setup.cfg`, `tox.ini`, `pyproject.toml`). Recomendamos centralizar en `pyproject.toml` con la sección `[tool.pytest.ini_options]`:

```toml
[tool.pytest.ini_options]
# Mínimo que pytest va a descubrir y ejecutar
testpaths = ["tests"]

# Hace accesibles los módulos del proyecto sin instalar
pythonpath = ["."]

# Modo estricto para async/await (pytest-asyncio)
asyncio_mode = "auto"

# Argumentos por defecto al ejecutar `pytest`
addopts = "-v --strict-markers --tb=short"
```

**Campos clave explicados:**

- `testpaths`: directorios donde pytest busca tests. Si no se define, busca desde la raíz.
- `pythonpath`: añade rutas al `sys.path`. Esencial para proyectos que usan `src/` layout.
- `asyncio_mode = "auto"`: le dice a `pytest-asyncio` que trate **toda** función `async def` como test, sin necesidad del marker.
- `--strict-markers`: falla si usas un marker no registrado. Evita typos.
- `--tb=short`: tracebacks concisos (vs. `--tb=long` que muestra todo).

### 2.4 Estructura de directorios recomendada

Existen dos layouts comunes:

#### Layout plano (sencillo, paquetes pequeños)

```
proyecto/
├── src/
│   └── paquete/
└── tests/
    ├── test_a.py
    └── test_b.py
```

#### Layout anidado (paquetes con bounded contexts, recomendado para Clean Architecture)

```
proyecto/
├── src/
│   └── paquete/
│       ├── domain/
│       ├── application/
│       └── infrastructure/
└── tests/
    ├── unit/
    │   └── domain/
    │       └── course/
    │           ├── entities/
    │           │   ├── test_course.py
    │           │   └── test_module.py
    │           └── enums/
    │               └── test_block_type.py
    ├── integration/
    └── smoke/
        └── test_imports.py
```

> **Regla de oro**: la estructura de tests **debe espejar** la estructura del código que prueban. Si un archivo está en `src/domain/course/entities/course.py`, su test está en `tests/unit/domain/course/entities/test_course.py`.

### 2.5 Convenciones de nombres

pytest descubre tests siguiendo estas reglas:

| Elemento | Convención | Ejemplo |
|---|---|---|
| Archivos de test | `test_*.py` o `*_test.py` | `test_course.py` |
| Funciones de test | `test_*` | `test_creates_course_with_title` |
| Clases de test | `Test*` (sin `__init__`) | `TestCourseValidation` |
| Métodos de clase | `test_*` | `test_raises_error_on_empty_title` |
| Fixtures | Cualquier nombre | `sample_course`, `db_session` |
| `conftest.py` | Siempre `conftest.py` (literal) | `tests/conftest.py` |

Si un archivo o función no sigue estas convenciones, pytest **lo ignora silenciosamente**. Para evitar sustos, usa `--strict-config`.

---

## 3. Tu primera prueba

### 3.1 El test más simple posible

```python
# tests/test_sample.py

def test_uno_mas_uno_es_dos():
    assert 1 + 1 == 2
```

```bash
$ pytest tests/test_sample.py
============== test session starts ==============
collected 1 item

tests/test_sample.py .                       [100%]

============== 1 passed in 0.01s ===============
```

El punto (`.`) indica un test pasado. Si fallara, verías una `F`:

```
tests/test_sample.py F                       [100%]

================================== FAILURES ===================================
_ test_uno_mas_uno_es_dos _

    def test_uno_mas_uno_es_dos():
>       assert 1 + 1 == 3
E       assert 2 == 3
E        +  where 2 = 1 + 1

1 failed in 0.01s
```

pytest usa **introspección** para mostrar el valor real (`2`) y el valor comparado (`3`), no solo "AssertionError". Esta es una de las razones por las que pytest es superior a `unittest`.

### 3.2 Probando algo real del proyecto

```python
# tests/test_course_smoke.py
from src.domain.course.entities.course import Course

def test_crear_curso_minimo():
    curso = Course(title="Introducción a Python")

    assert curso.id is not None
    assert curso.title == "Introducción a Python"
    assert curso.description is None
    assert curso.modules == []
```

### 3.3 Probando que algo falla (negativo)

```python
import pytest
from src.domain.course.entities.course import Course
from src.domain.shared.exceptions.validation_error import ValidationError


def test_curso_con_titulo_vacio_falla():
    with pytest.raises(ValidationError):
        Course(title="")
```

`pytest.raises` es un **context manager** que asegura que el bloque **sí lanza** la excepción esperada. Si no la lanza, el test falla.

---

## 4. Aserciones

pytest reescribe el bytecode de los `assert` para producir **introspección rica**. Por eso `assert a == b` muestra los valores, no solo el operador.

### 4.1 Aserciones básicas

```python
def test_ejemplos_aserciones():
    # Igualdad
    assert 2 + 2 == 4

    # Desigualdad
    assert "hola" != "adios"

    # Verdadero / falso
    assert True
    assert not False

    # Pertenencia
    assert 3 in [1, 2, 3]
    assert "x" not in "abc"

    # Identidad (es el mismo objeto en memoria)
    a = [1, 2]
    b = a
    assert a is b

    # Comparación
    assert 5 > 3
    assert 1 <= 2 <= 3

    # Tipo
    assert isinstance("hola", str)
```

### 4.2 Aserciones sobre strings

```python
def test_strings():
    texto = "Curso de Python"

    assert texto.startswith("Curso")
    assert texto.endswith("Python")
    assert "de" in texto
```

### 4.3 Aserciones sobre colecciones

```python
def test_listas():
    items = [1, 2, 3, 4, 5]

    assert len(items) == 5
    assert items[0] == 1
    assert items[-1] == 5
    assert 3 in items
    assert items == [1, 2, 3, 4, 5]
    assert items != [5, 4, 3, 2, 1]


def test_dicts():
    config = {"host": "localhost", "port": 5432}

    assert config["host"] == "localhost"
    assert "port" in config
    assert config.keys() >= {"host", "port"}
```

### 4.4 Mensajes personalizados en aserciones

```python
def test_con_mensaje():
    bloques = []

    assert len(bloques) > 0, f"Se esperaban bloques, pero hay {len(bloques)}"
```

El mensaje solo se muestra **si falla** (es como el `msg=` de unittest pero menos verboso).

### 4.5 Aserciones aproximadas (floats)

Nunca compares floats con `==` por errores de redondeo:

```python
def test_float():
    resultado = 0.1 + 0.2

    # MAL
    assert resultado == 0.3  # 0.30000000000000004 != 0.3

    # BIEN: usar pytest.approx
    assert resultado == pytest.approx(0.3)
```

### 4.6 Aserciones con regex

```python
import re

def test_curso_genera_uuid():
    curso = Course(title="X")

    assert re.match(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
        curso.id,
    )
```

---

## 5. Organización de tests

### 5.1 Funciones sueltas (estilo funcional)

```python
def test_curso_acepta_descripcion():
    curso = Course(title="X", description="desc")
    assert curso.description == "desc"


def test_curso_rechaza_titulo_vacio():
    with pytest.raises(ValidationError):
        Course(title="")
```

**Ventaja:** Simple, plano, fácil de leer.
**Desventaja:** Si tienes 50 tests para `Course`, el archivo se vuelve un caos.

### 5.2 Clases agrupadoras (recomendado)

Las clases en pytest **no son obligatorias** (a diferencia de unittest), pero son útiles para **agrupar visualmente** tests relacionados y compartir fixtures/helpers de clase.

```python
class TestCourseValidation:
    def test_rechaza_titulo_vacio(self):
        with pytest.raises(ValidationError):
            Course(title="")

    def test_rechaza_titulo_solo_espacios(self):
        with pytest.raises(ValidationError):
            Course(title="   ")


class TestCourseModuleManagement:
    def test_agrega_modulo(self):
        curso = Course(title="X")
        modulo = Module(title="M1", order=0)
        curso.add_module(modulo)
        assert len(curso.modules) == 1

    def test_ordena_modulos_por_order(self):
        curso = Course(title="X")
        curso.add_module(Module(title="M", order=2))
        curso.add_module(Module(title="M", order=0))
        assert [m.order for m in curso.modules] == [0, 2]
```

**Reglas importantes de las clases en pytest:**

1. La clase **no debe tener `__init__`** (pytest usa la suya propia).
2. Los métodos deben empezar con `test_`.
3. pytest **no** crea una instancia por método; usa la misma para todos (similar a `setUp` de unittest pero implícito).
4. Para compartir lógica entre métodos, usa fixtures o métodos de clase, no `self.atributo = ...`.

### 5.3 Patrón de tests agrupados por aspecto

```python
class TestCourse:
    """Agrupa TODOS los tests de Course. Anidamos clases por aspecto."""

    class TestInstantiation:
        """Tests de instanciación: ¿se crea correctamente?"""

        def test_creates_with_minimal_data(self):
            ...

        def test_strips_whitespace(self):
            ...

    class TestValidation:
        """Tests de validación: ¿rechaza datos inválidos?"""

        def test_rejects_empty_title(self):
            ...

    class TestStateManagement:
        """Tests de mutación: ¿cambia estado correctamente?"""

        def test_add_module(self):
            ...
```

Este es el patrón usado en el proyecto `course-automation` (ver `tests/unit/domain/course/entities/test_course.py`).

---

## 6. Ejecución desde la línea de comandos

### 6.1 Comandos esenciales

```bash
# Correr todo
pytest

# Verbose (muestra cada test por nombre)
pytest -v

# Verbose + más verboso (muestra diffs completos)
pytest -vv

# Solo un archivo
pytest tests/unit/domain/course/entities/test_course.py

# Solo un test por nombre
pytest tests/test_course.py::test_creates_with_title

# Solo un método de una clase
pytest tests/test_course.py::TestCourseValidation::test_rejects_empty_title
```

### 6.2 Selección por palabra clave ( `-k`)

```bash
# Todos los tests cuyo nombre contenga "validation"
pytest -k validation

# Todos los tests de Course o Module
pytest -k "course or module"

# Excluir los tests de Topic
pytest -k "not topic"
```

`-k` usa la sintaxis de Python para evaluar la expresión contra el nombre completo del test (incluyendo clases).

### 6.3 Selección por marker ( `-m`)

```bash
# Solo tests marcados como @pytest.mark.slow
pytest -m slow

# Todos EXCEPTO los slow
pytest -m "not slow"
```

### 6.4 Parar ante el primer fallo

```bash
pytest -x        # Para en el primer fallo
pytest --maxfail=3   # Para después de 3 fallos
```

Útil en CI o cuando debugueas: en lugar de ver 30 fallos, ves el primero y lo arreglas.

### 6.5 Tracebacks y debugging

```bash
pytest --tb=short     # Traceback corto (1 línea por frame)
pytest --tb=line      # Solo la línea que falló
pytest --tb=long      # Traceback completo
pytest --tb=no        # Sin traceback
```

### 6.6 Salida y reporte

```bash
pytest -s            # No captura stdout (ves los print)
pytest --capture=no  # Igual que -s
pytest -q            # Quiet (menos output)
pytest --durations=10  # Muestra los 10 tests más lentos
pytest --co          # Collect only: solo lista tests, no los corre
```

### 6.7 Ejecutar en paralelo

Con el plugin `pytest-xdist`:

```bash
pip install pytest-xdist
pytest -n auto       # Usa todos los cores
pytest -n 4          # Usa 4 workers
```

Importante: los tests deben ser **independientes** (no compartir estado mutable entre workers).

### 6.8 Salida con colores y formato

```bash
# Forzar color aunque la salida no sea TTY
pytest --color=yes

# Desactivar color
pytest --color=no
```

---

## 7. Fixtures

Las **fixtures** son el mecanismo más potente de pytest. Son funciones que **preparan el estado** necesario para un test (datos, conexiones, archivos, etc.) y lo **limpian** al final.

### 7.1 El problema que resuelven

```python
# SIN fixtures: duplicación
def test_curso_con_descripcion():
    curso = Course(title="ML", description="intro a ML")
    assert curso.description == "intro a ML"


def test_curso_con_modulo():
    curso = Course(title="ML", description="intro a ML")  # Duplicado
    modulo = Module(title="M1", order=0)
    curso.add_module(modulo)
    assert len(curso.modules) == 1
```

```python
# CON fixtures: limpio y DRY
@pytest.fixture
def curso():
    return Course(title="ML", description="intro a ML")


def test_curso_con_descripcion(curso):
    assert curso.description == "intro a ML"


def test_curso_con_modulo(curso):
    curso.add_module(Module(title="M1", order=0))
    assert len(curso.modules) == 1
```

**¿Cómo funciona?** pytest ve que el test pide un parámetro `curso`. Busca una función llamada `curso` decorada con `@pytest.fixture`, la llama, y le pasa el resultado. **Inyección de dependencias** automática.

### 7.2 Definir fixtures

```python
import pytest

@pytest.fixture
def sample_course_title():
    return "Introduction to Machine Learning"


@pytest.fixture
def sample_block_payload():
    return {"text": "Hello, world!"}
```

### 7.3 Usar fixtures en tests

**Como función:**

```python
def test_usa_fixture(sample_course_title):
    assert "Machine" in sample_course_title
```

**Como método de clase:**

```python
class TestCourse:
    def test_usa_fixture(self, sample_course_title):
        assert "Machine" in sample_course_title
```

**Múltiples fixtures:**

```python
def test_multiples(sample_course_title, sample_block_payload):
    assert "Machine" in sample_course_title
    assert "Hello" in sample_block_payload["text"]
```

### 7.4 Teardown: limpieza con `yield`

Si el fixture necesita **liberar recursos** (cerrar archivos, conexiones a DB, etc.), usa `yield` en lugar de `return`:

```python
@pytest.fixture
def temp_file(tmp_path):
    archivo = tmp_path / "datos.txt"
    archivo.write_text("contenido inicial")

    yield archivo  # <-- pytest pausa aquí, ejecuta el test

    # Teardown (corre después del test, incluso si falla)
    if archivo.exists():
        archivo.unlink()
```

**Regla clave**: el código **antes** de `yield` es el *setup*. El código **después** es el *teardown*. pytest garantiza que el teardown se ejecuta siempre, incluso si el test falla o lanza excepción.

### 7.5 `conftest.py`: fixtures compartidos

`conftest.py` es un archivo especial que pytest descubre automáticamente. Las fixtures definidas aquí están disponibles para **todos los tests** del mismo directorio y subdirectorios, **sin necesidad de importarlas**.

```
tests/
├── conftest.py            # Fixtures globales
├── unit/
│   ├── conftest.py        # Solo para tests/unit/** (opcional)
│   └── domain/
│       └── course/
│           ├── conftest.py   # Solo para tests/unit/domain/course/**
│           └── entities/
│               └── test_course.py
```

```python
# tests/conftest.py
import pytest

@pytest.fixture
def sample_course_title():
    return "Introduction to Machine Learning"
```

pytest aplica una **cascada**: si defines `sample_course_title` en `tests/conftest.py` y en `tests/unit/conftest.py`, gana el más cercano al test (anidamiento más profundo).

También es útil para configuración global:

```python
# tests/conftest.py
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
```

### 7.6 Scopes (alcance) de fixtures

Por defecto, una fixture se crea **una vez por test** (scope `function`). Puedes cambiar esto:

```python
@pytest.fixture(scope="module")
def expensive_resource():
    """Se crea UNA VEZ por módulo de test, no por cada test."""
    return create_expensive_thing()


@pytest.fixture(scope="session")
def db_engine():
    """Se crea UNA VEZ para toda la sesión de pytest."""
    return create_engine("postgresql://...")
```

**Scopes disponibles (de más a menos granular):**

| Scope | Frecuencia de creación | Caso de uso |
|---|---|---|
| `function` (default) | 1 vez por test | Objetos pequeños, sin estado compartido |
| `class` | 1 vez por clase de test | Compartir entre métodos de la misma clase |
| `module` | 1 vez por archivo | Conexiones a DB que se reutilizan |
| `package` | 1 vez por paquete | Poco común |
| `session` | 1 vez por ejecución | Recursos muy costosos (engine de DB) |

**Advertencia:** usar scopes distintos a `function` introduce **estado compartido entre tests**, lo que rompe el principio de independencia. Úsalo solo cuando el setup es muy caro y el recurso es **inmutable o idempotente**.

### 7.7 `autouse=True`: fixture automática

Una fixture con `autouse=True` se ejecuta **sin necesidad de pedirla explícitamente**:

```python
@pytest.fixture(autouse=True)
def reset_db():
    """Limpia la DB antes de cada test."""
    db.truncate_all()
    yield
    db.truncate_all()


def test_create_user():
    # No pido `reset_db` explícitamente, pero corre igual
    ...
```

Útil para **configuración transversal** (limpieza de estado, setup de logging, etc.). **Advertencia:** usar con moderación porque hace los tests menos explícitos.

### 7.8 Composición: fixtures que usan otras fixtures

Las fixtures pueden depender de otras fixtures:

```python
@pytest.fixture
def sample_course_title():
    return "ML Course"


@pytest.fixture
def empty_course(sample_course_title):
    """Depende de sample_course_title."""
    return Course(title=sample_course_title)


@pytest.fixture
def course_with_module(empty_course):
    """Depende de empty_course."""
    empty_course.add_module(Module(title="M1", order=0))
    return empty_course
```

pytest resuelve el grafo de dependencias automáticamente. Cada fixture **se crea una sola vez por test** (incluso si varias la piden).

### 7.9 Fixtures integradas (built-in)

pytest trae fixtures útiles sin instalar nada:

```python
def test_archivo_temporal(tmp_path):
    """Crea un directorio temporal único para el test."""
    archivo = tmp_path / "datos.json"
    archivo.write_text('{"key": "value"}')
    assert archivo.read_text() == '{"key": "value"}'


def test_archivo_temporal_factory(tmp_path_factory):
    """Como tmp_path pero para casos donde necesitas el path antes."""
    temp_dir = tmp_path_factory.mktemp("datos")
    ...


def test_capsys(capsys):
    """Captura stdout y stderr."""
    print("hola")
    captured = capsys.readouterr()
    assert captured.out == "hola\n"


def test_monkeypatch(monkeypatch):
    """Modifica atributos/env vars temporalmente."""
    monkeypatch.setenv("API_KEY", "test-key")
    assert os.environ["API_KEY"] == "test-key"


def test_recursos_compartidos(request):
    """Acceso a información del test en ejecución."""
    print(request.node.name)  # Nombre del test actual
```

### 7.10 Parametrizar fixtures

```python
@pytest.fixture(params=["text", "heading", "code"])
def block_type(request):
    return BlockType(request.param)


def test_acepta_varios_tipos(block_type):
    bloque = ContentBlock(block_type=block_type, order=0, payload={"x": 1})
    assert bloque.type == block_type
```

pytest ejecutará el test **3 veces**, una por cada valor de `params`.

### 7.11 Indirección: parametrizar fixtures indirectas

```python
@pytest.fixture
def database(request):
    db_type = request.param
    if db_type == "postgres":
        return PostgresDB()
    elif db_type == "sqlite":
        return SQLiteDB()


@pytest.mark.parametrize("database", ["postgres", "sqlite"], indirect=True)
def test_query(database):
    result = database.query("SELECT 1")
    assert result == 1
```

`indirect=True` hace que el valor se **pase al fixture** en vez de al test. Útil cuando quieres probar la misma lógica contra distintas configuraciones.

---

## 8. Parametrización

`@pytest.mark.parametrize` ejecuta el mismo test con **múltiples inputs**.

### 8.1 Ejemplo básico

```python
@pytest.mark.parametrize("num", [1, 2, 3, 4, 5])
def test_es_positivo(num):
    assert num > 0
```

Genera **5 tests** distintos: `test_es_positivo[1]`, `test_es_positivo[2]`, etc.

### 8.2 Múltiples parámetros

```python
@pytest.mark.parametrize("a, b, esperado", [
    (1, 1, 2),
    (0, 0, 0),
    (-1, 1, 0),
    (10, -5, 5),
])
def test_suma(a, b, esperado):
    assert a + b == esperado
```

### 8.3 Parametrización con IDs legibles

```python
@pytest.mark.parametrize("titulo, esperado", [
    pytest.param("", ValueError, id="titulo-vacio"),
    pytest.param("X", None, id="titulo-ok"),
    pytest.param("   ", ValueError, id="solo-espacios"),
])
def test_validacion(titulo, esperado):
    if esperado is ValueError:
        with pytest.raises(ValidationError):
            Course(title=titulo)
    else:
        curso = Course(title=titulo)
        assert curso.title == titulo
```

Sin IDs, pytest usa el string del valor (feo con números). Con `id=` puedes nombrar cada caso.

### 8.4 Apilar `@parametrize`

```python
@pytest.mark.parametrize("x", [1, 2])
@pytest.mark.parametrize("y", [10, 20])
def test_multiplica(x, y):
    assert isinstance(x * y, int)
```

Genera **4 tests**: `(1,10)`, `(1,20)`, `(2,10)`, `(2,20)` (combinación cartesiana).

### 8.5 Ejemplo real: validar todos los `BlockType`

```python
@pytest.mark.parametrize("block_type", [
    BlockType.HEADING,
    BlockType.TEXT,
    BlockType.CODE,
    BlockType.IMAGE,
    BlockType.QUOTE,
    BlockType.DIVIDER,
])
def test_acepta_todos_los_tipos_de_bloque(block_type):
    bloque = ContentBlock(
        block_type=block_type,
        order=0,
        payload={"text": "x"},
    )
    assert bloque.type == block_type
```

Añadir un nuevo `BlockType` al enum **rompe este test hasta que lo añades a la lista**, lo cual es bueno: te obliga a actualizar la cobertura.

---

## 9. Markers (marcadores)

Los markers son **etiquetas** que pytest aplica a los tests para clasificarlos, filtrarlos o cambiar su comportamiento.

### 9.1 Markers built-in

```python
import pytest
import sys


@pytest.mark.skip(reason="Funcionalidad aún no implementada")
def test_feature_futura():
    ...


@pytest.mark.skipif(sys.version_info < (3, 11), reason="Requiere Python 3.11+")
def test_sintaxis_moderna():
    ...


@pytest.mark.xfail(reason="Bug conocido, ver issue #42")
def test_comportamiento_conocido_roto():
    # Si PASA: test XPASSED (puede ser sorpresa)
    # Si FALLA: test XFAILED (esperado)
    assert 1 == 2
```

### 9.2 Markers personalizados

Declara tus propios markers en `pyproject.toml`:

```toml
[tool.pytest.ini_options]
markers = [
    "slow: tests que tardan más de 1 segundo",
    "integration: tests que requieren servicios externos",
    "ai: tests que llaman al LLM",
]
```

Úsalos:

```python
@pytest.mark.slow
def test_generar_curso_completo_con_llm_real():
    ...


@pytest.mark.integration
def test_conexion_neo4j_real():
    ...
```

Filtra con `-m`:

```bash
pytest -m slow            # Solo los lentos
pytest -m "not slow"      # Todos EXCEPTO los lentos
pytest -m "integration or ai"  # Combinados
```

### 9.3 `--strict-markers`

```toml
[tool.pytest.ini_options]
addopts = "--strict-markers"
```

Con este flag, **usar un marker no declarado falla**. Evita typos como `@pytest.mark.sloow`.

### 9.4 Organización por marker vs por directorio

Tienes dos formas de separar tests:

| Estrategia | Ventaja | Desventaja |
|---|---|---|
| Por directorio (`unit/`, `integration/`) | Estructura física, fácil de excluir | Inflexible |
| Por marker (`@pytest.mark.integration`) | Flexible, un test puede tener varios tags | Requiere disciplina |

**Recomendación**: usa ambos combinados. Directorios para separación física, markers para categorización adicional.

---

## 10. Pruebas asíncronas

Con `pytest-asyncio`, puedes probar funciones `async def`:

### 10.1 Configuración

```toml
# pyproject.toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
```

Con `auto`, **toda** función `async def` se trata como test. Sin `auto`, necesitas `@pytest.mark.asyncio` en cada una.

### 10.2 Tests asíncronos básicos

```python
import pytest


@pytest.mark.asyncio
async def test_fetch_data():
    result = await fetch_from_api()
    assert result["status"] == "ok"


# Con asyncio_mode = "auto", no necesitas el marker:
async def test_fetch_data_auto():
    result = await fetch_from_api()
    assert result["status"] == "ok"
```

### 10.3 Fixtures asíncronas

```python
@pytest.fixture
async def db_session():
    session = await create_async_session()
    yield session
    await session.close()


async def test_query(db_session):
    result = await db_session.execute("SELECT 1")
    assert result is not None
```

### 10.4 Buenas prácticas con async

- Usa `httpx.AsyncClient` en lugar de `requests` para tests de API.
- Asegúrate de que los recursos se cierren en el teardown (después de `yield`).
- Evita mezclar código sync y async en el mismo test.

---

## 11. Mocking y monkeypatching

**Mockear** = reemplazar una dependencia real por un **doble de prueba** que simula su comportamiento. Sirve para:

- Aislar la unidad bajo test.
- Probar casos de error sin provocarlos de verdad.
- Evitar I/O costosa o no determinista (red, tiempo, LLM).

### 11.1 `unittest.mock` (stdlib)

```python
from unittest.mock import Mock, MagicMock, patch


def test_send_email_usa_smtp_mockeado():
    smtp_mock = Mock()
    smtp_mock.send_email.return_value = True

    with patch("src.infrastructure.email.smtp", smtp_mock):
        resultado = send_welcome_email("user@example.com")

    assert resultado is True
    smtp_mock.send_email.assert_called_once_with(
        to="user@example.com",
        subject="Bienvenido",
    )
```

### 11.2 Tipos de dobles de prueba

| Tipo | Comportamiento | Uso |
|---|---|---|
| **Dummy** | Datos vacíos que solo se pasan como argumentos | `def get_user(id: int): pass` con `id=None` |
| **Stub** | Devuelve valores hardcodeados | `repo.find_by_id.return_value = fake_user` |
| **Spy** | Registra cómo fue llamado | `mock.assert_called_with(...)` |
| **Mock** | Pre-programado, verifica interacciones | Combinación de stub + spy |
| **Fake** | Implementación funcional pero simple | DB en memoria en vez de Postgres |

### 11.3 `MagicMock` vs `Mock`

- `Mock`: simula cualquier objeto, sin métodos mágicos.
- `MagicMock`: simula también métodos mágicos (`__str__`, `__iter__`, `__len__`, etc.). **Usa este por defecto**.

```python
mock = MagicMock()
mock.__str__.return_value = "fake"
str(mock)  # 'fake'
```

### 11.4 Patrones comunes de mockeo

**Decorador `@patch`:**

```python
@patch("src.infrastructure.gemini.client.GeminiClient")
def test_generate_outline(mock_gemini):
    mock_gemini.return_value.generate.return_value = '{"modules": []}'

    outline = generate_course_outline("Python basics")

    mock_gemini.return_value.generate.assert_called_once()
```

**Como context manager:**

```python
def test_generate_outline():
    with patch("src.infrastructure.gemini.client.GeminiClient") as mock_gemini:
        mock_gemini.return_value.generate.return_value = '{"modules": []}'
        outline = generate_course_outline("Python basics")
        ...
```

**`pytest-mock` (sintaxis más limpia):**

```bash
pip install pytest-mock
```

```python
def test_generate_outline(mocker):
    mock_gemini = mocker.patch("src.infrastructure.gemini.client.GeminiClient")
    mock_gemini.return_value.generate.return_value = '{"modules": []}'

    outline = generate_course_outline("Python basics")

    mock_gemini.return_value.generate.assert_called_once_with(
        prompt=...,
        temperature=...,
    )
```

### 11.5 `monkeypatch` (fixture built-in)

Para modificar **atributos, variables de entorno o paths** sin usar mocks:

```python
def test_api_key_required(monkeypatch):
    # Borra la env var temporalmente
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    with pytest.raises(MissingAPIKeyError):
        GeminiClient()


def test_api_key_present(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    client = GeminiClient()
    assert client is not None


def test_change_function(monkeypatch):
    def fake_now():
        from datetime import datetime
        return datetime(2026, 1, 1, 12, 0, 0)

    monkeypatch.setattr("src.app.datetime", fake_now)
    ...
```

`monkeypatch` **deshace los cambios automáticamente** al final del test. Es más seguro que `unittest.mock.patch` porque no tienes que recordar el `with` o el decorador.

### 11.6 Verificar excepciones con mocks

```python
def test_handles_api_error(mocker):
    mock_gemini = mocker.patch("src.app.GeminiClient")
    mock_gemini.return_value.generate.side_effect = GeminiAPIError("rate limit")

    with pytest.raises(GenerationError, match="rate limit"):
        generate_course("Python")
```

### 11.7 Cuándo NO mockear

- **No mockees tipos de datos simples** (dataclasses, dicts, listas).
- **No mockees la unidad bajo test**.
- **No mockees todo**: si mockeas 10 cosas, tu test no prueba nada.
- **No mockees funciones puras** que podrías testear directamente.

### 11.8 Anti-patrones de mocking

```python
# MAL: mock demasiado genérico
mock = MagicMock()
result = mock.do_thing("x", "y", key="value")  # Nunca falla, no prueba nada

# BIEN: mock específico con asserts
mock = MagicMock()
mock.do_thing.return_value = expected_result
result = my_function(mock)
assert result == expected
mock.do_thing.assert_called_once_with("x", "y", key="value")
```

---

## 12. Cobertura de código

La **cobertura** mide qué porcentaje de líneas/ramases de tu código se ejecutan durante los tests.

### 12.1 Instalación

```bash
pip install pytest-cov
```

### 12.2 Uso básico

```bash
# Cobertura del módulo src
pytest --cov=src tests/

# Con reporte de líneas no cubiertas
pytest --cov=src --cov-report=term-missing tests/

# Generar reporte HTML
pytest --cov=src --cov-report=html tests/
# Abre htmlcov/index.html en el navegador
```

### 12.3 Configuración en `pyproject.toml`

```toml
[tool.coverage.run]
source = ["src"]
omit = [
    "*/tests/*",
    "*/__init__.py",
    "*/migrations/*",
]

[tool.coverage.report]
# Falla el build si la cobertura es menor a 80%
fail_under = 80
exclude_lines = [
    "pragma: no cover",
    "if __name__ == .__main__.:",
    "raise NotImplementedError",
    "if TYPE_CHECKING:",
]
```

### 12.4 Tipos de cobertura

- **Line coverage**: porcentaje de líneas ejecutadas.
- **Branch coverage**: porcentaje de ramas (if/else) tomadas. Más estricto, recomendado: `--cov-branch`.

```bash
pytest --cov=src --cov-branch --cov-report=term-missing
```

### 12.5 La cobertura NO es calidad

Una cobertura del 100% **no garantiza** que el código sea correcto. Puedes tener:

```python
def divide(a, b):
    return a / b  # 100% cubierto

def test_divide():
    assert divide(10, 2) == 5  # Pasa, 100% cobertura
    # PERO divide(10, 0) NO se prueba → ZeroDivisionError sin manejar
```

**Regla**: 100% cobertura con tests malos < 80% cobertura con tests buenos.

### 12.6 Mutation testing (ir un paso más allá)

`mutmut` o `cosmic-ray` modifican tu código (cambian `==` por `!=`, etc.) y ven si tus tests **detectan** los cambios. Si un mutante sobrevive, tienes un gap.

```bash
pip install mutmut
mutmut run
mutmut results
```

---

## 13. Patrones y mejores prácticas

### 13.1 Patrón AAA (Arrange, Act, Assert)

Estructura recomendada para un test:

```python
def test_add_module():
    # Arrange (preparar)
    curso = Course(title="X")
    modulo = Module(title="M1", order=0)

    # Act (actuar)
    curso.add_module(modulo)

    # Assert (verificar)
    assert len(curso.modules) == 1
    assert curso.modules[0] is modulo
```

### 13.2 FIRST (principios de un buen test)

- **F**ast: rápido (< 100ms idealmente).
- **I**ndependent: no depende de otros tests.
- **R**epeatable: el mismo resultado siempre, sin red/tiempo.
- **S**elf-validating: PASSED o FAILED, sin inspección manual.
- **T**imely: escrito **junto** con el código, no "algún día".

### 13.3 Nombres de tests descriptivos

**Mal:**
```python
def test_course_1():
    ...
```

**Bien:**
```python
def test_course_raises_validation_error_when_title_is_empty():
    ...
```

Convención recomendada: `test_<unidad>_<comportamiento>_<condición>`.

Si usas clases, el nombre se acumula:
```python
class TestCourseValidation:
    def test_raises_validation_error_when_title_is_empty(self):
        ...
```

El nombre completo es: `TestCourseValidation::test_raises_validation_error_when_title_is_empty`.

### 13.4 Una aserción lógica por test (no necesariamente una sola línea)

```python
# BIEN: aserciones relacionadas
def test_creates_course_with_correct_title():
    curso = Course(title="ML")
    assert curso.title == "ML"
    assert curso.description is None
    assert curso.modules == []
    # Todas validan el mismo comportamiento: "se crea con defaults"

# MAL: aserciones no relacionadas
def test_create_and_delete():
    curso = Course(title="ML")
    assert curso.title == "ML"
    curso.delete()
    assert curso is None  # Asume que delete existe, sin testearlo aislado
```

### 13.5 Test data builders

Para construir objetos de prueba complejos, usa **builders**:

```python
class CourseBuilder:
    def __init__(self):
        self.title = "Default Title"
        self.description = "Default description"
        self.modules = []

    def with_title(self, title):
        self.title = title
        return self

    def with_description(self, description):
        self.description = description
        return self

    def with_module(self, module):
        self.modules.append(module)
        return self

    def build(self):
        return Course(
            title=self.title,
            description=self.description,
            modules=self.modules,
        )


# Uso:
def test_course_with_module():
    curso = (
        CourseBuilder()
        .with_title("ML")
        .with_module(Module(title="M1", order=0))
        .build()
    )
    assert len(curso.modules) == 1
```

### 13.6 Object Mother (entidades de prueba predefinidas)

Similar al builder pero expone instancias listas para usar:

```python
# tests/builders/courses.py
class Courses:
    @staticmethod
    def minimal():
        return Course(title="ML")

    @staticmethod
    def with_one_module():
        curso = Course(title="ML")
        curso.add_module(Module(title="M1", order=0))
        return curso


# Uso:
def test_module_management():
    curso = Courses.with_one_module()
    assert len(curso.modules) == 1
```

### 13.7 Test isolation (independencia)

Cada test debe poder correr **solo, en cualquier orden, en paralelo**, y dar el mismo resultado.

```python
# MAL: estado compartido mutable
counter = 0

def test_a():
    global counter
    counter += 1
    assert counter == 1  # Pasa solo si corre primero

def test_b():
    global counter
    counter += 1
    assert counter == 1  # Falla si test_a corrió antes
```

```python
# BIEN: estado encapsulado
def test_a():
    counter = 0
    counter += 1
    assert counter == 1

def test_b():
    counter = 0
    counter += 1
    assert counter == 1
```

### 13.8 Test pyramid en la práctica

```python
# tests/unit/domain/course/entities/test_course.py
# Tests unitarios: 95% de los tests, corren en <1s

# tests/integration/persistence/test_course_repository.py
# Tests de integración: 4% de los tests, requieren DB, corren en segundos

# tests/e2e/api/test_generate_course.py
# Tests E2E: 1% de los tests, requieren app + DB + Neo4j + LLM mock
```

Regla: **si tu test requiere más de 100ms, probablemente debería ser de integración**.

### 13.9 Tests como documentación

Los tests describen el comportamiento esperado del código. Un test bien escrito vale más que un párrafo de docstring:

```python
def test_user_cannot_be_created_with_duplicate_email():
    # Arrange
    existing = User(email="x@example.com")
    save(existing)

    # Act + Assert
    with pytest.raises(ConflictError, match="already exists"):
        save(User(email="x@example.com"))
```

Este test **documenta** la regla de negocio: "no se permiten emails duplicados".

### 13.10 Arrange complejo con fixtures anidadas

```python
@pytest.fixture
def course_with_content():
    """Curso con módulos, topics y bloques para tests de lectura."""
    return Course(
        title="ML 101",
        modules=[
            Module(
                title="Intro",
                order=0,
                topics=[
                    Topic(
                        title="What is ML?",
                        order=0,
                        blocks=[
                            ContentBlock(
                                block_type=BlockType.HEADING,
                                order=0,
                                payload={"text": "Intro"},
                            ),
                            ContentBlock(
                                block_type=BlockType.TEXT,
                                order=1,
                                payload={"text": "ML is..."},
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )
```

---

## 14. Conceptos avanzados

### 14.1 Property-based testing con Hypothesis

En lugar de probar **casos concretos**, defines **propiedades** que deben cumplirse y Hypothesis genera cientos de inputs aleatorios:

```bash
pip install hypothesis
```

```python
from hypothesis import given, strategies as st


@given(st.integers(min_value=1, max_value=1_000_000))
def test_divide_y_multiplicar_es_identidad(n):
    """Para cualquier n entero positivo, (n/2)*2 == n"""
    assert (n / 2) * 2 == pytest.approx(n)


@given(
    title=st.text(min_size=1, max_size=100).filter(lambda s: s.strip()),
)
def test_acepta_cualquier_titulo_no_vacio(title):
    curso = Course(title=title)
    assert curso.title == title.strip()
```

Hypothesis busca **casos mínimos que rompan** tu test (shrinking). Útil para encontrar edge cases que no se te ocurrieron.

### 14.2 Snapshot testing con `syrupy`

Captura la salida de una función y la compara con una "foto" guardada:

```bash
pip install syrupy
```

```python
def test_render_curso(snapshot):
    curso = Courses.with_one_module()
    rendered = render_to_dict(curso)

    assert rendered == snapshot
```

La primera vez se genera `__snapshots__/test_render_curso.ambr`. Las siguientes veces se compara. Si el cambio es intencional, ejecutas `pytest --snapshot-update`.

Útil para: estructuras JSON complejas, outputs de renderizado, schemas.

### 14.3 Comparación de objetos complejos: `__eq__`

Para que `assert obj1 == obj2` funcione, las entidades deben implementar `__eq__`. Para el proyecto `course-automation`, las entidades **no** lo implementan, lo cual es válido (cada test compara atributos específicos). Pero si quieres:

```python
from dataclasses import dataclass

@dataclass
class CourseDTO:
    title: str
    description: str | None
    module_count: int


def test_curso_a_dto():
    curso = Course(title="ML", modules=[Module(title="M", order=0)])
    dto = CourseDTO(title="ML", description=None, module_count=1)

    assert course_to_dto(curso) == dto
```

### 14.4 Tests parametrizados con `pytest_generate_tests`

Para generar tests **dinámicamente**:

```python
def pytest_generate_tests(metafunc):
    if "language" in metafunc.fixturenames:
        metafunc.parametrize("language", ["es", "en", "pt"])


def test_render_supports_languages(language):
    assert render_course(Course(title="X"), language=language) is not None
```

Útil cuando la lista de parámetros se calcula en runtime.

### 14.5 Pruebas con `freezegun` (mockear el tiempo)

```bash
pip install freezegun
```

```python
from freezegun import freeze_time


@freeze_time("2026-01-15 12:00:00")
def test_generation_job_uses_current_timestamp():
    job = create_generation_job()
    assert job.created_at == datetime(2026, 1, 15, 12, 0, 0)
```

### 14.6 Tests de performance con `pytest-benchmark`

```bash
pip install pytest-benchmark
```

```python
def test_validate_course_is_fast(benchmark):
    curso = Course(title="ML")
    result = benchmark(curso._validate)
    assert result is None
```

`pytest-benchmark` corre el test muchas veces y reporta estadísticas (media, mediana, std).

### 14.7 Tests de propiedades custom con `attrs` o `pydantic`

Si usas `pydantic` para DTOs, sus validadores también se pueden testear:

```python
from pydantic import BaseModel, ValidationError as PydanticValidationError


class CourseInput(BaseModel):
    title: str
    description: str | None = None


def test_pydantic_rejects_empty_title():
    with pytest.raises(PydanticValidationError):
        CourseInput(title="")
```

### 14.8 Test de pureza de capas (archery)

En Clean Architecture es común escribir un test que **verifica que una capa no importa de otra**:

```python
def test_domain_no_importa_infrastructure():
    import ast
    from pathlib import Path

    domain_root = Path("src/domain")
    forbidden = ["sqlalchemy", "neo4j", "fastapi", "google"]

    violations = []
    for py_file in domain_root.rglob("*.py"):
        tree = ast.parse(py_file.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[0] in forbidden:
                        violations.append(...)
            elif isinstance(node, ast.ImportFrom):
                if (node.module or "").split(".")[0] in forbidden:
                    violations.append(...)

    assert not violations
```

Este test es **arquitectónico**: falla si alguien rompe las reglas de dependencias.

### 14.9 Cobertura mutua entre tests (Property-based con esquemas)

```python
from hypothesis import given, strategies as st
from hypothesis.stateful import RuleBasedStateMachine, rule, invariant


class CourseStateMachine(RuleBasedStateMachine):
    @rule(title=st.text(min_size=1, max_size=100))
    def add_module_with_title(self, title):
        self.curso.add_module(Module(title=title, order=len(self.curso.modules)))

    @rule()
    def get_sorted_titles(self):
        titles = [m.title for m in self.curso.modules]
        assert titles == sorted(titles, key=lambda m: m.order)

    def __init__(self):
        super().__init__()
        self.curso = Course(title="State test")


# Hypothesis ejecuta una secuencia aleatoria de reglas y verifica invariantes
TestCourseState = CourseStateMachine.TestCase
```

---

## 15. Plugins útiles

| Plugin | Función | Instalación |
|---|---|---|
| `pytest-cov` | Cobertura de código | `pip install pytest-cov` |
| `pytest-mock` | Sintaxis limpia para `unittest.mock` | `pip install pytest-mock` |
| `pytest-asyncio` | Soporte para `async/await` | `pip install pytest-asyncio` |
| `pytest-xdist` | Ejecución paralela | `pip install pytest-xdist` |
| `pytest-benchmark` | Benchmarks de performance | `pip install pytest-benchmark` |
| `pytest-watch` | Re-ejecutar al guardar archivos | `pip install pytest-watch` |
| `pytest-sugar` | Output más bonito | `pip install pytest-sugar` |
| `pytest-clarity` | Tracebacks mejorados | `pip install pytest-clarity` |
| `pytest-randomly` | Orden aleatorio de tests (detecta dependencias ocultas) | `pip install pytest-randomly` |
| `pytest-pretty` | Reporter alternativo más visual | `pip install pytest-pretty` |
| `pytest-icdiff` | Diff de unicode/coloreado | `pip install pytest-icdiff` |
| `hypothesis` | Property-based testing | `pip install hypothesis` |
| `syrupy` | Snapshot testing | `pip install syrupy` |
| `freezegun` | Mockear `datetime` | `pip install freezegun` |
| `time-machine` | Alternativa moderna a freezegun | `pip install time-machine` |

### 15.1 `pytest-watch` (TDD workflow)

```bash
pip install pytest-watch
ptw
```

Corre los tests cada vez que guardas un archivo. Flujo TDD perfecto.

### 15.2 `pytest-randomly`

```bash
pip install pytest-randomly
```

Reordena los tests aleatoriamente. Si tu suite pasa siempre, no hay acoplamiento. Si empieza a fallar en algún orden, tienes una dependencia oculta.

```bash
pytest -p randomly   # Con seed aleatorio
pytest -p randomly --randomly-seed=12345  # Seed específico para reproducir
```

---

## 16. Integración con CI/CD

### 16.1 GitHub Actions

```yaml
# .github/workflows/tests.yml
name: Tests

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.11", "3.12"]

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
          cache: "pip"

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -e ".[dev]"

      - name: Run tests
        env:
          DATABASE_URL: postgresql://postgres:postgres@localhost:5432/test
        run: |
          pytest --cov=src --cov-report=xml --cov-report=term-missing

      - name: Upload coverage
        uses: codecov/codecov-action@v4
        with:
          file: coverage.xml
          fail_ci_if_error: true
```

### 16.2 Pre-commit hook

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: pytest-check
        name: pytest-check
        entry: pytest
        language: system
        pass_filenames: false
        always_run: true
```

```bash
pip install pre-commit
pre-commit install
```

Ahora cada `git commit` corre los tests antes de aceptar el commit.

### 16.3 Makefile (atajos locales)

```makefile
# Makefile
.PHONY: test test-unit test-integration test-cov test-fast

test:
	pytest

test-unit:
	pytest tests/unit

test-integration:
	pytest tests/integration

test-cov:
	pytest --cov=src --cov-report=term-missing --cov-report=html

test-fast:
	pytest -x --tb=short -q
```

```bash
make test-cov
```

---

## 17. Debugging de tests

### 17.1 `pytest --pdb` (post-mortem debugger)

Si un test falla, abre el debugger de Python justo en el punto de fallo:

```bash
pytest --pdb
```

Comandos en el debugger:
- `p variable` — imprime el valor
- `c` — continuar
- `q` — salir
- `l` — listar código cercano
- `h` — ayuda

### 17.2 `breakpoint()` dentro del test

```python
def test_algo():
    x = compute_x()
    breakpoint()  # Pausa aquí cuando corres con python -m pytest
    assert x > 0
```

### 17.3 Ver prints con `-s`

```bash
pytest -s
```

Por defecto pytest captura stdout/stderr. Con `-s` (`--capture=no`) ves los `print()`.

### 17.4 Tests lentos

```bash
pytest --durations=10
```

Muestra los 10 tests más lentos. Útil para optimizar.

### 17.5 `pytest -x --tb=long` para debugging

```bash
pytest -x --tb=long tests/unit/test_algo.py
```

Para en el primer fallo y muestra el traceback completo.

### 17.6 Marcar tests con `print` para inspección

```python
def test_curso():
    curso = Course(title="X")
    print(f"ID del curso: {curso.id}")
    print(f"Título: {curso.title}")
    assert curso.id is not None
```

Corre con `pytest -s` para ver la salida.

---

## 18. Glosario

| Término | Definición |
|---|---|
| **Assertion (aserción)** | Línea `assert` que verifica una condición. |
| **Asyncio mode** | Configuración de pytest-asyncio: `auto` ejecuta async tests sin marker. |
| **Autouse** | Fixture que se ejecuta sin necesidad de pedirla explícitamente. |
| **Branch coverage** | Cobertura que mide las ramas (if/else) tomadas, no solo líneas. |
| **Builder pattern** | Patrón para construir objetos de prueba complejos de forma fluida. |
| **Conftest.py** | Archivo mágico de pytest para fixtures y hooks compartidos. |
| **Coverage (cobertura)** | Porcentaje de código ejecutado por los tests. |
| **Decorator (`@`)** | Función que modifica otra función. `@pytest.fixture` registra un fixture. |
| **Direct test** | Test que usa valores concretos (vs. property-based). |
| **Edge case (caso límite)** | Input en el extremo de lo aceptable (vacío, máximo, negativo). |
| **E2E (end-to-end)** | Test que recorre el sistema completo, de UI a DB. |
| **Factory (factoría)** | Función o clase que crea instancias. Similar a un builder. |
| **Fake** | Doble de prueba con implementación funcional pero simple (ej: DB en memoria). |
| **Fixture** | Función que prepara el estado para un test. |
| **FIRST** | Fast, Independent, Repeatable, Self-validating, Timely. |
| **Hook** | Punto de extensión de pytest (ej: `pytest_collection_modifyitems`). |
| **Integration test** | Test que prueba la interacción entre módulos. |
| **Introspección** | Capacidad de pytest de mostrar valores reales en aserciones fallidas. |
| **Marker** | Etiqueta aplicada a un test (`@pytest.mark.slow`). |
| **Mock** | Doble de prueba que simula una dependencia y verifica interacciones. |
| **Mocking** | Técnica de reemplazar dependencias reales por dobles. |
| **Monkeypatch** | Fixture built-in para modificar atributos/env vars temporalmente. |
| **Parametrize** | Decorador que ejecuta un test con múltiples inputs. |
| **Patch** | Reemplazar un objeto/función por un mock durante un test. |
| **Property-based testing** | Técnica que genera inputs aleatorios para verificar propiedades. |
| **Pytest** | Framework de testing para Python. |
| **Scope (alcance)** | Vida útil de una fixture: function, class, module, session. |
| **Setup / Teardown** | Código que se ejecuta antes/después del test. |
| **Smoke test** | Test mínimo que verifica que la app arranca. |
| **Spy** | Doble que registra cómo fue llamado. |
| **Stub** | Doble que devuelve valores hardcodeados. |
| **Test case** | Un test individual (una función o método). |
| **Test discovery** | Mecanismo automático de pytest para encontrar tests. |
| **Test pyramid** | Principio: muchos unit tests, algunos integration, pocos E2E. |
| **TDD (Test-Driven Development)** | Escribir el test ANTES del código. |
| **Traceback** | Mensaje de error con la pila de llamadas. |
| **Unit test** | Test de una sola unidad lógica sin I/O. |
| **Unittest** | Módulo de testing de la stdlib de Python. |
| **Xfail (expected failure)** | Test que se espera que falle. |
| **Xpass (unexpected pass)** | Test marcado como xfail que pasó. |
| **Yield (en fixtures)** | Pausa el fixture para ejecutar el test, luego continúa con teardown. |

---

## Apéndice A: Cheatsheet de comandos

```bash
# Descubrimiento
pytest --collect-only            # Listar tests sin correr
pytest --co --quiet              # Más conciso

# Selección
pytest                          # Todo
pytest tests/                   # Un directorio
pytest test_x.py                # Un archivo
pytest test_x.py::test_y        # Un test
pytest -k pattern               # Por nombre
pytest -m marker                # Por marker
pytest -k "not slow"            # Excluir

# Ejecución
pytest -v                       # Verbose
pytest -vv                      # Muy verbose
pytest -s                       # No capturar stdout
pytest -x                       # Parar en primer fallo
pytest --maxfail=3              # Parar tras 3 fallos
pytest -n auto                   # Paralelo (xdist)
pytest --pdb                    # Debugger en fallo

# Cobertura
pytest --cov=src                # Cobertura básica
pytest --cov=src --cov-branch   # Branch coverage
pytest --cov=src --cov-report=html  # Reporte HTML

# Output
pytest --tb=short               # Traceback corto
pytest --tb=no                  # Sin traceback
pytest --durations=10           # Top 10 más lentos
pytest -q                       # Quiet
```

## Apéndice B: Estructura de proyecto de testing (template)

```
proyecto/
├── src/
│   └── paquete/
│       ├── domain/
│       ├── application/
│       └── infrastructure/
├── tests/
│   ├── __init__.py
│   ├── conftest.py                 # Fixtures globales
│   ├── unit/
│   │   ├── __init__.py
│   │   └── domain/
│   │       ├── __init__.py
│   │       ├── conftest.py         # Fixtures específicas
│   │       └── course/
│   │           ├── __init__.py
│   │           ├── conftest.py
│   │           ├── entities/
│   │           │   ├── __init__.py
│   │           │   ├── test_course.py
│   │           │   ├── test_module.py
│   │           │   ├── test_topic.py
│   │           │   └── test_content_block.py
│   │           └── enums/
│   │               ├── __init__.py
│   │               └── test_block_type.py
│   ├── integration/
│   │   ├── __init__.py
│   │   ├── persistence/
│   │   │   └── test_course_repository.py
│   │   └── ai/
│   │       └── test_gemini_client.py
│   ├── e2e/
│   │   └── test_api_generate_course.py
│   └── smoke/
│       ├── __init__.py
│       └── test_imports.py
├── pyproject.toml
└── .github/
    └── workflows/
        └── tests.yml
```

## Apéndice C: Recursos para profundizar

- [Documentación oficial de pytest](https://docs.pytest.org/)
- [Real Python - Testing](https://realpython.com/pytest-python-testing/)
- [Effective Python Testing With pytest](https://www.effectivepython.com/2020/01/22/testing-with-pytest/)
- [Hypothesis docs](https://hypothesis.readthedocs.io/)
- [Architecture Patterns with Python](https://www.cosmicpython.com/) (Clean Architecture + DDD con TDD)

---

> **Última nota**: las pruebas son código de primera clase. Merecen refactor, revisión por pares y mantenimiento continuo. Una suite de tests verde no es el objetivo final — es el punto de partida para refactorizar con confianza.
