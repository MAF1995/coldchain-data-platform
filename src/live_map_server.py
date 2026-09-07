import argparse
import json
import sqlite3
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = PROJECT_ROOT / "data" / "raw" / "mqtt_raw.db"

MACHINE_LOCATIONS = {
    "LYO_01": {
        "site_label": "042",
        "zone": "Bâtiment A - lyophilisation",
        "room_id": "A-120",
        "latitude": 45.70482,
        "longitude": 4.88805,
    },
    "FILL_02": {
        "site_label": "042",
        "zone": "Bâtiment A - remplissage aseptique",
        "room_id": "A-135",
        "latitude": 45.70455,
        "longitude": 4.88842,
    },
    "AUTO_03": {
        "site_label": "042",
        "zone": "Bâtiment B - stérilisation",
        "room_id": "B-020",
        "latitude": 45.70420,
        "longitude": 4.88764,
    },
    "HVAC_CR_04": {
        "site_label": "042",
        "zone": "Chambre froide qualifiée",
        "room_id": "CF-008",
        "latitude": 45.70493,
        "longitude": 4.88731,
    },
    "COMP_05": {
        "site_label": "042",
        "zone": "Local utilités",
        "room_id": "U-014",
        "latitude": 45.70396,
        "longitude": 4.88710,
    },
    "SENSOR_06": {
        "site_label": "042",
        "zone": "Quai expédition froid",
        "room_id": "QF-002",
        "latitude": 45.70518,
        "longitude": 4.88772,
    },
}


