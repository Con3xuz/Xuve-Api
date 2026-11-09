"""Rutas HTTP de notification - Conecta cada endpoint directamente con controllers.notification_controller."""
from fastapi import APIRouter
from controllers import notification_controller

router = APIRouter(prefix="/notifications", tags=["Notifications"])

router.get("")(notification_controller.get_notifications)
router.post("/{notification_id}/read")(notification_controller.mark_as_read)
router.post("/read-all")(notification_controller.mark_all_as_read)
router.delete("/{notification_id}")(notification_controller.delete_notification)
