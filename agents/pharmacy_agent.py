from langchain.agents import create_agent
from langchain_groq import ChatGroq
from langchain.tools import tool
from langgraph.checkpoint.memory import InMemorySaver
from langchain.messages import HumanMessage

from dotenv import load_dotenv
from pathlib import Path

import sys
import os

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT_DIR))
load_dotenv()

from tools.pharma_tools import get_nearly
from src.prompts import pharmacy_prompt

def pharmacy_agent():

    api_key = os.environ.get('GROQ_API_KEY')
    llm = ChatGroq(
        model="openai/gpt-oss-120b", 
        api_key=api_key, 
        temperature=0,
    )

    pha_agent = create_agent(
        model = llm,
        tools = [get_nearly],
        system_prompt = pharmacy_prompt,
        checkpointer = InMemorySaver(),
    )
    return pha_agent

#     while True:
#         q = input("\nUrgence : ")
#         config = {"configurable": {"thread_id": "1"}}

#         if q.lower() == 'q': 
#             break
#         q = HumanMessage(content=q)
#         try:
#             result = pha_agent.invoke({"messages": [q]}, config=config)
#             print(result['messages'][-1].content)
#         except Exception as e:
#             print(f"[BUG] l'agent n'a pas demarer !!")
#             print(f"Erreur : {e}")

# if __name__ == '__main__':
#     pharmacy_agent()




