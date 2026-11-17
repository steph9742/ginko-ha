# custom_components/ginko/gtfs_rt.py
from __future__ import annotations

import logging
import math
from datetime import datetime

from google.transit import gtfs_realtime_pb2 as rt

from .gtfs import GinkoGtfs, _bearing as _bearing_ll

_LOGGER = logging.getLogger(__name__)
_ARRETS_INCONNUS: set[str] = set()

SKIPPED = rt.TripUpdate.StopTimeUpdate.SKIPPED
A_QUAI_SEC = 10
A_QUAI_MAX_SEC = 180
TERMINUS_SEC = 1500
MEMOIRE_SEC = 120
DEPART_MARGE_SEC = 60


def _bearing(a: dict, b: dict) -> int | None:
    if None in (a.get("lat"), a.get("lon"), b.get("lat"), b.get("lon")):
        return None
    return _bearing_ll(a["lat"], a["lon"], b["lat"], b["lon"])


def _position(gtfs: GinkoGtfs, trip: dict, theo: dict, prev_seq: int | None, next_seq: int, frac: float) -> dict:
    nxt_id = theo[next_seq][0] if next_seq in theo else None
    prv_id = theo[prev_seq][0] if prev_seq in theo else None
    nxt = gtfs.stops.get(nxt_id, {}) if nxt_id else {}
    prv = gtfs.stops.get(prv_id, {}) if prv_id else {}
    out = {"lat": nxt.get("lat"), "lon": nxt.get("lon"), "cap": None, "progression_segment": round(frac, 2), "trace": "arret"}
    if frac >= 1.0 or not prv or prv.get("lat") is None or nxt.get("lat") is None:
        return out
    shape_id = trip.get("shape_id")
    if shape_id and shape_id != "0":
        dp = gtfs.shape_distance(shape_id, prv_id)
        dn = gtfs.shape_distance(shape_id, nxt_id)
        if dp is not None and dn is not None and dn > dp:
            pt = gtfs.shape_point(shape_id, dp + (dn - dp) * frac)
            if pt:
                out["lat"], out["lon"] = round(pt[0], 6), round(pt[1], 6)
                out["cap"] = pt[2] if pt[2] is not None else _bearing(prv, nxt)
                out["trace"] = "shape"
                return out
    out["lat"] = round(prv["lat"] + (nxt["lat"] - prv["lat"]) * frac, 6)
    out["lon"] = round(prv["lon"] + (nxt["lon"] - prv["lon"]) * frac, 6)
    out["cap"] = _bearing(prv, nxt)
    out["trace"] = "droite"
    return out


def _event(stu):
    ev = stu.departure if stu.HasField("departure") else stu.arrival
    return ev.time if ev.time else None


def _lire_flux(raw: bytes, now: int) -> tuple[int, dict[str, dict]]:
    feed = rt.FeedMessage()
    feed.ParseFromString(raw)
    courses = {}
    for entity in feed.entity:
        if not entity.HasField("trip_update"):
            continue
        tu = entity.trip_update
        if not tu.trip.trip_id or not tu.stop_time_update:
            continue
        vid = tu.vehicle.id if tu.vehicle.id and tu.vehicle.id != "0" else ""
        courses[tu.trip.trip_id] = {
            "vid": vid,
            "start_date": tu.trip.start_date or datetime.fromtimestamp(now).strftime("%Y%m%d"),
            "updates": [(u.stop_sequence, _event(u), u.schedule_relationship == SKIPPED) for u in tu.stop_time_update],
        }
    return feed.header.timestamp or now, courses


def _fusionner(courses: dict[str, dict], memoire: dict[str, dict], now: int) -> tuple[dict[str, dict], int]:
    for tid, c in courses.items():
        m = memoire.setdefault(tid, {})
        m["data"] = c
        m["vu"] = now
    fusion = dict(courses)
    reprises = 0
    for tid, m in list(memoire.items()):
        if tid in courses:
            continue
        if now - m.get("vu", 0) > MEMOIRE_SEC:
            del memoire[tid]
            continue
        restants = [u for u in m["data"]["updates"] if u[1] is None or u[1] >= now]
        if restants:
            fusion[tid] = {**m["data"], "updates": restants}
            reprises += 1
    return fusion, reprises


