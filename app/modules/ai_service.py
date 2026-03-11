"""
OpenAI-powered menu suggestion chat.

The system prompt strictly limits the assistant to menu/food recommendations
for the restaurant. When menu PDFs have been uploaded, the full extracted
menu text is included in the system prompt as context.
"""

import logging

from openai import OpenAI
from sqlalchemy import select

from app import settings
from app.db import async_sessionmaker
from app.models import MenuDocument

logger = logging.getLogger(__name__)

_client = OpenAI(api_key=settings.OPENAI_API_KEY)

BASE_SYSTEM_PROMPT = f"""You are a friendly food recommendation assistant for {settings.RESTAURANT_NAME}.

Your ONLY job is to help customers with:
- Recommendations from our menu
- Describing dishes (ingredients, taste, dietary info)
- Suggesting meal combinations or pairings
- Answering questions about allergens or dietary preferences (vegetarian, vegan, gluten-free, etc.)

Rules you MUST follow:
1. NEVER discuss topics unrelated to the restaurant's menu and food.
2. If a customer asks about anything off-topic (politics, coding, general trivia, etc.),
   politely redirect them: "I'm only here to help with menu recommendations! 😊 What can I suggest for you?"
3. Keep responses concise and friendly — this is a WhatsApp chat.
4. Use emojis where appropriate to keep it warm and inviting.
5. When menu context is provided below, use it to give accurate answers about dishes,
   prices, and ingredients. Base your recommendations on the actual menu data.
6. If the menu context doesn't cover what the customer asks about, let them know
   and suggest they ask staff for specifics.
7. Always stay in character as a restaurant assistant.

Restaurant name: {settings.RESTAURANT_NAME}
"""


async def _load_menu_context() -> str:
    """Load all menu texts from the database."""
    async with async_sessionmaker() as db:
        result = await db.execute(
            select(MenuDocument.filename, MenuDocument.extracted_text).order_by(
                MenuDocument.created_at
            )
        )
        docs = result.all()

    if not docs:
        return ""

    parts = []
    for doc in docs:
        parts.append(f"=== {doc.filename} ===\n{doc.extracted_text}")
    return "\n\n".join(parts)


async def _build_system_prompt() -> str:
    """Build system prompt, including menu text if available."""
    try:
        context = await _load_menu_context()
    except Exception as e:
        logger.warning(f"Failed to load menu context: {e}")
        context = ""

    if not context:
        return BASE_SYSTEM_PROMPT

    return (
        BASE_SYSTEM_PROMPT
        + "\n\n--- RESTAURANT MENU ---\n\n"
        + context
        + "\n\n--- END MENU ---"
    )


async def get_ai_suggestion(
    history: list[dict], user_message: str
) -> tuple[str, list[dict]]:
    """
    Send the user message to OpenAI with the full conversation history.

    Includes the full menu text from uploaded PDFs in the system prompt.

    Args:
        history: List of {"role": "user"|"assistant", "content": "..."} dicts
        user_message: The latest message from the customer

    Returns:
        (reply_text, updated_history)
    """
    system_prompt = await _build_system_prompt()

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_message})

    response = _client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=messages,
        max_tokens=400,
        temperature=0.7,
    )

    reply = response.choices[0].message.content.strip()

    updated_history = history + [
        {"role": "user", "content": user_message},
        {"role": "assistant", "content": reply},
    ]

    # Keep history bounded to last 20 turns to avoid token bloat
    if len(updated_history) > 40:
        updated_history = updated_history[-40:]

    return reply, updated_history
