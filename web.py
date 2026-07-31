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
Non dire mai che non puoi cercare online.
Se le informazioni dicono che un sito esiste, dillo.
"""

def search_web(query: str) -> str:
    try:
        # Cerca sia la query normale sia versioni più precise
        results = []
        
        with DDGS() as ddgs:
            # Prima ricerca normale
            for r in ddgs.text(query, region="it-it", max_results=5):
                results.append(r)
            
            # Se parla di un sito, cerca anche direttamente il dominio
            if "onytcg" in query.lower() or "sito" in query.lower():
                for r in ddgs.text("onytcg.it", region="it-it", max_results=3):
                    results.append(r)
                for r in ddgs.text("site:onytcg.it", region="it-it", max_results=3):
                    results.append(r)

        if not results:
            return ""

        text = ""
        seen = set()
        for r in results:
            title = r.get("title", "")
            body = r.get("body", "")
            href = r.get("href", "")
            key = title + body
            if key not in seen:
                seen.add(key)
                text += f"- {title}\n  {body}\n  Link: {href}\n\n"
        return text
    except Exception as e:
        print("Errore ricerca:", e)
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

        search_results = search_web(str(message))

        if search_results:
            user_content = f"""
Domanda dell'utente: {message}

Risultati della ricerca su internet:
{search_results}

Usa questi risultati per rispondere alla domanda.
"""
        else:
            user_content = message

        messages.append({"role": "user", "content": user_content})

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            temperature=0.6,
            max_tokens=400
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
