"""Gráficos del análisis. Un solo estilo para todas las figuras."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

FIGURAS = Path(__file__).resolve().parents[1] / "figuras"

COLOR = {"Hombre": "#2a78d6", "Mujer": "#eb6834"}
TINTA = "#0b0b0b"
TINTA_2 = "#52514e"
REJILLA = "#e4e3df"
FONDO = "#fcfcfb"


def _estilo(ax, titulo: str, nota: str | None = None) -> None:
    ax.set_facecolor(FONDO)
    ax.figure.set_facecolor(FONDO)
    ax.set_title(titulo, loc="left", fontsize=13, fontweight="bold", color=TINTA, pad=14)
    for lado in ("top", "right", "left"):
        ax.spines[lado].set_visible(False)
    ax.spines["bottom"].set_color(REJILLA)
    ax.tick_params(colors=TINTA_2, length=0, labelsize=9)
    ax.set_axisbelow(True)
    if nota:
        ax.figure.text(0.01, 0.01, nota, fontsize=8, color=TINTA_2, ha="left", va="bottom")


def _guardar(fig, nombre: str):
    FIGURAS.mkdir(exist_ok=True)
    fig.savefig(FIGURAS / nombre, dpi=150, bbox_inches="tight", facecolor=FONDO)
    return fig


def distribucion_salarial(salarios: pd.DataFrame):
    """Porcentaje de empleados de cada sexo en cada tramo salarial."""
    tabla = salarios.groupby(["tramo", "sexo"], observed=False)["personas"].sum().unstack()
    tabla = tabla / tabla.sum() * 100
    fig, ax = plt.subplots(figsize=(10, 4.8))
    x = range(len(tabla))
    ancho = 0.38
    for i, sexo in enumerate(("Hombre", "Mujer")):
        ax.bar([p + (i - 0.5) * (ancho + 0.03) for p in x], tabla[sexo], ancho,
               color=COLOR[sexo], label=f"{sexo}s" if sexo == "Hombre" else "Mujeres")
    ax.set_xticks(list(x), tabla.index, rotation=35, ha="right")
    ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0f}%")
    ax.grid(axis="y", color=REJILLA, linewidth=0.8)
    ax.legend(frameon=False, loc="upper right", fontsize=9)
    ax.set_xlabel("Salario mensual (B/.)", color=TINTA_2, fontsize=9)
    _estilo(ax, "Un tercio de los hombres gana entre B/.600 y B/.799;\n"
                "las mujeres pesan más de B/.1,500 en adelante")
    return _guardar(fig, "01_distribucion_salarial.png")


def mediana_por_actividad(brecha: pd.DataFrame, minimo: int = 10_000):
    """Mediana estimada de hombres y mujeres en cada actividad (dumbbell)."""
    t = brecha[brecha["personas"] >= minimo].dropna(subset=["Hombre", "Mujer"])
    t = t.sort_values("brecha")
    fig, ax = plt.subplots(figsize=(10, 7.5))
    y = range(len(t))
    ax.hlines(y, t["Hombre"], t["Mujer"], color=REJILLA, linewidth=3, zorder=1)
    for sexo, etiqueta in (("Hombre", "Hombres"), ("Mujer", "Mujeres")):
        ax.scatter(t[sexo], y, s=70, color=COLOR[sexo], label=etiqueta, zorder=2,
                   edgecolor=FONDO, linewidth=1.5)
    ax.set_yticks(list(y), [a if len(a) <= 46 else a[:44] + "…" for a in t["actividad"]])
    ax.xaxis.set_major_formatter(lambda v, _: f"B/.{v:,.0f}")
    ax.grid(axis="x", color=REJILLA, linewidth=0.8)
    ax.legend(frameon=False, loc="lower right", fontsize=9)
    _estilo(ax, "La brecha cambia de signo según la actividad",
            f"Mediana salarial mensual estimada. Actividades con al menos {minimo:,} empleados. "
            "Arriba: donde las mujeres ganan menos.")
    return _guardar(fig, "02_mediana_por_actividad.png")


def informalidad_por_provincia(tasas: pd.DataFrame, nacional: float):
    """Tasa de informalidad no agrícola por provincia (un solo año)."""
    t = tasas.sort_values("tasa")
    fig, ax = plt.subplots(figsize=(10, 5.5))
    barras = ax.barh(t["provincia"], t["tasa"] * 100, color="#2a78d6", height=0.62)
    ax.bar_label(barras, fmt="%.0f%%", padding=4, fontsize=9, color=TINTA_2)
    ax.axvline(nacional * 100, color=TINTA_2, linewidth=1, linestyle="--")
    ax.text(nacional * 100 + 1, len(t) - 0.45, f"Nacional {nacional:.0%}", fontsize=9, color=TINTA_2)
    ax.set_ylim(-0.6, len(t) - 0.1)
    ax.set_xlim(0, 105)
    ax.xaxis.set_major_formatter(lambda v, _: f"{v:.0f}%")
    ax.grid(axis="x", color=REJILLA, linewidth=0.8)
    _estilo(ax, "La informalidad va de 41% en Panamá a 95% en Kuna Yala",
            "Empleo informal como % de la población ocupada no agrícola, septiembre 2025.")
    return _guardar(fig, "03_informalidad_por_provincia.png")


def inactivos_por_condicion(inactivos: pd.DataFrame, anio: int = 2025):
    """Población no económicamente activa por condición y sexo."""
    t = inactivos[(inactivos["nivel"] == "area") & (inactivos["anio"] == anio)]
    t = t.groupby(["condicion", "sexo"])["personas"].sum().unstack() / 1000
    t = t.sort_values("Mujer")
    fig, ax = plt.subplots(figsize=(10, 4.2))
    alto = 0.36
    y = range(len(t))
    for i, sexo in enumerate(("Mujer", "Hombre")):
        barras = ax.barh([p + (0.5 - i) * (alto + 0.03) for p in y], t[sexo], alto,
                         color=COLOR[sexo], label="Mujeres" if sexo == "Mujer" else "Hombres")
        ax.bar_label(barras, fmt="%.0f mil", padding=4, fontsize=9, color=TINTA_2)
    ax.set_yticks(list(y), t.index)
    ax.set_xlim(0, t.max().max() * 1.15)
    ax.xaxis.set_major_formatter(lambda v, _: f"{v:.0f} mil")
    ax.grid(axis="x", color=REJILLA, linewidth=0.8)
    ax.legend(frameon=False, loc="lower right", fontsize=9)
    _estilo(ax, "El trabajo del hogar explica casi toda la diferencia\n"
                "entre mujeres y hombres fuera del mercado laboral",
            f"Población no económicamente activa, septiembre {anio}.")
    return _guardar(fig, "04_inactivos_por_condicion.png")
