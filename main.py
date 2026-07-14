"""
API - Salud Digital / GoEcosystem
Backend FastAPI + SQLite para el sistema de gestión de pacientes en espera.

Endpoints:
  POST   /auth/login              -> valida usuario/contraseña, retorna {usuario, nombre, rol}
  GET    /eps                     -> catálogo de EPS {codigo, nombre}
  GET    /dashboard               -> {total, pendiente, en_atencion, atendidos, prioridad_alta}
  GET    /patients                -> lista pacientes (?search=&estado=&prioridad=)
  POST   /patients                -> crea paciente
  PUT    /patients/{id}           -> actualiza cualquier campo (parcial o total)
  DELETE /patients/{id}           -> elimina paciente
"""

import hashlib
import secrets
import sqlite3
from datetime import date, datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

DB_NAME = "pacientes.db"

app = FastAPI(title="API Pacientes - Salud Digital")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ESTADOS_VALIDOS = ("Pendiente", "En atención", "Atendido")
PRIORIDADES_VALIDAS = ("Alta", "Media", "Baja")

EPS_SEED = [
    ("EPS001", "Nueva EPS"),
    ("EPS002", "Sura EPS"),
    ("EPS003", "Sanitas EPS"),
    ("EPS004", "Compensar EPS"),
    ("EPS005", "Salud Total EPS"),
    ("EPS006", "Famisanar EPS"),
    ("EPS007", "Coosalud EPS"),
    ("EPS008", "Mutual Ser EPS"),
    ("EPS009", "Aliansalud EPS"),
    ("EPS010", "Cajacopi EPS"),
]

# ---------------------------------------------------------------------------
# Utilidades de contraseña (hash + salt, sin dependencias externas)
# ---------------------------------------------------------------------------

