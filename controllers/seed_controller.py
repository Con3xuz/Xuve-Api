"""Controlador de seed - Validaciones y lógica de negocio."""
from models import *
import os

from fastapi import APIRouter, HTTPException
from datetime import datetime, timezone

from models import db
from utils.auth import hash_password



def _seed_enabled() -> bool:
    """El seed es DESTRUCTIVO (borra colecciones) y crea cuentas demo con
    contraseñas conocidas. Solo se permite si ENABLE_SEED está activo
    explícitamente (arnés local/tests). En producción queda sin definir -> 403."""
    return os.environ.get("ENABLE_SEED", "").lower() in ("1", "true", "yes")


async def seed_database():
    """Seed database with test data for all roles (solo dev/test)."""
    if not _seed_enabled():
        raise HTTPException(status_code=403, detail="Seed deshabilitado")

    # Exchange rate
    await ExchangeRateModel.delete_many({})
    await ExchangeRateModel.insert_one(
        {
            "rate_id": "rate_001",
            "usd_to_bs": 50.0,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "updated_by": "system",
        }
    )

    # Market stores
    await MarketStoreModel.delete_many({})
    stores = [
        {
            "store_id": "store_001",
            "name": "Arepas La Abuela",
            "category": "comida",
            "address": "Av. Las Américas, Mérida",
            "lat": 8.5897,
            "lng": -71.1561,
            "image_url": "https://images.unsplash.com/photo-1565299585323-38d6b0865b47?w=400",
            "rating": 4.8,
            "is_active": True,
        },
        {
            "store_id": "store_002",
            "name": "Farmacia Central",
            "category": "farmacia",
            "address": "Centro Comercial Alto Prado",
            "lat": 8.5900,
            "lng": -71.1500,
            "image_url": "https://images.unsplash.com/photo-1631549916768-4119b2e5f926?w=400",
            "rating": 4.5,
            "is_active": True,
        },
        {
            "store_id": "store_003",
            "name": "Super Andino",
            "category": "supermercado",
            "address": "Av. Urdaneta",
            "lat": 8.5850,
            "lng": -71.1600,
            "image_url": "https://images.unsplash.com/photo-1604719312566-8912e9227c6a?w=400",
            "rating": 4.2,
            "is_active": True,
        },
    ]
    await MarketStoreModel.insert_many(stores)

    # Market products
    await MarketProductModel.delete_many({})
    products = [
        {
            "product_id": "prod_001",
            "store_id": "store_001",
            "name": "Arepa Reina Pepiada",
            "description": "Arepa rellena con pollo y aguacate",
            "price_usd": 3.50,
            "category": "comida",
            "image_url": "https://images.unsplash.com/photo-1599974579688-8dbdd335c77f?w=400",
            "available": True,
        },
        {
            "product_id": "prod_002",
            "store_id": "store_001",
            "name": "Arepa Domino",
            "description": "Arepa con caraotas y queso",
            "price_usd": 2.50,
            "category": "comida",
            "image_url": "https://images.unsplash.com/photo-1599974579688-8dbdd335c77f?w=400",
            "available": True,
        },
        {
            "product_id": "prod_003",
            "store_id": "store_001",
            "name": "Jugo Natural",
            "description": "Jugo de naranja 500ml",
            "price_usd": 1.50,
            "category": "comida",
            "image_url": "https://images.unsplash.com/photo-1621506289937-a8e4df240d0b?w=400",
            "available": True,
        },
        {
            "product_id": "prod_004",
            "store_id": "store_002",
            "name": "Acetaminofén 500mg",
            "description": "Caja de 10 tabletas",
            "price_usd": 2.00,
            "category": "farmacia",
            "image_url": "https://images.unsplash.com/photo-1584308666744-24d5c474f2ae?w=400",
            "available": True,
        },
        {
            "product_id": "prod_005",
            "store_id": "store_002",
            "name": "Vitamina C",
            "description": "Frasco 30 cápsulas",
            "price_usd": 5.00,
            "category": "farmacia",
            "image_url": "https://images.unsplash.com/photo-1584308666744-24d5c474f2ae?w=400",
            "available": True,
        },
        {
            "product_id": "prod_006",
            "store_id": "store_003",
            "name": "Harina PAN 1kg",
            "description": "Harina de maíz precocida",
            "price_usd": 1.80,
            "category": "supermercado",
            "image_url": "https://images.unsplash.com/photo-1586201375761-83865001e31c?w=400",
            "available": True,
        },
        {
            "product_id": "prod_007",
            "store_id": "store_003",
            "name": "Arroz 1kg",
            "description": "Arroz tipo 1",
            "price_usd": 1.50,
            "category": "supermercado",
            "image_url": "https://images.unsplash.com/photo-1586201375761-83865001e31c?w=400",
            "available": True,
        },
        {
            "product_id": "prod_008",
            "store_id": "store_003",
            "name": "Aceite 1L",
            "description": "Aceite vegetal",
            "price_usd": 3.00,
            "category": "supermercado",
            "image_url": "https://images.unsplash.com/photo-1474979266404-7eaacbcd87c5?w=400",
            "available": True,
        },
    ]
    await MarketProductModel.insert_many(products)

    # Reset/Create admin user
    await UserModel.update_one(
        {"email": "admin@xuve.ve"},
        {
            "$set": {
                "user_id": "user_admin001",
                "email": "admin@xuve.ve",
                "password": hash_password("admin123"),
                "name": "Admin Xuve",
                "phone": "+58412000000",
                "role": "admin",
                "wallet_balance": 1000.0,
                "status": "active",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        },
        upsert=True,
    )

    await DriverModel.delete_many({"user_id": "user_admin001"})

    # Seed sample cars for Xuve Rent
    await RentCarModel.delete_many({})
    sample_cars = [
        {
            "car_id": "car_demo001",
            "vehicle_id": "car_demo001",
            "owner_id": "user_demo001",
            "owner_name": "Carlos González",
            "owner_phone": "0412-555-1234",
            "brand": "Toyota",
            "model": "Corolla",
            "year": "2018",
            "color": "Blanco",
            "plate_number": "ABC-123",
            "condition": "excelente",
            "daily_price": 25,
            "daily_rate": 25,
            "deposit_amount": 100,
            "description": "Vehículo en excelentes condiciones, aire acondicionado, vidrios eléctricos.",
            "location": "Mérida Centro",
            "photos": [
                "https://images.unsplash.com/photo-1549317661-bd32c8ce0db2?w=400"
            ],
            "image_url": "https://images.unsplash.com/photo-1549317661-bd32c8ce0db2?w=400",
            "rating": 4.8,
            "status": "available",
            "available": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
        {
            "car_id": "car_demo002",
            "vehicle_id": "car_demo002",
            "owner_id": "user_demo002",
            "owner_name": "María Rodríguez",
            "owner_phone": "0414-555-5678",
            "brand": "Chevrolet",
            "model": "Aveo",
            "year": "2015",
            "color": "Gris",
            "plate_number": "DEF-456",
            "condition": "bueno",
            "daily_price": 18,
            "daily_rate": 18,
            "deposit_amount": 80,
            "description": "Económico en gasolina, ideal para trabajar en la ciudad.",
            "location": "El Vigía",
            "photos": [
                "https://images.unsplash.com/photo-1552519507-da3b142c6e3d?w=400"
            ],
            "image_url": "https://images.unsplash.com/photo-1552519507-da3b142c6e3d?w=400",
            "rating": 4.5,
            "status": "available",
            "available": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
    ]
    await RentCarModel.insert_many(sample_cars)

    # Create test user for each role
    test_users = [
        {
            "user_id": "user_cliente001",
            "email": "cliente@xuve.ve",
            "password": hash_password("cliente123"),
            "name": "Cliente Demo",
            "phone": "+58412111111",
            "role": "user",
            "wallet_balance": 50.0,
            "wallet_held": 0.0,
            "status": "active",
            "kyc_status": "approved",
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
        {
            "user_id": "user_conductor001",
            "email": "conductor@xuve.ve",
            "password": hash_password("conductor123"),
            "name": "Conductor Demo",
            "phone": "+58412222222",
            "role": "socio_conductor",
            "sub_role": "carro_particular",
            "wallet_balance": 100.0,
            "wallet_held": 0.0,
            "status": "active",
            "kyc_status": "approved",
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
        {
            "user_id": "user_repartidor001",
            "email": "repartidor@xuve.ve",
            "password": hash_password("repartidor123"),
            "name": "Repartidor Demo",
            "phone": "+58412333333",
            "role": "socio_repartidor",
            "sub_role": "moto_delivery",
            "wallet_balance": 30.0,
            "wallet_held": 0.0,
            "status": "active",
            "kyc_status": "approved",
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
        {
            "user_id": "user_comercial001",
            "email": "comercial@xuve.ve",
            "password": hash_password("comercial123"),
            "name": "Comercial Demo",
            "phone": "+58412444444",
            "role": "socio_comercial",
            "wallet_balance": 200.0,
            "wallet_held": 0.0,
            "status": "active",
            "kyc_status": "approved",
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
        {
            "user_id": "user_farmabien001",
            "email": "farmabien@xuve.ve",
            "password": hash_password("farmabien123"),
            "name": "Farmabien - Sede Principal",
            "phone": "+58412999999",
            "role": "socio_comercial",
            "wallet_balance": 500.0,
            "wallet_held": 0.0,
            "status": "active",
            "kyc_status": "approved",
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
        {
            "user_id": "user_rent001",
            "email": "rent@xuve.ve",
            "password": hash_password("rent123"),
            "name": "Rent Owner Demo",
            "phone": "+58412555555",
            "role": "rent_owner",
            "wallet_balance": 500.0,
            "wallet_held": 0.0,
            "status": "active",
            "kyc_status": "approved",
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
        {
            "user_id": "user_medico001",
            "email": "medico@xuve.ve",
            "password": hash_password("medico123"),
            "name": "Dr. María González",
            "phone": "+58412888888",
            "role": "medico",
            "wallet_balance": 0.0,
            "wallet_held": 0.0,
            "status": "active",
            "kyc_status": "approved",
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
    ]

    for test_user in test_users:
        await UserModel.update_one(
            {"email": test_user["email"]}, {"$set": test_user}, upsert=True
        )

    # Create approved Socio Conductor profile
    await SocioConductorModel.delete_many({"user_id": "user_conductor001"})
    await SocioConductorModel.insert_one(
        {
            "socio_id": "conductor_demo001",
            "user_id": "user_conductor001",
            "vehicle_type": "carro_particular",
            "status": "approved",
            "activation_fee_paid": True,  # Fee de activación pagado
            "is_online": False,
            "daily_toll_paid": False,
            "current_location": {"lat": 8.5897, "lng": -71.1561},
            "kyc": {
                "cedula_url": "https://example.com/cedula.jpg",
                "cedula_number": "V-12345678",
                "license_url": "https://example.com/license.jpg",
                "license_category": "2da",
                "medical_card_url": "https://example.com/medical.jpg",
                "circulation_card_url": "https://example.com/circulation.jpg",
                "rcv_insurance_url": "https://example.com/rcv.jpg",
            },
            "vehicle": {
                "plate_number": "ABC-123",
                "brand": "Toyota",
                "model": "Corolla",
                "year": 2018,
                "color": "Blanco",
                "photo_url": "https://images.unsplash.com/photo-1549317661-bd32c8ce0db2?w=400",
            },
            "taxi_info": None,
            "total_trips": 150,
            "total_earnings": 450.0,
            "avg_rating": 4.8,
            "approved_at": datetime.now(timezone.utc).isoformat(),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )

    # Create approved Socio Repartidor profile
    await SocioRepartidorModel.delete_many({"user_id": "user_repartidor001"})
    await SocioRepartidorModel.insert_one(
        {
            "socio_id": "repartidor_demo001",
            "user_id": "user_repartidor001",
            "vehicle_type": "moto_delivery",
            "status": "approved",
            "activation_fee_paid": True,  # Fee de activación pagado
            "is_online": False,
            "is_available": True,
            "is_delivery_active": True,  # NUEVO: Modo delivery activo
            "current_location": {"lat": 8.5900, "lng": -71.1500},
            "kyc": {
                "cedula_url": "https://example.com/cedula.jpg",
                "cedula_number": "V-87654321",
                "frontal_photo_url": "https://example.com/frontal.jpg",
                "license_url": "https://example.com/license.jpg",
                "circulation_card_url": "https://example.com/circulation.jpg",
            },
            "vehicle": {
                "plate_number": "XYZ-789",
                "brand": "Honda",
                "model": "Wave",
            },
            "route_restrictions": {"avoid_highways": False, "max_distance_km": 20},
            "total_deliveries": 85,
            "total_earnings": 170.0,
            "avg_rating": 4.9,
            "approved_at": datetime.now(timezone.utc).isoformat(),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )

    # Create approved Socio Comercial profile
    await SocioComercialModel.delete_many({"user_id": "user_comercial001"})
    await SocioComercialModel.insert_one(
        {
            "comercial_id": "comercial_demo001",
            "user_id": "user_comercial001",
            "store_name": "Tienda Demo",
            "category": "restaurante",
            "address": "Av. Principal, Mérida",
            "phone": "+58412444444",
            "description": "Tienda de prueba",
            "logo_url": None,
            "status": "approved",
            "activation_fee_paid": True,  # Fee de activación pagado
            "is_open": True,
            "avg_rating": 4.7,
            "total_orders": 50,
            "total_revenue": 500.0,
            "approved_at": datetime.now(timezone.utc).isoformat(),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )

    # Create approved Médico profile
    await MedicoModel.delete_many({"user_id": "user_medico001"})
    await MedicoModel.insert_one(
        {
            "medico_id": "medico_demo001",
            "user_id": "user_medico001",
            "specialty": "Medicina General",
            "license_number": "MPPS-12345",
            "institution": "Hospital Universitario de Los Andes",
            "address": "Av. Urdaneta, Mérida",
            "status": "approved",
            "kyc": {
                "cedula_url": "https://example.com/cedula_medico.jpg",
                "cedula_number": "V-98765432",
                "titulo_url": "https://example.com/titulo.jpg",
                "colegiatura_url": "https://example.com/colegiatura.jpg",
                "mpps_url": "https://example.com/mpps.jpg",
            },
            "total_prescriptions": 0,
            "approved_at": datetime.now(timezone.utc).isoformat(),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )

    # Create Carga Pesada test user
    await UserModel.update_one(
        {"email": "carga@xuve.ve"},
        {
            "$set": {
                "user_id": "user_carga001",
                "email": "carga@xuve.ve",
                "password": hash_password("carga123"),
                "name": "Camionero Demo",
                "phone": "+58412666666",
                "role": "carga_pesada",
                "wallet_balance": 50.0,
                "wallet_held": 0.0,
                "status": "active",
                "kyc_status": "approved",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        },
        upsert=True,
    )

    # Create Socio Carga Pesada profile
    await SocioCargaPesadaModel.delete_many({"user_id": "user_carga001"})
    await SocioCargaPesadaModel.insert_one(
        {
            "socio_id": "carga_demo001",
            "user_id": "user_carga001",
            "vehicle_type": "camion_750",
            "status": "approved",
            "activation_fee_paid": True,
            "is_online": True,
            "current_location": {"lat": 8.5950, "lng": -71.1400},
            "kyc": {
                "cedula_url": "https://example.com/cedula.jpg",
                "cedula_number": "V-55555555",
                "license_url": "https://example.com/license.jpg",
            },
            "vehicle": {
                "plate_number": "CARGA-001",
                "brand": "Ford",
                "model": "F-750",
                "capacity": "7500 kg",
            },
            "total_trips": 25,
            "total_earnings": 1200.0,
            "avg_rating": 4.6,
            "approved_at": datetime.now(timezone.utc).isoformat(),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )

    # ==================== B2B: LÍNEA DE TRANSPORTE ====================

    # Create Line Admin user (Administrador de Terminal)
    await UserModel.update_one(
        {"email": "linea@xuve.ve"},
        {
            "$set": {
                "user_id": "user_linea001",
                "email": "linea@xuve.ve",
                "password": hash_password("linea123"),
                "name": "Admin Expresos Occidente",
                "phone": "+58412777777",
                "role": "line_admin",
                "wallet_balance": 0.0,  # La billetera está en la Línea, no en el usuario
                "wallet_held": 0.0,
                "status": "active",
                "kyc_status": "approved",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        },
        upsert=True,
    )

    # Socio Transporte Interurbano (cuenta demo para pruebas de interurbano)
    await UserModel.update_one(
        {"email": "interurbano@xuve.ve"},
        {
            "$set": {
                "user_id": "user_interurbano001",
                "email": "interurbano@xuve.ve",
                "password": hash_password("interurbano123"),
                "name": "Socio Interurbano Demo",
                "phone": "+58412888888",
                "role": "transporte_interurbano",
                "wallet_balance": 50.0,
                "wallet_held": 0.0,
                "status": "active",
                "kyc_status": "approved",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        },
        upsert=True,
    )

    # Create Línea de Transporte (Terminal) with its own wallet
    await LineaTransporteModel.delete_many({"linea_id": "linea_demo001"})
    await LineaTransporteModel.insert_one(
        {
            "linea_id": "linea_demo001",
            "admin_user_id": "user_linea001",
            "nombre_linea": "Expresos Occidente",
            "rif": "J-12345678-9",
            "direccion_oficina": "Terminal de Pasajeros de Mérida, Local 15",
            "telefono_contacto": "+58412777777",
            "email_contacto": "expresos.occidente@gmail.com",
            "tipo_servicio": "interurbano",
            "descripcion": "Línea de transporte interurbano con rutas hacia el occidente de Venezuela",
            "logo_url": None,
            # Billetera CENTRALIZADA de la Línea
            "wallet_balance": 200.0,
            "wallet_held": 0.0,
            "status": "approved",
            "activation_fee_paid": True,
            "total_viajes": 120,
            "total_pasajeros": 980,
            "total_earnings": 8500.0,
            "avg_rating": 4.7,
            "approved_at": datetime.now(timezone.utc).isoformat(),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )

    # Create Vehículos de la Línea (Flota)
    await VehiculoLineaModel.delete_many({"linea_id": "linea_demo001"})
    vehiculos_flota = [
        {
            "vehiculo_id": "veh_demo001",
            "linea_id": "linea_demo001",
            "placa": "VAN-001",
            "marca": "Toyota",
            "modelo": "Hiace",
            "year": 2020,
            "capacidad_pasajeros": 12,
            "tipo_vehiculo": "van",
            "foto_url": None,
            "status": "active",
            "qr_code": None,
            "ruta_asignada_id": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
        {
            "vehiculo_id": "veh_demo002",
            "linea_id": "linea_demo001",
            "placa": "EXP-002",
            "marca": "Mercedes-Benz",
            "modelo": "Sprinter",
            "year": 2019,
            "capacidad_pasajeros": 18,
            "tipo_vehiculo": "expreso",
            "foto_url": None,
            "status": "active",
            "qr_code": None,
            "ruta_asignada_id": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
    ]
    await VehiculoLineaModel.insert_many(vehiculos_flota)

    # Create Choferes afiliados a la Línea
    await ChoferLineaModel.delete_many({"linea_id": "linea_demo001"})

    # Create test user for chofer (chofer_linea role)
    await UserModel.update_one(
        {"email": "chofer@xuve.ve"},
        {
            "$set": {
                "user_id": "user_chofer001",
                "email": "chofer@xuve.ve",
                "password": hash_password("chofer123"),
                "name": "Carlos Ramírez (Chofer)",
                "phone": "+58414111222",
                "role": "chofer_linea",
                "wallet_balance": 0.0,
                "wallet_held": 0.0,
                "status": "active",
                "kyc_status": "approved",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        },
        upsert=True,
    )

    choferes = [
        {
            "chofer_id": "chofer_demo001",
            "linea_id": "linea_demo001",
            "user_id": "user_chofer001",  # Linked to user account
            "nombre": "Carlos Ramírez",
            "cedula": "V-12345678",
            "telefono": "+58414111222",
            "email": "chofer@xuve.ve",
            "cedula_url": "https://example.com/cedula1.jpg",
            "licencia_url": "https://example.com/licencia1.jpg",
            "licencia_categoria": "5ta",
            "medical_card_url": "https://example.com/medico1.jpg",
            "foto_url": None,
            "status": "active",
            "total_viajes": 65,
            "avg_rating": 4.8,
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
        {
            "chofer_id": "chofer_demo002",
            "linea_id": "linea_demo001",
            "user_id": None,
            "nombre": "José Pérez",
            "cedula": "V-87654321",
            "telefono": "+58414333444",
            "email": "jose.perez@gmail.com",
            "cedula_url": "https://example.com/cedula2.jpg",
            "licencia_url": "https://example.com/licencia2.jpg",
            "licencia_categoria": "5ta",
            "medical_card_url": "https://example.com/medico2.jpg",
            "foto_url": None,
            "status": "active",
            "total_viajes": 55,
            "avg_rating": 4.6,
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
    ]
    await ChoferLineaModel.insert_many(choferes)

    # Create sample Ruta Urbana
    await RutaUrbanaModel.delete_many({})
    await AsignacionRutaModel.delete_many({})
    await RecorridoActivoModel.delete_many({})

    ruta_urbana_demo = {
        "ruta_id": "ruta_demo001",
        "linea_id": "linea_demo001",
        "linea_nombre": "Expresos Occidente",
        "nombre_ruta": "Ruta 1: Centro - Universidad",
        "codigo_ruta": "R01",
        "tarifa": 0.50,
        "descripcion": "Plaza Bolívar → Av. Las Américas → ULA",
        "horario_inicio": "05:00",
        "horario_fin": "22:00",
        "color": "#10B981",
        "asignaciones": [
            {
                "chofer_id": "chofer_demo001",
                "chofer_nombre": "Carlos Ramírez",
                "vehiculo_id": "veh_demo001",
                "vehiculo_placa": "VAN-001",
            }
        ],
        "total_pasajes_hoy": 0,
        "total_ingresos_hoy": float(0),
        "total_pasajes_historico": 1250,
        "total_ingresos_historico": float(562.50),
        "status": "active",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await RutaUrbanaModel.insert_one(ruta_urbana_demo)

    # Create asignacion for Carlos Ramírez
    asignacion_demo = {
        "asignacion_id": "asig_demo001",
        "ruta_id": "ruta_demo001",
        "ruta_nombre": "Ruta 1: Centro - Universidad",
        "ruta_codigo": "R01",
        "linea_id": "linea_demo001",
        "chofer_id": "chofer_demo001",
        "chofer_nombre": "Carlos Ramírez",
        "chofer_telefono": "+58414111222",
        "vehiculo_id": "veh_demo001",
        "vehiculo_placa": "VAN-001",
        "tarifa": 0.50,
        "status": "active",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await AsignacionRutaModel.insert_one(asignacion_demo)

    # Create sample Viajes Interurbanos (con estructura B2B)
    await ViajeInterurbanoModel.delete_many({})
    await ReservaInterurbanoModel.delete_many({})

    sample_viajes = [
        {
            "viaje_id": "viaje_demo001",
            "linea_id": "linea_demo001",
            "linea_nombre": "Expresos Occidente",
            "origen": "Mérida",
            "destino": "Valera",
            "fecha_salida": "2026-03-12T08:00:00",
            "precio_asiento": 15.0,
            "vehiculo_id": "veh_demo001",
            "vehiculo_info": {
                "placa": "VAN-001",
                "marca": "Toyota",
                "modelo": "Hiace",
                "tipo": "van",
            },
            "chofer_id": "chofer_demo001",
            "chofer_info": {
                "chofer_id": "chofer_demo001",
                "nombre": "Carlos Ramírez",
                "telefono": "+58414111222",
            },
            "capacidad_total": 12,
            "puestos_disponibles": 8,
            "puestos_vendidos": 4,
            "descripcion": "Viaje directo sin paradas",
            "punto_encuentro": "Terminal de Pasajeros de Mérida - Puerta 3",
            "ingreso_potencial": 180.0,
            "comision_esperada": 18.0,
            "status": "programado",
            "reservas": [],
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
        {
            "viaje_id": "viaje_demo002",
            "linea_id": "linea_demo001",
            "linea_nombre": "Expresos Occidente",
            "origen": "Mérida",
            "destino": "Barinas",
            "fecha_salida": "2026-03-12T14:00:00",
            "precio_asiento": 20.0,
            "vehiculo_id": "veh_demo002",
            "vehiculo_info": {
                "placa": "EXP-002",
                "marca": "Mercedes-Benz",
                "modelo": "Sprinter",
                "tipo": "expreso",
            },
            "chofer_id": "chofer_demo002",
            "chofer_info": {
                "chofer_id": "chofer_demo002",
                "nombre": "José Pérez",
                "telefono": "+58414333444",
            },
            "capacidad_total": 18,
            "puestos_disponibles": 18,
            "puestos_vendidos": 0,
            "descripcion": "Con parada en El Vigía",
            "punto_encuentro": "Terminal de Pasajeros de Mérida - Puerta 5",
            "ingreso_potencial": 360.0,
            "comision_esperada": 36.0,
            "status": "programado",
            "reservas": [],
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
        {
            "viaje_id": "viaje_demo003",
            "linea_id": "linea_demo001",
            "linea_nombre": "Expresos Occidente",
            "origen": "Valera",
            "destino": "Mérida",
            "fecha_salida": "2026-03-13T06:00:00",
            "precio_asiento": 15.0,
            "vehiculo_id": "veh_demo001",
            "vehiculo_info": {
                "placa": "VAN-001",
                "marca": "Toyota",
                "modelo": "Hiace",
                "tipo": "van",
            },
            "chofer_id": None,  # Sin chofer asignado aún
            "chofer_info": None,
            "capacidad_total": 12,
            "puestos_disponibles": 12,
            "puestos_vendidos": 0,
            "descripcion": "Salida temprana - Chofer por asignar",
            "punto_encuentro": "Terminal de Valera - Boletería Principal",
            "ingreso_potencial": 180.0,
            "comision_esperada": 18.0,
            "status": "programado",
            "reservas": [],
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
    ]
    await ViajeInterurbanoModel.insert_many(sample_viajes)

    # ==================== LÍNEA DE TRANSPORTE URBANO ====================

    # Create Urban Line Admin user
    await UserModel.update_one(
        {"email": "linea.urbana@xuve.ve"},
        {
            "$set": {
                "user_id": "user_urbana001",
                "email": "linea.urbana@xuve.ve",
                "password": hash_password("urbana123"),
                "name": "Admin Transporte San Benito",
                "phone": "+58412999999",
                "role": "urban_line_admin",
                "wallet_balance": 0.0,
                "wallet_held": 0.0,
                "status": "active",
                "kyc_status": "approved",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        },
        upsert=True,
    )

    # Create Línea de Transporte Urbano
    await LineaUrbanaModel.delete_many({"linea_id": "urban_demo001"})
    await LineaUrbanaModel.insert_one(
        {
            "linea_id": "urban_demo001",
            "admin_user_id": "user_urbana001",
            "nombre_linea": "Transporte San Benito",
            "rif": "J-98765432-1",
            "direccion_oficina": "Av. Las Américas, Galpón 12",
            "telefono_contacto": "+58412999999",
            "email_contacto": "tsanbenito@gmail.com",
            "zona_operacion": "Mérida Centro-Sur",
            "descripcion": "Línea de busetas urbanas con rutas fijas en zona sur de Mérida",
            "logo_url": None,
            "wallet_balance": 150.0,
            "status": "approved",
            "total_pasajes": 5000,
            "total_ingresos": 2500.0,
            "avg_rating": 4.6,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )

    # Create Vehículos Urbanos
    await VehiculoUrbanoModel.delete_many({"linea_id": "urban_demo001"})
    await VehiculoUrbanoModel.insert_many(
        [
            {
                "vehiculo_id": "vurb_demo001",
                "linea_id": "urban_demo001",
                "placa": "BUS-101",
                "marca": "Toyota",
                "modelo": "Coaster",
                "year": 2019,
                "capacidad_pasajeros": 25,
                "tipo_vehiculo": "buseta",
                "status": "active",
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
            {
                "vehiculo_id": "vurb_demo002",
                "linea_id": "urban_demo001",
                "placa": "BUS-102",
                "marca": "Hyundai",
                "modelo": "County",
                "year": 2020,
                "capacidad_pasajeros": 22,
                "tipo_vehiculo": "buseta",
                "status": "active",
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        ]
    )

    # Create Chofer Urbano user
    await UserModel.update_one(
        {"email": "chofer.urbano@xuve.ve"},
        {
            "$set": {
                "user_id": "user_chofer_urb001",
                "email": "chofer.urbano@xuve.ve",
                "password": hash_password("urbano123"),
                "name": "Pedro Urbano",
                "phone": "+58414888888",
                "role": "chofer_urbano",
                "wallet_balance": 0.0,
                "wallet_held": 0.0,
                "status": "active",
                "kyc_status": "approved",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        },
        upsert=True,
    )

    # Create Chofer Urbano profile
    await ChoferUrbanoModel.delete_many({"linea_id": "urban_demo001"})
    await ChoferUrbanoModel.insert_one(
        {
            "chofer_id": "churb_demo001",
            "linea_id": "urban_demo001",
            "user_id": "user_chofer_urb001",
            "nombre": "Pedro Urbano",
            "cedula": "V-22334455",
            "telefono": "+58414888888",
            "email": "chofer.urbano@xuve.ve",
            "cedula_url": "https://example.com/cedula.jpg",
            "licencia_url": "https://example.com/licencia.jpg",
            "licencia_categoria": "5ta",
            "medical_card_url": "https://example.com/medical.jpg",
            "status": "active",
            "total_recorridos": 250,
            "total_pasajeros": 4500,
            "avg_rating": 4.8,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )

    # Create Rutas Urbanas
    await RutaUrbanaV2Model.delete_many({"linea_id": "urban_demo001"})
    ruta_urbana = {
        "ruta_id": "rurb_demo001",
        "linea_id": "urban_demo001",
        "linea_nombre": "Transporte San Benito",
        "nombre_ruta": "Ruta Centro - Pie del Llano",
        "codigo_ruta": "R01",
        "tarifa": 0.50,
        "descripcion": "Plaza Bolívar → Hospital → Universidad → Pie del Llano",
        "horario_inicio": "05:30",
        "horario_fin": "21:00",
        "color": "#10B981",
        "waypoints": [
            {"lat": 8.5959, "lng": -71.1450, "nombre_parada": "Plaza Bolívar"},
            {"lat": 8.5920, "lng": -71.1500, "nombre_parada": "Hospital"},
            {"lat": 8.5880, "lng": -71.1560, "nombre_parada": "Universidad"},
            {"lat": 8.5800, "lng": -71.1620, "nombre_parada": "Pie del Llano"},
        ],
        "asignaciones": [
            {
                "chofer_id": "churb_demo001",
                "chofer_nombre": "Pedro Urbano",
                "vehiculo_id": "vurb_demo001",
                "vehiculo_placa": "BUS-101",
            }
        ],
        "total_pasajes_hoy": 0,
        "total_ingresos_hoy": 0.0,
        "total_pasajes_historico": 3500,
        "total_ingresos_historico": 1750.0,
        "status": "active",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await RutaUrbanaV2Model.insert_one(ruta_urbana)

    # Create Asignación Urbana
    await AsignacionUrbanaModel.delete_many({"linea_id": "urban_demo001"})
    await AsignacionUrbanaModel.insert_one(
        {
            "asignacion_id": "asurb_demo001",
            "ruta_id": "rurb_demo001",
            "ruta_nombre": "Ruta Centro - Pie del Llano",
            "ruta_codigo": "R01",
            "linea_id": "urban_demo001",
            "chofer_id": "churb_demo001",
            "chofer_nombre": "Pedro Urbano",
            "chofer_telefono": "+58414888888",
            "vehiculo_id": "vurb_demo001",
            "vehiculo_placa": "BUS-101",
            "tarifa": 0.50,
            "status": "active",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )

    # ==================== STORE PROFILE CON CATEGORÍAS ====================

    # Create store profile for comercial demo
    await StoreProfileModel.delete_many({"user_id": "user_comercial001"})
    await StoreProfileModel.insert_one(
        {
            "store_id": "store_demo001",
            "user_id": "user_comercial001",
            "store_name": "Arepas La Abuela",
            "category": "restaurante",
            "category_config": {
                "icon": "utensils",
                "color": "#F97316",
                "label": "Restaurante",
                "emoji": "🍽️",
            },
            "description": "Las mejores arepas de Mérida, con recetas tradicionales de la abuela",
            "address": "Av. Las Américas, Centro Comercial Alto Prado, Local 23",
            "phone": "+58412444444",
            "logo_url": "https://images.unsplash.com/photo-1565299585323-38d6b0865b47?w=200",
            "opening_hours": "7:00 - 20:00",
            "delivery_available": True,
            "pickup_available": True,
            "min_order_amount": 3.0,
            "is_open": True,
            "avg_rating": 4.8,
            "total_orders": 156,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )

    # Create Farmabien store profile
    await StoreProfileModel.delete_many({"user_id": "user_farmabien001"})
    await StoreProfileModel.insert_one(
        {
            "store_id": "store_farmabien001",
            "user_id": "user_farmabien001",
            "store_name": "Farmabien - Sede Principal",
            "category": "farmacia",
            "category_config": {
                "icon": "pill",
                "color": "#10B981",
                "label": "Farmacia",
            },
            "description": "Farmacia con los mejores precios y recetas médicas a domicilio",
            "address": "Av. Urdaneta, Centro Comercial Mérida, Local 5",
            "phone": "+58412999999",
            "logo_url": "https://images.unsplash.com/photo-1576602976047-174e57a47881?w=200",
            "opening_hours": "8:00 - 21:00",
            "delivery_available": True,
            "pickup_available": True,
            "min_order_amount": 1.0,
            "is_open": True,
            "avg_rating": 4.9,
            "total_orders": 320,
            "payment_info": {
                "banco": "Banesco",
                "telefono": "0412-9999999",
                "cedula": "J-12345678-9",
                "tipo_cuenta": "Corriente",
            },
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )

    # ==================== EXPEDIENTES KYC COMPLETOS ====================

    # URLs placeholder para documentos
    PLACEHOLDER_CEDULA = (
        "https://images.unsplash.com/photo-1633332755192-727a05c4013d?w=400"
    )
    PLACEHOLDER_LICENSE = (
        "https://images.unsplash.com/photo-1449824913935-59a10b8d2000?w=400"
    )
    PLACEHOLDER_VEHICLE = (
        "https://images.unsplash.com/photo-1549317661-bd32c8ce0db2?w=400"
    )
    PLACEHOLDER_RCV = "https://images.unsplash.com/photo-1554224155-6726b3ff858f?w=400"
    PLACEHOLDER_MEDICAL = (
        "https://images.unsplash.com/photo-1576091160550-2173dba999ef?w=400"
    )
    PLACEHOLDER_STORE = (
        "https://images.unsplash.com/photo-1604719312566-8912e9227c6a?w=400"
    )
    PLACEHOLDER_RIF = "https://images.unsplash.com/photo-1554224155-6726b3ff858f?w=400"
    PLACEHOLDER_TRUCK = (
        "https://images.unsplash.com/photo-1601584115197-04ecc0da31d7?w=400"
    )
    PLACEHOLDER_BUS = "https://images.unsplash.com/photo-1544620347-c4fd4a3d5957?w=400"

    # Limpiar colección de solicitudes KYC
    await KYCRequestModel.delete_many({})

    # 1. KYC CONDUCTOR (APROBADO) - conductor@xuve.ve
    kyc_conductor = {
        "kyc_id": "kyc_conductor001",
        "user_id": "user_conductor001",
        "user_email": "conductor@xuve.ve",
        "user_name": "Conductor Demo",
        "user_phone": "+58412222222",
        "requested_role": "socio_conductor",
        "sub_role": "carro_particular",
        "status": "approved",
        "personal_data": {
            "cedula_number": "V-15234567",
            "cedula_front_url": PLACEHOLDER_CEDULA,
            "cedula_back_url": PLACEHOLDER_CEDULA,
            "selfie_url": PLACEHOLDER_CEDULA,
            "address": "Av. Las Américas, Mérida",
        },
        "driver_license": {
            "license_url": PLACEHOLDER_LICENSE,
            "license_number": "15234567",
            "license_grade": "3ra",
            "license_expiry": "2027-06-15",
        },
        "vehicle_light": {
            "plate_number": "ABC-123",
            "brand": "Toyota",
            "model": "Corolla",
            "year": 2018,
            "color": "Blanco",
            "circulation_card_url": PLACEHOLDER_RCV,
            "rcv_url": PLACEHOLDER_RCV,
            "rcv_expiry": "2026-12-31",
            "vehicle_photo_front_url": PLACEHOLDER_VEHICLE,
            "vehicle_photo_side_url": PLACEHOLDER_VEHICLE,
        },
        "submitted_at": "2026-02-15T10:00:00",
        "reviewed_at": "2026-02-16T14:30:00",
        "reviewed_by": "admin@xuve.ve",
        "approved_at": "2026-02-16T14:30:00",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await KYCRequestModel.insert_one(kyc_conductor)

    # 2. KYC REPARTIDOR (APROBADO) - repartidor@xuve.ve
    kyc_repartidor = {
        "kyc_id": "kyc_repartidor001",
        "user_id": "user_repartidor001",
        "user_email": "repartidor@xuve.ve",
        "user_name": "Repartidor Demo",
        "user_phone": "+58412333333",
        "requested_role": "socio_repartidor",
        "sub_role": "moto_delivery",
        "status": "approved",
        "personal_data": {
            "cedula_number": "V-18765432",
            "cedula_front_url": PLACEHOLDER_CEDULA,
            "cedula_back_url": PLACEHOLDER_CEDULA,
            "address": "Urb. La Pedregosa, Mérida",
        },
        "driver_license": {
            "license_url": PLACEHOLDER_LICENSE,
            "license_number": "18765432",
            "license_grade": "2da",
            "license_expiry": "2027-03-20",
        },
        "vehicle_light": {
            "plate_number": "XYZ-789",
            "brand": "Honda",
            "model": "Wave 110",
            "year": 2021,
            "color": "Rojo",
            "circulation_card_url": PLACEHOLDER_RCV,
            "rcv_url": PLACEHOLDER_RCV,
            "rcv_expiry": "2026-11-30",
            "vehicle_photo_front_url": PLACEHOLDER_VEHICLE,
        },
        "submitted_at": "2026-02-18T09:00:00",
        "reviewed_at": "2026-02-18T16:00:00",
        "reviewed_by": "admin@xuve.ve",
        "approved_at": "2026-02-18T16:00:00",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await KYCRequestModel.insert_one(kyc_repartidor)

    # 3. KYC CARGA PESADA (APROBADO) - carga@xuve.ve
    kyc_carga = {
        "kyc_id": "kyc_carga001",
        "user_id": "user_carga001",
        "user_email": "carga@xuve.ve",
        "user_name": "Camionero Demo",
        "user_phone": "+58412666666",
        "requested_role": "carga_pesada",
        "sub_role": "camion_750",
        "status": "approved",
        "personal_data": {
            "cedula_number": "V-12987654",
            "cedula_front_url": PLACEHOLDER_CEDULA,
            "cedula_back_url": PLACEHOLDER_CEDULA,
            "address": "El Vigía, Mérida",
        },
        "driver_license": {
            "license_url": PLACEHOLDER_LICENSE,
            "license_number": "12987654",
            "license_grade": "5ta",
            "license_expiry": "2028-01-15",
        },
        "medical_data": {
            "medical_certificate_url": PLACEHOLDER_MEDICAL,
            "medical_expiry": "2026-08-20",
            "blood_type": "O+",
        },
        "vehicle_heavy": {
            "plate_number": "CARGA-001",
            "brand": "Ford",
            "model": "F-750",
            "year": 2017,
            "vehicle_type": "camion_750",
            "circulation_card_url": PLACEHOLDER_RCV,
            "rcv_heavy_url": PLACEHOLDER_RCV,
            "rcv_expiry": "2026-12-15",
            "capacity_kg": 7500,
            "vehicle_photo_front_url": PLACEHOLDER_TRUCK,
            "vehicle_photo_cargo_url": PLACEHOLDER_TRUCK,
        },
        "submitted_at": "2026-02-10T11:00:00",
        "reviewed_at": "2026-02-12T10:00:00",
        "reviewed_by": "admin@xuve.ve",
        "approved_at": "2026-02-12T10:00:00",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await KYCRequestModel.insert_one(kyc_carga)

    # 4. KYC CHOFER INTERURBANO (APROBADO) - chofer@xuve.ve
    kyc_chofer_inter = {
        "kyc_id": "kyc_chofer001",
        "user_id": "user_chofer001",
        "user_email": "chofer@xuve.ve",
        "user_name": "Carlos Ramírez (Chofer)",
        "user_phone": "+58414111222",
        "requested_role": "chofer_linea",
        "sub_role": "van",
        "status": "approved",
        "personal_data": {
            "cedula_number": "V-12345678",
            "cedula_front_url": PLACEHOLDER_CEDULA,
            "cedula_back_url": PLACEHOLDER_CEDULA,
            "address": "Av. Urdaneta, Mérida",
        },
        "driver_license": {
            "license_url": PLACEHOLDER_LICENSE,
            "license_number": "12345678",
            "license_grade": "5ta",
            "license_expiry": "2027-09-10",
        },
        "medical_data": {
            "medical_certificate_url": PLACEHOLDER_MEDICAL,
            "medical_expiry": "2026-10-15",
            "blood_type": "A+",
        },
        "vehicle_heavy": {
            "plate_number": "VAN-001",
            "brand": "Toyota",
            "model": "Hiace",
            "year": 2020,
            "vehicle_type": "van",
            "circulation_card_url": PLACEHOLDER_RCV,
            "rcv_heavy_url": PLACEHOLDER_RCV,
            "rcv_expiry": "2027-01-20",
            "capacity_passengers": 12,
            "vehicle_photo_front_url": PLACEHOLDER_BUS,
        },
        "submitted_at": "2026-01-20T08:00:00",
        "reviewed_at": "2026-01-22T15:00:00",
        "reviewed_by": "admin@xuve.ve",
        "approved_at": "2026-01-22T15:00:00",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await KYCRequestModel.insert_one(kyc_chofer_inter)

    # 5. KYC CHOFER URBANO (APROBADO) - chofer.urbano@xuve.ve
    kyc_chofer_urbano = {
        "kyc_id": "kyc_chofer_urb001",
        "user_id": "user_chofer_urb001",
        "user_email": "chofer.urbano@xuve.ve",
        "user_name": "Pedro Urbano",
        "user_phone": "+58414888888",
        "requested_role": "chofer_urbano",
        "sub_role": "buseta",
        "status": "approved",
        "personal_data": {
            "cedula_number": "V-22334455",
            "cedula_front_url": PLACEHOLDER_CEDULA,
            "cedula_back_url": PLACEHOLDER_CEDULA,
            "address": "Sector Pie del Llano, Mérida",
        },
        "driver_license": {
            "license_url": PLACEHOLDER_LICENSE,
            "license_number": "22334455",
            "license_grade": "5ta",
            "license_expiry": "2028-05-22",
        },
        "medical_data": {
            "medical_certificate_url": PLACEHOLDER_MEDICAL,
            "medical_expiry": "2026-12-01",
            "blood_type": "B+",
        },
        "vehicle_heavy": {
            "plate_number": "BUS-101",
            "brand": "Toyota",
            "model": "Coaster",
            "year": 2019,
            "vehicle_type": "buseta",
            "circulation_card_url": PLACEHOLDER_RCV,
            "rcv_heavy_url": PLACEHOLDER_RCV,
            "rcv_expiry": "2026-11-10",
            "capacity_passengers": 25,
            "vehicle_photo_front_url": PLACEHOLDER_BUS,
        },
        "submitted_at": "2026-02-01T07:30:00",
        "reviewed_at": "2026-02-03T09:00:00",
        "reviewed_by": "admin@xuve.ve",
        "approved_at": "2026-02-03T09:00:00",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await KYCRequestModel.insert_one(kyc_chofer_urbano)

    # 6. KYC TERMINAL ADMIN B2B (APROBADO) - linea@xuve.ve
    kyc_terminal = {
        "kyc_id": "kyc_terminal001",
        "user_id": "user_linea001",
        "user_email": "linea@xuve.ve",
        "user_name": "Admin Expresos Occidente",
        "user_phone": "+58412777777",
        "requested_role": "line_admin",
        "sub_role": "interurbano",
        "status": "approved",
        "personal_data": {
            "cedula_number": "V-10111213",
            "cedula_front_url": PLACEHOLDER_CEDULA,
            "address": "Terminal de Pasajeros, Mérida",
        },
        "company_data": {
            "company_name": "Expresos Occidente C.A.",
            "rif_type": "J",
            "rif_number": "J-12345678-9",
            "rif_url": PLACEHOLDER_RIF,
            "registro_mercantil_url": PLACEHOLDER_RIF,
            "acta_constitutiva_url": PLACEHOLDER_RIF,
            "permiso_ruta_url": PLACEHOLDER_RIF,
            "office_address": "Terminal de Pasajeros de Mérida, Local 15",
            "legal_representative": "José Antonio García",
            "legal_representative_cedula": "V-10111213",
        },
        "submitted_at": "2026-01-05T10:00:00",
        "reviewed_at": "2026-01-08T11:30:00",
        "reviewed_by": "admin@xuve.ve",
        "approved_at": "2026-01-08T11:30:00",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await KYCRequestModel.insert_one(kyc_terminal)

    # 7. KYC LÍNEA URBANA B2B (APROBADO) - linea.urbana@xuve.ve
    kyc_linea_urbana = {
        "kyc_id": "kyc_urbana001",
        "user_id": "user_urbana001",
        "user_email": "linea.urbana@xuve.ve",
        "user_name": "Admin Transporte San Benito",
        "user_phone": "+58412999999",
        "requested_role": "urban_line_admin",
        "sub_role": "urbano",
        "status": "approved",
        "personal_data": {
            "cedula_number": "V-14151617",
            "cedula_front_url": PLACEHOLDER_CEDULA,
            "address": "Av. Las Américas, Mérida",
        },
        "company_data": {
            "company_name": "Asociación Civil Transporte San Benito",
            "rif_type": "J",
            "rif_number": "J-98765432-1",
            "rif_url": PLACEHOLDER_RIF,
            "registro_mercantil_url": PLACEHOLDER_RIF,
            "permiso_ruta_url": PLACEHOLDER_RIF,
            "office_address": "Av. Las Américas, Galpón 12, Mérida",
            "legal_representative": "María Elena Rodríguez",
            "legal_representative_cedula": "V-14151617",
        },
        "submitted_at": "2026-01-10T14:00:00",
        "reviewed_at": "2026-01-12T10:00:00",
        "reviewed_by": "admin@xuve.ve",
        "approved_at": "2026-01-12T10:00:00",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await KYCRequestModel.insert_one(kyc_linea_urbana)

    # 8. KYC COMERCIAL (APROBADO) - comercial@xuve.ve
    kyc_comercial = {
        "kyc_id": "kyc_comercial001",
        "user_id": "user_comercial001",
        "user_email": "comercial@xuve.ve",
        "user_name": "Comercial Demo",
        "user_phone": "+58412444444",
        "requested_role": "socio_comercial",
        "sub_role": "restaurante",
        "status": "approved",
        "personal_data": {
            "cedula_number": "V-16171819",
            "cedula_front_url": PLACEHOLDER_CEDULA,
            "address": "Centro Comercial Alto Prado, Mérida",
        },
        "store_data": {
            "store_name": "Arepas La Abuela",
            "store_category": "restaurante",
            "rif_type": "J",
            "rif_number": "J-40123456-7",
            "rif_url": PLACEHOLDER_RIF,
            "store_address": "Av. Las Américas, C.C. Alto Prado, Local 23",
            "store_photo_exterior_url": PLACEHOLDER_STORE,
            "store_photo_interior_url": PLACEHOLDER_STORE,
            "health_permit_url": PLACEHOLDER_RIF,
        },
        "submitted_at": "2026-02-05T12:00:00",
        "reviewed_at": "2026-02-06T14:00:00",
        "reviewed_by": "admin@xuve.ve",
        "approved_at": "2026-02-06T14:00:00",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await KYCRequestModel.insert_one(kyc_comercial)

    # 9. KYC RENT OWNER (APROBADO) - rent@xuve.ve
    kyc_rent = {
        "kyc_id": "kyc_rent001",
        "user_id": "user_rent001",
        "user_email": "rent@xuve.ve",
        "user_name": "Rent Owner Demo",
        "user_phone": "+58412555555",
        "requested_role": "rent_owner",
        "sub_role": "sedan",
        "status": "approved",
        "personal_data": {
            "cedula_number": "V-19202122",
            "cedula_front_url": PLACEHOLDER_CEDULA,
            "cedula_back_url": PLACEHOLDER_CEDULA,
            "address": "Urbanización Los Curos, Mérida",
        },
        "rent_owner_data": {
            "title_property_url": PLACEHOLDER_RCV,
            "vehicle_plate": "RENT-001",
            "vehicle_brand": "Chevrolet",
            "vehicle_model": "Aveo",
            "vehicle_year": 2019,
            "vehicle_color": "Gris Plata",
            "rcv_url": PLACEHOLDER_RCV,
            "rcv_expiry": "2027-02-28",
            "photo_exterior_front_url": PLACEHOLDER_VEHICLE,
            "photo_exterior_back_url": PLACEHOLDER_VEHICLE,
            "photo_exterior_left_url": PLACEHOLDER_VEHICLE,
            "photo_exterior_right_url": PLACEHOLDER_VEHICLE,
            "photo_interior_dashboard_url": PLACEHOLDER_VEHICLE,
            "photo_interior_seats_url": PLACEHOLDER_VEHICLE,
            "photo_interior_trunk_url": PLACEHOLDER_VEHICLE,
            "condition_notes": "Vehículo en excelentes condiciones, A/C funcional, recién pintado",
        },
        "submitted_at": "2026-02-20T09:30:00",
        "reviewed_at": "2026-02-22T11:00:00",
        "reviewed_by": "admin@xuve.ve",
        "approved_at": "2026-02-22T11:00:00",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await KYCRequestModel.insert_one(kyc_rent)

    # ==================== 2 USUARIOS PENDING PARA PRUEBAS ====================

    # Usuario PENDING 1: Nuevo Conductor
    await UserModel.update_one(
        {"email": "nuevo.conductor@xuve.ve"},
        {
            "$set": {
                "user_id": "user_pending001",
                "email": "nuevo.conductor@xuve.ve",
                "password": hash_password("pending123"),
                "name": "Juan Pérez (Pendiente)",
                "phone": "+58414567890",
                "role": "user",  # Aún es "user", esperando aprobación
                "pending_role": "socio_conductor",
                "wallet_balance": 0.0,
                "wallet_held": 0.0,
                "status": "active",
                "kyc_status": "pending",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        },
        upsert=True,
    )

    kyc_pending_conductor = {
        "kyc_id": "kyc_pending001",
        "user_id": "user_pending001",
        "user_email": "nuevo.conductor@xuve.ve",
        "user_name": "Juan Pérez (Pendiente)",
        "user_phone": "+58414567890",
        "requested_role": "socio_conductor",
        "sub_role": "taxi_linea",
        "status": "pending",
        "personal_data": {
            "cedula_number": "V-25678901",
            "cedula_front_url": PLACEHOLDER_CEDULA,
            "cedula_back_url": PLACEHOLDER_CEDULA,
            "selfie_url": PLACEHOLDER_CEDULA,
            "address": "Urb. Santa Juana, Mérida",
        },
        "driver_license": {
            "license_url": PLACEHOLDER_LICENSE,
            "license_number": "25678901",
            "license_grade": "3ra",
            "license_expiry": "2028-04-15",
        },
        "vehicle_light": {
            "plate_number": "TAX-999",
            "brand": "Hyundai",
            "model": "Accent",
            "year": 2020,
            "color": "Amarillo",
            "circulation_card_url": PLACEHOLDER_RCV,
            "rcv_url": PLACEHOLDER_RCV,
            "rcv_expiry": "2027-06-30",
            "vehicle_photo_front_url": PLACEHOLDER_VEHICLE,
            "vehicle_photo_side_url": PLACEHOLDER_VEHICLE,
        },
        "submitted_at": datetime.now(timezone.utc).isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await KYCRequestModel.insert_one(kyc_pending_conductor)

    # Usuario PENDING 2: Nueva Línea Urbana B2B
    await UserModel.update_one(
        {"email": "nueva.linea@xuve.ve"},
        {
            "$set": {
                "user_id": "user_pending002",
                "email": "nueva.linea@xuve.ve",
                "password": hash_password("pending123"),
                "name": "Cooperativa Los Andes",
                "phone": "+58424123456",
                "role": "user",
                "pending_role": "urban_line_admin",
                "wallet_balance": 0.0,
                "wallet_held": 0.0,
                "status": "active",
                "kyc_status": "pending",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        },
        upsert=True,
    )

    kyc_pending_linea = {
        "kyc_id": "kyc_pending002",
        "user_id": "user_pending002",
        "user_email": "nueva.linea@xuve.ve",
        "user_name": "Cooperativa Los Andes",
        "user_phone": "+58424123456",
        "requested_role": "urban_line_admin",
        "sub_role": "urbano",
        "status": "pending",
        "personal_data": {
            "cedula_number": "V-30405060",
            "cedula_front_url": PLACEHOLDER_CEDULA,
            "address": "Av. Universidad, Mérida",
        },
        "company_data": {
            "company_name": "Cooperativa de Transporte Los Andes R.L.",
            "rif_type": "J",
            "rif_number": "J-50607080-9",
            "rif_url": PLACEHOLDER_RIF,
            "registro_mercantil_url": PLACEHOLDER_RIF,
            "permiso_ruta_url": PLACEHOLDER_RIF,
            "office_address": "Av. Universidad, Local 45, Mérida",
            "legal_representative": "Roberto Mendoza",
            "legal_representative_cedula": "V-30405060",
        },
        "submitted_at": datetime.now(timezone.utc).isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await KYCRequestModel.insert_one(kyc_pending_linea)

    return {
        "message": "Data seeded successfully",
        "test_accounts": {
            "admin": "admin@xuve.ve / admin123",
            "cliente": "cliente@xuve.ve / cliente123",
            "conductor": "conductor@xuve.ve / conductor123 (KYC APPROVED)",
            "repartidor": "repartidor@xuve.ve / repartidor123 (KYC APPROVED)",
            "comercial": "comercial@xuve.ve / comercial123 (KYC APPROVED)",
            "rent_owner": "rent@xuve.ve / rent123 (KYC APPROVED)",
            "carga_pesada": "carga@xuve.ve / carga123 (KYC APPROVED - Licencia 5ta)",
            "line_admin": "linea@xuve.ve / linea123 (KYC APPROVED - Terminal B2B)",
            "chofer_linea": "chofer@xuve.ve / chofer123 (KYC APPROVED - Licencia 5ta)",
            "urban_line_admin": "linea.urbana@xuve.ve / urbana123 (KYC APPROVED - Línea Urbana B2B)",
            "chofer_urbano": "chofer.urbano@xuve.ve / urbano123 (KYC APPROVED - Licencia 5ta)",
            "pending_conductor": "nuevo.conductor@xuve.ve / pending123 (KYC PENDING - Para pruebas)",
            "pending_linea": "nueva.linea@xuve.ve / pending123 (KYC PENDING - Para pruebas)",
        },
    }
