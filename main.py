from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient
from datetime import datetime
import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

# os.environ para despliegue. Descomente cuando ya probó todo local.
#client = MongoClient(os.environ["MONGO_URI"])
client = MongoClient("mongodb://ISIS2304H07202610:qNfD8OfLyRFM@157.253.236.88:8087")
    
db = client["ISIS2304H07202610"]


# =========================
# ENDPOINT BASE
# =========================
@app.get("/")
def inicio():
    return {"estado": "API funcionando correctamente"}


# =====================================================
# 1. VER RESEÑAS DE UN CLIENTE
# Busca por tipo de documento y número
# =====================================================
@app.get('/resenas')
def get_resenas(tipo_id: str, numero_id: int):

    resenas = list(
        db.resenas.find(
            {
                "cliente.tipo_identificacion": tipo_id,
                "cliente.numero_identificacion": numero_id
            },
            {"_id": 0}
        )
    )

    return resenas

# =====================================================
# 2. CREAR RESEÑA
# Recibe:
# id_reserva
# id_hotel
# cliente
# puntaje
# comentario
# =====================================================
@app.post('/resenas')
def post_resena(datos: dict):

    # buscar último id para autoincremento
    ultima_resena = db.resenas.find_one(
        sort=[("id", -1)]
    )

    nuevo_id = 1

    if ultima_resena:
        nuevo_id = ultima_resena["id"] + 1

    # construir documento
    nueva_resena = {
        "id": nuevo_id,
        "id_reserva": datos["id_reserva"],

        "cliente": {
            "tipo_identificacion":
                datos["cliente"]["tipo_identificacion"],
            "numero_identificacion":
                datos["cliente"]["numero_identificacion"]
        },

        "id_hotel": datos["id_hotel"],

        "fecha_publicacion":
            datetime.now(),

        "puntaje":
            datos["puntaje"],

        "comentario":
            datos["comentario"],

        "estado":
            True,

        "votos":
            [],

        "respuesta":
            None
    }

    # insertar reseña
    db.resenas.insert_one(
        nueva_resena
    )

    # =====================================
    # actualizar datos del hotel
    # cantidad_resenas y promedio_puntaje
    # =====================================
    resenas_hotel = list(
        db.resenas.find(
            {
                "id_hotel": datos["id_hotel"]
            }
        )
    )

    cantidad = len(resenas_hotel)

    suma = 0
    for r in resenas_hotel:
        suma += r["puntaje"]

    promedio = round(suma / cantidad)

    db.hotel.update_one(
        {
            "id": datos["id_hotel"]
        },
        {
            "$set": {
                "cantidad_resenas": cantidad,
                "promedio_puntaje": promedio
            }
        }
    )

    return {
        "mensaje": "Reseña guardada exitosamente",
        "id_resena": nuevo_id
    }

#========================
# 3. RFC
#========================
#1
@app.get('/rfc1')
def rfc1(fecha_inicio: str, fecha_fin: str):

    inicio = datetime.strptime(
        fecha_inicio,
        "%Y-%m-%d"
    )

    fin = datetime.strptime(
        fecha_fin,
        "%Y-%m-%d"
    )

    resultado = list(

        db.resenas.aggregate([

            {
                "$match": {
                    "fecha_publicacion": {
                        "$gte": inicio,
                        "$lte": fin
                    },
                    "estado": True
                }
            },

            {
                "$group": {
                    "_id": "$id_hotel",

                    "promedio_calificacion": {
                        "$avg": "$puntaje"
                    },

                    "total_resenas": {
                        "$sum": 1
                    }
                }
            },

            {
                "$sort": {
                    "promedio_calificacion": -1
                }
            },

            {
                "$limit": 10
            }

        ])

    )

    return resultado
#2
@app.get('/rfc2')
def rfc2(id_hotel: int):

    resultado = list(

        db.resenas.aggregate([

            {
                "$match": {
                    "id_hotel": id_hotel,
                    "estado": True
                }
            },

            {
                "$group": {

                    "_id": {
                        "mes": {
                            "$month": "$fecha_publicacion"
                        }
                    },

                    "promedio_mensual": {
                        "$avg": "$puntaje"
                    },

                    "total_resenas": {
                        "$sum": 1
                    }

                }
            },

            {
                "$sort": {
                    "_id.mes": 1
                }
            }

        ])

    )

    return resultado

#3
@app.get('/rfc3')
def rfc3(ciudad: str):

    resultado = list(

        db.Hotel.aggregate([

            {
                "$match": {
                    "ciudad.nombre": ciudad
                }
            },

            {
                "$lookup": {
                    "from": "Resenas",
                    "localField": "id",
                    "foreignField": "id_hotel",
                    "as": "resenas"
                }
            },

            {
                "$project": {
                    "nombre": 1,

                    "total_resenas": {
                        "$size": "$resenas"
                    },

                    "promedio_hotel": {
                        "$avg": "$resenas.puntaje"
                    },

                    "resenas_con_respuesta": {
                        "$size": {
                            "$filter": {
                                "input": "$resenas",
                                "as": "r",
                                "cond": {
                                    "$ne": ["$$r.respuesta", None]
                                }
                            }
                        }
                    },

                    "resenas_destacadas": {
                        "$size": {
                            "$filter": {
                                "input": "$resenas",
                                "as": "r",
                                "cond": {
                                    "$eq": [
                                        "$$r.respuesta.destacada",
                                        True
                                    ]
                                }
                            }
                        }
                    }
                }
            },

            {
                "$project": {

                    "nombre": 1,
                    "total_resenas": 1,

                    "promedio_hotel": {
                        "$round": ["$promedio_hotel", 2]
                    },

                    "porcentaje_respuesta": {
                        "$cond": [
                            {
                                "$eq": ["$total_resenas", 0]
                            },
                            0,
                            {
                                "$round": [
                                    {
                                        "$multiply": [
                                            {
                                                "$divide": [
                                                    "$resenas_con_respuesta",
                                                    "$total_resenas"
                                                ]
                                            },
                                            100
                                        ]
                                    },
                                    2
                                ]
                            }
                        ]
                    },

                    "porcentaje_destacadas": {
                        "$cond": [
                            {
                                "$eq": ["$total_resenas", 0]
                            },
                            0,
                            {
                                "$round": [
                                    {
                                        "$multiply": [
                                            {
                                                "$divide": [
                                                    "$resenas_destacadas",
                                                    "$total_resenas"
                                                ]
                                            },
                                            100
                                        ]
                                    },
                                    2
                                ]
                            }
                        ]
                    }
                }
            },

            {
                "$group": {
                    "_id": None,

                    "promedio_ciudad": {
                        "$avg": "$promedio_hotel"
                    },

                    "hoteles": {
                        "$push": "$$ROOT"
                    }
                }
            },

            {
                "$unwind": "$hoteles"
            },

            {
                "$project": {

                    "_id": 0,

                    "nombre_hotel": "$hoteles.nombre",

                    "total_resenas":
                        "$hoteles.total_resenas",

                    "promedio_calificacion":
                        "$hoteles.promedio_hotel",

                    "porcentaje_respuesta":
                        "$hoteles.porcentaje_respuesta",

                    "porcentaje_destacadas":
                        "$hoteles.porcentaje_destacadas",

                    "promedio_ciudad": {
                        "$round": [
                            "$promedio_ciudad",
                            2
                        ]
                    }
                }
            }

        ])

    )

    return resultado