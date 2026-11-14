"""Carga, limpieza y métricas del mercado laboral panameño (cuadros del INEC).

Cada cuadro se convierte a formato largo ("tidy") para poder agrupar por
provincia, sexo, actividad o periodo sin repetir lógica en el notebook.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
DATOS = RAIZ / "data" / "raw"

# Límites de cada tramo de salario mensual (B/.). El último tramo es abierto
# ("3,000 y más"); se le asigna un techo supuesto solo para poder interpolar.
TRAMOS = [
    ("Menos de 100", 0, 100),
    ("100 - 124", 100, 125),
    ("125 - 174", 125, 175),
    ("175 - 249", 175, 250),
    ("250 - 399", 250, 400),
    ("400 - 599", 400, 600),
    ("600 - 799", 600, 800),
    ("800 - 999", 800, 1000),
    ("1,000 - 1,499", 1000, 1500),
    ("1,500 - 1,999", 1500, 2000),
    ("2,000 - 2,999", 2000, 3000),
    ("3,000 y más", 3000, 4000),
]
ETIQUETAS_TRAMO = [t[0] for t in TRAMOS]

AREAS = ("Urbana", "Rural")

# Los cuadros escriben las provincias de forma distinta (con y sin tilde,
# "Com." vs "Comarca"); se unifican para poder cruzarlos.
_PROVINCIAS = {
    "Cocle": "Coclé",
    "Colon": "Colón",
    "Chiriqui": "Chiriquí",
    "Darien": "Darién",
    "Panama": "Panamá",
    "Panama Oeste": "Panamá Oeste",
    "Com. Kuna Yala": "Comarca Kuna Yala",
    "Com. Emberá": "Comarca Emberá",
    "Comarca Embera": "Comarca Emberá",
    "Com. Ngäbe Buglé": "Comarca Ngäbe Buglé",
    "Comarca Ngabe Bugle": "Comarca Ngäbe Buglé",
}


def _leer(nombre: str) -> pd.DataFrame:
    return pd.read_csv(DATOS / nombre, sep=";", encoding="latin-1")


# --------------------------------------------------------------------------
# Cuadro 25: empleados por tramo de salario mensual
# --------------------------------------------------------------------------
def cargar_salarios() -> pd.DataFrame:
    """Devuelve una fila por provincia, sexo, actividad y tramo salarial.

    El cuadro original trae el total de empleados y el porcentaje que cae en
    cada tramo. Aquí se convierte ese porcentaje en personas estimadas.
    Las filas sin distribución (porcentajes en cero) se descartan.
    """
    df = _leer("cuadro_25_empleados_por_salario.csv")
    df.columns = ["provincia", "sexo", "actividad", "empleados", *ETIQUETAS_TRAMO]
    df["actividad"] = df["actividad"].str.strip()
    df["provincia"] = df["provincia"].replace(_PROVINCIAS)

    suma_pct = df[ETIQUETAS_TRAMO].sum(axis=1)
    df = df[(df["empleados"] > 0) & (suma_pct > 0)].copy()
    # Los porcentajes vienen redondeados (suman 98-102); se reescalan a 100.
    df[ETIQUETAS_TRAMO] = df[ETIQUETAS_TRAMO].div(suma_pct[df.index], axis=0)

    largo = df.melt(
        id_vars=["provincia", "sexo", "actividad", "empleados"],
        value_vars=ETIQUETAS_TRAMO,
        var_name="tramo",
        value_name="proporcion",
    )
    largo["personas"] = largo["empleados"] * largo["proporcion"]
    largo["tramo"] = pd.Categorical(largo["tramo"], ETIQUETAS_TRAMO, ordered=True)
    return largo.drop(columns=["empleados", "proporcion"])


def mediana_agrupada(personas_por_tramo: pd.Series) -> float:
    """Mediana de datos agrupados por interpolación lineal dentro del tramo.

    `personas_por_tramo` debe venir indexada por la etiqueta del tramo.
    """
    conteos = personas_por_tramo.reindex(ETIQUETAS_TRAMO).fillna(0)
    total = conteos.sum()
    if total <= 0:
        return float("nan")
    mitad = total / 2
    acumulado = 0.0
    for (etiqueta, piso, techo), n in zip(TRAMOS, conteos):
        if n > 0 and acumulado + n >= mitad:
            return piso + (mitad - acumulado) / n * (techo - piso)
        acumulado += n
    return float("nan")


def mediana_por(salarios: pd.DataFrame, grupos: list[str]) -> pd.DataFrame:
    """Mediana salarial estimada y personas para cada combinación de `grupos`."""
    por_tramo = salarios.groupby([*grupos, "tramo"], observed=False)["personas"].sum()
    filas = []
    for clave, serie in por_tramo.groupby(level=list(range(len(grupos)))):
        clave = clave if isinstance(clave, tuple) else (clave,)
        serie = serie.droplevel(list(range(len(grupos))))
        filas.append((*clave, mediana_agrupada(serie), serie.sum()))
    return pd.DataFrame(filas, columns=[*grupos, "mediana", "personas"])


def brecha_salarial(medianas: pd.DataFrame, indice: list[str]) -> pd.DataFrame:
    """Brecha = 1 - mediana mujeres / mediana hombres (positivo: ganan menos)."""
    tabla = medianas.pivot(index=indice, columns="sexo", values="mediana")
    personas = medianas.pivot(index=indice, columns="sexo", values="personas")
    tabla["brecha"] = 1 - tabla["Mujer"] / tabla["Hombre"]
    tabla["personas"] = personas.sum(axis=1)
    return tabla.reset_index()


# --------------------------------------------------------------------------
# Cuadro 39: empleo informal no agrícola
# --------------------------------------------------------------------------
def cargar_informalidad() -> pd.DataFrame:
    """Una fila por provincia, sexo y año con la tasa de informalidad."""
    df = _leer("cuadro_39_empleo_informal.csv")
    df = df.rename(columns={df.columns[0]: "provincia", df.columns[1]: "sexo"})
    df["provincia"] = df["provincia"].replace(_PROVINCIAS)
    df["sexo"] = df["sexo"].replace({"Hombres": "Hombre", "Mujeres": "Mujer"})

    partes = []
    for anio in (2024, 2025):
        parte = df[["provincia", "sexo"]].copy()
        parte["anio"] = anio
        parte["ocupados"] = df[f"Poblacion ocupada no agricola {anio}"]
        parte["informal_sector_formal"] = df[
            f"empleo informal en empresas del sector formal {anio}"
        ]
        parte["informal_sector_informal"] = df[
            f"empleo informal en empresas del sector informal {anio}"
        ]
        parte["informal_hogares"] = df[f"Hogares {anio}"]
        partes.append(parte)
    largo = pd.concat(partes, ignore_index=True)
    largo["informales"] = largo[
        ["informal_sector_formal", "informal_sector_informal", "informal_hogares"]
    ].sum(axis=1)
    return largo


def tasa_informalidad(informalidad: pd.DataFrame, grupos: list[str]) -> pd.DataFrame:
    """Tasa = empleo informal / población ocupada no agrícola."""
    t = informalidad.groupby(grupos, as_index=False)[["informales", "ocupados"]].sum()
    t["tasa"] = t["informales"] / t["ocupados"]
    return t


# --------------------------------------------------------------------------
# Cuadro 29: población no económicamente activa (PNEA)
# --------------------------------------------------------------------------
def cargar_inactivos() -> pd.DataFrame:
    """Una fila por lugar, tipo de inactividad, condición, sexo y periodo.

    `nivel` distingue los totales por área (Urbana/Rural) de las provincias,
    porque ambos suman el mismo total nacional y no deben mezclarse.
    """
    df = _leer("cuadro_29_poblacion_no_economicamente_activa.csv")
    df.columns = ["lugar", "detalle", "Hombre|2024", "Mujer|2024", "Hombre|2025", "Mujer|2025"]
    df["lugar"] = df["lugar"].replace(_PROVINCIAS)
    df[["tipo", "condicion"]] = df["detalle"].str.split(" - ", n=1, expand=True)
    largo = df.melt(
        id_vars=["lugar", "tipo", "condicion"],
        value_vars=["Hombre|2024", "Mujer|2024", "Hombre|2025", "Mujer|2025"],
        value_name="personas",
    )
    largo[["sexo", "anio"]] = largo["variable"].str.split("|", expand=True)
    largo["anio"] = largo["anio"].astype(int)
    largo["nivel"] = largo["lugar"].isin(AREAS).map({True: "area", False: "provincia"})
    return largo.drop(columns="variable")
