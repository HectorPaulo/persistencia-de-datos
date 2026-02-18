import os
import sys
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from omniORB import CORBA
import AlquimiaApp


IOR_FILE_HECHIZO = os.getenv("IOR_FILE_HECHIZO", "HechizoService.ior")
IOR_FILE_INGREDIENTE = os.getenv("IOR_FILE_INGREDIENTE", "IngredienteService.ior")
IOR_FILE_RECETA = os.getenv("IOR_FILE_RECETA", "RecetaAlquimicaService.ior")

app = FastAPI(title="Alquimia REST -> CORBA -> PostgreSQL")

_orb: Optional[CORBA.ORB] = None
_hechizo_svc: Optional[AlquimiaApp.HechizoService] = None
_ingrediente_svc: Optional[AlquimiaApp.IngredienteService] = None
_receta_svc: Optional[AlquimiaApp.RecetaAlquimicaService] = None


def get_orb() -> CORBA.ORB:
    global _orb
    if _orb is None:
        _orb = CORBA.ORB_init(sys.argv, CORBA.ORB_ID)
    return _orb


def hechizo_service() -> AlquimiaApp.HechizoService:
    global _hechizo_svc
    if _hechizo_svc is not None:
        try:
            # Validar que el servicio sigue siendo accesible
            _hechizo_svc.listar()
            return _hechizo_svc
        except Exception:
            # Si falla, resetear y reintentar conexión
            _hechizo_svc = None

    orb = get_orb()
    try:
        with open(IOR_FILE_HECHIZO, "r") as f:
            ior = f.read().strip()
    except FileNotFoundError:
        raise HTTPException(
            status_code=503,
            detail=f"No existe el archivo IOR '{IOR_FILE_HECHIZO}'. ¿Está corriendo el servidor CORBA?",
        )

    try:
        obj = orb.string_to_object(ior)
        svc = obj._narrow(AlquimiaApp.HechizoService)
        if svc is None:
            raise HTTPException(status_code=503, detail="No se pudo hacer narrow a HechizoService.")
        _hechizo_svc = svc
        return _hechizo_svc
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Error al conectar CORBA: {str(e)}")


def ingrediente_service() -> AlquimiaApp.IngredienteService:
    global _ingrediente_svc
    if _ingrediente_svc is not None:
        return _ingrediente_svc

    orb = get_orb()
    try:
        with open(IOR_FILE_INGREDIENTE, "r") as f:
            ior = f.read().strip()
    except FileNotFoundError:
        raise HTTPException(
            status_code=503,
            detail=f"No existe el archivo IOR '{IOR_FILE_INGREDIENTE}'. ¿Está corriendo el servidor CORBA?",
        )

    obj = orb.string_to_object(ior)
    svc = obj._narrow(AlquimiaApp.IngredienteService)
    if svc is None:
        raise HTTPException(status_code=503, detail="No se pudo hacer narrow a IngredienteService.")

    _ingrediente_svc = svc
    return _ingrediente_svc


def receta_service() -> AlquimiaApp.RecetaAlquimicaService:
    global _receta_svc
    if _receta_svc is not None:
        return _receta_svc

    orb = get_orb()
    try:
        with open(IOR_FILE_RECETA, "r") as f:
            ior = f.read().strip()
    except FileNotFoundError:
        raise HTTPException(
            status_code=503,
            detail=f"No existe el archivo IOR '{IOR_FILE_RECETA}'. ¿Está corriendo el servidor CORBA?",
        )

    obj = orb.string_to_object(ior)
    svc = obj._narrow(AlquimiaApp.RecetaAlquimicaService)
    if svc is None:
        raise HTTPException(status_code=503, detail="No se pudo hacer narrow a RecetaAlquimicaService.")

    _receta_svc = svc
    return _receta_svc


# ==================== MODELOS PYDANTIC HECHIZOS ====================

