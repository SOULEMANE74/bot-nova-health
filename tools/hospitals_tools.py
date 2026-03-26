import os
import psycopg2
from dotenv import load_dotenv
from langchain.tools import tool

# Connexion a la db
load_dotenv()

def get_db_connection():
    db_url = os.getenv("DB_URL")
    if not db_url:
        raise ValueError("L'URL de la base de données RENDER_DB_URL est introuvable dans le .env")
    return psycopg2.connect(db_url)

@tool
def find_hospitals(user_lat: float, user_lon: float, service_requis: str, is_specialist: bool = False):
    """
    Cherche les 5 hôpitaux les plus proches avec lits disponibles, sans limite de distance.
    """

    print("[INFO] : Connexion a db")
    conn = get_db_connection()
    cursor = conn.cursor()

    # Requête unique et propre : on calcule la distance, on filtre par service/lits, 
    # on trie par proximité et on limite à 5.
    query = """
        SELECT h.name, h.address, h.phone, 
               (6371 * acos(cos(radians(%s)) * cos(radians(h.latitude)) * cos(radians(h.longitude) - radians(%s)) + 
               sin(radians(%s)) * sin(radians(h.latitude)))) AS distance_reelle,
               h.latitude, 
               h.longitude
        FROM structures h
        WHERE EXISTS (
            SELECT 1 FROM services s 
            WHERE s.structure_id = h.id 
            AND s.name ILIKE %s
            AND s.total_beds >= 2
        )
        ORDER BY distance_reelle ASC 
        LIMIT 5;
    """
    print("[INFO] : Recherche des mots cle")
    def executer_recherche(mot_cle):
        # On passe systématiquement les 4 paramètres requis par la requête ci-dessus
        cursor.execute(query, (user_lat, user_lon, user_lat, f"%{mot_cle}%"))
        return cursor.fetchall()

    print("[INFO] : Fin de la recherche")

    try:
        # 3. On tente d'abord de chercher le service demandé

        print("[INFO] : Recherche du service")
        resultats_recherche = executer_recherche(service_requis)
        
        # 4. GESTION DU REPLI
        if not resultats_recherche:
            resultats_fallback = executer_recherche("général")
            
            if not resultats_fallback:
                return "Aucun médecin généraliste trouvé à proximité."
            
            resultats_finaux = resultats_fallback 
            
        else:
            # Si on a trouvé le spécialiste
            resultats_finaux = resultats_recherche

        # 5. Boucle d'affichage
        resultats_json = []
        print("[INFO] : Sauvegarde dans le JSON file")
        for row in resultats_finaux:
            resultats_json.append({
                "name": row[0],
                "address": row[1],
                "phone": row[2],
                "distance": round(row[3], 2),
                "map_link": f"https://www.google.com/maps/dir/?api=1&origin={user_lat},{user_lon}&destination={row[4]},{row[5]}"
            })
        return resultats_json
    
    except Exception as e:
        return f"[ERROR] Erreur base de données : {e}"
    finally:
        cursor.close()
        conn.close()