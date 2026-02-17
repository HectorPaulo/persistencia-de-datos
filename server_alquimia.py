import os
import sys
import signal
import psycopg2
import psycopg2.extras

from omniORB import CORBA

import AlquimiaApp
import AlquimiaApp__POA


DB_DSN = os.getenv(
    "DB_DSN",
    "dbname=persistencia user=postgres password=postgres host=localhost port=5432",
)
IOR_FILE_HECHIZO = os.getenv("IOR_FILE_HECHIZO", "HechizoService.ior")
IOR_FILE_INGREDIENTE = os.getenv("IOR_FILE_INGREDIENTE", "IngredienteService.ior")
IOR_FILE_RECETA = os.getenv("IOR_FILE_RECETA", "RecetaAlquimicaService.ior")


# ==================== IMPLEMENTACIÓN SERVICIO HECHIZOS ====================

class HechizoServiceImpl(AlquimiaApp__POA.HechizoService):
    def __init__(self, conn):
        self.conn = conn

    # Después
    def crear(self, nombre, tipo_magia, nivel_poder, efecto, activo):
        try:
            with self.conn, self.conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO hechizos(nombre, tipo_magia, nivel_poder, efecto, activo)
                    VALUES (%s, %s, %s, %s, %s) RETURNING id
                    """,
                    (nombre, tipo_magia, nivel_poder, efecto, activo),
                )
                return cur.fetchone()[0]
        except Exception as e:
            self.conn.rollback()
            raise

    def obtener(self, id):
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT id, nombre, tipo_magia, nivel_poder, efecto, activo FROM hechizos WHERE id=%s",
                (id,),
            )
            r = cur.fetchone()
            if not r:
                raise AlquimiaApp.NotFound(f"Hechizo {id} no existe")
            return AlquimiaApp.Hechizo(
                r["id"], r["nombre"], r["tipo_magia"], r["nivel_poder"], r["efecto"], r["activo"]
            )

    def listar(self):
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT id, nombre, tipo_magia, nivel_poder, efecto, activo FROM hechizos ORDER BY id")
            rows = cur.fetchall()
            return [
                AlquimiaApp.Hechizo(
                    r["id"], r["nombre"], r["tipo_magia"], r["nivel_poder"], r["efecto"], r["activo"]
                )
                for r in rows
            ]

    def actualizar(self, id, nombre, tipo_magia, nivel_poder, efecto, activo):
        with self.conn, self.conn.cursor() as cur:
            cur.execute(
                """
                UPDATE hechizos
                SET nombre=%s, tipo_magia=%s, nivel_poder=%s, efecto=%s, activo=%s
                WHERE id=%s
                """,
                (nombre, tipo_magia, nivel_poder, efecto, activo, id),
            )
            if cur.rowcount == 0:
                raise AlquimiaApp.NotFound(f"Hechizo {id} no existe")

    def eliminar(self, id):
        with self.conn, self.conn.cursor() as cur:
            # Borrado en cascada: primero eliminar recetas asociadas
            cur.execute("DELETE FROM recetas_alquimicas WHERE hechizo_id=%s", (id,))
            # Luego eliminar el hechizo
            cur.execute("DELETE FROM hechizos WHERE id=%s", (id,))
            if cur.rowcount == 0:
                raise AlquimiaApp.NotFound(f"Hechizo {id} no existe")

    def obtenerConIngredientes(self, id):
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # Obtener hechizo
            cur.execute(
                "SELECT id, nombre, tipo_magia, nivel_poder, efecto, activo FROM hechizos WHERE id=%s",
                (id,),
            )
            h = cur.fetchone()
            if not h:
                raise AlquimiaApp.NotFound(f"Hechizo {id} no existe")

            hechizo = AlquimiaApp.Hechizo(
                h["id"], h["nombre"], h["tipo_magia"], h["nivel_poder"], h["efecto"], h["activo"]
            )

            # Obtener ingredientes relacionados (INNER JOIN)
            cur.execute(
                """
                SELECT i.id, i.nombre, i.origen, i.potencia_magica, i.cantidad_disponible, i.esta_prohibido,
                       r.cantidad_requerida
                FROM ingredientes i
                INNER JOIN recetas_alquimicas r ON i.id = r.ingrediente_id
                WHERE r.hechizo_id = %s
                ORDER BY i.id
                """,
                (id,),
            )
            rows = cur.fetchall()

            ingredientes = []
            cantidades = []
            for r in rows:
                ingredientes.append(
                    AlquimiaApp.Ingrediente(
                        r["id"], r["nombre"], r["origen"],
                        float(r["potencia_magica"]), r["cantidad_disponible"], r["esta_prohibido"]
                    )
                )
                cantidades.append(r["cantidad_requerida"])

            return AlquimiaApp.HechizoConIngredientes(hechizo, ingredientes, cantidades)


# ==================== IMPLEMENTACIÓN SERVICIO INGREDIENTES ====================

class IngredienteServiceImpl(AlquimiaApp__POA.IngredienteService):
    def __init__(self, conn):
        self.conn = conn

    def crear(self, nombre, origen, potencia_magica, cantidad_disponible, esta_prohibido):
        with self.conn, self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO ingredientes(nombre, origen, potencia_magica, cantidad_disponible, esta_prohibido)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
                """,
                (nombre, origen, potencia_magica, cantidad_disponible, esta_prohibido),
            )
            return cur.fetchone()[0]

    def obtener(self, id):
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT id, nombre, origen, potencia_magica, cantidad_disponible, esta_prohibido FROM ingredientes WHERE id=%s",
                (id,),
            )
            r = cur.fetchone()
            if not r:
                raise AlquimiaApp.NotFound(f"Ingrediente {id} no existe")
            return AlquimiaApp.Ingrediente(
                r["id"], r["nombre"], r["origen"],
                float(r["potencia_magica"]), r["cantidad_disponible"], r["esta_prohibido"]
            )

    def listar(self):
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT id, nombre, origen, potencia_magica, cantidad_disponible, esta_prohibido FROM ingredientes ORDER BY id")
            rows = cur.fetchall()
            return [
                AlquimiaApp.Ingrediente(
                    r["id"], r["nombre"], r["origen"],
                    float(r["potencia_magica"]), r["cantidad_disponible"], r["esta_prohibido"]
                )
                for r in rows
            ]

    def actualizar(self, id, nombre, origen, potencia_magica, cantidad_disponible, esta_prohibido):
        with self.conn, self.conn.cursor() as cur:
            cur.execute(
                """
                UPDATE ingredientes
                SET nombre=%s, origen=%s, potencia_magica=%s, cantidad_disponible=%s, esta_prohibido=%s
                WHERE id=%s
                """,
                (nombre, origen, potencia_magica, cantidad_disponible, esta_prohibido, id),
            )
            if cur.rowcount == 0:
                raise AlquimiaApp.NotFound(f"Ingrediente {id} no existe")

    def eliminar(self, id):
        with self.conn, self.conn.cursor() as cur:
            # Borrado en cascada: primero eliminar recetas asociadas
            cur.execute("DELETE FROM recetas_alquimicas WHERE ingrediente_id=%s", (id,))
            # Luego eliminar el ingrediente
            cur.execute("DELETE FROM ingredientes WHERE id=%s", (id,))
            if cur.rowcount == 0:
                raise AlquimiaApp.NotFound(f"Ingrediente {id} no existe")

    def obtenerConHechizos(self, id):
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # Obtener ingrediente
            cur.execute(
                "SELECT id, nombre, origen, potencia_magica, cantidad_disponible, esta_prohibido FROM ingredientes WHERE id=%s",
                (id,),
            )
            i = cur.fetchone()
            if not i:
                raise AlquimiaApp.NotFound(f"Ingrediente {id} no existe")

            ingrediente = AlquimiaApp.Ingrediente(
                i["id"], i["nombre"], i["origen"],
                float(i["potencia_magica"]), i["cantidad_disponible"], i["esta_prohibido"]
            )

            # Obtener hechizos relacionados (INNER JOIN)
            cur.execute(
                """
                SELECT h.id, h.nombre, h.tipo_magia, h.nivel_poder, h.efecto, h.activo,
                       r.cantidad_requerida
                FROM hechizos h
                INNER JOIN recetas_alquimicas r ON h.id = r.hechizo_id
                WHERE r.ingrediente_id = %s
                ORDER BY h.id
                """,
                (id,),
            )
            rows = cur.fetchall()

            hechizos = []
            cantidades = []
            for r in rows:
                hechizos.append(
                    AlquimiaApp.Hechizo(
                        r["id"], r["nombre"], r["tipo_magia"], r["nivel_poder"], r["efecto"], r["activo"]
                    )
                )
                cantidades.append(r["cantidad_requerida"])

            return AlquimiaApp.IngredienteConHechizos(ingrediente, hechizos, cantidades)