class HechizoCreate(BaseModel):
    nombre: str = Field(min_length=1, max_length=200)
    tipo_magia: str = Field(min_length=1, max_length=100)
    nivel_poder: int = Field(ge=1, le=100)
    efecto: str
    activo: bool = True


class HechizoUpdate(HechizoCreate):
    pass


class HechizoOut(HechizoCreate):
    id: int


class IngredienteSimple(BaseModel):
    id: int
    nombre: str
    origen: str
    potencia_magica: float
    cantidad_disponible: int
    esta_prohibido: bool


class HechizoConIngredientesOut(BaseModel):
    hechizo: HechizoOut
    ingredientes: List[IngredienteSimple]
    cantidades_requeridas: List[int]


# ==================== MODELOS PYDANTIC INGREDIENTES ====================

class IngredienteCreate(BaseModel):
    nombre: str = Field(min_length=1, max_length=200)
    origen: str = Field(min_length=1, max_length=200)
    potencia_magica: float = Field(ge=0.0, le=10.0)
    cantidad_disponible: int = Field(ge=0)
    esta_prohibido: bool = False


class IngredienteUpdate(IngredienteCreate):
    pass


class IngredienteOut(IngredienteCreate):
    id: int


class HechizoSimple(BaseModel):
    id: int
    nombre: str
    tipo_magia: str
    nivel_poder: int
    efecto: str
    activo: bool


class IngredienteConHechizosOut(BaseModel):
    ingrediente: IngredienteOut
    hechizos: List[HechizoSimple]
    cantidades_usadas: List[int]


# ==================== MODELOS PYDANTIC RECETAS ====================

class RecetaAlquimicaCreate(BaseModel):
    hechizo_id: int
    ingrediente_id: int
    cantidad_requerida: int = Field(ge=1)
    funcion_en_hechizo: str


class RecetaAlquimicaUpdate(BaseModel):
    cantidad_requerida: int = Field(ge=1)
    funcion_en_hechizo: str


class RecetaAlquimicaOut(BaseModel):
    id: int
    hechizo_id: int
    ingrediente_id: int
    cantidad_requerida: int
    funcion_en_hechizo: str


class RecetaAlquimicaConDetallesOut(BaseModel):
    id: int
    hechizo: HechizoOut
    ingrediente: IngredienteOut
    cantidad_requerida: int
    funcion_en_hechizo: str


# ==================== ENDPOINTS HECHIZOS ====================

@app.post("/hechizos", response_model=int, tags=["Hechizos"])
def crear_hechizo(h: HechizoCreate):
    """Crear un nuevo hechizo"""
    svc = hechizo_service()
    try:
        return svc.crear(h.nombre, h.tipo_magia, h.nivel_poder, h.efecto, h.activo)
    except CORBA.Exception as e:
        raise HTTPException(status_code=503, detail=f"Error CORBA: {e}")


@app.get("/hechizos", response_model=List[HechizoOut], tags=["Hechizos"])
def listar_hechizos():
    """GET ALL - Obtener todos los hechizos"""
    svc = hechizo_service()
    try:
        return [
            HechizoOut(
                id=r.id, nombre=r.nombre, tipo_magia=r.tipo_magia,
                nivel_poder=r.nivel_poder, efecto=r.efecto, activo=r.activo
            )
            for r in svc.listar()
        ]
    except CORBA.Exception as e:
        raise HTTPException(status_code=503, detail=f"Error CORBA: {e}")


@app.get("/hechizos/{id}", response_model=HechizoOut, tags=["Hechizos"])
def obtener_hechizo(id: int):
    """GET - Obtener hechizo por ID"""
    svc = hechizo_service()
    try:
        r = svc.obtener(id)
        return HechizoOut(
            id=r.id, nombre=r.nombre, tipo_magia=r.tipo_magia,
            nivel_poder=r.nivel_poder, efecto=r.efecto, activo=r.activo
        )
    except AlquimiaApp.NotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except CORBA.Exception as e:
        raise HTTPException(status_code=503, detail=f"Error CORBA: {e}")


