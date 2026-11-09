"""Rutas HTTP de carga - Conecta cada endpoint directamente con controllers.carga_controller."""
from fastapi import APIRouter
from controllers import carga_controller

router = APIRouter(prefix="/carga", tags=["Carga Pesada"])

router.post("/cotizacion")(carga_controller.crear_cotizacion)
router.post("/cotizacion/{cotizacion_id}/enviar")(carga_controller.enviar_cotizacion_a_conductores)
router.post("/cotizacion/{cotizacion_id}/aceptar")(carga_controller.aceptar_cotizacion)
router.post("/cotizacion/{cotizacion_id}/completar")(carga_controller.completar_servicio_carga)
router.get("/mis-cotizaciones")(carga_controller.get_mis_cotizaciones)
router.get("/servicios-disponibles")(carga_controller.get_servicios_disponibles)
router.get("/tarifas")(carga_controller.get_tarifas)
