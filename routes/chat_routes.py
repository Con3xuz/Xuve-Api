"""Rutas HTTP de chat - Conecta cada endpoint directamente con controllers.chat_controller."""
from fastapi import APIRouter
from controllers import chat_controller

router = APIRouter(prefix="/chat", tags=["Chat"])

router.get("/conversations")(chat_controller.get_conversations)
router.post("/conversations")(chat_controller.create_conversation)
router.get("/conversations/{conversation_id}/messages")(chat_controller.get_messages)
router.post("/conversations/{conversation_id}/messages")(chat_controller.send_message)
router.get("/service/{service_type}/{service_id}")(chat_controller.get_service_conversation)
router.post("/service")(chat_controller.create_service_conversation)
