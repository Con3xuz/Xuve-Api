"""Rutas HTTP de rutas_urbanas - Conecta cada endpoint directamente con controllers.rutas_urbanas_controller."""
from fastapi import APIRouter
from controllers import rutas_urbanas_controller

router = APIRouter(prefix="/rutas-urbanas", tags=["Rutas Urbanas - Transporte Público"])

router.post("/rutas")(rutas_urbanas_controller.crear_ruta)
router.get("/rutas")(rutas_urbanas_controller.listar_rutas)
router.delete("/rutas/{ruta_id}")(rutas_urbanas_controller.eliminar_ruta)
router.post("/rutas/{ruta_id}/asignar")(rutas_urbanas_controller.asignar_chofer_vehiculo)
router.delete("/rutas/{ruta_id}/asignar/{chofer_id}")(rutas_urbanas_controller.desasignar_chofer)
router.get("/mi-asignacion")(rutas_urbanas_controller.get_mi_asignacion)
router.post("/iniciar-recorrido")(rutas_urbanas_controller.iniciar_recorrido)
router.post("/actualizar-ubicacion")(rutas_urbanas_controller.actualizar_ubicacion)
router.post("/finalizar-recorrido")(rutas_urbanas_controller.finalizar_recorrido)
router.get("/rutas-publicas")(rutas_urbanas_controller.get_rutas_publicas)
router.get("/busetas-activas")(rutas_urbanas_controller.get_busetas_activas)
router.get("/busetas-activas/{ruta_id}")(rutas_urbanas_controller.get_busetas_por_ruta)
router.post("/pagar-pasaje")(rutas_urbanas_controller.pagar_pasaje)
router.get("/mis-pasajes")(rutas_urbanas_controller.get_mis_pasajes)
