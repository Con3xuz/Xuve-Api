"""Rutas HTTP de interurbano - Conecta cada endpoint directamente con controllers.interurbano_controller."""
from fastapi import APIRouter
from controllers import interurbano_controller

router = APIRouter(prefix="/interurbano", tags=["Transporte Interurbano"])

router.post("/viajes")(interurbano_controller.crear_viaje)
router.get("/mis-viajes")(interurbano_controller.get_mis_viajes)
router.post("/viajes/{viaje_id}/iniciar")(interurbano_controller.iniciar_viaje)
router.post("/viajes/{viaje_id}/completar")(interurbano_controller.completar_viaje)
router.delete("/viajes/{viaje_id}")(interurbano_controller.cancelar_viaje)
router.get("/viajes/buscar")(interurbano_controller.buscar_viajes)
router.get("/viajes/{viaje_id}")(interurbano_controller.get_viaje)
router.post("/viajes/{viaje_id}/comprar")(interurbano_controller.comprar_boletos)
router.get("/mis-reservas")(interurbano_controller.get_mis_reservas)
router.delete("/reservas/{reserva_id}")(interurbano_controller.cancelar_reserva)
router.get("/rutas-populares")(interurbano_controller.get_rutas_populares)
