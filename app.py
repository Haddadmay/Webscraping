"""
App Streamlit — Recherche Offres Data via API France Travail
Déploiement : Streamlit Cloud (gratuit)
"""

import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import io

# ─────────────────────────────────────────────
#  CONFIG PAGE
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="Offres Data — France Travail",
    page_icon="🔍",
    layout="wide"
)

st.title("🔍 Recherche d'offres — Consultant Data")
st.caption("Données en temps réel via l'API officielle France Travail")

# ─────────────────────────────────────────────
#  AUTHENTIFICATION
# ─────────────────────────────────────────────
@st.cache_data(ttl=1700)  # token valide ~28 min
def get_token(client_id, client_secret):
    url = "https://entreprise.francetravail.fr/connexion/oauth2/access_token"
    data = {
        "grant_type":    "client_credentials",
        "client_id":     client_id,
        "client_secret": client_secret,
        "scope":         "api_offresdemploiv2 o2dsoffre"
    }
    r = requests.post(url, params={"realm": "/partenaire"}, data=data)
    r.raise_for_status()
    return r.json()["access_token"]


# ─────────────────────────────────────────────
#  RÉCUPÉRATION DES OFFRES
# ─────────────────────────────────────────────
@st.cache_data(ttl=300)
def fetch_offres(token, keywords, departement, type_contrat, nb_max):
    url = "https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    all_offres = []
    range_start = 0

    while len(all_offres) < nb_max:
        range_end = min(range_start + 49, nb_max - 1, 149)
        params = {"motsCles": keywords, "range": f"{range_start}-{range_end}"}
        if departement:
            params["departement"] = departement
        if type_contrat:
            params["typeContrat"] = type_contrat

        r = requests.get(url, headers=headers, params=params)
        if r.status_code in (200, 206):
            offres = r.json().get("resultats", [])
            all_offres.extend(offres)
            if len(offres) < 50:
                break
            range_start += 50
        elif r.status_code == 204:
            break
        else:
            st.error(f"Erreur API : {r.status_code}")
            break

    return all_offres


def parse_offres(offres):
    rows = []
    for o in offres:
        lieu = o.get("lieuTravail", {})
        salaire = o.get("salaire", {}).get("libelle", "Non précisé")
        competences = ", ".join([c["libelle"] for c in o.get("competences", [])])
        rows.append({
            "Titre":           o.get("intitule", ""),
            "Entreprise":      o.get("entreprise", {}).get("nom", "N/A"),
            "Localisation":    lieu.get("libelle", ""),
            "Contrat":         o.get("typeContratLibelle", ""),
            "Expérience":      o.get("experienceLibelle", ""),
            "Salaire":         salaire,
            "Date":            o.get("dateCreation", "")[:10] if o.get("dateCreation") else "",
            "Compétences":     competences,
            "Description":     o.get("description", "")[:300] + "..." if len(o.get("description","")) > 300 else o.get("description",""),
            "Lien":            o.get("origineOffre", {}).get("urlOrigine", ""),
        })
    return pd.DataFrame(rows)


# ─────────────────────────────────────────────
#  SIDEBAR — Paramètres
# ─────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Paramètres")

    st.subheader("🔑 Identifiants API")
    st.markdown("[Obtenir vos clés sur francetravail.io](https://francetravail.io)", unsafe_allow_html=True)

    client_id     = st.text_input("Client ID",     type="password", placeholder="Votre client_id")
    client_secret = st.text_input("Client Secret", type="password", placeholder="Votre client_secret")

    st.divider()
    st.subheader("🔍 Recherche")

    keywords = st.text_input("Mots-clés", value="consultant data")

    departements = {
        "Toute la France": "",
        "Paris (75)":      "75",
        "Hauts-de-Seine (92)": "92",
        "Seine-Saint-Denis (93)": "93",
        "Val-de-Marne (94)": "94",
        "Essonne (91)":    "91",
        "Yvelines (78)":   "78",
        "Lyon (69)":       "69",
        "Marseille (13)":  "13",
        "Bordeaux (33)":   "33",
        "Toulouse (31)":   "31",
        "Nantes (44)":     "44",
        "Lille (59)":      "59",
    }
    dept_label   = st.selectbox("Localisation", list(departements.keys()))
    departement  = departements[dept_label]

    contrats = {
        "Tous":      "",
        "CDI":       "CDI",
        "CDD":       "CDD",
        "Intérim":   "MIS",
        "Stage":     "STA",
        "Alternance":"CNA",
    }
    contrat_label = st.selectbox("Type de contrat", list(contrats.keys()))
    type_contrat  = contrats[contrat_label]

    nb_max = st.slider("Nombre d'offres max", 10, 150, 50, step=10)

    search_btn = st.button("🚀 Lancer la recherche", use_container_width=True, type="primary")