# ==================== IMPLEMENTACIÓN SERVICIO RECETAS ALQUÍMICAS ====================

class RecetaAlquimicaServiceImpl(AlquimiaApp__POA.RecetaAlquimicaService):
    def __init__(self, conn):
        self.conn = conn

    def crear(self, hechizo_id, ingrediente_id, cantidad_requerida, funcion_en_hechizo):
        with self.conn, self.conn.cursor() as cur:
            # Verificar que hechizo existe
            cur.execute("SELECT id FROM hechizos WHERE id=%s", (hechizo_id,))
            if not cur.fetchone():
                raise AlquimiaApp.InvalidOperation(f"Hechizo {hechizo_id} no existe")

            # Verificar que ingrediente existe
            cur.execute("SELECT id FROM ingredientes WHERE id=%s", (ingrediente_id,))
            if not cur.fetchone():
                raise AlquimiaApp.InvalidOperation(f"Ingrediente {ingrediente_id} no existe")

            # Crear receta
            cur.execute(
                """
                INSERT INTO recetas_alquimicas(hechizo_id, ingrediente_id, cantidad_requerida, funcion_en_hechizo)
                VALUES (%s, %s, %s, %s)
                RETURNING id
                """,
                (hechizo_id, ingrediente_id, cantidad_requerida, funcion_en_hechizo),
            )
            return cur.fetchone()[0]

    def obtener(self, id):
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT id, hechizo_id, ingrediente_id, cantidad_requerida, funcion_en_hechizo FROM recetas_alquimicas WHERE id=%s",
                (id,),
            )
            r = cur.fetchone()
            if not r:
                raise AlquimiaApp.NotFound(f"RecetaAlquimica {id} no existe")
            return AlquimiaApp.RecetaAlquimica(
                r["id"], r["hechizo_id"], r["ingrediente_id"], r["cantidad_requerida"], r["funcion_en_hechizo"]
            )

    def listar(self):
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT id, hechizo_id, ingrediente_id, cantidad_requerida, funcion_en_hechizo FROM recetas_alquimicas ORDER BY id")
            rows = cur.fetchall()
            return [
                AlquimiaApp.RecetaAlquimica(
                    r["id"], r["hechizo_id"], r["ingrediente_id"], r["cantidad_requerida"], r["funcion_en_hechizo"]
                )
                for r in rows
            ]

    def actualizar(self, id, cantidad_requerida, funcion_en_hechizo):
        with self.conn, self.conn.cursor() as cur:
            cur.execute(
                """
                UPDATE recetas_alquimicas
                SET cantidad_requerida=%s, funcion_en_hechizo=%s
                WHERE id=%s
                """,
                (cantidad_requerida, funcion_en_hechizo, id),
            )
            if cur.rowcount == 0:
                raise AlquimiaApp.NotFound(f"RecetaAlquimica {id} no existe")

    def eliminar(self, id):
        with self.conn, self.conn.cursor() as cur:
            cur.execute("DELETE FROM recetas_alquimicas WHERE id=%s", (id,))
            if cur.rowcount == 0:
                raise AlquimiaApp.NotFound(f"RecetaAlquimica {id} no existe")

    def obtenerPorHechizo(self, hechizo_id):
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT id, hechizo_id, ingrediente_id, cantidad_requerida, funcion_en_hechizo FROM recetas_alquimicas WHERE hechizo_id=%s ORDER BY id",
                (hechizo_id,),
            )
            rows = cur.fetchall()
            return [
                AlquimiaApp.RecetaAlquimica(
                    r["id"], r["hechizo_id"], r["ingrediente_id"], r["cantidad_requerida"], r["funcion_en_hechizo"]
                )
                for r in rows
            ]

    def obtenerPorIngrediente(self, ingrediente_id):
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT id, hechizo_id, ingrediente_id, cantidad_requerida, funcion_en_hechizo FROM recetas_alquimicas WHERE ingrediente_id=%s ORDER BY id",
                (ingrediente_id,),
            )
            rows = cur.fetchall()
            return [
                AlquimiaApp.RecetaAlquimica(
                    r["id"], r["hechizo_id"], r["ingrediente_id"], r["cantidad_requerida"], r["funcion_en_hechizo"]
                )
                for r in rows
            ]


