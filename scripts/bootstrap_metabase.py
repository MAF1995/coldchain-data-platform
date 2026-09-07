"""Create the Bloc II Metabase dashboard from the PostgreSQL analytical marts."""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from typing import Any

import requests


COLLECTION_NAME = "Bloc II - Analyse qualité"
DASHBOARD_NAME = "Pilotage qualité de la chaîne du froid"


@dataclass(frozen=True)
class CardSpec:
    name: str
    description: str
    display: str
    query: str
    settings: dict[str, Any]
    position: tuple[int, int, int, int]
    aliases: tuple[str, ...] = ()


CARD_SPECS = (
    CardSpec(
        name="Conformité thermique globale",
        aliases=("Taux de conformite thermique",),
        description="Part des mesures éligibles comprises entre les seuils applicables.",
        display="scalar",
        query="""
            select round(
                100.0 * sum(compliant_reading_count)
                / nullif(sum(eligible_reading_count), 0),
                2
            ) as "Conformité (%)"
            from analytics.mart_quality_daily
        """,
        settings={"scalar.field": "Conformité (%)"},
        position=(0, 0, 8, 3),
    ),
    CardSpec(
        name="Mesures thermiques éligibles",
        description="Nombre de mesures auxquelles une règle thermique est applicable.",
        display="scalar",
        query="""
            select sum(eligible_reading_count) as "Mesures éligibles"
            from analytics.mart_quality_daily
        """,
        settings={"scalar.field": "Mesures éligibles"},
        position=(0, 8, 8, 3),
    ),
    CardSpec(
        name="Mesures hors plage",
        description="Nombre de mesures sous le seuil bas ou au-dessus du seuil haut.",
        display="scalar",
        query="""
            select
                sum(too_cold_reading_count + too_hot_reading_count)
                    as "Mesures hors plage"
            from analytics.mart_quality_daily
        """,
        settings={"scalar.field": "Mesures hors plage"},
        position=(0, 16, 8, 3),
    ),
    CardSpec(
        name="Conformité par jour et par zone",
        description="Répartition des mesures conformes, trop froides et trop chaudes.",
        display="bar",
        query="""
            select
                to_char(observation_date, 'DD/MM/YYYY') || ' | ' || room_id
                    as "Périmètre",
                round(100.0 * too_cold_reading_count
                    / nullif(eligible_reading_count, 0), 2) as "Trop froides (%)",
                round(100.0 * too_hot_reading_count
                    / nullif(eligible_reading_count, 0), 2) as "Trop chaudes (%)",
                temperature_compliance_rate_pct as "Conformes (%)"
            from analytics.mart_quality_daily
            order by observation_date, room_id
        """,
        settings={
            "graph.dimensions": ["Périmètre"],
            "graph.metrics": ["Trop froides (%)", "Trop chaudes (%)", "Conformes (%)"],
            "graph.colors": ["#5BC0BE", "#2D9CDB", "#2A9D8F"],
            "stackable.stack_type": "stacked",
        },
        position=(3, 0, 12, 8),
    ),
    CardSpec(
        name="Température observée et seuils",
        description="Évolution des mesures de la chambre froide CF-008 face aux seuils 2-8 °C.",
        display="line",
        query="""
            select
                event_time as "Horodatage",
                temperature_c as "Température (°C)",
                threshold_min_c as "Seuil bas (°C)",
                threshold_max_c as "Seuil haut (°C)"
            from clean.int_temperature_status
            where temperature_rule_eligible
              and room_id = 'CF-008'
            order by event_time
        """,
        settings={
            "graph.dimensions": ["Horodatage"],
            "graph.metrics": ["Température (°C)", "Seuil bas (°C)", "Seuil haut (°C)"],
            "graph.colors": ["#2D9CDB", "#5BC0BE", "#0077B6"],
        },
        position=(3, 12, 12, 8),
    ),
    CardSpec(
        name="Détail des mesures hors plage",
        description="Mesures à investiguer, triées de la plus récente à la plus ancienne.",
        display="table",
        query="""
            select
                event_time as "Horodatage",
                room_id as "Local",
                machine_id as "Équipement",
                batch_id as "Lot",
                temperature_c as "Température (°C)",
                temperature_status as "Statut",
                temperature_deviation_c as "Écart maximal (°C)",
                alarm_code as "Code alarme"
            from clean.int_temperature_status
            where temperature_rule_eligible
              and temperature_status in ('TOO_COLD', 'TOO_HOT')
            order by event_time desc
        """,
        settings={"table.pivot_column": "Local"},
        position=(11, 0, 24, 7),
    ),
)


