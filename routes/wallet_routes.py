"""Rutas HTTP de wallet - Conecta cada endpoint directamente con controllers.wallet_controller."""
from fastapi import APIRouter
from controllers import wallet_controller

router = APIRouter(prefix="/wallet", tags=["Wallet"])
exchange_router = APIRouter(tags=["Exchange Rate"])

router.get("/balance")(wallet_controller.get_wallet_balance)
router.post("/recharge")(wallet_controller.recharge_wallet)
router.post("/withdraw")(wallet_controller.withdraw_wallet)
router.get("/transactions")(wallet_controller.get_transactions)
router.post("/hold")(wallet_controller.create_wallet_hold)
router.post("/hold/{hold_id}/release")(wallet_controller.release_wallet_hold)
router.post("/hold/{hold_id}/charge")(wallet_controller.charge_wallet_hold)
router.get("/holds")(wallet_controller.get_wallet_holds)
exchange_router.get("/exchange-rate")(wallet_controller.get_exchange_rate)
exchange_router.post("/exchange-rate")(wallet_controller.set_exchange_rate)
