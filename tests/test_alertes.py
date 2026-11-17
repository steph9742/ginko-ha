import io
import zipfile
from datetime import date

import pytest
from google.transit import gtfs_realtime_pb2 as rt

from ginko_pure.gtfs import GinkoGtfs
from ginko_pure.gtfs_rt import parse_alerts

STOPS = """stop_id,stop_name,stop_lat,stop_lon,location_type,parent_station,wheelchair_boarding
st_chamars,Chamars,47.2337,6.0203,1,,
st_canot,Canot,47.2361,6.0160,1,,
CHAMARS1,Chamars,47.2338,6.0204,0,st_chamars,1
JULEHAG4,Lycée Jules Haag,47.2400,6.0300,0,,1
t_cham1,Chamars,47.2337,6.0203,0,st_chamars,1
t_cham2,Chamars,47.2336,6.0202,0,st_chamars,1
t_cano1,Canot,47.2361,6.0160,0,st_canot,1
t_vide1,,47.2361,6.0161,0,st_canot,1
"""

ROUTES = """route_id,route_short_name,route_long_name,route_type,route_color,route_text_color
102,T2,Hauts du Chazal <> Gare Viotte,0,006D78,FFFFFF
6,L6,Ligne 6,3,F39200,FFFFFF
"""


def _gtfs() -> GinkoGtfs:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("stops.txt", STOPS)
        z.writestr("routes.txt", ROUTES)
    g = GinkoGtfs()
    g.load(buf.getvalue(), date(2026, 11, 17))
    return g


def _feed(*stop_ids: str, route_id: str = "102") -> bytes:
    f = rt.FeedMessage()
    f.header.gtfs_realtime_version = "2.0"
    e = f.entity.add()
    e.id = "alert-test"
    a = e.alert
    a.effect = rt.Alert.DETOUR
    a.header_text.translation.add().text = "Travaux T2"
    for sid in stop_ids:
        ie = a.informed_entity.add()
        ie.route_id = route_id
        ie.stop_id = sid
    return f.SerializeToString()


@pytest.fixture(scope="module")
def gtfs() -> GinkoGtfs:
    return _gtfs()


def test_arret_de_bus_connu(gtfs):
    alerte = parse_alerts(_feed("JULEHAG4", route_id="6"), gtfs)[0]
    assert alerte["arrets"] == ["Lycée Jules Haag"]
    assert alerte["arrets_ids"] == ["JULEHAG4"]
    assert alerte["lignes"] == ["L6"]


def test_quais_de_tram_en_noms_sans_doublon(gtfs):
    alerte = parse_alerts(_feed("t_cham1", "t_cano1", "t_cham2", "CHAMARS1"), gtfs)[0]
    assert alerte["arrets"] == ["Chamars", "Canot"]
    assert alerte["arrets_ids"] == ["t_cham1", "t_cano1", "t_cham2", "CHAMARS1"]
    assert alerte["lignes"] == ["T2"]


def test_identifiant_inconnu_hors_des_noms(gtfs):
    alerte = parse_alerts(_feed("t_cham1", "ZZINCONNU"), gtfs)[0]
    assert alerte["arrets"] == ["Chamars"]
    assert "ZZINCONNU" in alerte["arrets_ids"]
    assert all("_" not in nom and not nom.isupper() for nom in alerte["arrets"])


@pytest.mark.parametrize("variante", [" t_cano1", "t_cano1 ", "T_CANO1", "t_Cano1"])
def test_variantes_d_ecriture(gtfs, variante):
    alerte = parse_alerts(_feed(variante), gtfs)[0]
    assert alerte["arrets"] == ["Canot"]
    assert alerte["arrets_ids"] == ["t_cano1"]


def test_quai_sans_nom_prend_celui_de_la_station(gtfs):
    alerte = parse_alerts(_feed("t_vide1"), gtfs)[0]
    assert alerte["arrets"] == ["Canot"]


def test_gtfs_non_charge_ne_laisse_passer_aucun_code():
    alerte = parse_alerts(_feed("t_cham1", "t_cano1"), GinkoGtfs())[0]
    assert alerte["arrets"] == []
    assert alerte["arrets_ids"] == ["t_cham1", "t_cano1"]
