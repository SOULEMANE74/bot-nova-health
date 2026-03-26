from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from typing import Any
from tools.transcription import transcribe_audio
from fastapi import  File, UploadFile, Form
import os
import shutil
import uvicorn

# On importe  graphe LangGraph depuis  main.py
from main import app as langgraph_app

# Initialisation de l'API
app = FastAPI(
    title="Nova Health API", 
    description="API d'orientation médicale propulsée par l'IA"
)

# --- CONFIGURATION CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def accueil():
    """Route d'accueil simple pour vérifier que l'API tourne."""
    return {
        "nom_projet": "Nova Health API",
        "statut": "En ligne ",
        "message": "Bienvenue ! Le système d'orientation médicale IA est opérationnel.",
        "documentation": "Allez sur /docs pour tester l'API avec Swagger UI."
    }

# --- MODÈLES DE DONNÉES (JSON) ---

# Ce que le frontend doit t'envoyer
class ChatRequest(BaseModel):
    user_message: Any
    user_lat: float
    user_lon: float

# front 
class ChatResponse(BaseModel):
    intention: str
    mot_cle: str
    message:str
    reponse_texte: Any

# --- LA ROUTE DE L'API ---

@app.post("/api/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """
    Reçoit le message et les coordonnées GPS du patient, 
    et renvoie l'orientation médicale formatée en JSON.
    
    """
    try:
        # On prépare les données pour ton routeur LangGraph
        inputs = {
            "user_message": request.user_message,
            "user_lat": request.user_lat,
            "user_lon": request.user_lon
        }
        
        # On fait réfléchir l'IA
        result = langgraph_app.invoke(inputs)
        
        # On renvoie le résultat au format JSON propre
        return ChatResponse(
            intention=result.get("intention", "INCONNU"),
            mot_cle=result.get("mot_cle", ""),
            message=result.get("message", ""),
            reponse_texte=result.get("reponse_texte", "Désolé, une erreur est survenue lors de la recherche.")
        )
        
    except Exception as e:
        # S'il y a un crash, on renvoie une erreur 500 propre au frontend
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/audio", response_model=ChatResponse)
async def audio_endpoint(
    user_lat: float = Form(...),
    user_lon: float = Form(...),
    file: UploadFile = File(...)
):
    temp_file_path = f"temp_{file.filename}"
    
    try:
        # 1. Sauvegarde
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # 2. Transcription
        texte_transcrit = transcribe_audio(temp_file_path) 
        print(f"[VOCAL] Message transcrit : {texte_transcrit}")

        # 3. Appel LangGraph
        print("[INFO] : Lancement du Graph")
        inputs = {
            "user_message": str(texte_transcrit),
            "user_lat": float(user_lat),
            "user_lon": float(user_lon)
        }

        result = langgraph_app.invoke(inputs)
        
        # 4. RETOUR UNIFIÉ 
        return ChatResponse(
            intention=result.get("intention", "INCONNU"),
            mot_cle=result.get("mot_cle", ""),
            message=result.get("message", ""),
            reponse_texte=result.get("reponse_texte", "Désolé, une erreur est survenue lors de la recherche.")
        )

    except Exception as e:
        print(f"Erreur Audio : {e}")
        raise HTTPException(status_code=500, detail=f"Erreur : {str(e)}")
        
    finally:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