@app.get("/hechizos/{id}/ingredientes", response_model=HechizoConIngredientesOut, tags=["Hechizos"])
def obtener_hechizo_con_ingredientes(id: int):
    """GET - Obtener hechizo con sus ingredientes (INNER JOIN - LEFT JOIN)"""
    svc = hechizo_service()
    try:
        result = svc.obtenerConIngredientes(id)
        h = result.hechizo

        hechizo_out = HechizoOut(
            id=h.id, nombre=h.nombre, tipo_magia=h.tipo_magia,
            nivel_poder=h.nivel_poder, efecto=h.efecto, activo=h.activo
        )

        ingredientes_out = [
            IngredienteSimple(
                id=i.id, nombre=i.nombre, origen=i.origen,
                potencia_magica=i.potencia_magica,
                cantidad_disponible=i.cantidad_disponible,
                esta_prohibido=i.esta_prohibido
            )
            for i in result.ingredientes
        ]

        return HechizoConIngredientesOut(
            hechizo=hechizo_out,
            ingredientes=ingredientes_out,
            cantidades_requeridas=list(result.cantidades_requeridas)
        )
    except AlquimiaApp.NotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except CORBA.Exception as e:
        raise HTTPException(status_code=503, detail=f"Error CORBA: {e}")


@app.put("/hechizos/{id}", tags=["Hechizos"])
def actualizar_hechizo(id: int, h: HechizoUpdate):
    """UPDATE - Actualizar hechizo"""
    svc = hechizo_service()
    try:
        svc.actualizar(id, h.nombre, h.tipo_magia, h.nivel_poder, h.efecto, h.activo)
        return {"ok": True, "mensaje": "Hechizo actualizado"}
    except AlquimiaApp.NotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except CORBA.Exception as e:
        raise HTTPException(status_code=503, detail=f"Error CORBA: {e}")


@app.delete("/hechizos/{id}", tags=["Hechizos"])
def eliminar_hechizo(id: int):
    """DELETE - Eliminar hechizo con borrado en cascada (elimina recetas asociadas)"""
    svc = hechizo_service()
    try:
        svc.eliminar(id)
        return {"ok": True, "mensaje": "Hechizo eliminado (borrado en cascada)"}
    except AlquimiaApp.NotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except CORBA.Exception as e:
        raise HTTPException(status_code=503, detail=f"Error CORBA: {e}")


# ==================== ENDPOINTS INGREDIENTES ====================

@app.post("/ingredientes", response_model=int, tags=["Ingredientes"])
def crear_ingrediente(i: IngredienteCreate):
    """Crear un nuevo ingrediente alquímico"""
    svc = ingrediente_service()
    try:
        return svc.crear(i.nombre, i.origen, i.potencia_magica, i.cantidad_disponible, i.esta_prohibido)
    except CORBA.Exception as e:
        raise HTTPException(status_code=503, detail=f"Error CORBA: {e}")


@app.get("/ingredientes", response_model=List[IngredienteOut], tags=["Ingredientes"])
def listar_ingredientes():
    """GET ALL - Obtener todos los ingredientes"""
    svc = ingrediente_service()
    try:
        return [
            IngredienteOut(
                id=r.id, nombre=r.nombre, origen=r.origen,
                potencia_magica=r.potencia_magica,
                cantidad_disponible=r.cantidad_disponible,
                esta_prohibido=r.esta_prohibido
            )
            for r in svc.listar()
        ]
    except CORBA.Exception as e:
        raise HTTPException(status_code=503, detail=f"Error CORBA: {e}")


@app.get("/ingredientes/{id}", response_model=IngredienteOut, tags=["Ingredientes"])
def obtener_ingrediente(id: int):
    """GET - Obtener ingrediente por ID"""
    svc = ingrediente_service()
    try:
        r = svc.obtener(id)
        return IngredienteOut(
            id=r.id, nombre=r.nombre, origen=r.origen,
            potencia_magica=r.potencia_magica,
            cantidad_disponible=r.cantidad_disponible,
            esta_prohibido=r.esta_prohibido
        )
    except AlquimiaApp.NotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except CORBA.Exception as e:
        raise HTTPException(status_code=503, detail=f"Error CORBA: {e}")


