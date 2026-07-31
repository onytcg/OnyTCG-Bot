import os
import gradio as gr
from openai import OpenAI
from ddgs import DDGS
import requests
from bs4 import BeautifulSoup

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

client = OpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1"
)

SYSTEM_PROMPT = """
Sei OnyTCG.
Rispondi SEMPRE in italiano, in modo chiaro e diretto.

Hai la capacità di cercare su internet e di leggere il contenuto delle pagine web.
Quando ti vengono forniti i contenuti delle pagine, significa che le hai già aperte e lette.
Non dire mai che non puoi aprire i link.
Usa le informazioni fornite per rispondere.
"""

def get_page_content(url: str) -> str:
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        r = requests.get(url, headers=headers, timeout=12)
        if r.status_code != 200:
            return ""
        
        soup = BeautifulSoup(r.text, "html.parser")
        
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()
        
        text = soup.get_text(separator=" ", strip=True)
        text = " ".join(text.split())
        return text[:3500]
    except Exception as e:
        print(f"Errore pagina {url}:", e)
        return ""

def search_web(query: str) -> str:
    try:
        results = []
        
        # Se parla del sito, cerca direttamente
        if "onytcg" in query.lower():
            results = list(DDGS().text("onytcg.it", region="it-it", max_results=5))
            results += list(DDGS().text("site:onytcg.it", region="it-it", max_results=3))
        else:
            results = list(DDGS().text(query, region="it-it", max_results=5))

        if not results:
            return ""

        text = ""
        seen_urls = set()
        
        for i, r in enumerate(results, 1):
            title = r.get("title", "")
            body = r.get("body", "")
            href = r.get("href", "")
            
            if href in seen_urls:
                continue
            seen_urls.add(href)
            
            text += f"=== PAGINA {i} ===\n"
            text += f"Titolo: {title}\n"
            text += f"Riassunto: {body}\n"
            text += f"URL: {href}\n"
            
            if href and href.startswith("http"):
                content = get_page_content(href)
                if content:
                    text += f"CONTENUTO LETTO:\n{content}\n"
            
            text += "\n"
        
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
Ho cercato e aperto le pagine per te.

Domanda: {message}

Ecco cosa ho trovato e letto:

{search_results}

Rispondi alla domanda usando queste informazioni. Hai già aperto e letto le pagine.
"""
        else:
            user_content = message

        messages.append({"role": "user", "content": user_content})

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            temperature=0.3,
            max_tokens=500
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
