# custom_components/ginko/gtfs.py
from __future__ import annotations

import bisect
import csv
import io
import math
import zipfile
from datetime import date, datetime, timedelta

GTFS_URL = "https://api.ginko.voyage/gtfs-ginko.zip"


def _hms(value: str) -> int:
    h, m, s = value.split(":")
    return int(h) * 3600 + int(m) * 60 + int(s)


class GinkoGtfs:
    def __init__(self) -> None:
        self.routes: dict[str, dict] = {}
        self.stops: dict[str, dict] = {}
        self.trips: dict[str, dict] = {}
        self.stop_times: dict[str, list[tuple[int, str, int]]] = {}
        self.shapes: dict[str, tuple[list[float], list[float], list[float]]] = {}
        self.services: dict[str, set[str]] = {}
        self._proj: dict[tuple[str, str], float | None] = {}
        self.loaded_at: datetime | None = None
        self.loaded_for: date | None = None

    @property
    def loaded(self) -> bool:
        return self.loaded_at is not None

    def needs_reload(self, today: date) -> bool:
        if self.loaded_at is None or self.loaded_for != today:
            return True
        return datetime.now() - self.loaded_at > timedelta(hours=24)

    def load(self, raw: bytes, today: date) -> None:
        z = zipfile.ZipFile(io.BytesIO(raw))

        def rows(name: str):
            if name not in z.namelist():
                return []
            return csv.DictReader(io.TextIOWrapper(z.open(name), encoding="utf-8-sig"))

        keep_dates = {(today + timedelta(days=d)).strftime("%Y%m%d") for d in (-1, 0, 1)}
        services: dict[str, set[str]] = {d: set() for d in keep_dates}
        for r in rows("calendar_dates.txt"):
            if r["date"] in keep_dates and r.get("exception_type") == "1":
                services[r["date"]].add(r["service_id"])
        weekdays = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        for r in rows("calendar.txt"):
            for d in keep_dates:
                day = datetime.strptime(d, "%Y%m%d").date()
                if r["start_date"] <= d <= r["end_date"] and r.get(weekdays[day.weekday()]) == "1":
                    services[d].add(r["service_id"])
        active = set().union(*services.values())

        routes = {
            r["route_id"]: {
                "num": r.get("route_short_name") or r["route_id"],
                "nom": r.get("route_long_name", ""),
                "couleurFond": r.get("route_color") or None,
                "couleurTexte": r.get("route_text_color") or None,
                "type": r.get("route_type"),
            }
            for r in rows("routes.txt")
        }
        stops = {}
        for r in rows("stops.txt"):
            try:
                lat, lon = float(r.get("stop_lat") or ""), float(r.get("stop_lon") or "")
            except ValueError:
                lat = lon = None
            stops[r["stop_id"]] = {
                "nom": r.get("stop_name", ""),
                "parent": r.get("parent_station") or None,
                "lat": lat,
                "lon": lon,
            }
        trips = {
            r["trip_id"]: {
                "route_id": r["route_id"],
                "service_id": r["service_id"],
                "direction_id": r.get("direction_id", "0"),
                "headsign": r.get("trip_headsign", ""),
                "shape_id": r.get("shape_id") or None,
            }
            for r in rows("trips.txt")
            if r["service_id"] in active
        }
        used_shapes = {t["shape_id"] for t in trips.values() if t["shape_id"] and t["shape_id"] != "0"}
        raw_shapes: dict[str, list[tuple[int, float, float]]] = {}
        for r in rows("shapes.txt"):
            sid = r["shape_id"]
            if sid in used_shapes:
                try:
                    raw_shapes.setdefault(sid, []).append((int(r["shape_pt_sequence"]), float(r["shape_pt_lat"]), float(r["shape_pt_lon"])))
                except ValueError:
                    continue
        shapes = {}
        for sid, pts in raw_shapes.items():
            pts.sort()
            lats = [p[1] for p in pts]
            lons = [p[2] for p in pts]
            cum = [0.0]
            for i in range(1, len(pts)):
                cum.append(cum[-1] + _meters(lats[i - 1], lons[i - 1], lats[i], lons[i]))
            shapes[sid] = (lats, lons, cum)
        stop_times: dict[str, list[tuple[int, str, int]]] = {}
        for r in rows("stop_times.txt"):
            tid = r["trip_id"]
            if tid in trips:
                stop_times.setdefault(tid, []).append(
                    (int(r["stop_sequence"]), r["stop_id"], _hms(r["departure_time"] or r["arrival_time"]))
                )
        for lst in stop_times.values():
            lst.sort()

        self.routes, self.stops, self.trips, self.stop_times, self.services = routes, stops, trips, stop_times, services
        self.shapes = shapes
        self._proj = {}
        self.loaded_at = datetime.now()
        self.loaded_for = today

    def stop_name(self, stop_id: str) -> str:
        return self.stops.get(stop_id, {}).get("nom", stop_id)

    def theoretical(self, trip_id: str) -> dict[int, tuple[str, int]]:
        return {seq: (stop_id, dep) for seq, stop_id, dep in self.stop_times.get(trip_id, [])}

    def shape_distance(self, shape_id: str, stop_id: str) -> float | None:
        key = (shape_id, stop_id)
        if key in self._proj:
            return self._proj[key]
        shape = self.shapes.get(shape_id)
        stop = self.stops.get(stop_id, {})
        result = None
        if shape and stop.get("lat") is not None:
            lats, lons, cum = shape
            best = None
            k = math.cos(math.radians(stop["lat"]))
            px, py = stop["lon"] * k, stop["lat"]
            for i in range(len(lats) - 1):
                ax, ay = lons[i] * k, lats[i]
                bx, by = lons[i + 1] * k, lats[i + 1]
                dx, dy = bx - ax, by - ay
                seg = dx * dx + dy * dy
                t = 0.0 if seg == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / seg))
                qx, qy = ax + t * dx, ay + t * dy
                d2 = (px - qx) ** 2 + (py - qy) ** 2
                if best is None or d2 < best[0]:
                    best = (d2, cum[i] + t * (cum[i + 1] - cum[i]))
            if best is not None and math.sqrt(best[0]) * 111320 < 150:
                result = best[1]
        self._proj[key] = result
        return result

    def shape_point(self, shape_id: str, dist: float) -> tuple[float, float, int | None] | None:
        shape = self.shapes.get(shape_id)
        if not shape:
            return None
        lats, lons, cum = shape
        i = bisect.bisect_right(cum, dist) - 1
        i = max(0, min(i, len(cum) - 2))
        span = cum[i + 1] - cum[i]
        t = 0.0 if span <= 0 else max(0.0, min(1.0, (dist - cum[i]) / span))
        lat = lats[i] + (lats[i + 1] - lats[i]) * t
        lon = lons[i] + (lons[i + 1] - lons[i]) * t
        return lat, lon, _bearing(lats[i], lons[i], lats[i + 1], lons[i + 1])


def _meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    k = math.cos(math.radians((lat1 + lat2) / 2))
    dx = (lon2 - lon1) * k * 111320
    dy = (lat2 - lat1) * 110540
    return math.hypot(dx, dy)


def _bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> int | None:
    if lat1 == lat2 and lon1 == lon2:
        return None
    la1, la2 = math.radians(lat1), math.radians(lat2)
    dlon = math.radians(lon2 - lon1)
    x = math.sin(dlon) * math.cos(la2)
    y = math.cos(la1) * math.sin(la2) - math.sin(la1) * math.cos(la2) * math.cos(dlon)
    return int(math.degrees(math.atan2(x, y)) % 360)
