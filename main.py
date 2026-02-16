from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List
import psycopg2
from psycopg2.extras import RealDictCursor
import os

app = FastAPI()

# Configuración de conexión a PostgreSQL
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "database": os.getenv("DB_NAME", "persistencia"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "postgres"),
    "port": os.getenv("DB_PORT", "5432")
}

def get_db_connection():
    return psycopg2.connect(**DB_CONFIG)

# Modelos Pydantic
class ProductoCreate(BaseModel):
    nombre: str
    precio: float = Field(ge=0)
    cantidad: int = Field(ge=0)
    estado: bool = True

class ProductoUpdate(BaseModel):
    nombre: Optional[str] = None
    precio: Optional[float] = Field(None, ge=0)
    cantidad: Optional[int] = Field(None, ge=0)
    estado: Optional[bool] = None

class VentaCreate(BaseModel):
    producto_id: int
    cantidad_vendida: int = Field(ge=1)
    precio_unitario: float = Field(ge=0)
    cliente: str

class VentaUpdate(BaseModel):
    cantidad_vendida: Optional[int] = Field(None, ge=1)
    precio_unitario: Optional[float] = Field(None, ge=0)
    cliente: Optional[str] = None

# ==================== ENDPOINTS PRODUCTOS (Tabla Principal) ====================

@app.get("/productos")
async def get_all_productos():
    """GET ALL - Obtener todos los productos"""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("SELECT * FROM productos ORDER BY id")
        productos = cur.fetchall()
        return {"productos": productos}
    finally:
        cur.close()
        conn.close()

@app.get("/productos/{producto_id}")
async def get_producto_by_id(producto_id: int):
    """GET - Obtener producto por ID con sus ventas (INNER JOIN)"""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        # Producto principal
        cur.execute("SELECT * FROM productos WHERE id = %s", (producto_id,))
        producto = cur.fetchone()

        if not producto:
            raise HTTPException(status_code=404, detail="Producto no encontrado")

        # Ventas relacionadas (INNER JOIN - solo ventas existentes)
        cur.execute("""
            SELECT v.id, v.cantidad_vendida, v.precio_unitario, v.cliente, v.fecha_venta,
                   p.nombre as producto_nombre, p.precio as precio_actual
            FROM ventas v
            INNER JOIN productos p ON v.producto_id = p.id
            WHERE v.producto_id = %s
            ORDER BY v.fecha_venta DESC
        """, (producto_id,))
        ventas_inner = cur.fetchall()

        # LEFT JOIN - todas las ventas o NULL si no hay
        cur.execute("""
            SELECT p.id, p.nombre, p.precio, p.cantidad, p.estado,
                   v.id as venta_id, v.cantidad_vendida, v.cliente, v.fecha_venta
            FROM productos p
            LEFT JOIN ventas v ON p.id = v.producto_id
            WHERE p.id = %s
            ORDER BY v.fecha_venta DESC
        """, (producto_id,))
        ventas_left = cur.fetchall()

        return {
            "producto": producto,
            "ventas_inner_join": ventas_inner,
            "ventas_left_join": ventas_left
        }
    finally:
        cur.close()
        conn.close()

# ==================== ENDPOINTS VENTAS (Tabla Secundaria) ====================