def _seq_precedente(theo: dict, seq: int) -> int | None:
    avant = [s for s in theo if s < seq]
    return max(avant) if avant else None


def parse_trip_updates(raw: bytes, gtfs: GinkoGtfs, now: int, etat: dict | None = None) -> dict:
    etat = {} if etat is None else etat
    memoire = etat.setdefault("courses", {})
    horodatage, courses = _lire_flux(raw, now)
    fusion, reprises = _fusionner(courses, memoire, now)
    vehicules: dict[str, dict] = {}
    index: dict[tuple[str, str], list[tuple]] = {}

    for trip_id, c in fusion.items():
        trip = gtfs.trips.get(trip_id)
        theo = gtfs.theoretical(trip_id)
        if not trip or not theo:
            continue
        m = memoire.get(trip_id, {})
        updates = [u for u in c["updates"] if u[0] >= m.get("seq", 0)]
        if not updates:
            continue
        route_id = trip["route_id"]
        route = gtfs.routes.get(route_id, {})
        aller = trip["direction_id"] == "0"
        midnight = int(datetime.strptime(c["start_date"], "%Y%m%d").timestamp())
        vid = c["vid"]

        for seq, est, skipped in updates:
            if est is None or seq not in theo:
                continue
            stop_id, dep = theo[seq]
            index.setdefault((route_id, stop_id), []).append(
                (est, est - (midnight + dep), skipped, trip_id, aller, vid)
            )

        first_seq, est_first, _ = updates[0]
        retard = (est_first - (midnight + theo[first_seq][1])) if (est_first and first_seq in theo) else None
        origine = min(theo)
        depart_origine = midnight + theo[origine][1] + (retard or 0)
        started = first_seq > origine and depart_origine <= now + DEPART_MARGE_SEC

        if not started:
            if not vid or depart_origine - now > TERMINUS_SEC:
                continue
            statut = "depart"
            dans_sec = max(0, depart_origine - now)
            prev_seq, next_seq, frac = None, origine, 1.0
            m["au_depart"] = True
        else:
            if m.get("seq") != first_seq:
                m["t_change"] = now if ("seq" in m or m.pop("au_depart", False)) else None
                m["seq"] = first_seq
                m["frac"] = 0.0
                m["quai_depuis"] = None
            dans_sec = max(0, est_first - now) if est_first else 0
            if m.get("quai_depuis") is None and est_first is not None and est_first - now <= A_QUAI_SEC:
                m["quai_depuis"] = now
            a_quai = m.get("quai_depuis") is not None and now - m["quai_depuis"] <= A_QUAI_MAX_SEC
            statut = "a_quai" if a_quai else "en_route"
            prev_seq, next_seq = _seq_precedente(theo, first_seq), first_seq
            if a_quai or m.get("frac", 0.0) >= 1.0:
                frac = 1.0
                m["frac"] = 1.0
            else:
                if m.get("t_change"):
                    t_dep = m["t_change"]
                elif prev_seq is not None:
                    t_dep = midnight + theo[prev_seq][1] + (retard or 0)
                else:
                    t_dep = now
                span = (est_first or now) - t_dep
                frac = 1.0 if span <= 0 else max(0.0, min(1.0, (now - t_dep) / span))
                frac = max(frac, m.get("frac", 0.0))
                m["frac"] = frac

        cle = vid or f"trip:{trip_id}"
        total = max(theo)
        bus = {
            "id": cle,
            "num_vehicule": None,
            "ligne": route.get("num", route_id),
            "id_ligne": route_id,
            "couleurFond": route.get("couleurFond"),
            "couleurTexte": route.get("couleurTexte"),
            "mode": "tram" if route.get("type") == "0" else "bus",
            **_position(gtfs, trip, theo, prev_seq, next_seq, frac),
            "prochains": [
                {
                    "nom": gtfs.stop_name(theo[seq][0]) if seq in theo else None,
                    "heure": est,
                    "dans_sec": max(0, est - now) if est else None,
                    "non_desservi": skipped,
                }
                for seq, est, skipped in updates[:6]
            ],
            "sens": "aller" if aller else "retour",
            "terminus": trip["headsign"],
            "prochain_arret": gtfs.stop_name(theo[next_seq][0]) if next_seq in theo else None,
            "arret_precedent": gtfs.stop_name(theo[prev_seq][0]) if prev_seq in theo else None,
            "statut": statut,
            "dans_sec": dans_sec,
            "retard": retard,
            "arrets_restants": len(updates),
            "progression": round(first_seq / total, 2) if total else None,
            "trip_id": trip_id,
            "memoire": trip_id not in courses,
        }
        rank = (0 if started else 1, dans_sec)
        current = vehicules.get(cle)
        if current is None or rank < current["_rank"]:
            vehicules[cle] = {**bus, "_rank": rank}

    for lst in index.values():
        lst.sort()
    return {
        "horodatage": horodatage,
        "vehicules": sorted(
            ({k: v for k, v in b.items() if k != "_rank"} for b in vehicules.values()),
            key=lambda b: (b["ligne"], b["dans_sec"]),
        ),
        "index": index,
        "courses_flux": len(courses),
        "courses_reprises": reprises,
    }


