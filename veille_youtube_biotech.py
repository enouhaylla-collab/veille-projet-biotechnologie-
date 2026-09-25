import os
import pandas as pd
from googleapiclient.discovery import build

def extraire_donnees_youtube():
    # 1. Récupération de la clé depuis l'environnement (Aucun fichier .env nécessaire)
    api_key = os.environ.get("YOUTUBE_API_KEY")
    
    if not api_key:
        raise ValueError("Erreur : La clé API YOUTUBE_API_KEY est introuvable.")

    # 2. Initialisation de l'API YouTube
    youtube = build("youtube", "v3", developerKey=api_key)
    
    mots_cles = "biotechnologie halieutique OR aquaculture innovation OR micro-algues pêche"
    donnees_videos = []

    print("Lancement de la recherche YouTube...")

    # 3. Lancement de la requête
    request = youtube.search().list(
        q=mots_cles,
        part="snippet",
        type="video",
        maxResults=50
    )
    response = request.execute()

    # 4. Extraction des métadonnées pour chaque vidéo
    for item in response.get("items", []):
        video_id = item["id"]["videoId"]
        titre = item["snippet"]["title"]
        chaine = item["snippet"]["channelTitle"]
        date_pub = item["snippet"]["publishedAt"]
        description = item["snippet"]["description"]
        url = f"https://www.youtube.com/watch?v={video_id}"

        # Optionnel : Faire une 2ème requête pour obtenir le nombre de vues
        try:
            video_request = youtube.videos().list(
                part="statistics",
                id=video_id
            )
            video_response = video_request.execute()
            vues = video_response["items"][0]["statistics"].get("viewCount", 0)
        except Exception as e:
            vues = 0
            print(f"Impossible de récupérer les vues pour {video_id}: {e}")

        donnees_videos.append({
            "Titre": titre,
            "Chaîne": chaine,
            "Vues": vues,
            "Date": date_pub[:10], # On garde juste AAAA-MM-JJ
            "URL": url,
            "Description": description
        })

    # 5. Sauvegarde dans un fichier CSV (grâce à Pandas)
    df = pd.DataFrame(donnees_videos)
    df.to_csv("veille_biotech.csv", index=False, encoding="utf-8-sig")
    print(f"Succès ! {len(donnees_videos)} vidéos ont été extraites dans 'veille_biotech.csv'.")

if __name__ == "__main__":
    extraire_donnees_youtube()
