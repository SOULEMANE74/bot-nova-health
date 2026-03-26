import os
from typing import TypedDict, Literal
from dotenv import load_dotenv

from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END
from pydantic import BaseModel, Field

from tools.pharma_tools import get_nearly
from tools.hospitals_tools import find_hospitals
from tools.prompts import SYSTEM_PROMPT_RESPONSE

load_dotenv()

import json
from datetime import datetime
import os

def save_for_finetuning(user_message: str, intention: str, mot_cle: str):
    """Sauvegarde l'interaction au format JSONL pour un futur fine-tuning."""
    
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "messages": [
            {"role": "user", "content": user_message},
            {"role": "assistant", "content": f'{{"categorie": "{intention}", "mot_cle": "{mot_cle}"}}'}
        ]
    }
    
    # Chemin vers le fichier de sauvegarde (dans ton dossier data)
    os.makedirs("data", exist_ok=True)
    log_file = "data/finetuning_dataset.jsonl"
    
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

# Definition de l'Etat
class GraphState(TypedDict):
    user_message: str
    user_lat: float
    user_lon: float
    intention: str
    mot_cle: str
    reponse_texte: list

# 2. Définition du format de sortie 
class RouterOutput(BaseModel):
    categorie: Literal["ORIENTATION", "SPECIALISTE", "PHARMACIE", "INCONNU"] = Field(
        description="Classer la demande dans l'une de ces catégories."
    )
    mot_cle: str = Field(
        description="Le service (ex: maternité), la spécialité (ex: cardiologue) ou vide si pharmacie.", 
        default=""
    )

# Initialisation du LLM 
llm = ChatGroq(model="openai/gpt-oss-120b", temperature=0)
# On force le LLM à répondre avec notre structure Pydantic
router_llm = llm.with_structured_output(RouterOutput)

# --- LES NOEUDS DU GRAPHE (NODES) ---

def analyze_intent(state: GraphState):
    """Analyse le message de l'utilisateur et détermine la route à prendre."""
    prompt = f"""Tu es le routeur principal d'un assistant médical au Togo.
    Analyse ce message et extrais l'intention et le mot clé utile.
    
    RÈGLE ABSOLUE POUR LE MOT_CLE :
    Si l'utilisateur cherche un spécialiste, le mot clé DOIT TOUJOURS être le nom du service médical exact (souvent en "ie" ou "logie"), car c'est ce format qui est dans la base de données.
    Exemples stricts : 
    - "pédiatre" ou "enfant" -> "pédiatrie"
    - "cardiologue" -> "cardiologie"
    - "ophtalmo" -> "ophtalmologie"
    - "chirurgien" -> "chirurgie"
    - "gynéco" ou "accoucher" -> "maternité"
    Si le message est une salutation (ex: "Salut", "Bonjour", "Comment ça va ?") ou n'a aucun rapport avec la santé, classe l'intention STRICTEMENT en "INCONNU".
    
    Message : {state["user_message"]}"""
    
    result = router_llm.invoke([SystemMessage(content=prompt)])

    save_for_finetuning(state["user_message"], result.categorie, result.mot_cle)
    
    return {"intention": result.categorie, "mot_cle": result.mot_cle}

def route_to_pharmacy(state: GraphState):
    """Gère la recherche de pharmacies."""
    response = get_nearly.invoke({
        "user_lat": state["user_lat"], 
        "user_lon": state["user_lon"]
    })
    
    return {"reponse_texte": response}

def handle_greeting(state: GraphState):
    """Gère les salutations et la politesse de l'assistant."""
    user_msg = state.get("user_message", "")
    
    prompt = f"L'utilisateur a dit : '{user_msg}'. Réponds très poliment en une ou deux phrases maximum. Dis-lui que tu es l'assistant médical de Togo-SafeFlow et demande-lui comment tu peux l'aider pour sa santé aujourd'hui."
    
    try:
        
        response = llm.invoke([
            SystemMessage(content="Tu es un assistant médical très poli, accueillant et bienveillant pour NOVA HEALTH."),
            HumanMessage(content=prompt)
        ])
        message_accueil = response.content.strip()
    except Exception as e:
        message_accueil = "Bonjour ! Je suis votre assistant médical NOVA HEALTH. Comment puis-je vous aider aujourd'hui ?"

    return {"reponse_texte": [{"message": message_accueil}]}

