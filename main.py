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
client = MongoClient(os.environ["MONGO_URI"])
#client = MongoClient("mongodb://ISIS2304H07202610:qNfD8OfLyRFM@157.253.236.88:8087")
    
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
                    "from": "resenas",
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

# =====================================================
# 4. EDITAR RESEÑA (cambiar puntaje y comentario) RF2
# Recibe el id de la reseña y los nuevos datos
# =====================================================
@app.put('/resenas/{id_resena}')
def update_resena(id_resena: int, datos: dict):
    # Buscar la reseña original
    resena_original = db.resenas.find_one({"id": id_resena})
    if not resena_original:
        return {"error": "Reseña no encontrada"}, 404

    # Nuevos valores (si no vienen, se mantienen los originales)
    nuevo_puntaje = datos.get("puntaje", resena_original["puntaje"])
    nuevo_comentario = datos.get("comentario", resena_original["comentario"])

    # Actualizar la reseña
    db.resenas.update_one(
        {"id": id_resena},
        {"$set": {
            "puntaje": nuevo_puntaje,
            "comentario": nuevo_comentario,
            "fecha_publicacion": datetime.now()  # Opcional: actualizar fecha de modificación
        }}
    )

    # =====================================
    # Recalcular promedio del hotel afectado
    # =====================================
    id_hotel = resena_original["id_hotel"]
    resenas_hotel = list(db.resenas.find({"id_hotel": id_hotel, "estado": True}))
    cantidad = len(resenas_hotel)
    suma = sum(r["puntaje"] for r in resenas_hotel)
    promedio = round(suma / cantidad) if cantidad > 0 else 0

    db.hotel.update_one(
        {"id": id_hotel},
        {"$set": {
            "cantidad_resenas": cantidad,
            "promedio_puntaje": promedio
        }}
    )

    return {
        "mensaje": "Reseña actualizada correctamente",
        "id_resena": id_resena,
        "nuevo_puntaje": nuevo_puntaje,
        "nuevo_comentario": nuevo_comentario
    }
# =====================================================
# RF3 Eliminar Resenas
# =====================================================
@app.delete('/rf3/{id_resena}')
def eliminar_resena(id_resena: int):

    resultado = db.resenas.delete_one(
        {
            "id": id_resena
        }
    )

    if resultado.deleted_count == 1:

        return {
            "mensaje":
                "Reseña eliminada"
        }

    return {
        "mensaje":
            "No se encontró la reseña"
    }
# =====================================================
# RF4 Consulta Resenas
# ===================================================== 
@app.get('/rf4')
def rf4(
    id_hotel: int,
    pagina: int = 1,
    orden: str = "fecha"
):

    limite = 5
    skip = (pagina - 1) * limite

    # Ordenar por fecha
    if orden == "fecha":

        sort_criteria = {
            "fecha_publicacion": -1
        }

    # Ordenar por utilidad
    else:

        sort_criteria = {
            "cantidad_votos": -1
        }

    resultado = list(

        db.resenas.aggregate([

            {
                "$match": {
                    "id_hotel": id_hotel,
                    "estado": True
                }
            },

            {
                "$project": {

                    "_id": 0,

                    "fecha_publicacion": 1,

                    "puntaje": 1,

                    "comentario": 1,

                    "cantidad_votos": {
                        "$size": "$votos"
                    }

                }
            },

            {
                "$sort": sort_criteria
            },

            {
                "$skip": skip
            },

            {
                "$limit": limite
            }

        ])

    )

    return resultado



# RF5 - MARCAR RESEÑA COMO ÚTIL
# =====================================================
# RF5 - MARCAR RESEÑA COMO UTIL
# =====================================================
@app.post('/rf5')
def rf5(datos: dict):

    id_resena = int(datos["id_resena"])

    # buscar reseña
    resena = db.resenas.find_one(
        {"id": id_resena}
    )

    # si no existe
    if not resena:

        return {
            "mensaje": "Reseña no encontrada"
        }

    # si no tiene votos
    if "votos" not in resena:

        db.resenas.update_one(
            {"id": id_resena},
            {
                "$set": {
                    "votos": []
                }
            }
        )

    # agregar voto
    resultado = db.resenas.update_one(

        {"id": id_resena},

        {
            "$push": {
                "votos": "usuario"
            }
        }

    )

    return {

        "mensaje":
            "Voto agregado correctamente",

        "modificados":
            resultado.modified_count

    }

# RF7 - RESPONDER RESEÑA

@app.post('/rf7')
def rf7(datos: dict):

    id_resena = datos["id_resena"]

    respuesta = datos["respuesta"]

    db.resenas.update_one(
        {"id": id_resena},
        {
            "$set": {
                "respuesta": {
                    "descripcion": respuesta,
                    "destacada": False
                }
            }
        }
    )

    return {
        "mensaje": "Respuesta agregada correctamente"
    }



# RF8 - ELIMINAR RESEÑA

@app.post('/rf8')
def rf8(datos: dict):

    id_resena = datos["id_resena"]

    db.resenas.update_one(
        {"id": id_resena},
        {
            "$set": {
                "estado": False
            }
        }
    )

    return {
        "mensaje": "Reseña eliminada correctamente"
    }



# RF9 - DESTACAR RESPUESTA

@app.post('/rf9')
def rf9(datos: dict):

    id_resena = datos["id_resena"]

    db.resenas.update_one(
        {"id": id_resena},
        {
            "$set": {
                "respuesta.destacada": True
            }
        }
    )

    return {
        "mensaje": "Respuesta destacada correctamente"
    }