class MetabaseClient:
    def __init__(self, base_url: str, email: str, password: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        response = self.session.post(
            f"{self.base_url}/api/session",
            json={"username": email, "password": password},
            timeout=30,
        )
        self._raise(response, "connexion à Metabase")
        self.session.headers.update({"X-Metabase-Session": response.json()["id"]})

    @staticmethod
    def _raise(response: requests.Response, action: str) -> None:
        if response.ok:
            return
        detail = response.text[:800]
        raise RuntimeError(f"Échec pendant {action}: HTTP {response.status_code} - {detail}")

    def get(self, path: str) -> Any:
        response = self.session.get(f"{self.base_url}{path}", timeout=60)
        self._raise(response, f"GET {path}")
        return response.json()

    def send(self, method: str, path: str, payload: dict[str, Any]) -> Any:
        response = self.session.request(
            method,
            f"{self.base_url}{path}",
            json=payload,
            timeout=60,
        )
        self._raise(response, f"{method} {path}")
        return response.json() if response.content else None


def ensure_collection(client: MetabaseClient) -> int:
    aliases = {COLLECTION_NAME, "Bloc II - Analyse qualite"}
    existing = next(
        (item for item in client.get("/api/collection") if item.get("name") in aliases),
        None,
    )
    payload = {
        "name": COLLECTION_NAME,
        "description": "Analyses de conformité thermique et d'excursion des zones fixes.",
    }
    if existing:
        client.send("PUT", f"/api/collection/{existing['id']}", payload)
        return int(existing["id"])
    return int(client.send("POST", "/api/collection", payload)["id"])


def ensure_dashboard(client: MetabaseClient, collection_id: int) -> int:
    aliases = {DASHBOARD_NAME, "Pilotage qualite de la chaine du froid"}
    existing = next(
        (item for item in client.get("/api/dashboard") if item.get("name") in aliases),
        None,
    )
    payload = {
        "name": DASHBOARD_NAME,
        "description": (
            "Période qualifiée : 1er et 2 juillet 2026. "
            "Les indicateurs décrivent 119 mesures thermiques éligibles ; "
            "ils qualifient le pipeline et ne suffisent pas à établir une tendance de long terme."
        ),
        "collection_id": collection_id,
        "width": "fixed",
    }
    if existing:
        client.send("PUT", f"/api/dashboard/{existing['id']}", payload)
        return int(existing["id"])
    return int(client.send("POST", "/api/dashboard", payload)["id"])


def database_id(client: MetabaseClient, name: str) -> int:
    databases = client.get("/api/database")["data"]
    match = next((item for item in databases if item.get("name") == name), None)
    if not match:
        raise RuntimeError(f"La base Metabase '{name}' est introuvable.")
    return int(match["id"])


def card_payload(
    spec: CardSpec,
    database: int,
    collection_id: int,
    dashboard_id: int | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "name": spec.name,
        "description": spec.description,
        "collection_id": collection_id,
        "display": spec.display,
        "dataset_query": {
            "database": database,
            "type": "native",
            "native": {"query": spec.query.strip(), "template-tags": {}},
        },
        "visualization_settings": spec.settings,
    }
    if dashboard_id is not None:
        payload["dashboard_id"] = dashboard_id
    return payload


def ensure_cards(
    client: MetabaseClient,
    database: int,
    collection_id: int,
    dashboard_id: int,
) -> dict[str, int]:
    cards = client.get("/api/card?f=all")
    by_name = {item["name"]: item for item in cards if not item.get("archived")}
    dashboard = client.get(f"/api/dashboard/{dashboard_id}")
    attached_card_ids = {
        int(item["card_id"]) for item in dashboard.get("dashcards", [])
    }
    result: dict[str, int] = {}

    for spec in CARD_SPECS:
        existing = next(
            (by_name[name] for name in (spec.name, *spec.aliases) if name in by_name),
            None,
        )
        if existing and int(existing["id"]) in attached_card_ids:
            card_id = int(existing["id"])
            client.send(
                "PUT",
                f"/api/card/{card_id}",
                card_payload(spec, database, collection_id),
            )
        else:
            if existing:
                client.send("PUT", f"/api/card/{existing['id']}", {"archived": True})
            card = client.send(
                "POST",
                "/api/card",
                card_payload(spec, database, collection_id, dashboard_id),
            )
            card_id = int(card["id"])
        result[spec.name] = card_id

    return result


def position_cards(
    client: MetabaseClient,
    dashboard_id: int,
    card_ids: dict[str, int],
) -> None:
    dashboard = client.get(f"/api/dashboard/{dashboard_id}")
    dashcard_by_card_id = {
        int(item["card_id"]): item for item in dashboard.get("dashcards", [])
    }
    missing = [card_id for card_id in card_ids.values() if card_id not in dashcard_by_card_id]
    if missing:
        raise RuntimeError(
            "Certaines cartes ne sont pas rattachées au dashboard: "
            + ", ".join(map(str, missing))
        )

    layout = []
    for spec in CARD_SPECS:
        row, col, size_x, size_y = spec.position
        dashcard = dict(dashcard_by_card_id[card_ids[spec.name]])
        dashcard.update(
            {
                "row": row,
                "col": col,
                "size_x": size_x,
                "size_y": size_y,
            }
        )
        layout.append(dashcard)
    client.send("PUT", f"/api/dashboard/{dashboard_id}", {"dashcards": layout})


def validate_cards(client: MetabaseClient, card_ids: dict[str, int]) -> None:
    for name, card_id in card_ids.items():
        result = client.send("POST", f"/api/card/{card_id}/query", {"parameters": []})
        if result.get("status") == "failed":
            raise RuntimeError(f"La requête de la carte '{name}' a échoué: {result}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--url",
        default=os.getenv("METABASE_URL", "http://localhost:3001"),
    )
    parser.add_argument(
        "--email",
        default=os.getenv("METABASE_ADMIN_EMAIL", "admin@pharma-analytics.internal"),
    )
    parser.add_argument("--password", default=os.getenv("METABASE_ADMIN_PASSWORD"))
    parser.add_argument("--database", default="Pharma Analytics")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.password:
        print(
            "Définissez METABASE_ADMIN_PASSWORD ou utilisez --password.",
            file=sys.stderr,
        )
        return 2

    client = MetabaseClient(args.url, args.email, args.password)
    collection_id = ensure_collection(client)
    dashboard_id = ensure_dashboard(client, collection_id)
    source_database_id = database_id(client, args.database)
    cards = ensure_cards(client, source_database_id, collection_id, dashboard_id)
    position_cards(client, dashboard_id, cards)
    validate_cards(client, cards)

    print(f"Dashboard prêt : {args.url}/dashboard/{dashboard_id}")
    print(f"Cartes validées : {len(cards)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