# ==================== MAIN ====================

def main():
    conn = psycopg2.connect(DB_DSN)

    orb = CORBA.ORB_init(sys.argv, CORBA.ORB_ID)

    poa = orb.resolve_initial_references("RootPOA")
    poa_mgr = poa._get_the_POAManager()

    # Crear e inicializar servicios
    hechizo_servant = HechizoServiceImpl(conn)
    hechizo_objref = hechizo_servant._this()

    ingrediente_servant = IngredienteServiceImpl(conn)
    ingrediente_objref = ingrediente_servant._this()

    receta_servant = RecetaAlquimicaServiceImpl(conn)
    receta_objref = receta_servant._this()

    poa_mgr.activate()

    # Escribir IORs
    ior_hechizo = orb.object_to_string(hechizo_objref)
    with open(IOR_FILE_HECHIZO, "w") as f:
        f.write(ior_hechizo)

    ior_ingrediente = orb.object_to_string(ingrediente_objref)
    with open(IOR_FILE_INGREDIENTE, "w") as f:
        f.write(ior_ingrediente)

    ior_receta = orb.object_to_string(receta_objref)
    with open(IOR_FILE_RECETA, "w") as f:
        f.write(ior_receta)

    print("=" * 60)
    print("Servidor CORBA de Alquimia listo")
    print("=" * 60)
    print(f"  HechizoService       -> {IOR_FILE_HECHIZO}")
    print(f"  IngredienteService   -> {IOR_FILE_INGREDIENTE}")
    print(f"  RecetaAlquimicaService -> {IOR_FILE_RECETA}")
    print("=" * 60)

    def shutdown(signum, frame):
        try:
            print("\nApagando servidor...")
            for ior_file in [IOR_FILE_HECHIZO, IOR_FILE_INGREDIENTE, IOR_FILE_RECETA]:
                try:
                    os.remove(ior_file)
                except OSError:
                    pass
            try:
                conn.close()
            except Exception:
                pass
            orb.shutdown(True)
        except Exception:
            pass

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    orb.run()


if __name__ == "__main__":
    main()
