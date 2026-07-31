import os
import tempfile
import gradio as gr
import edge_tts
from openai import OpenAI
from ddgs import DDGS
import asyncio

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

client = OpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1"
)

SYSTEM_PROMPT = """
Sei OnyTCG, un ragazzo giovane, simpatico e intelligente.
Lavori per onytcg.it (negozio di carte collezionabili), ma sei soprattutto un amico con cui parlare.

Parla sempre in italiano in modo molto naturale, come se stessi chattando con un amico su WhatsApp.
Usa frasi corte, semplici e spontanee.
Puoi usare espressioni tipo “dai”, “guarda”, “sì”, “tipo”, “insomma”.
Fai domande di tanto in tanto.
Non parlare come un manuale o come un’assistente formale.
Se non sai qualcosa, dillo in modo leggero.
Puoi essere ironico e un po’ spiritoso.
Quando usi informazioni da internet, trasformale in un discorso naturale, non elencare i risultati come un robot.
"""

def search_web(query: str) -> str:
    try:
        results = DDGS().text(query, region="it-it", max_results=4)
        if not results:
            return ""
        text = ""
        for i, r in enumerate(results, 1):
            text += f"{i}. {r.get('title', '')}\n{r.get('body', '')}\n\n"
        return text
    except:
        return ""

def chat(message, history):
    try:
        if not message or not message.strip():
            return "Scrivi pure qualcosa!"
        
        search_results = search_web(message)
        
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        
        if history:
            for human, assistant in history:
                messages.append({"role": "user", "content": str(human)})
                messages.append({"role": "assistant", "content": str(assistant)})
        
        enhanced = f"""
Domanda dell'utente: {message}

Informazioni trovate su internet:
{search_results}

Rispondi usando queste informazioni se sono utili, ma parla in modo naturale.
"""
        messages.append({"role": "user", "content": enhanced})
        
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            temperature=0.85,
            max_tokens=450
        )
        
        reply = response.choices[0].message.content
        return reply
        
    except Exception as e:
        print("Errore:", e)
        return "Scusa, ho avuto un piccolo problema. Puoi ripetere la domanda?"

demo = gr.ChatInterface(
    fn=chat,
    title="OnyTCG 🤖",
    description="Il tuo assistente personale",
    examples=["Ciao!", "Che tempo fa a La Spezia?", "Dimmi qualcosa sulle carte Pokémon"]
)

demo.launch(server_name="0.0.0.0", server_port=7860)
