"""Rutas HTTP de urban_line - Conecta cada endpoint directamente con controllers.urban_line_controller."""
from fastapi import APIRouter
from controllers import urban_line_controller

router = APIRouter(prefix="/urban-linea", tags=["Líneas Transporte Urbano"])

router.post("/registro")(urban_line_controller.registrar_linea_urbana)
router.get("/mi-linea")(urban_line_controller.get_mi_linea_urbana)
router.post("/recargar")(urban_line_controller.recargar_wallet_urbana)
router.post("/vehiculos")(urban_line_controller.registrar_vehiculo_urbano)
router.get("/vehiculos")(urban_line_controller.listar_vehiculos_urbanos)
router.delete("/vehiculos/{vehiculo_id}")(urban_line_controller.eliminar_vehiculo_urbano)
router.post("/choferes")(urban_line_controller.registrar_chofer_urbano)
router.get("/choferes")(urban_line_controller.listar_choferes_urbanos)
router.delete("/choferes/{chofer_id}")(urban_line_controller.eliminar_chofer_urbano)
router.post("/rutas")(urban_line_controller.crear_ruta_urbana)
router.get("/rutas")(urban_line_controller.listar_rutas_urbanas)
router.delete("/rutas/{ruta_id}")(urban_line_controller.eliminar_ruta_urbana)
router.put("/rutas/{ruta_id}/waypoints")(urban_line_controller.actualizar_waypoints)
router.post("/rutas/{ruta_id}/asignar")(urban_line_controller.asignar_a_ruta_urbana)
router.delete("/rutas/{ruta_id}/asignar/{chofer_id}")(urban_line_controller.desasignar_de_ruta_urbana)
router.get("/chofer/mi-asignacion")(urban_line_controller.get_mi_asignacion_urbana)
router.post("/chofer/iniciar-recorrido")(urban_line_controller.iniciar_recorrido_urbano)
router.post("/chofer/actualizar-ubicacion")(urban_line_controller.actualizar_ubicacion_urbana)
router.post("/chofer/finalizar-recorrido")(urban_line_controller.finalizar_recorrido_urbano)
router.get("/publico/rutas")(urban_line_controller.get_rutas_publicas_urbanas)
router.get("/publico/busetas-activas")(urban_line_controller.get_busetas_activas_urbanas)
router.post("/publico/pagar-pasaje")(urban_line_controller.pagar_pasaje_urbano)
