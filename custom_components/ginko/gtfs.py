# custom_components/ginko/gtfs.py
from __future__ import annotations

import csv
import io
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
        self.services: dict[str, set[str]] = {}
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
            }
            for r in rows("trips.txt")
            if r["service_id"] in active
        }
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
        self.loaded_at = datetime.now()
        self.loaded_for = today

    def stop_name(self, stop_id: str) -> str:
        return self.stops.get(stop_id, {}).get("nom", stop_id)

    def theoretical(self, trip_id: str) -> dict[int, tuple[str, int]]:
        return {seq: (stop_id, dep) for seq, stop_id, dep in self.stop_times.get(trip_id, [])}
