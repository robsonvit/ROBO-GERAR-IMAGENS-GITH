import os
import sys
import time
import json
import base64
import requests
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE_DIR, '.env'))

TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY') or os.environ.get('GOOGLE_API_KEY')

def send_to_telegram(filepath, caption):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Aviso: TELEGRAM_BOT_TOKEN ou TELEGRAM_CHAT_ID não definidos.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    try:
        with open(filepath, 'rb') as f:
            response = requests.post(
                url,
                files={'photo': f},
                data={'chat_id': TELEGRAM_CHAT_ID, 'caption': caption, 'parse_mode': 'Markdown'},
                timeout=60
            )
            if response.status_code == 200:
                print("✅ Foto enviada com sucesso ao Telegram!")
            else:
                f.seek(0)
                r2 = requests.post(
                    url,
                    files={'photo': f},
                    data={'chat_id': TELEGRAM_CHAT_ID, 'caption': caption},
                    timeout=60
                )
                if r2.status_code == 200:
                    print("✅ Foto enviada com sucesso ao Telegram (modo texto simples)!")
                else:
                    print(f"Aviso ao enviar ao Telegram: {r2.text}")
    except Exception as e:
        print(f"Erro ao enviar para o Telegram: {e}")

def edit_status_message(message_id, text):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID or not message_id:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/editMessageText"
    try:
        requests.post(
            url,
            data={'chat_id': TELEGRAM_CHAT_ID, 'message_id': message_id, 'text': text, 'parse_mode': 'Markdown'},
            timeout=5
        )
    except Exception as e:
        print(f"Erro ao editar status: {e}")

def gerar_imagem_com_api(prompt, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    file_path = os.path.join(output_dir, f"imagen_{int(time.time())}.jpg")

    # 1. Tentativa via google-genai SDK
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=GEMINI_API_KEY)
        
        models_to_try = [
            "imagen-3.0-generate-002",
            "imagen-3.0",
            "gemini-2.5-flash-image",
            "gemini-3.1-flash-image"
        ]
        
        for model_name in models_to_try:
            try:
                print(f"Tentando gerar imagem com modelo: {model_name}...")
                if "imagen" in model_name:
                    result = client.models.generate_images(
                        model=model_name,
                        prompt=prompt,
                        config=types.GenerateImagesConfig(
                            number_of_images=1,
                            aspect_ratio="1:1"
                        )
                    )
                    if result.generated_images:
                        img_bytes = result.generated_images[0].image.image_bytes
                        with open(file_path, "wb") as f:
                            f.write(img_bytes)
                        print(f"✅ Imagem gerada com sucesso via {model_name}!")
                        return file_path
                else:
                    result = client.models.generate_content(
                        model=model_name,
                        contents=[prompt],
                        config=types.GenerateContentConfig(
                            response_mime_type="image/jpeg"
                        )
                    )
                    if result.candidates:
                        for part in result.candidates[0].content.parts:
                            if hasattr(part, 'inline_data') and part.inline_data:
                                img_bytes = part.inline_data.data
                                with open(file_path, "wb") as f:
                                    f.write(img_bytes)
                                print(f"✅ Imagem gerada com sucesso via {model_name}!")
                                return file_path
            except Exception as e_model:
                print(f"Aviso no modelo {model_name}: {e_model}")
                continue

    except Exception as e_sdk:
        print(f"Aviso no SDK google-genai: {e_sdk}. Tentando via chamada REST direta...")

    # 2. Fallback REST para a API do Google AI Studio
    rest_endpoints = [
        f"https://generativelanguage.googleapis.com/v1beta/models/imagen-3.0-generate-002:predict?key={GEMINI_API_KEY}",
        f"https://generativelanguage.googleapis.com/v1beta/models/imagen-3.0:predict?key={GEMINI_API_KEY}"
    ]

    payload = {
        "instances": [{"prompt": prompt}],
        "parameters": {
            "sampleCount": 1,
            "aspectRatio": "1:1",
            "outputMimeType": "image/jpeg"
        }
    }

    for ep in rest_endpoints:
        try:
            resp = requests.post(ep, json=payload, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                predictions = data.get("predictions", [])
                if predictions:
                    b64 = predictions[0].get("bytesBase64Encoded")
                    if b64:
                        with open(file_path, "wb") as f:
                            f.write(base64.b64decode(b64))
                        print("✅ Imagem gerada com sucesso via API REST!")
                        return file_path
        except Exception as e_rest:
            print(f"Aviso no endpoint REST: {e_rest}")

    raise Exception("Não foi possível gerar a imagem através dos modelos da API do Google.")

def main():
    if not GEMINI_API_KEY:
        print("❌ ERRO: GEMINI_API_KEY ou GOOGLE_API_KEY não encontrada no ambiente!")
        msg = (
            "⚠️ *Chave de API não configurada!*\n\n"
            "Configure o segredo `GEMINI_API_KEY` no GitHub Secrets para gerar imagens via API Oficial do Google."
        )
        msg_id = os.environ.get('MESSAGE_ID')
        if msg_id:
            edit_status_message(int(msg_id), msg)
        sys.exit(1)

    prompt = os.environ.get('SINGLE_PROMPT')
    if not prompt or not prompt.strip():
        if len(sys.argv) > 1:
            prompt = " ".join(sys.argv[1:])
        else:
            prompt = "Uma linda paisagem futurista com luzes neon e alta definição"

    msg_id = os.environ.get('MESSAGE_ID')
    status_msg_id = int(msg_id) if msg_id and msg_id.isdigit() else None

    if status_msg_id:
        edit_status_message(
            status_msg_id,
            f"🎨 *Google Imagen 3 (API Oficial)*\n\n`[█████░░░░░] 50%`\n⚡ _Gerando imagem em altíssima velocidade..._"
        )

    output_dir = os.path.join(BASE_DIR, "output")
    start_time = time.time()

    try:
        file_path = gerar_imagem_com_api(prompt, output_dir)
        elapsed = round(time.time() - start_time, 1)

        caption = (
            f"🎨 *Prompt:* {prompt}\n"
            f"✨ *Gerado via Google Imagen 3 (API Oficial)*\n"
            f"⏱️ Tempo: {elapsed}s"
        )
        send_to_telegram(file_path, caption)

        if status_msg_id:
            edit_status_message(
                status_msg_id,
                f"✅ *Imagem concluída e enviada!*\n\n⏱️ Tempo de geração: {elapsed}s\n🚀 *100% na nuvem sem cookies ou login!*"
            )

    except Exception as e:
        print(f"❌ Erro ao gerar imagem: {e}")
        if status_msg_id:
            edit_status_message(status_msg_id, f"❌ *Erro na geração com Google Imagen:* `{e}`")
        sys.exit(1)

if __name__ == "__main__":
    main()