@app.get("/ingredientes/{id}/hechizos", response_model=IngredienteConHechizosOut, tags=["Ingredientes"])
def obtener_ingrediente_con_hechizos(id: int):
    """GET - Obtener ingrediente con sus hechizos (INNER JOIN - RIGHT JOIN)"""
    svc = ingrediente_service()
    try:
        result = svc.obtenerConHechizos(id)
        i = result.ingrediente

        ingrediente_out = IngredienteOut(
            id=i.id, nombre=i.nombre, origen=i.origen,
            potencia_magica=i.potencia_magica,
            cantidad_disponible=i.cantidad_disponible,
            esta_prohibido=i.esta_prohibido
        )

        hechizos_out = [
            HechizoSimple(
                id=h.id, nombre=h.nombre, tipo_magia=h.tipo_magia,
                nivel_poder=h.nivel_poder, efecto=h.efecto, activo=h.activo
            )
            for h in result.hechizos
        ]

        return IngredienteConHechizosOut(
            ingrediente=ingrediente_out,
            hechizos=hechizos_out,
            cantidades_usadas=list(result.cantidades_usadas)
        )
    except AlquimiaApp.NotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except CORBA.Exception as e:
        raise HTTPException(status_code=503, detail=f"Error CORBA: {e}")


@app.put("/ingredientes/{id}", tags=["Ingredientes"])
def actualizar_ingrediente(id: int, i: IngredienteUpdate):
    """UPDATE - Actualizar ingrediente"""
    svc = ingrediente_service()
    try:
        svc.actualizar(id, i.nombre, i.origen, i.potencia_magica, i.cantidad_disponible, i.esta_prohibido)
        return {"ok": True, "mensaje": "Ingrediente actualizado"}
    except AlquimiaApp.NotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except CORBA.Exception as e:
        raise HTTPException(status_code=503, detail=f"Error CORBA: {e}")


@app.delete("/ingredientes/{id}", tags=["Ingredientes"])
def eliminar_ingrediente(id: int):
    """DELETE - Eliminar ingrediente con borrado en cascada (elimina recetas asociadas)"""
    svc = ingrediente_service()
    try:
        svc.eliminar(id)
        return {"ok": True, "mensaje": "Ingrediente eliminado (borrado en cascada)"}
    except AlquimiaApp.NotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except CORBA.Exception as e:
        raise HTTPException(status_code=503, detail=f"Error CORBA: {e}")


# ==================== ENDPOINTS RECETAS ALQUÍMICAS (Relación M:N) ====================

@app.post("/recetas", response_model=int, tags=["Recetas Alquímicas"])
def crear_receta(r: RecetaAlquimicaCreate):
    """POST - Crear una nueva receta alquímica (relación M:N entre hechizo e ingrediente)"""
    svc = receta_service()
    try:
        return svc.crear(r.hechizo_id, r.ingrediente_id, r.cantidad_requerida, r.funcion_en_hechizo)
    except AlquimiaApp.InvalidOperation as e:
        raise HTTPException(status_code=400, detail=str(e))
    except CORBA.Exception as e:
        raise HTTPException(status_code=503, detail=f"Error CORBA: {e}")


