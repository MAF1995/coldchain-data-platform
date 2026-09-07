from pathlib import Path
from textwrap import dedent

import nbformat as nbf


PROJECT_ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK_PATH = PROJECT_ROOT / "notebooks" / "bloc2_qualite_donnees.ipynb"


def markdown(source: str):
    return nbf.v4.new_markdown_cell(dedent(source).strip())


def code(source: str):
    return nbf.v4.new_code_cell(dedent(source).strip())


notebook = nbf.v4.new_notebook()
notebook["metadata"] = {
    "kernelspec": {
        "display_name": "Python 3 (pharma-coldchain)",
        "language": "python",
        "name": "python3",
    },
    "language_info": {"name": "python", "version": "3.10"},
}

notebook["cells"] = [
    markdown(
        """
        # Bloc II - Audit de qualité des données

        ## tl;dr

        Ce notebook vérifie si les événements MQTT actuellement conservés sont
        suffisamment fiables pour construire les analyses statistiques et le
        dashboard du bloc II. Il ne cherche pas encore à démontrer une relation
        métier : il contrôle le grain, la couverture temporelle, les doublons,
        la complétude et la cohérence des règles thermiques.

        **Source contrôlée :** `data/raw/mqtt_raw.db`, table
        `raw_mqtt_events`. Les messages ont été produits dans le cadre de la
        qualification technique du pipeline ; ils ne constituent pas un
        historique industriel longitudinal.
        """
    ),
    markdown(
        """
        ## Context & Methods

        ### Question de qualité

        Le jeu est-il assez complet, homogène et correctement qualifié pour
        calculer un taux de conformité thermique par zone et tester les facteurs
        associés aux excursions ?

        ### Grain attendu

        Une ligne doit représenter un événement reçu d'un équipement, identifié
        par son empreinte `raw_hash`, son horodatage, sa zone et son type de
        mesure. La règle `2-8 °C` ne s'applique qu'aux mesures de stockage ou
        d'expédition explicitement éligibles.
        """
    ),
    code(
        """
        from pathlib import Path
        import json
        import sqlite3

        import matplotlib.pyplot as plt
        import pandas as pd
        import seaborn as sns
        from IPython.display import Markdown, display
        from scipy.stats import fisher_exact

        sns.set_theme(style="whitegrid")
        plt.rcParams["figure.figsize"] = (10, 5)
        plt.rcParams["axes.titleweight"] = "bold"

        project_root = Path.cwd()
        if not (project_root / "data" / "raw" / "mqtt_raw.db").exists():
            project_root = project_root.parent

        database_path = project_root / "data" / "raw" / "mqtt_raw.db"
        screenshot_dir = project_root / "assets" / "screenshots" / "bloc2"
        screenshot_dir.mkdir(parents=True, exist_ok=True)

        assert database_path.exists(), f"Base introuvable : {database_path}"
        database_path
        """
    ),
    markdown("## Data\n\n### 1. Chargement de la base brute"),
    code(
        """
        connection = sqlite3.connect(f"file:{database_path}?mode=ro", uri=True)

        raw_events = pd.read_sql_query(
            '''
            SELECT
                id,
                received_at_utc,
                broker,
                topic,
                qos,
                retained,
                payload_json,
                raw_hash,
                classification,
                machine_id AS envelope_machine_id,
                supplier AS envelope_supplier
            FROM raw_mqtt_events
            ORDER BY id
            ''',
            connection,
        )

        capture_runs = pd.read_sql_query(
            "SELECT * FROM capture_runs ORDER BY id",
            connection,
        )
        connection.close()

        raw_events.shape, capture_runs.shape
        """
    ),
    code(
        """
        def parse_payload(value):
            if value is None:
                return {}
            try:
                return json.loads(value)
            except (TypeError, json.JSONDecodeError):
                return {"_json_parse_error": True}


        payload = pd.json_normalize(raw_events["payload_json"].map(parse_payload))
        payload = payload.add_prefix("event_")
        events = pd.concat(
            [raw_events.drop(columns=["payload_json"]), payload],
            axis=1,
        )

        events["received_at_utc"] = pd.to_datetime(
            events["received_at_utc"], utc=True, errors="coerce"
        )
        events["event_timestamp"] = pd.to_datetime(
            events["event_timestamp"], utc=True, errors="coerce"
        )
        events["ingestion_delay_seconds"] = (
            events["received_at_utc"] - events["event_timestamp"]
        ).dt.total_seconds()

        events.head(3)
        """
    ),
    markdown("### 2. Profil compact du jeu"),
    code(
        """
        required_columns = [
            "raw_hash",
            "received_at_utc",
            "event_timestamp",
            "event_machine_id",
            "event_machine_type",
            "event_zone",
            "event_room_id",
            "event_temperature_c",
            "event_state",
        ]

        profile = pd.DataFrame(
            {
                "indicateur": [
                    "Nombre d'événements",
                    "Nombre de colonnes après normalisation",
                    "Début de couverture",
                    "Fin de couverture",
                    "Empreintes dupliquées",
                    "Messages JSON illisibles",
                    "Valeurs requises manquantes",
                ],
                "valeur": [
                    len(events),
                    len(events.columns),
                    events["received_at_utc"].min(),
                    events["received_at_utc"].max(),
                    int(events["raw_hash"].duplicated(keep=False).sum()),
                    int(events.get("event__json_parse_error", pd.Series(False, index=events.index)).sum()),
                    int(events[required_columns].isna().sum().sum()),
                ],
            }
        )
        profile
        """
    ),
    markdown("## Results\n\n### 3. Couverture temporelle et fraîcheur"),
    code(
        """
        events_by_hour = (
            events.set_index("received_at_utc")
            .resample("h")
            .size()
            .rename("event_count")
            .reset_index()
        )
        events_by_hour = events_by_hour.loc[events_by_hour["event_count"] > 0]

        display(events_by_hour)
        display(capture_runs)

        figure, axis = plt.subplots()
        sns.barplot(
            data=events_by_hour,
            x="received_at_utc",
            y="event_count",
            color="#43C6B6",
            ax=axis,
        )
        axis.set(
            title="Événements reçus par heure active",
            xlabel="Heure UTC",
            ylabel="Nombre d'événements",
        )
        axis.tick_params(axis="x", rotation=25)
        figure.tight_layout()
        figure.savefig(
            screenshot_dir / "01_couverture_temporelle.png",
            dpi=180,
            bbox_inches="tight",
        )
        plt.show()
        """
    ),
    markdown("### 4. Comparabilité des températures"),
    code(
        """
        measurement_rules = pd.DataFrame(
            [
                {
                    "event_machine_type": "hvac_cold_room",
                    "measurement_context": "cold_storage",
                    "threshold_min_c": 2.0,
                    "threshold_max_c": 8.0,
                    "temperature_rule_eligible": True,
                },
                {
                    "event_machine_type": "sensor",
                    "measurement_context": "cold_dispatch",
                    "threshold_min_c": 2.0,
                    "threshold_max_c": 8.0,
                    "temperature_rule_eligible": True,
                },
                {
                    "event_machine_type": "lyophilizer",
                    "measurement_context": "process",
                    "threshold_min_c": None,
                    "threshold_max_c": None,
                    "temperature_rule_eligible": False,
                },
                {
                    "event_machine_type": "filling_line",
                    "measurement_context": "process",
                    "threshold_min_c": None,
                    "threshold_max_c": None,
                    "temperature_rule_eligible": False,
                },
                {
                    "event_machine_type": "autoclave",
                    "measurement_context": "process",
                    "threshold_min_c": None,
                    "threshold_max_c": None,
                    "temperature_rule_eligible": False,
                },
                {
                    "event_machine_type": "compressor",
                    "measurement_context": "utility",
                    "threshold_min_c": None,
                    "threshold_max_c": None,
                    "temperature_rule_eligible": False,
                },
            ]
        )

        qualified = events.merge(
            measurement_rules,
            on="event_machine_type",
            how="left",
            validate="many_to_one",
        )
        qualified["naive_outside_2_8"] = ~qualified["event_temperature_c"].between(2, 8)
        qualified["qualified_excursion"] = (
            qualified["temperature_rule_eligible"].fillna(False)
            & ~qualified["event_temperature_c"].between(
                qualified["threshold_min_c"],
                qualified["threshold_max_c"],
            )
        )

        comparison = pd.DataFrame(
            {
                "calcul": [
                    "Application uniforme de la règle 2-8 °C",
                    "Application aux seules mesures éligibles",
                ],
                "mesures_hors_plage": [
                    int(qualified["naive_outside_2_8"].sum()),
                    int(qualified["qualified_excursion"].sum()),
                ],
                "mesures_éligibles": [
                    len(qualified),
                    int(qualified["temperature_rule_eligible"].fillna(False).sum()),
                ],
            }
        )
        comparison
        """
    ),
    code(
        """
        machine_summary = (
            qualified.groupby(
                ["event_machine_id", "event_machine_type", "measurement_context"],
                dropna=False,
            )
            .agg(
                event_count=("id", "size"),
                temperature_min_c=("event_temperature_c", "min"),
                temperature_median_c=("event_temperature_c", "median"),
                temperature_max_c=("event_temperature_c", "max"),
                first_event=("received_at_utc", "min"),
                last_event=("received_at_utc", "max"),
            )
            .reset_index()
        )
        machine_summary
        """
    ),
    code(
        """
        figure, axis = plt.subplots(figsize=(11, 5))
        sns.boxplot(
            data=qualified,
            x="event_machine_type",
            y="event_temperature_c",
            color="#8FD3F4",
            ax=axis,
        )
        axis.axhspan(2, 8, color="#9EE7D2", alpha=0.35, label="Plage 2-8 °C")
        axis.set(
            title="Des températures non comparables selon le type d'équipement",
            xlabel="Type d'équipement",
            ylabel="Température (°C)",
        )
        axis.tick_params(axis="x", rotation=20)
        axis.legend()
        figure.tight_layout()
        figure.savefig(
            screenshot_dir / "02_temperature_par_equipement.png",
            dpi=180,
            bbox_inches="tight",
        )
        plt.show()
        """
    ),
    markdown("### 5. Régularité des événements et métadonnées de capture"),
    code(
        """
        event_gaps = (
            qualified.sort_values(["event_machine_id", "event_timestamp"])
            .groupby("event_machine_id")["event_timestamp"]
            .diff()
            .dt.total_seconds()
        )
        qualified["gap_seconds"] = event_gaps

        gap_summary = (
            qualified.groupby("event_machine_id")
            .agg(
                event_count=("id", "size"),
                median_gap_seconds=("gap_seconds", "median"),
                max_gap_seconds=("gap_seconds", "max"),
            )
            .reset_index()
        )

        stale_runs = capture_runs[
            capture_runs["ended_at_utc"].isna()
            | capture_runs["status"].str.lower().eq("running")
        ]

        display(gap_summary)
        display(stale_runs)
        """
    ),
    markdown(
        """
        ### 6. Test statistique exploratoire

        Le test porte uniquement sur la fenêtre observée. L'hypothèse nulle
        `H0` suppose que le statut thermique est indépendant du local. L'hypothèse
        alternative `H1` suppose une association entre le local et la présence
        d'une mesure hors plage.

        Le test exact de Fisher est retenu plutôt qu'un test du khi-deux : il n'y
        a que deux écarts et une cellule du tableau de contingence vaut zéro.
        """
    ),
    code(
        """
        eligible = qualified[
            qualified["temperature_rule_eligible"].fillna(False)
        ].copy()
        eligible["statut_thermique"] = eligible["qualified_excursion"].map(
            {False: "Conforme", True: "Hors plage"}
        )

        room_order = ["CF-008", "QF-002"]
        contingency = (
            pd.crosstab(eligible["event_room_id"], eligible["statut_thermique"])
            .reindex(index=room_order, columns=["Conforme", "Hors plage"], fill_value=0)
        )
        display(contingency)

        fisher_table = contingency[["Hors plage", "Conforme"]].to_numpy()
        fisher_result = fisher_exact(fisher_table, alternative="two-sided")
        alpha = 0.05

        room_rates = (
            100
            * contingency["Hors plage"]
            / contingency.sum(axis=1)
        )
        risk_difference_points = float(room_rates["CF-008"] - room_rates["QF-002"])

        fisher_summary = pd.DataFrame(
            {
                "indicateur": [
                    "Taux hors plage CF-008",
                    "Taux hors plage QF-002",
                    "Écart de taux",
                    "Odds ratio exact",
                    "p-value bilatérale",
                    "Seuil alpha",
                ],
                "valeur": [
                    f"{room_rates['CF-008']:.2f} %",
                    f"{room_rates['QF-002']:.2f} %",
                    f"{risk_difference_points:.2f} points",
                    str(fisher_result.statistic),
                    f"{fisher_result.pvalue:.3f}",
                    f"{alpha:.2f}",
                ],
            }
        )
        display(fisher_summary)

        decision = (
            "H0 n'est pas rejetée"
            if fisher_result.pvalue >= alpha
            else "H0 est rejetée"
        )
        display(
            Markdown(
                f'''
                **Décision statistique : {decision}.** La p-value vaut
                **{fisher_result.pvalue:.3f}**, au-dessus du seuil de 5 %. Le
                local `CF-008` présente deux écarts sur 57 mesures, contre zéro
                sur 62 pour `QF-002`, mais cette fenêtre ne permet pas d'établir
                une association statistiquement significative. L'odds ratio
                exact est infini parce qu'une cellule vaut zéro ; il ne constitue
                pas ici une estimation d'effet stable.
                '''
            )
        )

        result_path = project_root / "data" / "processed" / "bloc2_fisher_test.json"
        result_path.parent.mkdir(parents=True, exist_ok=True)
        result_path.write_text(
            json.dumps(
                {
                    "test": "Fisher exact bilatéral",
                    "hypothese_nulle": "Le statut thermique est indépendant du local.",
                    "alpha": alpha,
                    "rooms": room_order,
                    "table_hors_plage_conforme": fisher_table.tolist(),
                    "p_value": float(fisher_result.pvalue),
                    "odds_ratio": (
                        "infinite"
                        if fisher_result.statistic == float("inf")
                        else float(fisher_result.statistic)
                    ),
                    "risk_difference_percentage_points": risk_difference_points,
                    "decision": decision,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        result_path
        """
    ),
    markdown("## Takeaways"),
    code(
        """
        eligible_count = int(qualified["temperature_rule_eligible"].fillna(False).sum())
        eligible_rate = eligible_count / len(qualified) if len(qualified) else 0
        active_hours = len(events_by_hour)
        stale_run_count = len(stale_runs)
        stale_run_label = (
            "capture non clôturée"
            if stale_run_count == 1
            else "captures non clôturées"
        )
        duplicate_count = int(events["raw_hash"].duplicated(keep=False).sum())
        missing_required = int(events[required_columns].isna().sum().sum())

        display(
            Markdown(
                f'''
                - **{len(events)} événements** sont disponibles, concentrés sur
                  **{active_hours} heures actives**, entre le
                  **{events["received_at_utc"].min():%d/%m/%Y %H:%M UTC}** et le
                  **{events["received_at_utc"].max():%d/%m/%Y %H:%M UTC}** :
                  la couverture n'est pas encore longitudinale.
                - **{eligible_count} événements ({eligible_rate:.1%})** relèvent
                  explicitement du stockage ou de l'expédition sous température
                  dirigée.
                - Une règle uniforme `2-8 °C` classe
                  **{int(qualified["naive_outside_2_8"].sum())} mesures** hors
                  plage, alors que les températures de procédé et d'utilité ne
                  sont pas comparables à cette consigne.
                - Les contrôles techniques trouvent **{duplicate_count}
                  empreintes dupliquées** et **{missing_required} valeurs
                  requises manquantes**.
                - Le registre contient **{stale_run_count}
                  {stale_run_label}** dans les métadonnées.

                **Décision :** le jeu est utilisable pour qualifier le pipeline
                et préparer le modèle analytique. Le test exact de Fisher ne
                rejette pas l'indépendance entre le local et le statut thermique
                sur cette fenêtre (**p = {fisher_result.pvalue:.3f}**). Ce résultat
                ne démontre ni l'équivalence des locaux ni l'absence de risque :
                la prochaine collecte doit couvrir plusieurs jours, plusieurs
                zones froides et des variables opérationnelles telles que la
                consigne, l'ouverture de porte et l'état du groupe froid.
                '''
            )
        )
        """
    ),
]

NOTEBOOK_PATH.parent.mkdir(parents=True, exist_ok=True)
nbf.write(notebook, NOTEBOOK_PATH)
print(NOTEBOOK_PATH)
