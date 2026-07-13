from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional
import sqlite3

DB_NAME = "pacientes.db"

app = FastAPI(title="API Pacientes - Salud Digital")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS pacientes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                identificacion TEXT NOT NULL UNIQUE,
                edad INTEGER NOT NULL,
                sintomas TEXT NOT NULL,
                estado TEXT NOT NULL DEFAULT 'Pendiente'
            )
            """
        )
        conn.commit()


init_db()


class PacienteCreate(BaseModel):
    nombre: str = Field(..., min_length=1)
    identificacion: str = Field(..., min_length=1)
    edad: int = Field(..., ge=0)
    sintomas: str = Field(..., min_length=1)


class EstadoUpdate(BaseModel):
    estado: str = Field(..., min_length=1)


class Paciente(BaseModel):
    id: int
    nombre: str
    identificacion: str
    edad: int
    sintomas: str
    estado: str


def row_to_dict(row) -> dict:
    return {
        "id": row[0],
        "nombre": row[1],
        "identificacion": row[2],
        "edad": row[3],
        "sintomas": row[4],
        "estado": row[5],
    }


@app.get("/pacientes", response_model=list[Paciente])
def listar_pacientes():
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.execute(
            "SELECT id, nombre, identificacion, edad, sintomas, estado FROM pacientes ORDER BY id DESC"
        )
        rows = cursor.fetchall()
    return [row_to_dict(r) for r in rows]


@app.post("/pacientes", response_model=Paciente, status_code=201)
def crear_paciente(paciente: PacienteCreate):
    try:
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.execute(
                """
                INSERT INTO pacientes (nombre, identificacion, edad, sintomas, estado)
                VALUES (?, ?, ?, ?, 'Pendiente')
                """,
                (paciente.nombre, paciente.identificacion, paciente.edad, paciente.sintomas),
            )
            conn.commit()
            new_id = cursor.lastrowid
            row = conn.execute(
                "SELECT id, nombre, identificacion, edad, sintomas, estado FROM pacientes WHERE id = ?",
                (new_id,),
            ).fetchone()
        return row_to_dict(row)
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="La identificación ya existe")


@app.put("/pacientes/{paciente_id}/estado", response_model=Paciente)
def actualizar_estado(paciente_id: int, data: EstadoUpdate):
    with sqlite3.connect(DB_NAME) as conn:
        existe = conn.execute(
            "SELECT id FROM pacientes WHERE id = ?", (paciente_id,)
        ).fetchone()
        if not existe:
            raise HTTPException(status_code=404, detail="Paciente no encontrado")

        conn.execute(
            "UPDATE pacientes SET estado = ? WHERE id = ?",
            (data.estado, paciente_id),
        )
        conn.commit()
        row = conn.execute(
            "SELECT id, nombre, identificacion, edad, sintomas, estado FROM pacientes WHERE id = ?",
            (paciente_id,),
        ).fetchone()
    return row_to_dict(row)


@app.delete("/pacientes/{paciente_id}", status_code=204)
def eliminar_paciente(paciente_id: int):
    with sqlite3.connect(DB_NAME) as conn:
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
