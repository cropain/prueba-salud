import pandas as pd
import sqlite3
import os
# Importamos la función de hash para almacenar contraseñas seguras
from main import hash_password, DB_NAME

EXCEL_NAME = "Datos_Sinteticos_Prueba_Full_Stack_Junior_2026.xlsx"

def migrar():
    if not os.path.exists(EXCEL_NAME):
        print(f"❌ Error: No se encontró el archivo '{EXCEL_NAME}' en esta carpeta.")
        return

    try:
        print(f" Leyendo el archivo {EXCEL_NAME}...")
        
        # 1. Cargar datos del Excel
        df_cat = pd.read_excel(EXCEL_NAME, sheet_name="Catalogos")
        eps_unicas = df_cat[['eps_codigo', 'eps_nombre']].dropna().drop_duplicates()
        
        df_usr = pd.read_excel(EXCEL_NAME, sheet_name="Usuarios_Login")
        df_pac = pd.read_excel(EXCEL_NAME, sheet_name="Pacientes")

        print(" Conectando a la base de datos...")
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        # Limpiar datos previos para evitar duplicados en la prueba
        cursor.execute("DELETE FROM eps")
        cursor.execute("DELETE FROM usuarios")
        cursor.execute("DELETE FROM pacientes")
        conn.commit()
        
        # 2. Insertar Catálogo de EPS en la tabla 'eps' (nueva definición)
        print(" Registrando catálogo de EPS...")
        for _, row in eps_unicas.iterrows():
            cursor.execute(
                "INSERT OR IGNORE INTO eps (codigo, nombre) VALUES (?, ?)",
                (str(row['eps_codigo']).strip(), str(row['eps_nombre']).strip())
            )
            
        # 3. Insertar Usuarios de demostración con hash de seguridad
        print("👤 Registrando usuarios demo con hash de contraseña...")
        for _, row in df_usr.iterrows():
            plain_password = str(row['password_demo']).strip()
            hashed = hash_password(plain_password) # Encriptamos con la utilidad de main.py
            
            cursor.execute(
                "INSERT OR IGNORE INTO usuarios (usuario, password_hash, nombre, rol) VALUES (?, ?, ?, ?)",
                (
                    str(row['usuario']).strip(),
                    hashed,
                    str(row['nombre']).strip(),
                    str(row['rol']).strip()
                )
            )
            
        # 4. Insertar los 1.000 Pacientes sintéticos
        print("🩺 Importando 1,000 pacientes sintéticos...")
        registrados = 0
        for _, row in df_pac.iterrows():
            fecha_nac = str(row['fecha_nacimiento']).split()[0] # Extrae solo AAAA-MM-DD
            
            cursor.execute(
                """
                INSERT INTO pacientes 
                    (nombre, tipo_documento, identificacion, fecha_nacimiento, genero, telefono, eps_codigo, prioridad, estado)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(row['nombre_completo']).strip(),
                    str(row['tipo_documento']).strip(),
                    str(row['documento']).strip(),
                    fecha_nac,
                    str(row['genero']).strip(),
                    str(row['telefono']).strip(),
                    str(row['eps_codigo']).strip(),
                    str(row['prioridad']).strip(),
                    str(row['estado']).strip()
                )
            )
            registrados += 1
            
        conn.commit()
        conn.close()
        print(f"\n ¡MIGRACIÓN COMPLETADA CON ÉXITO!")
        print(f"   • EPS registradas de forma única.")
        print(f"   • Usuarios cargados de forma segura con Hash.")
        print(f"   • {registrados} pacientes listos para el Dashboard.")
        
    except Exception as e:
        print(f"❌ Error durante la migración: {e}")

if __name__ == "__main__":
    migrar()