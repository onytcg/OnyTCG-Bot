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
Sei OnyTCG, un ragazzo giovane e simpatico.
Rispondi SEMPRE in italiano, in modo naturale, breve e diretto.
Rispondi SOLO alla domanda fatta.
Non inventare storie o collegamenti inutili.

REGOLE IMPORTANTI:
- Il sito ufficiale è https://onytcg.it
- Quando ti chiedono il link del sito, dai SEMPRE https://onytcg.it
- Non dire mai che non puoi fornire il link
- Se trovi link utili nelle informazioni, mettili nella risposta
"""

def clean_content(content):
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        texts = []
        for item in content:
            if isinstance(item, dict) and "text" in item:
                texts.append(str(item["text"]))
            else:
                texts.append(str(item))
        return " ".join(texts)
    if isinstance(content, dict):
        return str(content.get("text", content))
    return str(content)

def get_page_content(url: str) -> str:
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        r = requests.get(url, headers=headers, timeout=6)
        if r.status_code != 200:
            return ""
        soup = BeautifulSoup(r.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()
        text = soup.get_text(separator=" ", strip=True)
        return " ".join(text.split())[:2000]
    except:
        return ""

def search_web(query: str) -> str:
    try:
        results = list(DDGS().text(query, region="it-it", max_results=3))
        if not results:
            return ""
        text = ""
        for i, r in enumerate(results, 1):
            title = r.get("title", "")
            body = r.get("body", "")
            href = r.get("href", "")
            text += f"{i}. {title}\n{body}\nLink: {href}\n"
            if href and href.startswith("http"):
                content = get_page_content(href)
                if content:
                    text += f"Contenuto: {content}\n"
            text += "\n"
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
                    if isinstance(item, dict):
                        role = item.get("role", "user")
                        content = clean_content(item.get("content", ""))
                        if role and content:
                            messages.append({"role": role, "content": content})
                    elif isinstance(item, (list, tuple)) and len(item) >= 2:
                        messages.append({"role": "user", "content": clean_content(item[0])})
                        messages.append({"role": "assistant", "content": clean_content(item[1])})
                except:
                    continue

        search_results = ""
        keywords = ["tempo", "meteo", "notizie", "sito", "onytcg", "prezzo", "oggi", "quando", "dove", "link"]
        if any(k in message.lower() for k in keywords):
            search_results = search_web(str(message))

        if search_results:
            user_content = f"""
Domanda: {message}

Info trovate:
{search_results}

Rispondi in modo breve e preciso.
Se chiedono il link di onytcg, dai https://onytcg.it
Se trovi altri link utili, mettili nella risposta.
"""
        else:
            user_content = str(message)

        messages.append({"role": "user", "content": user_content})

        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=messages,
            temperature=0.3,
            max_tokens=300
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
