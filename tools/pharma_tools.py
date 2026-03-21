import requests
import os 
import math
import json
from dotenv import load_dotenv
from pathlib import Path
from langchain.tools import tool

load_dotenv()

# --- CONFIGURATION DES CHEMINS ---
BASE_DIR = Path(__file__).resolve().parent.parent
DB_DIR = BASE_DIR / 'data'
CACHE_FILE_PATH = DB_DIR / 'pharmacies_cache.json'


def fetch_and_save_pharmacies():
    url = os.environ.get('url')
    payload = {
        'access_token': os.environ.get('access_token'),
        'c_identifiant': os.environ.get('c_identifiant'),
        'u_identifiant': os.environ.get('u_identifiant'),
        'latitude': '6.2545014',
        'longitude': '1.1690376',
        'client': '{"fullname": "soulemane bilali","phone": "+22891016567"}'
    }
    
    headers = {'apiKey': os.environ.get('apiKey')}

    try:
        response = requests.post(url, headers=headers, data=payload, timeout=15)
        response.raise_for_status()
        data = response.json()

        filtered_pharmacies = []

        print("[INFO] : Loading pharmacy")

        for phar in data.get('pharmacies', []):
            
            clean_phar = {
                "nom": phar.get("nom"),
                "quartier": phar.get("ville"),
                "contacts": f"{phar.get('contact_1') or ''} / {phar.get('contact_2') or ''}".strip(" / "),
                "latitude": phar.get("latitude"),
                "longitude": phar.get("longitude"),
                "map_link": phar.get('map_link'),
                "adresse": phar.get("adresse")
            }
            filtered_pharmacies.append(clean_phar)

        # Sauvegarde
        os.makedirs(DB_DIR, exist_ok=True)
        with open(CACHE_FILE_PATH, 'w', encoding='utf-8') as f:
            json.dump(filtered_pharmacies, f, ensure_ascii=False, indent=4)
        
        print("[DEBUG] : Sucess update")

    except Exception as e:
        print(f"[ERROR] Update failed: {e}")


########################################  CALCULATE DISTANCE   ######################################################33

import math
def calculat_distance(lat1, lon1, lat2, lon2):
    R = 6371  
    
    dlat = math.radians(float(lat2) - float(lat1))
    dlon = math.radians(float(lon2) - float(lon1))
    
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(float(lat1))) * \
        math.cos(math.radians(float(lat2))) * math.sin(dlon / 2)**2
    
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

############################################# NEARLY PHARMMACY #####################################################################
@tool
def get_nearly(user_lat, user_lon, fichier_json=CACHE_FILE_PATH):
    """ Get nearly pharmacy """
    try:
        print('[INFOS] : fetch and save save pharmacy')
        fetch_and_save_pharmacies()

        with open(fichier_json, 'r', encoding='utf-8') as f:
            pharmacies = json.load(f)
        
        for phar in pharmacies:
            
            if float(phar['latitude']) != 0:
                dist = calculat_distance(user_lat, user_lon, phar['latitude'], phar['longitude'])
                phar['distance_reelle'] = round(dist, 2)
            else:
                phar['distance_reelle'] = float('inf') # Trop loin si pas de GPS

        top_3 = sorted(pharmacies, key=lambda x: x['distance_reelle'])[:3]

        response_txt = ""
        for p in top_3:
             response_txt += f"\n - {p['nom']} \n {p['quartier']} \n {p['adresse']} \n {p['contacts']} \n {p['distance_reelle']} Km \n {p['map_link']} \n"
        return response_txt
    
    except FileNotFoundError:
            return "[ERROR] : JSON files does not exist"
    except Exception as e:
            return f"[ERROR] : {e}"

