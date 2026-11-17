import io
import zipfile
from datetime import date, datetime

import pytest
from google.transit import gtfs_realtime_pb2 as rt

from ginko_pure.gtfs import GinkoGtfs
from ginko_pure.gtfs_rt import MEMOIRE_SEC, parse_trip_updates

JOUR = "20261117"
MINUIT = int(datetime.strptime(JOUR, "%Y%m%d").timestamp())


def T(h: int, m: int, s: int = 0) -> int:
    return MINUIT + h * 3600 + m * 60 + s


def _gtfs() -> GinkoGtfs:
    files = {
        "stops.txt": "stop_id,stop_name,stop_lat,stop_lon,location_type,parent_station\n"
        "S1,Un,47.2300,6.0000,0,\nS2,Deux,47.2310,6.0010,0,\nS3,Trois,47.2320,6.0020,0,\nS4,Quatre,47.2330,6.0030,0,\n",
        "routes.txt": "route_id,route_short_name,route_long_name,route_type,route_color,route_text_color\n101,T1,Tram,0,00A5C2,FFFFFF\n",
        "trips.txt": "route_id,service_id,trip_id,trip_headsign,direction_id,shape_id\n"
        "101,S,TA,Quatre,0,\n101,S,TB,Quatre,0,\n",
        "stop_times.txt": "trip_id,arrival_time,departure_time,stop_id,stop_sequence\n"
        "TA,08:00:00,08:00:00,S1,1\nTA,08:02:00,08:02:00,S2,2\nTA,08:04:00,08:04:00,S3,3\nTA,08:06:00,08:06:00,S4,4\n"
        "TB,08:20:00,08:20:00,S2,2\nTB,08:22:00,08:22:00,S3,3\nTB,08:24:00,08:24:00,S4,4\n",
        "calendar_dates.txt": f"service_id,date,exception_type\nS,{JOUR},1\n",
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, content in files.items():
            z.writestr(name, content)
    g = GinkoGtfs()
    g.load(buf.getvalue(), date(2026, 11, 17))
    return g


def _flux(*courses: tuple[str, str, list[tuple[int, int]]]) -> bytes:
    f = rt.FeedMessage()
    f.header.gtfs_realtime_version = "2.0"
    for trip_id, vid, arrets in courses:
        e = f.entity.add()
        e.id = trip_id
        tu = e.trip_update
        tu.trip.trip_id = trip_id
        tu.trip.start_date = JOUR
        tu.vehicle.id = vid
        for seq, t in arrets:
            u = tu.stop_time_update.add()
            u.stop_sequence = seq
            u.departure.time = t
    return f.SerializeToString()


def _vehicule(data: dict, vid: str) -> dict | None:
    return next((b for b in data["vehicules"] if b["id"] == vid), None)


@pytest.fixture(scope="module")
def gtfs() -> GinkoGtfs:
    return _gtfs()


def test_course_future_au_deuxieme_arret_n_est_pas_commencee(gtfs):
    now = T(8, 3)
    data = parse_trip_updates(_flux(("TB", "V2", [(2, T(8, 20)), (3, T(8, 22))])), gtfs, now, {})
    b = _vehicule(data, "V2")
    assert b["statut"] == "depart"
    assert b["prochain_arret"] == "Deux"
    assert b["arret_precedent"] is None
    assert (b["lat"], b["lon"]) == (47.231, 6.001)
    assert b["dans_sec"] == T(8, 20) - now


def test_course_en_cours_preferee_a_la_suivante(gtfs):
    now = T(8, 3)
    flux = _flux(("TA", "V1", [(3, T(8, 4)), (4, T(8, 6))]), ("TB", "V1", [(2, T(8, 20)), (3, T(8, 22))]))
    b = _vehicule(parse_trip_updates(flux, gtfs, now, {}), "V1")
    assert b["trip_id"] == "TA"
    assert b["statut"] == "en_route"


def test_course_absente_du_flux_reprise_puis_oubliee(gtfs):
    etat = {}
    t0 = T(8, 2, 30)
    parse_trip_updates(_flux(("TA", "V1", [(3, T(8, 4)), (4, T(8, 6))])), gtfs, t0, etat)
    vide = _flux()
    b = _vehicule(parse_trip_updates(vide, gtfs, t0 + 20, etat), "V1")
    assert b is not None and b["memoire"] is True
    assert b["prochain_arret"] == "Trois"
    data = parse_trip_updates(vide, gtfs, t0 + MEMOIRE_SEC + 30, etat)
    assert _vehicule(data, "V1") is None


def test_a_quai_a_dix_secondes_et_maintenu(gtfs):
    etat = {}
    a = _vehicule(parse_trip_updates(_flux(("TA", "V1", [(3, T(8, 4))])), gtfs, T(8, 4) - 25, etat), "V1")
    assert a["statut"] == "en_route"
    b = _vehicule(parse_trip_updates(_flux(("TA", "V1", [(3, T(8, 4))])), gtfs, T(8, 4) - 8, etat), "V1")
    assert b["statut"] == "a_quai"
    c = _vehicule(parse_trip_updates(_flux(("TA", "V1", [(3, T(8, 4) + 60)])), gtfs, T(8, 4) + 20, etat), "V1")
    assert c["statut"] == "a_quai"
    d = _vehicule(parse_trip_updates(_flux(("TA", "V1", [(3, T(8, 4) + 400)])), gtfs, T(8, 4) + 200, etat), "V1")
    assert d["statut"] == "en_route"


def test_le_vehicule_ne_recule_pas_quand_l_heure_est_repoussee(gtfs):
    etat = {}
    a = _vehicule(parse_trip_updates(_flux(("TA", "V1", [(3, T(8, 4))])), gtfs, T(8, 3), etat), "V1")
    b = _vehicule(parse_trip_updates(_flux(("TA", "V1", [(3, T(8, 6))])), gtfs, T(8, 3, 10), etat), "V1")
    assert b["progression_segment"] >= a["progression_segment"]


def test_pas_de_bond_au_depart_d_un_arret(gtfs):
    etat = {}
    parse_trip_updates(_flux(("TA", "V1", [(2, T(8, 5)), (3, T(8, 7))])), gtfs, T(8, 5, 50), etat)
    avec = _vehicule(parse_trip_updates(_flux(("TA", "V1", [(3, T(8, 7))])), gtfs, T(8, 6), etat), "V1")
    sans = _vehicule(parse_trip_updates(_flux(("TA", "V1", [(3, T(8, 7))])), gtfs, T(8, 6), {}), "V1")
    assert avec["progression_segment"] == 0.0
    assert sans["progression_segment"] > 0.3


def test_jamais_de_retour_a_un_arret_depasse(gtfs):
    etat = {}
    parse_trip_updates(_flux(("TA", "V1", [(3, T(8, 4)), (4, T(8, 6))])), gtfs, T(8, 3), etat)
    b = _vehicule(parse_trip_updates(_flux(("TA", "V1", [(2, T(8, 3, 20)), (3, T(8, 4)), (4, T(8, 6))])), gtfs, T(8, 3, 10), etat), "V1")
    assert b["prochain_arret"] == "Trois"
