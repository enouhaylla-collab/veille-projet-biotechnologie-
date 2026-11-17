"""
Veille YouTube – Biotechnologie halieutique & aquaculture.

Recherche les 50 vidéos les plus récentes pour chaque mot-clé via la
YouTube Data API v3, enrichit les résultats (vues, description complète)
et sauvegarde le tout dans veille_biotech.csv.

Prérequis :
    pip install google-api-python-client pandas

Configuration de la clé API (jamais en clair dans le code) :
    PowerShell :  $env:YOUTUBE_API_KEY = "votre_cle"
    Bash       :  export YOUTUBE_API_KEY="votre_cle"
"""

import os
import sys

import pandas as pd
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

MOTS_CLES = [
    "biotechnologie halieutique",
    "aquaculture innovation",
    "micro-algues pêche",
]
MAX_RESULTATS = 50  # maximum autorisé par requête search.list
# Le CSV vit dans docs/ : le site GitHub Pages le lit directement.
FICHIER_SORTIE = os.path.join("docs", "veille_biotech.csv")


def get_youtube_client():
    api_key = os.environ.get("YOUTUBE_API_KEY")
    if not api_key:
        sys.exit(
            "Erreur : la variable d'environnement YOUTUBE_API_KEY n'est pas définie."
        )
    return build("youtube", "v3", developerKey=api_key)


def rechercher_videos(youtube, mot_cle, max_resultats=MAX_RESULTATS):
    """Retourne les IDs des vidéos les plus récentes pour un mot-clé."""
    reponse = (
        youtube.search()
        .list(
            q=mot_cle,
            part="id",
            type="video",
            order="date",
            maxResults=max_resultats,
        )
        .execute()
    )
    return [item["id"]["videoId"] for item in reponse.get("items", [])]


def recuperer_details(youtube, video_ids):
    """Récupère snippet + statistiques par lots de 50 (limite de l'API)."""
    details = []
    for i in range(0, len(video_ids), 50):
        lot = video_ids[i : i + 50]
        reponse = (
            youtube.videos()
            .list(part="snippet,statistics,status", id=",".join(lot))
            .execute()
        )
        details.extend(reponse.get("items", []))
    return details


def main():
    youtube = get_youtube_client()
    lignes = []

    for mot_cle in MOTS_CLES:
        print(f"Recherche : « {mot_cle} »...")
        try:
            ids = rechercher_videos(youtube, mot_cle)
            videos = recuperer_details(youtube, ids)
        except HttpError as e:
            print(f"  Erreur API pour « {mot_cle} » : {e}")
            continue

        for video in videos:
            # On ignore les vidéos dont l'auteur interdit la lecture
            # intégrée : elles renverraient le visiteur vers YouTube.
            if not video.get("status", {}).get("embeddable", False):
                continue
            snippet = video["snippet"]
            stats = video.get("statistics", {})
            lignes.append(
                {
                    "Mot-clé": mot_cle,
                    "Titre": snippet.get("title"),
                    "Chaîne": snippet.get("channelTitle"),
                    "Vues": int(stats.get("viewCount", 0)),
                    "Date": snippet.get("publishedAt"),
                    "URL": f"https://www.youtube.com/watch?v={video['id']}",
                    "Description": snippet.get("description", ""),
                }
            )
        print(f"  {len(videos)} vidéos récupérées.")

    if not lignes:
        print("Aucune donnée récupérée.")
        return

    df = pd.DataFrame(lignes)
    # Une même vidéo peut remonter pour plusieurs mots-clés : on regroupe.
    df = (
        df.groupby("URL", as_index=False)
        .agg({
            "Mot-clé": lambda s: " | ".join(sorted(set(s))),
            "Titre": "first",
            "Chaîne": "first",
            "Vues": "first",
            "Date": "first",
            "Description": "first",
        })
    )
    df = df[["Titre", "Chaîne", "Vues", "Date", "URL", "Description", "Mot-clé"]]

    # Ajout à l'historique : les anciennes vidéos restent sur le site,
    # les doublons gardent les statistiques les plus récentes.
    if os.path.exists(FICHIER_SORTIE):
        ancien = pd.read_csv(FICHIER_SORTIE, encoding="utf-8-sig")
        df = pd.concat([df, ancien], ignore_index=True).drop_duplicates(
            subset="URL", keep="first"
        )
    df["Date"] = pd.to_datetime(df["Date"], utc=True, format="mixed")
    df = df.sort_values("Date", ascending=False)
    df["Date"] = df["Date"].dt.strftime("%Y-%m-%d")

    # utf-8-sig : accents correctement affichés à l'ouverture dans Excel
    df.to_csv(FICHIER_SORTIE, index=False, encoding="utf-8-sig")
    print(f"\n{len(df)} vidéos au total dans {FICHIER_SORTIE}")


if __name__ == "__main__":
    main()
