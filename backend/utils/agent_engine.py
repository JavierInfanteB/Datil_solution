import os
import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted, GoogleAPICallError
from config import Config

def get_knowledge_base() -> str:
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    file_path = os.path.join(base_dir, "knowledge_base.md")
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as file:
            return file.read()
    return "Datil Solutions internal documentation."

def query_agent(prompt: str, history: list = None) -> str:
    api_key = Config.GEMINI_API_KEY
    if not api_key:
        return "Error: GEMINI_API_KEY is not configured on the server."

    genai.configure(api_key=api_key)
    knowledge_base = get_knowledge_base()

    system_instruction = (
        "You are the official corporate and technical assistant for Datil Solutions. "
        "Answer questions in Spanish, clearly and professionally. "
        "Use exclusively the information provided in the following documentation. "
        "If a question cannot be answered using this context, state that the topic "
        "is under technical definition.\n\n"
        f"Documentation:\n{knowledge_base}"
    )

    try:
        model = genai.GenerativeModel(
            model_name="gemini-3.5-flash-lite",
            system_instruction=system_instruction,
            generation_config={
                "temperature": 0.2,
                "max_output_tokens": 800,
            }
        )

        chat = model.start_chat(history=history or [])
        response = chat.send_message(prompt)
        return response.text

    except ResourceExhausted as e:
        return f"Cuota excedida en Google AI Studio: {str(e)}"
    except GoogleAPICallError as e:
        return f"Error en la comunicación con Google AI Studio: {str(e)}"
    except Exception as e:
        return f"Error inesperado al procesar la consulta: {str(e)}"