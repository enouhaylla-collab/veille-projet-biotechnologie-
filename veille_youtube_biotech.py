"""
Veille YouTube – Biotechnologie halieutique & aquaculture.

Recherche les vidéos les plus récentes pour chaque mot-clé (français et
anglais, plusieurs pages de résultats) via la YouTube Data API v3, enrichit les résultats (vues, description complète)
et sauvegarde le tout dans veille_biotech.csv.

Prérequis :
    pip install google-api-python-client pandas

Configuration de la clé API (jamais en clair dans le code) :
    PowerShell :  $env:YOUTUBE_API_KEY = "votre_cle"
    Bash       :  export YOUTUBE_API_KEY="votre_cle"
"""

import os
import re
import sys

import pandas as pd
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# (mot-clé, langue de recherche, pages de 50 résultats)
# La langue indique à YouTube quelles vidéos privilégier (relevanceLanguage).
MOTS_CLES = [
    # Français
    ("biotechnologie halieutique", "fr", 2),
    ("aquaculture innovation", "fr", 2),
    ("micro-algues pêche", "fr", 2),
    ("biotechnologie marine", "fr", 2),
    ("micro-algues", "fr", 2),
    ("culture d'algues", "fr", 2),
    ("pisciculture durable", "fr", 2),
    ("économie bleue", "fr", 2),
    ("recherche halieutique", "fr", 2),
    # Anglais
    ("marine biotechnology", "en", 2),
    ("aquaculture technology", "en", 2),
    ("microalgae", "en", 2),
    ("seaweed farming", "en", 2),
    ("cell-cultured seafood", "en", 2),
    ("blue biotechnology", "en", 2),
    ("sustainable aquaculture", "en", 2),
    # Espagnol
    ("biotecnología marina", "es", 1),
    ("acuicultura innovación", "es", 1),
    ("microalgas", "es", 1),
    # Portugais
    ("biotecnologia marinha", "pt", 1),
    ("aquicultura inovação", "pt", 1),
    ("cultivo de algas", "pt", 1),
    # Allemand
    ("Meeresbiotechnologie", "de", 1),
    ("Aquakultur Innovation", "de", 1),
    ("Mikroalgen", "de", 1),
    # Italien
    ("biotecnologie marine", "it", 1),
    ("acquacoltura innovazione", "it", 1),
    ("microalghe", "it", 1),
    # Arabe : biotechnologie marine, aquaculture, micro-algues
    ("التكنولوجيا الحيوية البحرية", "ar", 1),
    ("الاستزراع السمكي", "ar", 1),
    ("الطحالب الدقيقة", "ar", 1),
    # Japonais : biotechnologie marine, aquaculture à terre, micro-algues
    ("海洋バイオテクノロジー", "ja", 1),
    ("陸上養殖", "ja", 1),
    ("微細藻類", "ja", 1),
    # Chinois : biotechnologie marine, technologie aquacole, micro-algues
    ("海洋生物技术", "zh-Hans", 1),
    ("水产养殖技术", "zh-Hans", 1),
    ("微藻", "zh-Hans", 1),
]
MAX_RESULTATS = 50  # maximum autorisé par requête search.list
# Quota : chaque page de recherche coûte 100 unités. Ici 16 x 2 + 21 x 1
# = 53 pages, soit environ 5 300 unités par exécution, sur 10 000 par jour.DUREE_MIN_SECONDES = 60  # écarte les Shorts, peu adaptés au site
# Le CSV vit dans docs/ : le site GitHub Pages le lit directement.
FICHIER_SORTIE = os.path.join("docs", "veille_biotech.csv")


def get_youtube_client():
    api_key = os.environ.get("YOUTUBE_API_KEY")
    if not api_key:
        sys.exit(
            "Erreur : la variable d'environnement YOUTUBE_API_KEY n'est pas définie."
        )
    return build("youtube", "v3", developerKey=api_key)


def rechercher_videos(youtube, mot_cle, langue, pages):
    """Retourne les IDs des vidéos les plus récentes pour un mot-clé."""
    ids, page_token = [], None
    for _ in range(pages):
        reponse = (
            youtube.search()
            .list(
                q=mot_cle,
                part="id",
                type="video",
                order="date",
                relevanceLanguage=langue,
                maxResults=MAX_RESULTATS,
                pageToken=page_token,
            )
            .execute()
        )
        ids += [item["id"]["videoId"] for item in reponse.get("items", [])]
        page_token = reponse.get("nextPageToken")
        if not page_token:
            break
    return ids


def duree_en_secondes(iso):
    """Convertit une durée ISO 8601 (ex. PT1H2M30S) en secondes."""
    m = re.fullmatch(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso or "")
    if not m:
        return 0
    j, h, mn, s = (int(x or 0) for x in m.groups())
    return ((j * 24 + h) * 60 + mn) * 60 + s


def recuperer_details(youtube, video_ids):
    """Récupère snippet + statistiques par lots de 50 (limite de l'API)."""
    details = []
    for i in range(0, len(video_ids), 50):
        lot = video_ids[i : i + 50]
        reponse = (
            youtube.videos()
            .list(part="snippet,statistics,status,contentDetails", id=",".join(lot))
            .execute()
        )
        details.extend(reponse.get("items", []))
    return details


def main():
    youtube = get_youtube_client()
    lignes = []

    for mot_cle, langue, pages in MOTS_CLES:
        print(f"Recherche : « {mot_cle} »...")
        try:
            ids = rechercher_videos(youtube, mot_cle, langue, pages)
            videos = recuperer_details(youtube, ids)
        except HttpError as e:
            print(f"  Erreur API pour « {mot_cle} » : {e}")
            continue

        for video in videos:
            # On ignore les vidéos dont l'auteur interdit la lecture
            # intégrée : elles renverraient le visiteur vers YouTube.
            if not video.get("status", {}).get("embeddable", False):
                continue
            duree = video.get("contentDetails", {}).get("duration")
            if duree_en_secondes(duree) < DUREE_MIN_SECONDES:
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
                    # Langue déclarée par la chaîne (souvent vide : le site
                    # devine alors la langue à partir du titre)
                    "Langue": snippet.get("defaultAudioLanguage")
                    or snippet.get("defaultLanguage", ""),
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
            "Langue": "first",
        })
    )
    df = df[["Titre", "Chaîne", "Vues", "Date", "URL", "Description", "Langue", "Mot-clé"]]

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
