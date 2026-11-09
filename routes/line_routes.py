"""Rutas HTTP de line - Conecta cada endpoint directamente con controllers.line_controller."""
from fastapi import APIRouter
from controllers import line_controller

router = APIRouter(prefix="/linea", tags=["Líneas de Transporte B2B"])

router.post("/registro")(line_controller.registrar_linea)
router.get("/mi-linea")(line_controller.get_mi_linea)
router.post("/recargar")(line_controller.recargar_wallet_linea)
router.post("/vehiculos")(line_controller.registrar_vehiculo)
router.get("/vehiculos")(line_controller.listar_vehiculos)
router.delete("/vehiculos/{vehiculo_id}")(line_controller.eliminar_vehiculo)
router.post("/choferes")(line_controller.registrar_chofer)
router.get("/choferes")(line_controller.listar_choferes)
router.delete("/choferes/{chofer_id}")(line_controller.eliminar_chofer)
router.post("/viajes")(line_controller.crear_viaje)
router.get("/viajes")(line_controller.listar_mis_viajes)
router.patch("/viajes/{viaje_id}/asignar-chofer")(line_controller.asignar_chofer)
router.post("/viajes/{viaje_id}/iniciar")(line_controller.iniciar_viaje)
router.post("/viajes/{viaje_id}/completar")(line_controller.completar_viaje)
router.delete("/viajes/{viaje_id}")(line_controller.cancelar_viaje)
router.get("/viajes/buscar")(line_controller.buscar_viajes)
router.get("/viajes/{viaje_id}")(line_controller.get_viaje_detalle)
router.post("/viajes/{viaje_id}/comprar")(line_controller.comprar_boletos)
router.get("/mis-reservas")(line_controller.get_mis_reservas)
router.delete("/reservas/{reserva_id}")(line_controller.cancelar_reserva)
router.get("/rutas-populares")(line_controller.get_rutas_populares)
