import os

from google import genai
from google.genai import types

from app.services.device_knowledge import search_devices


# ============================================================
# CONFIGURATION
# ============================================================

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

client = (
    genai.Client(api_key=GEMINI_API_KEY)
    if GEMINI_API_KEY
    else None
)

MODEL_NAME = "gemini-2.5-flash"


# ============================================================
# BUILD CONTEXT
# ============================================================

def build_context(results):

    if not results:
        return "No matching devices were found."

    context_parts = []

    for i, device in enumerate(results, start=1):

        metadata = device.get("metadata", {})

        context_parts.append(
            f"Device {i}:\n"
            f"Brand: {metadata.get('brand', '')}\n"
            f"Model: {metadata.get('model', '')}\n"
            f"RAM: {metadata.get('ram', '')} GB\n"
            f"Storage: {metadata.get('storage', '')} GB\n"
            f"Variant: {metadata.get('variant_name', '')}"
        )

    return "\n\n".join(context_parts)


# ============================================================
# GENERATE AI ANSWER
# ============================================================

def generate_rag_answer(
    query: str,
    top_k: int = 5
):

    # --------------------------------------------------------
    # Retrieve relevant devices
    # --------------------------------------------------------

    results = search_devices(
        query=query,
        top_k=top_k
    )

    context = build_context(results)

    # --------------------------------------------------------
    # If Gemini API key is unavailable
    # --------------------------------------------------------

    if not client:

        return {
            "answer": (
                "AI service is not configured. "
                "Here are the matching devices from the catalog."
            ),
            "sources": results
        }

    # --------------------------------------------------------
    # Prompt
    # --------------------------------------------------------

    prompt = (
        "You are the AI assistant for a Device Valuation Platform.\n\n"
        "Answer the user's question using ONLY the device "
        "information provided in the context below.\n\n"
        "Do not invent specifications.\n\n"
        "If the requested information is not present in "
        "the context, clearly say that it is not available "
        "in the current device catalog.\n\n"
        "Keep the answer concise and useful.\n\n"
        f"USER QUESTION:\n{query}\n\n"
        f"DEVICE CATALOG CONTEXT:\n{context}"
    )

    # --------------------------------------------------------
    # Gemini request
    # --------------------------------------------------------

    try:

        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.2,
                max_output_tokens=500,
            ),
        )

        answer = response.text or ""

    except Exception as exc:

        return {
            "answer": (
                "I found relevant devices, but the AI "
                "response service is currently unavailable."
            ),
            "sources": results,
            "error": str(exc)
        }

    return {
        "answer": answer.strip(),
        "sources": results
    }