@app.get("/recetas", response_model=List[RecetaAlquimicaConDetallesOut], tags=["Recetas Alquímicas"])
def listar_recetas():
    """GET ALL - Obtener todas las recetas alquímicas con datos completos del hechizo e ingrediente"""
    svc_receta = receta_service()
    svc_hechizo = hechizo_service()
    svc_ingrediente = ingrediente_service()
    try:
        recetas = svc_receta.listar()
        result = []
        for receta in recetas:
            try:
                # Obtener datos completos del hechizo
                hechizo = svc_hechizo.obtener(receta.hechizo_id)
                # Obtener datos completos del ingrediente
                ingrediente = svc_ingrediente.obtener(receta.ingrediente_id)

                result.append(
                    RecetaAlquimicaConDetallesOut(
                        id=receta.id,
                        hechizo=HechizoOut(
                            id=hechizo.id,
                            nombre=hechizo.nombre,
                            tipo_magia=hechizo.tipo_magia,
                            nivel_poder=hechizo.nivel_poder,
                            efecto=hechizo.efecto,
                            activo=hechizo.activo
                        ),
                        ingrediente=IngredienteOut(
                            id=ingrediente.id,
                            nombre=ingrediente.nombre,
                            origen=ingrediente.origen,
                            potencia_magica=ingrediente.potencia_magica,
                            cantidad_disponible=ingrediente.cantidad_disponible,
                            esta_prohibido=ingrediente.esta_prohibido
                        ),
                        cantidad_requerida=receta.cantidad_requerida,
                        funcion_en_hechizo=receta.funcion_en_hechizo
                    )
                )
            except (AlquimiaApp.NotFound, CORBA.Exception):
                # Si no encontramos los detalles, saltamos esta receta
                pass
        return result
    except CORBA.Exception as e:
        raise HTTPException(status_code=503, detail=f"Error CORBA: {e}")


@app.get("/recetas/{id}", response_model=RecetaAlquimicaConDetallesOut, tags=["Recetas Alquímicas"])
def obtener_receta(id: int):
    """GET - Obtener receta por ID con datos completos del hechizo e ingrediente"""
    svc_receta = receta_service()
    svc_hechizo = hechizo_service()
    svc_ingrediente = ingrediente_service()
    try:
        receta = svc_receta.obtener(id)
        hechizo = svc_hechizo.obtener(receta.hechizo_id)
        ingrediente = svc_ingrediente.obtener(receta.ingrediente_id)

        return RecetaAlquimicaConDetallesOut(
            id=receta.id,
            hechizo=HechizoOut(
                id=hechizo.id,
                nombre=hechizo.nombre,
                tipo_magia=hechizo.tipo_magia,
                nivel_poder=hechizo.nivel_poder,
                efecto=hechizo.efecto,
                activo=hechizo.activo
            ),
            ingrediente=IngredienteOut(
                id=ingrediente.id,
                nombre=ingrediente.nombre,
                origen=ingrediente.origen,
                potencia_magica=ingrediente.potencia_magica,
                cantidad_disponible=ingrediente.cantidad_disponible,
                esta_prohibido=ingrediente.esta_prohibido
            ),
            cantidad_requerida=receta.cantidad_requerida,
            funcion_en_hechizo=receta.funcion_en_hechizo
        )
    except AlquimiaApp.NotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except CORBA.Exception as e:
        raise HTTPException(status_code=503, detail=f"Error CORBA: {e}")


@app.get("/recetas/hechizo/{hechizo_id}", response_model=List[RecetaAlquimicaConDetallesOut], tags=["Recetas Alquímicas"])
def obtener_recetas_por_hechizo(hechizo_id: int):
    """GET - Obtener todas las recetas de un hechizo específico con datos completos"""
    svc_receta = receta_service()
    svc_hechizo = hechizo_service()
    svc_ingrediente = ingrediente_service()
    try:
        recetas = svc_receta.obtenerPorHechizo(hechizo_id)
        result = []
        for receta in recetas:
            try:
                hechizo = svc_hechizo.obtener(receta.hechizo_id)
                ingrediente = svc_ingrediente.obtener(receta.ingrediente_id)
                result.append(
                    RecetaAlquimicaConDetallesOut(
                        id=receta.id,
                        hechizo=HechizoOut(
                            id=hechizo.id,
                            nombre=hechizo.nombre,
                            tipo_magia=hechizo.tipo_magia,
                            nivel_poder=hechizo.nivel_poder,
                            efecto=hechizo.efecto,
                            activo=hechizo.activo
                        ),
                        ingrediente=IngredienteOut(
                            id=ingrediente.id,
                            nombre=ingrediente.nombre,
                            origen=ingrediente.origen,
                            potencia_magica=ingrediente.potencia_magica,
                            cantidad_disponible=ingrediente.cantidad_disponible,
                            esta_prohibido=ingrediente.esta_prohibido
                        ),
                        cantidad_requerida=receta.cantidad_requerida,
                        funcion_en_hechizo=receta.funcion_en_hechizo
                    )
                )
            except (AlquimiaApp.NotFound, CORBA.Exception):
                pass
        return result
    except CORBA.Exception as e:
        raise HTTPException(status_code=503, detail=f"Error CORBA: {e}")


