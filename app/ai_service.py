"""
OpenAI-powered menu suggestion chat.

The system prompt strictly limits the assistant to menu/food recommendations
for the restaurant. Off-topic questions are politely declined.
"""

from openai import OpenAI

from app import settings

_client = OpenAI(api_key=settings.OPENAI_API_KEY)

SYSTEM_PROMPT = f"""You are a friendly food recommendation assistant for {settings.RESTAURANT_NAME}.

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
5. If you don't know the exact menu details, suggest the customer ask staff for specifics,
   but still try to help based on dish categories (pasta, pizza, starters, desserts, etc.).
6. Always stay in character as a restaurant assistant.

Restaurant name: {settings.RESTAURANT_NAME}
"""


def get_ai_suggestion(history: list[dict], user_message: str) -> tuple[str, list[dict]]:
    """
    Send the user message to OpenAI with the full conversation history.
    
    Args:
        history: List of {"role": "user"|"assistant", "content": "..."} dicts
        user_message: The latest message from the customer

    Returns:
        (reply_text, updated_history)
    """
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
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
        {"role": "user",      "content": user_message},
        {"role": "assistant", "content": reply},
    ]

    # Keep history bounded to last 20 turns to avoid token bloat
    if len(updated_history) > 40:
        updated_history = updated_history[-40:]

    return reply, updated_history