def parse_alerts(raw: bytes, gtfs: GinkoGtfs) -> list[dict]:
    feed = rt.FeedMessage()
    feed.ParseFromString(raw)
    alertes = []
    for entity in feed.entity:
        if not entity.HasField("alert"):
            continue
        al = entity.alert
        titre = al.header_text.translation[0].text if al.header_text.translation else ""
        texte = al.description_text.translation[0].text if al.description_text.translation else ""
        lignes, arrets, arrets_ids = [], [], []
        for ie in al.informed_entity:
            if ie.route_id:
                num = gtfs.routes.get(ie.route_id, {}).get("num", ie.route_id)
                if num not in lignes:
                    lignes.append(num)
            if ie.stop_id:
                sid = gtfs.resolve_stop(ie.stop_id) or ie.stop_id.strip()
                if sid and sid not in arrets_ids:
                    arrets_ids.append(sid)
                nom = gtfs.resolve_stop_name(ie.stop_id)
                if nom is None:
                    if ie.stop_id not in _ARRETS_INCONNUS:
                        _ARRETS_INCONNUS.add(ie.stop_id)
                        _LOGGER.warning(
                            "Ginko: arrêt %r de l'alerte %s introuvable dans le GTFS chargé (%d arrêts, chargé le %s)",
                            ie.stop_id, entity.id, len(gtfs.stops), gtfs.loaded_at,
                        )
                elif nom not in arrets:
                    arrets.append(nom)
        periodes = [
            {
                "debut": datetime.fromtimestamp(p.start).isoformat() if p.start else None,
                "fin": datetime.fromtimestamp(p.end).isoformat() if p.end else None,
            }
            for p in al.active_period
        ]
        alertes.append({
            "id": entity.id,
            "titre": titre,
            "texte": texte,
            "effet": rt.Alert.Effect.Name(al.effect),
            "cause": rt.Alert.Cause.Name(al.cause),
            "lignes": lignes,
            "arrets": arrets,
            "arrets_ids": arrets_ids,
            "periodes": periodes,
        })
    return alertes


def enrich_passages(passages: list, index: dict, now: int, tolerance: int = 150, on_match=None) -> list:
    if not index:
        return passages
    result = []
    for p in passages:
        if not isinstance(p, dict):
            continue
        key = (str(p.get("idLigne")), str(p.get("idArret")))
        candidates = index.get(key)
        temps = p.get("tempsEnSeconde")
        if not candidates or temps is None:
            result.append(p)
            continue
        target = now + int(temps)
        aller = bool(p.get("sensAller", True))
        best = None
        for est, retard, skipped, trip_id, sens_aller, vid in candidates:
            if sens_aller != aller:
                continue
            gap = abs(est - target)
            if gap <= tolerance and (best is None or gap < best[0]):
                best = (gap, retard, skipped, vid)
        if best is None:
            result.append(p)
            continue
        vid = best[3]
        num = p.get("numVehicule")
        if on_match is not None and vid and vid != "0" and num is not None:
            on_match(vid, str(num))
        if best[2]:
            result.append({**p, "nonDesservi": True, "idVehiculeRt": vid or None})
            continue
        result.append({**p, "retard": int(best[1]), "idVehiculeRt": vid or None})
    return result