@app.get("/recetas/ingrediente/{ingrediente_id}", response_model=List[RecetaAlquimicaConDetallesOut], tags=["Recetas Alquímicas"])
def obtener_recetas_por_ingrediente(ingrediente_id: int):
    """GET - Obtener todas las recetas que usan un ingrediente específico con datos completos"""
    svc_receta = receta_service()
    svc_hechizo = hechizo_service()
    svc_ingrediente = ingrediente_service()
    try:
        recetas = svc_receta.obtenerPorIngrediente(ingrediente_id)
        result = []
        for receta in recetas:
            try:
                hechizo = svc_hechizo.obtener(receta.hechizo_id)
                ingrediente = svc_ingrediente.obtener(receta.ingrediente_id)
                result.append(
                    RecetaAlquimicaConDetallesOut(
                        id=receta.id,
                        hechizo=HechizoOut(
                            id=hechizo.id,
                            nombre=hechizo.nombre,
                            tipo_magia=hechizo.tipo_magia,
                            nivel_poder=hechizo.nivel_poder,
                            efecto=hechizo.efecto,
                            activo=hechizo.activo
                        ),
                        ingrediente=IngredienteOut(
                            id=ingrediente.id,
                            nombre=ingrediente.nombre,
                            origen=ingrediente.origen,
                            potencia_magica=ingrediente.potencia_magica,
                            cantidad_disponible=ingrediente.cantidad_disponible,
                            esta_prohibido=ingrediente.esta_prohibido
                        ),
                        cantidad_requerida=receta.cantidad_requerida,
                        funcion_en_hechizo=receta.funcion_en_hechizo
                    )
                )
            except (AlquimiaApp.NotFound, CORBA.Exception):
                pass
        return result
    except CORBA.Exception as e:
        raise HTTPException(status_code=503, detail=f"Error CORBA: {e}")


@app.put("/recetas/{id}", tags=["Recetas Alquímicas"])
def actualizar_receta(id: int, r: RecetaAlquimicaUpdate):
    """UPDATE - Actualizar receta alquímica"""
    svc = receta_service()
    try:
        svc.actualizar(id, r.cantidad_requerida, r.funcion_en_hechizo)
        return {"ok": True, "mensaje": "Receta actualizada"}
    except AlquimiaApp.NotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except CORBA.Exception as e:
        raise HTTPException(status_code=503, detail=f"Error CORBA: {e}")


@app.delete("/recetas/{id}", tags=["Recetas Alquímicas"])
def eliminar_receta(id: int):
    """DELETE - Eliminar receta alquímica"""
    svc = receta_service()
    try:
        svc.eliminar(id)
        return {"ok": True, "mensaje": "Receta eliminada"}
    except AlquimiaApp.NotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except CORBA.Exception as e:
        raise HTTPException(status_code=503, detail=f"Error CORBA: {e}")


@app.get("/")
def root():
    return {
        "mensaje": "API de Alquimia",
        "descripcion": "Sistema de gestión de hechizos e ingredientes alquímicos con relación muchos a muchos",
        "endpoints": {
            "hechizos": "/hechizos",
            "ingredientes": "/ingredientes",
            "recetas": "/recetas",
            "documentacion": "/docs"
        }
    }
