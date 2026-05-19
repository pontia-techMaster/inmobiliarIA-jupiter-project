import unicodedata
from dataclasses import dataclass
from typing import Literal

from rapidfuzz import fuzz, process, utils


def _spanish_process(s: str) -> str:
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return utils.default_process(s)


DISTRICTS = {
    "Arganzuela": ["Acacias", "Chopera", "Delicias", "Imperial", "Legazpi", "Palos de la Frontera"],
    "Barajas": ["Aeropuerto", "Alameda de Osuna", "Campo de las Naciones-Corralejos", "Casco Histórico de Barajas", "Timón"],
    "Barrio de Salamanca": ["Castellana", "Fuente del Berro", "Goya", "Guindalera", "Lista", "Recoletos"],
    "Carabanchel": [
        "Abrantes",
        "Buena Vista",
        "Comillas",
        "Opañel",
        "Pau de Carabanchel",
        "Puerta Bonita",
        "San Isidro",
        "Vista Alegre",
    ],
    "Centro": ["Chueca-Justicia", "Huertas-Cortes", "Lavapiés-Embajadores", "Malasaña-Universidad", "Palacio", "Sol"],
    "Chamartín": ["Bernabéu-Hispanoamérica", "Castilla", "Ciudad Jardín", "El Viso", "Nueva España", "Prosperidad"],
    "Chamberí": ["Almagro", "Arapiles", "Gaztambide", "Nuevos Ministerios-Ríos Rosas", "Trafalgar", "Vallehermoso"],
    "Ciudad Lineal": [
        "Atalaya",
        "Colina",
        "Concepción",
        "Costillares",
        "Pueblo Nuevo",
        "Quintana",
        "San Juan Bautista",
        "San Pascual",
        "Ventas",
    ],
    "Fuencarral": [
        "Arroyo del Fresno",
        "El Pardo",
        "Fuentelarreina",
        "La Paz",
        "Las Tablas",
        "Mirasierra",
        "Montecarmelo",
        "Peñagrande",
        "Pilar",
        "Tres Olivos - Valverde",
    ],
    "Hortaleza": [
        "Apóstol Santiago",
        "Canillas",
        "Conde Orgaz-Piovera",
        "Palomas",
        "Pinar del Rey",
        "Sanchinarro",
        "Valdebebas - Valdefuentes",
        "Virgen del Cortijo - Manoteras",
    ],
    "Latina": ["Aluche", "Campamento", "Cuatro Vientos", "Los Cármenes", "Lucero", "Puerta del Ángel", "Águilas"],
    "Moncloa": ["Aravaca", "Argüelles", "Casa de Campo", "Ciudad Universitaria", "El Plantío", "Valdemarín", "Valdezarza"],
    "Moratalaz": ["Fontarrón", "Horcajo", "Marroquina", "Media Legua", "Pavones", "Vinateros"],
    "Puente de Vallecas": ["Entrevías", "Numancia", "Palomeras Bajas", "Palomeras sureste", "Portazgo", "San Diego"],
    "Retiro": ["Adelfas", "Estrella", "Ibiza", "Jerónimos", "Niño Jesús", "Pacífico"],
    "San Blas": ["Amposta", "Arcos", "Canillejas", "Hellín", "Rejas", "Rosas", "Salvador", "Simancas"],
    "Tetuán": ["Bellas Vistas", "Berruguete", "Cuatro Caminos", "Cuzco-Castillejos", "Valdeacederas", "Ventilla-Almenara"],
    "Usera": ["12 de Octubre-Orcasur", "Almendrales", "Moscardó", "Orcasitas", "Pradolongo", "San Fermín", "Zofío"],
    "Vicálvaro": [
        "Ambroz",
        "Casco Histórico de Vicálvaro",
        "El Cañaveral",
        "Los Ahijones",
        "Los Berrocales",
        "Los Cerros",
        "Valdebernardo - Valderrivas",
    ],
    "Villa de Vallecas": ["Casco Histórico de Vallecas", "Ensanche de Vallecas - La Gavia", "Santa Eugenia", "Valdecarros"],
    "Villaverde": ["Butarque", "Los Rosales", "Los Ángeles", "San Cristóbal", "Villaverde Alto"],
}


@dataclass
class ResolvedLocation:
    type: Literal["district", "neighborhood"]
    value: str
    score: float
    parent_district: str | None = None


def resolve_location(query: str, score_cutoff=60) -> ResolvedLocation | None:
    all_districts = list(DISTRICTS.keys())
    all_neighborhoods = {nb: dist for dist, nbs in DISTRICTS.items() for nb in nbs}

    dist_match = process.extractOne(
        query, all_districts, scorer=fuzz.token_set_ratio, score_cutoff=score_cutoff, processor=_spanish_process
    )

    nb_match = process.extractOne(
        query,
        list(all_neighborhoods.keys()),
        scorer=fuzz.token_set_ratio,
        score_cutoff=score_cutoff,
        processor=_spanish_process,
    )

    if dist_match and nb_match:
        if dist_match[1] >= nb_match[1]:
            return ResolvedLocation(type="district", value=dist_match[0], score=dist_match[1])
        else:
            nb = nb_match[0]
            return ResolvedLocation(type="neighborhood", value=nb, score=nb_match[1], parent_district=all_neighborhoods[nb])
    elif dist_match:
        return ResolvedLocation(type="district", value=dist_match[0], score=dist_match[1])
    elif nb_match:
        nb = nb_match[0]
        return ResolvedLocation(type="neighborhood", value=nb, score=nb_match[1], parent_district=all_neighborhoods[nb])
    return None