def hash_password(password: str, salt: Optional[str] = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.sha256(f"{salt}{password}".encode("utf-8")).hexdigest()
    return f"{salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt, _ = stored.split("$", 1)
    except ValueError:
        return False
    return hash_password(password, salt) == stored


# ---------------------------------------------------------------------------
# Inicialización de base de datos
# ---------------------------------------------------------------------------

def get_conn():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                nombre TEXT NOT NULL,
                rol TEXT NOT NULL DEFAULT 'Usuario'
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS eps (
                codigo TEXT PRIMARY KEY,
                nombre TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS pacientes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                tipo_documento TEXT NOT NULL,
                identificacion TEXT NOT NULL UNIQUE,
                fecha_nacimiento TEXT NOT NULL,
                genero TEXT NOT NULL,
                telefono TEXT NOT NULL,
                eps_codigo TEXT NOT NULL,
                prioridad TEXT NOT NULL,
                estado TEXT NOT NULL DEFAULT 'Pendiente'
            )
            """
        )
        conn.commit()

        # --- Seed EPS ---
        existing = conn.execute("SELECT COUNT(*) FROM eps").fetchone()[0]
        if existing == 0:
            conn.executemany("INSERT INTO eps (codigo, nombre) VALUES (?, ?)", EPS_SEED)
            conn.commit()

        # --- Seed usuario admin por defecto ---
        existing_user = conn.execute(
            "SELECT COUNT(*) FROM usuarios WHERE usuario = ?", ("admin",)
        ).fetchone()[0]
        if existing_user == 0:
            conn.execute(
                "INSERT INTO usuarios (usuario, password_hash, nombre, rol) VALUES (?, ?, ?, ?)",
                ("admin", hash_password("admin123"), "Administrador", "Administrador"),
            )
            conn.commit()


init_db()


# ---------------------------------------------------------------------------
# Modelos Pydantic
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    usuario: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class LoginResponse(BaseModel):
    usuario: str
    nombre: str
    rol: str


class EPS(BaseModel):
    codigo: str
    nombre: str


class DashboardResponse(BaseModel):
    total: int
    pendiente: int
    en_atencion: int
    atendidos: int
    prioridad_alta: int


class PacienteCreate(BaseModel):
    nombre: str = Field(..., min_length=1)
    tipo_documento: str = Field(..., min_length=1)
    identificacion: str = Field(..., min_length=1)
    fecha_nacimiento: date
    genero: str = Field(..., min_length=1)
    telefono: str = Field(..., min_length=1)
    eps_codigo: str = Field(..., min_length=1)
    prioridad: str
    estado: str = "Pendiente"

    @field_validator("fecha_nacimiento")
    @classmethod
    def fecha_no_futura(cls, v: date) -> date:
        if v > date.today():
            raise ValueError("La fecha de nacimiento no puede ser futura")
        return v

    @field_validator("prioridad")
    @classmethod
    def prioridad_valida(cls, v: str) -> str:
        if v not in PRIORIDADES_VALIDAS:
            raise ValueError(f"Prioridad inválida. Usa una de: {PRIORIDADES_VALIDAS}")
        return v

    @field_validator("estado")
    @classmethod
    def estado_valido(cls, v: str) -> str:
        if v not in ESTADOS_VALIDOS:
            raise ValueError(f"Estado inválido. Usa uno de: {ESTADOS_VALIDOS}")
        return v


class PacienteUpdate(BaseModel):
    """Todos los campos son opcionales para permitir actualizaciones parciales
    (por ejemplo, cambiar solo el estado o la prioridad desde la tabla)."""

    nombre: Optional[str] = Field(None, min_length=1)
    tipo_documento: Optional[str] = Field(None, min_length=1)
    identificacion: Optional[str] = Field(None, min_length=1)
    fecha_nacimiento: Optional[date] = None
    genero: Optional[str] = Field(None, min_length=1)
    telefono: Optional[str] = Field(None, min_length=1)
    eps_codigo: Optional[str] = Field(None, min_length=1)
    prioridad: Optional[str] = None
    estado: Optional[str] = None

    @field_validator("fecha_nacimiento")
    @classmethod
    def fecha_no_futura(cls, v: Optional[date]) -> Optional[date]:
        if v is not None and v > date.today():
            raise ValueError("La fecha de nacimiento no puede ser futura")
        return v

    @field_validator("prioridad")
    @classmethod
    def prioridad_valida(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in PRIORIDADES_VALIDAS:
            raise ValueError(f"Prioridad inválida. Usa una de: {PRIORIDADES_VALIDAS}")
        return v

    @field_validator("estado")
    @classmethod
    def estado_valido(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ESTADOS_VALIDOS:
            raise ValueError(f"Estado inválido. Usa uno de: {ESTADOS_VALIDOS}")
        return v


class Paciente(BaseModel):
    id: int
    nombre: str
    tipo_documento: str
    identificacion: str
    fecha_nacimiento: str
    genero: str
    telefono: str
    eps_codigo: str
    prioridad: str
    estado: str


def row_to_paciente(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "nombre": row["nombre"],
        "tipo_documento": row["tipo_documento"],
        "identificacion": row["identificacion"],
        "fecha_nacimiento": row["fecha_nacimiento"],
        "genero": row["genero"],
        "telefono": row["telefono"],
        "eps_codigo": row["eps_codigo"],
        "prioridad": row["prioridad"],
        "estado": row["estado"],
    }


# ---------------------------------------------------------------------------
# AUTH
# ---------------------------------------------------------------------------

@app.post("/auth/login", response_model=LoginResponse)
def login(data: LoginRequest):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT usuario, password_hash, nombre, rol FROM usuarios WHERE usuario = ?",
            (data.usuario,),
        ).fetchone()

    if not row or not verify_password(data.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos")

    return {"usuario": row["usuario"], "nombre": row["nombre"], "rol": row["rol"]}


# ---------------------------------------------------------------------------
# EPS
# ---------------------------------------------------------------------------

@app.get("/eps", response_model=list[EPS])
def listar_eps():
    with get_conn() as conn:
        rows = conn.execute("SELECT codigo, nombre FROM eps ORDER BY nombre").fetchall()
    return [{"codigo": r["codigo"], "nombre": r["nombre"]} for r in rows]


# ---------------------------------------------------------------------------
# DASHBOARD
# ---------------------------------------------------------------------------

@app.get("/dashboard", response_model=DashboardResponse)
def dashboard():
    with get_conn() as conn:
        total = conn.execute("SELECT COUNT(*) FROM pacientes").fetchone()[0]
        pendiente = conn.execute(
            "SELECT COUNT(*) FROM pacientes WHERE estado = 'Pendiente'"
        ).fetchone()[0]
        en_atencion = conn.execute(
            "SELECT COUNT(*) FROM pacientes WHERE estado = 'En atención'"
        ).fetchone()[0]
        atendidos = conn.execute(
            "SELECT COUNT(*) FROM pacientes WHERE estado = 'Atendido'"
        ).fetchone()[0]
        prioridad_alta = conn.execute(
            "SELECT COUNT(*) FROM pacientes WHERE prioridad = 'Alta'"
        ).fetchone()[0]

    return {
        "total": total,
        "pendiente": pendiente,
        "en_atencion": en_atencion,
        "atendidos": atendidos,
        "prioridad_alta": prioridad_alta,
    }


# ---------------------------------------------------------------------------
# PACIENTES
# ---------------------------------------------------------------------------

@app.get("/patients", response_model=list[Paciente])
def listar_pacientes(
    search: Optional[str] = Query(None, description="Busca por nombre o identificación"),
    estado: Optional[str] = Query(None),
    prioridad: Optional[str] = Query(None),
):
    query = """
        SELECT id, nombre, tipo_documento, identificacion, fecha_nacimiento,
               genero, telefono, eps_codigo, prioridad, estado
        FROM pacientes
        WHERE 1=1
    """
    params: list = []

    if search:
        query += " AND (nombre LIKE ? OR identificacion LIKE ?)"
        like = f"%{search}%"
        params.extend([like, like])

    if estado:
        query += " AND estado = ?"
        params.append(estado)

    if prioridad:
        query += " AND prioridad = ?"
        params.append(prioridad)

    query += " ORDER BY id DESC"

    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()

    return [row_to_paciente(r) for r in rows]


@app.post("/patients", response_model=Paciente, status_code=201)
def crear_paciente(paciente: PacienteCreate):
    try:
        with get_conn() as conn:
            cursor = conn.execute(
                """
                INSERT INTO pacientes
                    (nombre, tipo_documento, identificacion, fecha_nacimiento,
                     genero, telefono, eps_codigo, prioridad, estado)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    paciente.nombre,
                    paciente.tipo_documento,
                    paciente.identificacion,
                    paciente.fecha_nacimiento.isoformat(),
                    paciente.genero,
                    paciente.telefono,
                    paciente.eps_codigo,
                    paciente.prioridad,
                    paciente.estado,
                ),
            )
            conn.commit()
            new_id = cursor.lastrowid
            row = conn.execute(
                """
                SELECT id, nombre, tipo_documento, identificacion, fecha_nacimiento,
                       genero, telefono, eps_codigo, prioridad, estado
                FROM pacientes WHERE id = ?
                """,
                (new_id,),
            ).fetchone()
        return row_to_paciente(row)
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="La identificación ya existe")