@app.get("/ventas")
async def get_all_ventas():
    """GET ALL - Obtener todas las ventas"""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            SELECT v.*, p.nombre as producto_nombre
            FROM ventas v
            LEFT JOIN productos p ON v.producto_id = p.id
            ORDER BY v.id
        """)
        ventas = cur.fetchall()
        return {"ventas": ventas}
    finally:
        cur.close()
        conn.close()

@app.get("/ventas/{venta_id}")
async def get_venta_by_id(venta_id: int):
    """GET - Obtener venta por ID con relación a productos (INNER JOIN y RIGHT JOIN)"""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        # Venta principal
        cur.execute("SELECT * FROM ventas WHERE id = %s", (venta_id,))
        venta = cur.fetchone()

        if not venta:
            raise HTTPException(status_code=404, detail="Venta no encontrada")

        # INNER JOIN - venta con su producto
        cur.execute("""
            SELECT v.id, v.cantidad_vendida, v.precio_unitario, v.cliente, v.fecha_venta,
                   p.id as producto_id, p.nombre, p.precio, p.cantidad as stock_actual
            FROM ventas v
            INNER JOIN productos p ON v.producto_id = p.id
            WHERE v.id = %s
        """, (venta_id,))
        venta_inner = cur.fetchone()

        # RIGHT JOIN simulado (PostgreSQL soporta RIGHT JOIN)
        # Muestra todos los productos, incluso si no tienen esta venta específica
        cur.execute("""
            SELECT p.id as producto_id, p.nombre, p.precio, p.cantidad,
                   v.id as venta_id, v.cantidad_vendida, v.cliente
            FROM ventas v
            RIGHT JOIN productos p ON v.producto_id = p.id AND v.id = %s
            ORDER BY p.id
        """, (venta_id,))
        productos_right = cur.fetchall()

        return {
            "venta": venta,
            "venta_con_producto_inner": venta_inner,
            "productos_right_join": productos_right
        }
    finally:
        cur.close()
        conn.close()

# ==================== ENDPOINTS POST ====================

@app.post("/productos")
async def create_producto(producto: ProductoCreate):
    """POST - Crear nuevo producto"""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cur.execute("""
            INSERT INTO productos (nombre, precio, cantidad, estado)
            VALUES (%s, %s, %s, %s)
            RETURNING *
        """, (producto.nombre, producto.precio, producto.cantidad, producto.estado))
        nuevo_producto = cur.fetchone()
        conn.commit()
        return {"mensaje": "Producto creado exitosamente", "producto": nuevo_producto}
    finally:
        cur.close()
        conn.close()

@app.post("/ventas")
async def create_venta(venta: VentaCreate):
    """POST - Crear nueva venta"""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        # Verificar que el producto existe y tiene stock suficiente
        cur.execute("SELECT cantidad FROM productos WHERE id = %s", (venta.producto_id,))
        producto = cur.fetchone()

        if not producto:
            raise HTTPException(status_code=404, detail="Producto no encontrado")

        if producto['cantidad'] < venta.cantidad_vendida:
            raise HTTPException(status_code=400, detail="Stock insuficiente")

        # Crear venta
        cur.execute("""
            INSERT INTO ventas (producto_id, cantidad_vendida, precio_unitario, cliente)
            VALUES (%s, %s, %s, %s)
            RETURNING *
        """, (venta.producto_id, venta.cantidad_vendida, venta.precio_unitario, venta.cliente))
        nueva_venta = cur.fetchone()

        # Actualizar stock del producto
        cur.execute("""
            UPDATE productos
            SET cantidad = cantidad - %s
            WHERE id = %s
        """, (venta.cantidad_vendida, venta.producto_id))

        conn.commit()
        return {"mensaje": "Venta registrada exitosamente", "venta": nueva_venta}
    except HTTPException:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()

# ==================== ENDPOINTS UPDATE ====================

@app.put("/productos/{producto_id}")
async def update_producto(producto_id: int, producto: ProductoUpdate):
    """UPDATE - Actualizar producto"""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        # Verificar que existe
        cur.execute("SELECT * FROM productos WHERE id = %s", (producto_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Producto no encontrado")

        # Construir query dinámico solo con campos proporcionados
        campos = []
        valores = []
        if producto.nombre is not None:
            campos.append("nombre = %s")
            valores.append(producto.nombre)
        if producto.precio is not None:
            campos.append("precio = %s")
            valores.append(producto.precio)
        if producto.cantidad is not None:
            campos.append("cantidad = %s")
            valores.append(producto.cantidad)
        if producto.estado is not None:
            campos.append("estado = %s")
            valores.append(producto.estado)

        if not campos:
            raise HTTPException(status_code=400, detail="No hay campos para actualizar")

        valores.append(producto_id)
        query = f"UPDATE productos SET {', '.join(campos)} WHERE id = %s RETURNING *"

        cur.execute(query, valores)
        producto_actualizado = cur.fetchone()
        conn.commit()

        return {"mensaje": "Producto actualizado exitosamente", "producto": producto_actualizado}
    finally:
        cur.close()
        conn.close()

@app.put("/ventas/{venta_id}")
async def update_venta(venta_id: int, venta: VentaUpdate):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        # Verificar que existe
        cur.execute("SELECT * FROM ventas WHERE id = %s", (venta_id,))
        venta_actual = cur.fetchone()
        if not venta_actual:
            raise HTTPException(status_code=404, detail="Venta no encontrada")

        # Construir query dinámico
        campos = []
        valores = []
        if venta.cantidad_vendida is not None:
            campos.append("cantidad_vendida = %s")
            valores.append(venta.cantidad_vendida)
        if venta.precio_unitario is not None:
            campos.append("precio_unitario = %s")
            valores.append(venta.precio_unitario)
        if venta.cliente is not None:
            campos.append("cliente = %s")
            valores.append(venta.cliente)

        if not campos:
            raise HTTPException(status_code=400, detail="No hay campos para actualizar")

        valores.append(venta_id)
        query = f"UPDATE ventas SET {', '.join(campos)} WHERE id = %s RETURNING *"

        cur.execute(query, valores)
        venta_actualizada = cur.fetchone()
        conn.commit()

        return {"mensaje": "Venta actualizada exitosamente", "venta": venta_actualizada}
    finally:
        cur.close()
        conn.close()

# ==================== ENDPOINTS DELETE ====================

@app.delete("/productos/{producto_id}")
async def delete_producto(producto_id: int):
    """DELETE - Eliminar producto con borrado en cascada de sus ventas"""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        # Verificar que existe
        cur.execute("SELECT * FROM productos WHERE id = %s", (producto_id,))
        producto = cur.fetchone()
        if not producto:
            raise HTTPException(status_code=404, detail="Producto no encontrado")

        # Contar ventas asociadas
        cur.execute("SELECT COUNT(*) as total FROM ventas WHERE producto_id = %s", (producto_id,))
        ventas_count = cur.fetchone()['total']

        # Eliminar ventas asociadas (cascada manual)
        cur.execute("DELETE FROM ventas WHERE producto_id = %s", (producto_id,))

        # Eliminar producto
        cur.execute("DELETE FROM productos WHERE id = %s", (producto_id,))

        conn.commit()
        return {
            "mensaje": "Producto eliminado exitosamente (borrado en cascada)",
            "producto_eliminado": producto,
            "ventas_eliminadas": ventas_count
        }
    finally:
        cur.close()
        conn.close()

@app.delete("/ventas/{venta_id}")
async def delete_venta(venta_id: int):
    """DELETE - Eliminar venta (restaura stock del producto)"""
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        # Obtener venta
        cur.execute("SELECT * FROM ventas WHERE id = %s", (venta_id,))
        venta = cur.fetchone()
        if not venta:
            raise HTTPException(status_code=404, detail="Venta no encontrada")

        # Restaurar stock
        cur.execute("""
            UPDATE productos
            SET cantidad = cantidad + %s
            WHERE id = %s
        """, (venta['cantidad_vendida'], venta['producto_id']))

        # Eliminar venta
        cur.execute("DELETE FROM ventas WHERE id = %s", (venta_id,))

        conn.commit()
        return {
            "mensaje": "Venta eliminada exitosamente (stock restaurado)",
            "venta_eliminada": venta
        }
    finally:
        cur.close()
        conn.close()

@app.get("/")
async def root():
    return {
        "message": "API de Persistencia de Datos",
        "endpoints": {
            "productos": "/productos",
            "ventas": "/ventas",
            "docs": "/docs"
        }
    }