HTML = r"""<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Carte live MQTT - chaîne du froid pharma</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
  <style>
    :root {
      --aqua-500: #43c6b6;
      --mint-300: #9ee7d2;
      --seafoam-100: #e8f8f4;
      --sky-300: #8fd3f4;
      --sky-600: #2f9fd0;
      --ink: #20343c;
      --muted: #6a7d86;
      --line: #d8ecec;
      --alarm: #d94b5f;
      --warn: #d88f2f;
      --ok: #2ea67a;
      --idle: #5188c7;
    }

    * { box-sizing: border-box; }

    body {
      margin: 0;
      min-height: 100vh;
      color: var(--ink);
      font-family: Garamond, "EB Garamond", "Cormorant Garamond", Georgia, serif;
      font-weight: 300;
      background: #f7fbfb;
      letter-spacing: 0;
    }

    .app {
      display: grid;
      grid-template-columns: minmax(0, 1fr) 390px;
      min-height: 100vh;
    }

    #map {
      min-height: 100vh;
      width: 100%;
    }

    aside {
      border-left: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.96);
      display: flex;
      flex-direction: column;
      min-width: 0;
    }

    header {
      padding: 20px 22px 14px;
      border-bottom: 1px solid var(--line);
    }

    h1 {
      margin: 0 0 8px;
      font-size: 25px;
      line-height: 1.1;
      font-weight: 300;
      color: var(--ink);
    }

    .subtitle {
      margin: 0;
      font-size: 15px;
      line-height: 1.35;
      color: var(--muted);
    }

    .statusbar {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 8px;
      padding: 14px 14px 12px;
      border-bottom: 1px solid var(--line);
      background: var(--seafoam-100);
    }

    .metric {
      min-height: 66px;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 10px;
      background: #ffffff;
    }

    .metric .label {
      display: block;
      font-size: 12px;
      color: var(--muted);
      margin-bottom: 6px;
    }

    .metric .value {
      display: block;
      font-size: 22px;
      line-height: 1;
      color: var(--sky-600);
    }

    .toolbar {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 12px 14px;
      border-bottom: 1px solid var(--line);
    }

    button {
      border: 1px solid var(--sky-600);
      border-radius: 8px;
      background: var(--sky-600);
      color: #ffffff;
      min-height: 34px;
      padding: 7px 12px;
      font: inherit;
      cursor: pointer;
    }

    button.secondary {
      background: #ffffff;
      color: var(--sky-600);
    }

    .last-refresh {
      margin-left: auto;
      font-size: 13px;
      color: var(--muted);
      white-space: nowrap;
    }

    .stream {
      overflow: auto;
      padding: 12px 14px 18px;
    }

    .event {
      border: 1px solid var(--line);
      border-left: 5px solid var(--ok);
      border-radius: 8px;
      padding: 10px 11px;
      margin-bottom: 10px;
      background: #ffffff;
    }

    .event.warning { border-left-color: var(--warn); }
    .event.alarm { border-left-color: var(--alarm); }
    .event.idle { border-left-color: var(--idle); }

    .event-title {
      display: flex;
      justify-content: space-between;
      gap: 10px;
      font-size: 15px;
      line-height: 1.25;
      margin-bottom: 6px;
    }

    .event-title strong {
      font-weight: 600;
    }

    .event small {
      color: var(--muted);
      white-space: nowrap;
    }

    .event p {
      margin: 0;
      font-size: 14px;
      line-height: 1.38;
      color: var(--ink);
    }

    .legend {
      position: absolute;
      left: 14px;
      bottom: 22px;
      z-index: 500;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: rgba(255, 255, 255, 0.96);
      padding: 10px 12px;
      font-size: 13px;
      color: var(--ink);
      box-shadow: 0 8px 30px rgba(32, 52, 60, 0.12);
    }

    .legend-row {
      display: flex;
      align-items: center;
      gap: 8px;
      margin: 4px 0;
    }

    .dot {
      width: 11px;
      height: 11px;
      border-radius: 50%;
      display: inline-block;
      background: var(--ok);
      border: 1px solid rgba(32, 52, 60, 0.2);
    }

    .dot.warning { background: var(--warn); }
    .dot.alarm { background: var(--alarm); }
    .dot.idle { background: var(--idle); }

    .leaflet-popup-content {
      font-family: Garamond, "EB Garamond", Georgia, serif;
      font-size: 14px;
      line-height: 1.35;
      color: var(--ink);
    }

    @media (max-width: 920px) {
      .app {
        grid-template-columns: 1fr;
        grid-template-rows: 58vh auto;
      }

      #map {
        min-height: 58vh;
      }

      aside {
        border-left: 0;
        border-top: 1px solid var(--line);
      }
    }
  </style>
</head>
<body>
  <main class="app">
    <section id="map" aria-label="Carte live des signaux MQTT"></section>
    <aside>
      <header>
        <h1>Carte live MQTT</h1>
        <p class="subtitle">Flux Mosquitto capturé en base brute SQLite, localisé sur le site 042.</p>
      </header>
      <section class="statusbar">
        <div class="metric"><span class="label">Messages</span><span class="value" id="totalMessages">0</span></div>
        <div class="metric"><span class="label">Machines actives</span><span class="value" id="activeMachines">0</span></div>
        <div class="metric"><span class="label">Alarmes</span><span class="value" id="alarmCount">0</span></div>
        <div class="metric"><span class="label">Broker</span><span class="value" id="brokerName">-</span></div>
      </section>
      <section class="toolbar">
        <button type="button" id="refreshButton">Actualiser</button>
        <button type="button" class="secondary" id="fitButton">Centrer</button>
        <span class="last-refresh" id="lastRefresh">-</span>
      </section>
      <section class="stream" id="eventStream" aria-label="Derniers événements"></section>
    </aside>
  </main>
  <div class="legend">
    <div class="legend-row"><span class="dot"></span><span>Normal</span></div>
    <div class="legend-row"><span class="dot idle"></span><span>Idle</span></div>
    <div class="legend-row"><span class="dot warning"></span><span>Sortie de plage</span></div>
    <div class="legend-row"><span class="dot alarm"></span><span>Alarme</span></div>
  </div>
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <script>
    const map = L.map("map", { zoomControl: true }).setView([45.7046, 4.8878], 17);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 20,
      attribution: "&copy; OpenStreetMap contributors"
    }).addTo(map);

    const latestMarkers = new Map();
    const traceLayer = L.layerGroup().addTo(map);
    let lastData = null;

    function colorFor(event) {
      if (event.status === "alarm") return "#d94b5f";
      if (event.status === "warning") return "#d88f2f";
      if (event.status === "idle") return "#5188c7";
      return "#2ea67a";
    }

    function statusLabel(event) {
      if (event.status === "alarm") return "Alarme";
      if (event.status === "warning") return "Sortie de plage";
      if (event.status === "idle") return "Idle";
      return "Normal";
    }

    function safe(value, fallback = "n/a") {
      return value === null || value === undefined || value === "" ? fallback : value;
    }

    function popupHtml(event) {
      return `
        <strong>${safe(event.machine_id)} - ${safe(event.machine_type)}</strong><br>
        ${safe(event.zone)} / ${safe(event.room_id)}<br>
        Etat : ${safe(event.state)} ${event.alarm_code ? "(" + event.alarm_code + ")" : ""}<br>
        Lot : ${safe(event.batch_id)}<br>
        Température : ${safe(event.temperature_c)}°C<br>
        Humidité : ${safe(event.humidity_pct)}% HR<br>
        Pression : ${safe(event.pressure_bar)} bar<br>
        Vibration : ${safe(event.vibration_mm_s)} mm/s<br>
        Broker : ${safe(event.broker)}<br>
        Reçu : ${safe(event.received_at_utc)}
      `;
    }

    function updateMetrics(data) {
      document.getElementById("totalMessages").textContent = data.total_messages;
      document.getElementById("activeMachines").textContent = data.latest_by_machine.length;
      document.getElementById("alarmCount").textContent = data.alarm_count;
      document.getElementById("brokerName").textContent = data.broker || "-";
      document.getElementById("lastRefresh").textContent = new Date().toLocaleTimeString("fr-FR");
    }

    function updateMap(data) {
      traceLayer.clearLayers();

      data.events.slice(0, 80).forEach((event) => {
        if (!event.latitude || !event.longitude) return;
        L.circleMarker([event.latitude, event.longitude], {
          radius: 4,
          color: colorFor(event),
          fillColor: colorFor(event),
          fillOpacity: 0.22,
          opacity: 0.35,
          weight: 1
        }).addTo(traceLayer).bindPopup(popupHtml(event));
      });

      const seen = new Set();
      data.latest_by_machine.forEach((event) => {
        seen.add(event.machine_id);
        const latlng = [event.latitude, event.longitude];
        const options = {
          radius: event.status === "alarm" ? 13 : 10,
          color: "#ffffff",
          fillColor: colorFor(event),
          fillOpacity: 0.88,
          weight: 3
        };
        const existing = latestMarkers.get(event.machine_id);
        if (existing) {
          existing.setLatLng(latlng);
          existing.setStyle(options);
          existing.setPopupContent(popupHtml(event));
        } else {
          latestMarkers.set(event.machine_id, L.circleMarker(latlng, options).addTo(map).bindPopup(popupHtml(event)));
        }
      });

      for (const [machineId, marker] of latestMarkers.entries()) {
        if (!seen.has(machineId)) {
          marker.remove();
          latestMarkers.delete(machineId);
        }
      }
    }

    function updateStream(data) {
      const stream = document.getElementById("eventStream");
      stream.innerHTML = "";
      data.events.slice(0, 18).forEach((event) => {
        const item = document.createElement("article");
        item.className = `event ${event.status}`;
        item.innerHTML = `
          <div class="event-title">
            <strong>${safe(event.machine_id)} · ${safe(event.state)}</strong>
            <small>${safe(event.received_time_local)}</small>
          </div>
          <p>${safe(event.zone)} - ${safe(event.room_id)}</p>
          <p>Lot ${safe(event.batch_id)} · ${safe(event.temperature_c)}°C · ${safe(event.humidity_pct)}% HR · ${statusLabel(event)}</p>
        `;
        stream.appendChild(item);
      });
    }

    function fitToMachines() {
      const points = Array.from(latestMarkers.values()).map((marker) => marker.getLatLng());
      if (!points.length) return;
      map.fitBounds(L.latLngBounds(points), { padding: [40, 40], maxZoom: 18 });
    }

    async function refresh() {
      const response = await fetch("/api/events?limit=240", { cache: "no-store" });
      const data = await response.json();
      lastData = data;
      updateMetrics(data);
      updateMap(data);
      updateStream(data);
    }

    document.getElementById("refreshButton").addEventListener("click", refresh);
    document.getElementById("fitButton").addEventListener("click", fitToMachines);

    refresh().then(() => setTimeout(fitToMachines, 200));
    setInterval(refresh, 3000);
  </script>
</body>
</html>
"""