@app.put("/patients/{paciente_id}", response_model=Paciente)
def actualizar_paciente(paciente_id: int, data: PacienteUpdate):
    campos = data.model_dump(exclude_unset=True)

    if not campos:
        raise HTTPException(status_code=400, detail="No se enviaron campos para actualizar")

    with get_conn() as conn:
        existe = conn.execute(
            "SELECT id FROM pacientes WHERE id = ?", (paciente_id,)
        ).fetchone()
        if not existe:
            raise HTTPException(status_code=404, detail="Paciente no encontrado")

        set_clause = ", ".join(f"{campo} = ?" for campo in campos)
        valores = [
            v.isoformat() if isinstance(v, date) else v for v in campos.values()
        ]
        valores.append(paciente_id)

        try:
            conn.execute(
                f"UPDATE pacientes SET {set_clause} WHERE id = ?", valores
            )
            conn.commit()
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=400, detail="La identificación ya existe")

        row = conn.execute(
            """
            SELECT id, nombre, tipo_documento, identificacion, fecha_nacimiento,
                   genero, telefono, eps_codigo, prioridad, estado
            FROM pacientes WHERE id = ?
            """,
            (paciente_id,),
        ).fetchone()

    return row_to_paciente(row)


@app.delete("/patients/{paciente_id}", status_code=204)
def eliminar_paciente(paciente_id: int):
    with get_conn() as conn:
        existe = conn.execute(
            "SELECT id FROM pacientes WHERE id = ?", (paciente_id,)
        ).fetchone()
        if not existe:
            raise HTTPException(status_code=404, detail="Paciente no encontrado")

        conn.execute("DELETE FROM pacientes WHERE id = ?", (paciente_id,))
        conn.commit()
    return None


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
