import os
import gradio as gr
from openai import OpenAI
from ddgs import DDGS

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

client = OpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1"
)

SYSTEM_PROMPT = """
Sei OnyTCG, un ragazzo giovane e simpatico.
Rispondi SEMPRE in italiano, in modo breve e naturale.
Rispondi SOLO alla domanda fatta.

Quando ti vengono date informazioni da internet, usale per rispondere.
Non dire mai che non puoi cercare su internet o che non hai accesso in tempo reale.
Se ti vengono fornite informazioni aggiornate, usale come se le conoscessi.
"""

def search_web(query: str) -> str:
    try:
        results = DDGS().text(query, region="it-it", max_results=5)
        if not results:
            return ""
        text = ""
        for r in results:
            text += f"- {r.get('title', '')}: {r.get('body', '')}\n"
        return text
    except:
        return ""

def chat(message, history):
    try:
        if not message or not str(message).strip():
            return "Scrivi pure!"

        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        
        if history:
            for item in history:
                try:
                    if isinstance(item, (list, tuple)) and len(item) >= 2:
                        messages.append({"role": "user", "content": str(item[0])})
                        messages.append({"role": "assistant", "content": str(item[1])})
                    elif isinstance(item, dict):
                        messages.append({"role": item.get("role", "user"), "content": str(item.get("content", ""))})
                except:
                    continue

        # Fai sempre la ricerca
        search_results = search_web(str(message))

        if search_results:
            user_content = f"""
Domanda: {message}

Informazioni aggiornate da internet:
{search_results}

Rispondi alla domanda usando queste informazioni. Non dire che non puoi cercare online.
"""
        else:
            user_content = message

        messages.append({"role": "user", "content": user_content})

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            temperature=0.7,
            max_tokens=350
        )

        return response.choices[0].message.content

    except Exception as e:
        print("Errore:", e)
        return "Scusa, riprova pure."

demo = gr.ChatInterface(
    fn=chat,
    title="OnyTCG 🤖",
    description="Il tuo assistente personale"
)

demo.launch(server_name="0.0.0.0", server_port=7860)