def read_payload(payload_json: str | None) -> dict:
    if not payload_json:
        return {}
    try:
        payload = json.loads(payload_json)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def to_float(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def local_time(value: str) -> str:
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return value
    return dt.astimezone().strftime("%H:%M:%S")


def enrich_event(row: sqlite3.Row) -> dict:
    payload = read_payload(row["payload_json"])
    machine_id = payload.get("machine_id") or row["machine_id"]
    location = MACHINE_LOCATIONS.get(machine_id, {})
    latitude = to_float(payload.get("latitude")) or location.get("latitude")
    longitude = to_float(payload.get("longitude")) or location.get("longitude")
    machine_type = payload.get("machine_type")
    state = payload.get("state")
    alarm_code = payload.get("alarm_code")
    temperature = payload.get("temperature_c")

    status = "normal"
    if state == "IDLE":
        status = "idle"
    if machine_type in {"hvac_cold_room", "sensor"} and isinstance(temperature, (int, float)) and not 2 <= temperature <= 8:
        status = "warning"
    if state == "ALARM" or alarm_code:
        status = "alarm"

    return {
        "id": row["id"],
        "received_at_utc": row["received_at_utc"],
        "received_time_local": local_time(row["received_at_utc"]),
        "broker": row["broker"],
        "topic": row["topic"],
        "qos": row["qos"],
        "retained": row["retained"],
        "classification": row["classification"],
        "matched_keywords": row["matched_keywords"],
        "machine_id": machine_id,
        "machine_type": machine_type,
        "supplier": payload.get("supplier") or row["supplier"],
        "site_id": payload.get("site_id"),
        "site_label": payload.get("site_label") or location.get("site_label"),
        "zone": payload.get("zone") or location.get("zone"),
        "room_id": payload.get("room_id") or location.get("room_id"),
        "latitude": latitude,
        "longitude": longitude,
        "batch_id": payload.get("batch_id") or payload.get("lot_id"),
        "state": state,
        "alarm_code": alarm_code,
        "temperature_c": temperature,
        "humidity_pct": payload.get("humidity_pct"),
        "pressure_bar": payload.get("pressure_bar"),
        "vibration_mm_s": payload.get("vibration_mm_s"),
        "motor_current_a": payload.get("motor_current_a"),
        "rpm": payload.get("rpm"),
        "cycle_count": payload.get("cycle_count"),
        "raw_hash": row["raw_hash"],
        "status": status,
    }


def fetch_events(db_path: Path, limit: int) -> dict:
    if not db_path.exists():
        return {
            "server_time_utc": datetime.now(timezone.utc).isoformat(),
            "total_messages": 0,
            "alarm_count": 0,
            "broker": None,
            "events": [],
            "latest_by_machine": [],
        }

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    total = conn.execute("SELECT COUNT(*) FROM raw_mqtt_events").fetchone()[0]
    rows = conn.execute(
        """
        SELECT
            id,
            received_at_utc,
            broker,
            topic,
            qos,
            retained,
            classification,
            matched_keywords,
            machine_id,
            supplier,
            payload_json,
            raw_hash
        FROM raw_mqtt_events
        ORDER BY id DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    conn.close()

    events = [enrich_event(row) for row in rows]
    latest_by_machine = []
    seen = set()
    alarm_count = 0
    broker = None
    for event in events:
        broker = broker or event["broker"]
        if event["status"] == "alarm":
            alarm_count += 1
        machine_id = event.get("machine_id")
        if machine_id and machine_id not in seen:
            latest_by_machine.append(event)
            seen.add(machine_id)

    return {
        "server_time_utc": datetime.now(timezone.utc).isoformat(),
        "total_messages": total,
        "alarm_count": alarm_count,
        "broker": broker,
        "events": events,
        "latest_by_machine": latest_by_machine,
    }


class LiveMapHandler(BaseHTTPRequestHandler):
    db_path: Path = DEFAULT_DB

    def log_message(self, format: str, *args: object) -> None:
        print(f"{self.address_string()} - {format % args}")

    def send_text(self, status: int, body: str, content_type: str) -> None:
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path in {"/", "/index.html"}:
            self.send_text(200, HTML, "text/html")
            return
        if parsed.path == "/api/events":
            query = parse_qs(parsed.query)
            limit = int(query.get("limit", ["240"])[0])
            limit = max(1, min(limit, 1000))
            payload = fetch_events(self.db_path, limit)
            self.send_text(200, json.dumps(payload, ensure_ascii=False), "application/json")
            return
        if parsed.path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return
        self.send_text(404, "Not found", "text/plain")


def main() -> None:
    parser = argparse.ArgumentParser(description="Serveur local pour visualiser les événements MQTT sur une carte.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    args = parser.parse_args()

    LiveMapHandler.db_path = args.db
    server = ThreadingHTTPServer((args.host, args.port), LiveMapHandler)
    print(f"Carte live disponible sur http://{args.host}:{args.port}")
    print(f"Base lue: {args.db}")
    server.serve_forever()


if __name__ == "__main__":
    main()