# ─────────────────────────────────────────────
#  MAIN — Affichage
# ─────────────────────────────────────────────
if search_btn:
    if not client_id or not client_secret:
        st.warning("⚠️ Renseigne ton Client ID et Client Secret dans le panneau de gauche.")
    else:
        with st.spinner("Connexion à l'API France Travail..."):
            try:
                token = get_token(client_id, client_secret)
            except Exception as e:
                st.error(f"❌ Authentification échouée : {e}")
                st.stop()

        with st.spinner(f"Recherche des offres « {keywords} »..."):
            offres_raw = fetch_offres(token, keywords, departement, type_contrat, nb_max)

        if not offres_raw:
            st.warning("Aucune offre trouvée. Essaie d'autres mots-clés.")
        else:
            df = parse_offres(offres_raw)

            # ── Métriques ──
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("📋 Offres trouvées",   len(df))
            col2.metric("🏢 Entreprises uniques", df["Entreprise"].nunique())
            col3.metric("📍 Villes",              df["Localisation"].nunique())
            col4.metric("📅 Dernière offre",       df["Date"].max() if not df["Date"].empty else "—")

            st.divider()

            # ── Filtres dynamiques ──
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                contrat_options = ["Tous"] + sorted(df["Contrat"].dropna().unique().tolist())
                filtre_contrat  = st.selectbox("Filtrer par contrat", contrat_options)
            with col_f2:
                search_text = st.text_input("🔎 Rechercher dans les résultats", placeholder="ex: dbt, Airflow, CDI...")

            df_filtered = df.copy()
            if filtre_contrat != "Tous":
                df_filtered = df_filtered[df_filtered["Contrat"] == filtre_contrat]
            if search_text:
                mask = df_filtered.apply(lambda row: row.astype(str).str.contains(search_text, case=False).any(), axis=1)
                df_filtered = df_filtered[mask]

            st.caption(f"{len(df_filtered)} offres affichées")

            # ── Tableau ──
            st.dataframe(
                df_filtered[["Titre","Entreprise","Localisation","Contrat","Expérience","Salaire","Date","Compétences"]],
                use_container_width=True,
                height=450,
                column_config={
                    "Titre":       st.column_config.TextColumn("Titre", width="large"),
                    "Entreprise":  st.column_config.TextColumn("Entreprise", width="medium"),
                    "Compétences": st.column_config.TextColumn("Compétences", width="large"),
                    "Date":        st.column_config.DateColumn("Date", format="DD/MM/YYYY"),
                }
            )

            # ── Top compétences ──
            st.subheader("📊 Top compétences demandées")
            all_skills = []
            for skills_str in df_filtered["Compétences"].dropna():
                all_skills.extend([s.strip() for s in skills_str.split(",") if s.strip()])
            if all_skills:
                skill_counts = pd.Series(all_skills).value_counts().head(15)
                st.bar_chart(skill_counts)
            else:
                st.info("Aucune compétence extraite pour ces offres.")

            # ── Export Excel ──
            st.divider()
            st.subheader("⬇️ Exporter les résultats")

            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
                df_filtered.to_excel(writer, index=False, sheet_name="Offres")
                stats = pd.DataFrame({
                    "Info": ["Total offres", "Recherche", "Localisation", "Contrat", "Date extraction"],
                    "Valeur": [len(df_filtered), keywords, dept_label, contrat_label, datetime.now().strftime("%d/%m/%Y %H:%M")]
                })
                stats.to_excel(writer, index=False, sheet_name="Statistiques")

            st.download_button(
                label="📥 Télécharger en Excel",
                data=buffer.getvalue(),
                file_name=f"offres_data_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

else:
    st.info("👈 Configure tes paramètres dans le panneau de gauche, puis clique sur **Lancer la recherche**.")
    st.markdown("""
    ### Comment ça marche ?
    1. **Crée un compte** sur [francetravail.io](https://francetravail.io) (gratuit)
    2. **Active** l'API *Offres d'emploi v2* dans ton espace
    3. **Colle** ton `client_id` et `client_secret` dans le panneau gauche
    4. **Lance** ta recherche et exporte en Excel !
    """)
