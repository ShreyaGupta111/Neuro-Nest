# backend/chatbot.py  (NEW – using google-genai SDK)

from datetime import datetime
from pymongo import MongoClient
from google import genai
from google.genai import types
import traceback
import logging

# ------------------ LOGGING SETUP ------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("neuronest")

# ------------------ API KEY & CLIENT ------------------

# 👇 Yahan apni asli Gemini API key daalo (AI Studio se "AIzaSy..." wali)
API_KEY = "AIzaSyA5Avm-FFGejf2ufW-eLiqMxyjF0KjOf8c"

try:
    client = genai.Client(api_key=API_KEY)
    logger.info("✅ Google Gen AI client configured.")
except Exception:
    logger.error("❌ Error configuring Google Gen AI client:")
    logger.error(traceback.format_exc())
    client = None

# Konsa model use karna hai (new GenAI models)
MODEL_ID = "gemini-2.0-flash"   # ya "gemini-2.5-flash-lite" agar chaho


# ------------------ MONGODB CONNECTION ------------------
try:
    mongo_client = MongoClient("mongodb://localhost:27017/", serverSelectionTimeoutMS=5000)
    mongo_client.server_info()
    db = mongo_client["neuronest"]
    chat_collection = db["chat_history"]
    logger.info("✅ Connected to MongoDB.")
except Exception:
    logger.error("❌ Error connecting to MongoDB:")
    logger.error(traceback.format_exc())
    chat_collection = None


# ------------------ CHAT LOG FUNCTION ------------------
def log_chat(user_msg, bot_response, user_id=None):
    try:
        if chat_collection is None:
            logger.warning("⚠ MongoDB not connected. Chat not saved.")
            return

        record = {
            "user_id": user_id,
            "user_msg": user_msg,
            "bot_response": bot_response,
            "timestamp": datetime.utcnow(),
        }

        chat_collection.insert_one(record)
        logger.info("✅ Chat saved in DB.")

    except Exception:
        logger.error("❌ Error logging chat:")
        logger.error(traceback.format_exc())


# ------------------ MAIN RESPONSE FUNCTION ------------------
def get_response(user_input, personality="calm therapist", user_id=None):
    """
    Generate a reply using Gemini and log to MongoDB.
    """
    if client is None:
        return "DEBUG ERROR: GenAI client is not configured."

    prompt = f"""
You are a chatbot named NeuroNest.
Your personality is: {personality}
Reply briefly and kindly (2-3 sentences).

User says: {user_input}
"""

    try:
        # New SDK style call
        response = client.models.generate_content(
            model=MODEL_ID,
            contents=prompt,
            config=types.GenerateContentConfig(
                max_output_tokens=256,
                temperature=0.8,
            ),
        )

        bot_response = getattr(response, "text", None) or str(response)

        if not bot_response or not bot_response.strip():
            bot_response = "I couldn't think of a response. Please try again."

        # Log chat in DB
        log_chat(user_input, bot_response, user_id=user_id)

        return bot_response

    except Exception:
        error_text = traceback.format_exc()
        logger.error("❌ GENAI API ERROR:")
        logger.error(error_text)
        # Debug ke liye actual error return kar rahe; baad me user-friendly text rakh sakte ho
        return f"DEBUG ERROR (GenAI):\n{error_text}"


# ------------------ CLI TEST MODE ------------------
if __name__ == "__main__":
    print("🤖 NeuroNest (GenAI SDK) test mode — type 'exit' to quit.\n")
    while True:
        msg = input("You: ")
        if msg.lower() == "exit":
            break
        print("NeuroNest:", get_response(msg))
