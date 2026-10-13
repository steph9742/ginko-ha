# custom_components/ginko/gtfs_rt.py
from __future__ import annotations

import math
from datetime import datetime

from google.transit import gtfs_realtime_pb2 as rt

from .gtfs import GinkoGtfs, _bearing as _bearing_ll

SKIPPED = rt.TripUpdate.StopTimeUpdate.SKIPPED
A_QUAI_SEC = 30
TERMINUS_SEC = 1500


def _bearing(a: dict, b: dict) -> int | None:
    if None in (a.get("lat"), a.get("lon"), b.get("lat"), b.get("lon")):
        return None
    return _bearing_ll(a["lat"], a["lon"], b["lat"], b["lon"])


def _position(gtfs: GinkoGtfs, trip: dict, theo: dict, prev_seq: int, first_seq: int, midnight: int, est_first, retard, now: int, started: bool) -> dict:
    nxt_id = theo[first_seq][0] if first_seq in theo else None
    prv_id = theo[prev_seq][0] if prev_seq in theo else None
    nxt = gtfs.stops.get(nxt_id, {}) if nxt_id else {}
    prv = gtfs.stops.get(prv_id, {}) if prv_id else {}
    out = {"lat": nxt.get("lat"), "lon": nxt.get("lon"), "cap": None, "progression_segment": 1.0, "trace": "arret"}
    if not started or not prv or prv.get("lat") is None or nxt.get("lat") is None or est_first is None:
        return out
    prev_est = midnight + theo[prev_seq][1] + (retard or 0)
    span = est_first - prev_est
    frac = 1.0 if span <= 0 else max(0.0, min(1.0, (now - prev_est) / span))
    out["progression_segment"] = round(frac, 2)
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


def parse_trip_updates(raw: bytes, gtfs: GinkoGtfs, now: int) -> dict:
    feed = rt.FeedMessage()
    feed.ParseFromString(raw)
    vehicules: dict[str, dict] = {}
    index: dict[tuple[str, str], list[tuple[int, int, bool, str, bool]]] = {}

    for entity in feed.entity:
        if not entity.HasField("trip_update"):
            continue
        tu = entity.trip_update
        trip_id = tu.trip.trip_id
        trip = gtfs.trips.get(trip_id)
        if not trip or not tu.stop_time_update:
            continue
        route_id = trip["route_id"]
        route = gtfs.routes.get(route_id, {})
        aller = trip["direction_id"] == "0"
        theo = gtfs.theoretical(trip_id)
        start_date = tu.trip.start_date or datetime.fromtimestamp(now).strftime("%Y%m%d")
        midnight = int(datetime.strptime(start_date, "%Y%m%d").timestamp())

        updates = list(tu.stop_time_update)
        first = updates[0]
        first_seq = first.stop_sequence
        total = max(theo) if theo else first_seq
        est_first = _event(first)
        retard_first = (est_first - (midnight + theo[first_seq][1])) if (est_first and first_seq in theo) else None

        for stu in updates:
            est = _event(stu)
            if est is None or stu.stop_sequence not in theo:
                continue
            stop_id, dep = theo[stu.stop_sequence]
            index.setdefault((route_id, stop_id), []).append(
                (est, est - (midnight + dep), stu.schedule_relationship == SKIPPED, trip_id, aller, tu.vehicle.id)
            )

        started = first_seq > 1
        has_vid = bool(tu.vehicle.id) and tu.vehicle.id != "0"
        if not started and (not has_vid or est_first is None or est_first - now > TERMINUS_SEC):
            continue
        dans_sec = max(0, (est_first or now) - now)
        if not started:
            statut = "depart"
        elif dans_sec <= A_QUAI_SEC:
            statut = "a_quai"
        else:
            statut = "en_route"
        prev_seq = first_seq - 1
        vid = tu.vehicle.id if has_vid else f"trip:{trip_id}"
        bus = {
            "id": vid,
            "num_vehicule": None,
            "ligne": route.get("num", route_id),
            "id_ligne": route_id,
            "couleurFond": route.get("couleurFond"),
            "couleurTexte": route.get("couleurTexte"),
            "mode": "tram" if route.get("type") == "0" else "bus",
            **_position(gtfs, trip, theo, prev_seq, first_seq, midnight, est_first, retard_first, now, started),
            "prochains": [
                {
                    "nom": gtfs.stop_name(theo[u.stop_sequence][0]) if u.stop_sequence in theo else None,
                    "heure": _event(u),
                    "dans_sec": max(0, _event(u) - now) if _event(u) else None,
                    "non_desservi": u.schedule_relationship == SKIPPED,
                }
                for u in updates[:6]
            ],
            "sens": "aller" if aller else "retour",
            "terminus": trip["headsign"],
            "prochain_arret": gtfs.stop_name(theo[first_seq][0]) if first_seq in theo else None,
            "arret_precedent": gtfs.stop_name(theo[prev_seq][0]) if prev_seq in theo else None,
            "statut": statut,
            "dans_sec": dans_sec,
            "retard": retard_first,
            "arrets_restants": len(updates),
            "progression": round(first_seq / total, 2) if total else None,
            "trip_id": trip_id,
        }
        rank = (0 if started else 1, dans_sec)
        current = vehicules.get(vid)
        if current is None or rank < current["_rank"]:
            vehicules[vid] = {**bus, "_rank": rank}

    for lst in index.values():
        lst.sort()
    return {
        "horodatage": feed.header.timestamp or now,
        "vehicules": sorted(
            ({k: v for k, v in b.items() if k != "_rank"} for b in vehicules.values()),
            key=lambda b: (b["ligne"], b["dans_sec"]),
        ),
        "index": index,
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
        lignes, arrets = [], []
        for ie in al.informed_entity:
            if ie.route_id:
                num = gtfs.routes.get(ie.route_id, {}).get("num", ie.route_id)
                if num not in lignes:
                    lignes.append(num)
            if ie.stop_id:
                nom = gtfs.stop_name(ie.stop_id)
                if nom not in arrets:
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