def route_to_orientation(state: GraphState):
    """Gère l'orientation (rayon 20km)."""
    response = find_hospitals.invoke({
        "user_lat": state["user_lat"], 
        "user_lon": state["user_lon"], 
        "service_requis": state["mot_cle"], 
        "is_specialist": False
    })
    return {"reponse_texte": response}

def route_to_specialist(state: GraphState):
    """Gère la recherche de spécialiste."""
    response = find_hospitals.invoke({
        "user_lat": state["user_lat"], 
        "user_lon": state["user_lon"], 
        "service_requis": state["mot_cle"], 
        "is_specialist": True
    })
    return {"reponse_texte": response}

def generate_final_response(state):
    # On récupère les données brutes
    raw_data = state.get("reponse_texte", [])
    user_msg = state.get("user_message", "")
    
    # SÉCURITÉ VITALE 
    if not isinstance(raw_data, list) or len(raw_data) == 0:
        return {"reponse_texte": raw_data}

    # On prépare la question pour le LLM
    prompt = f"L'utilisateur a dit : '{user_msg}'. Les résultats trouvés sont : {raw_data}. " \
             f"Rédige le message d'introduction pour ces résultats."

    # Appel au LLM (Groq)
    try:
        response = llm.invoke([
            SystemMessage(content=SYSTEM_PROMPT_RESPONSE),
            HumanMessage(content=prompt)
        ])
        generated_message = response.content.strip()
    except Exception as e:
        print(f"[WARNING] Erreur génération empathie : {e}")
        generated_message = "Voici les meilleures options trouvées pour vous."

    # On injecte ce message généré par l'IA dans chaque objet de la liste
    for item in raw_data:
        # On vérifie que item est bien un dictionnaire avant d'ajouter la clé
        if isinstance(item, dict): 
            item["message"] = generated_message

    return {"reponse_texte": raw_data}

# --- LA LOGIQUE DE ROUTAGE CONDITIONNEL (EDGES) ---

def decide_next_node(state: GraphState):
    """Détermine le prochain nœud en fonction de l'intention."""
    if state["intention"] == "PHARMACIE":
        return "pharmacy_node"
    elif state["intention"] == "SPECIALISTE":
        return "specialist_node"
    elif state["intention"] == "ORIENTATION":
        return "orientation_node"
    elif state["intention"] == "INCONNU":
        return "greeting_node"
    else:
        return END 

# --- CONSTRUCTION DU GRAPHE ---

workflow = StateGraph(GraphState)

# 1. Ajout de TOUS les nœuds (y compris l'empathie)
workflow.add_node("router_node", analyze_intent)
workflow.add_node("pharmacy_node", route_to_pharmacy)
workflow.add_node("orientation_node", route_to_orientation)
workflow.add_node("specialist_node", route_to_specialist)
workflow.add_node("empathy_node", generate_final_response)
workflow.add_node("greeting_node", handle_greeting)

# Le point d'entrée
workflow.set_entry_point("router_node")

# Le routage conditionnel (Reste intact)
workflow.add_conditional_edges(
    "router_node",
    decide_next_node,
    {
        "pharmacy_node": "pharmacy_node",
        "specialist_node": "specialist_node",
        "orientation_node": "orientation_node",
        "greeting_node": "greeting_node",
        END: END
    }
)

# 2. TOUS les outils convergent vers le nœud d'empathie au lieu de END
workflow.add_edge("pharmacy_node", "empathy_node")
workflow.add_edge("orientation_node", "empathy_node")
workflow.add_edge("specialist_node", "empathy_node")

# 3. Le nœud d'empathie clôture le graphe
workflow.add_edge("greeting_node", END)
workflow.add_edge("empathy_node", END)

# Compilation du graphe
app = workflow.compile()