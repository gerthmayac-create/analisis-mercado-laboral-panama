import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import mercado_laboral as ml  # noqa: E402


def test_mediana_interpola_dentro_del_tramo():
    # 100 personas en 600-799: la mitad cae justo en el centro del tramo.
    assert ml.mediana_agrupada(pd.Series({"600 - 799": 100})) == pytest.approx(700)


def test_mediana_usa_el_acumulado_de_tramos_anteriores():
    serie = pd.Series({"400 - 599": 40, "600 - 799": 60})
    # Mitad = 50; faltan 10 de 60 dentro de 600-799 -> 600 + 10/60 * 200.
    assert ml.mediana_agrupada(serie) == pytest.approx(600 + 200 / 6)


def test_mediana_sin_datos_es_nan():
    assert pd.isna(ml.mediana_agrupada(pd.Series(dtype=float)))


def test_salarios_conserva_el_total_de_empleados():
    crudo = pd.read_csv(ml.DATOS / "cuadro_25_empleados_por_salario.csv", sep=";", encoding="latin-1")
    con_distribucion = crudo[crudo.iloc[:, 4:].sum(axis=1) > 0]
    assert ml.cargar_salarios()["personas"].sum() == pytest.approx(con_distribucion["Empleados"].sum())


def test_informalidad_nunca_supera_a_los_ocupados():
    inf = ml.cargar_informalidad()
    assert (inf["informales"] <= inf["ocupados"]).all()
    assert set(inf["sexo"]) == {"Hombre", "Mujer"}
    assert inf["provincia"].nunique() == 13


def test_inactivos_areas_y_provincias_suman_lo_mismo():
    totales = ml.cargar_inactivos().groupby(["nivel", "anio"])["personas"].sum().unstack(0)
    assert (totales["area"] == totales["provincia"]).all()


def test_provincias_coinciden_entre_cuadros():
    assert set(ml.cargar_informalidad()["provincia"]) == set(ml.cargar_salarios()["provincia"])
