def menu_suggestion_summary():
    pass

import json

from app import settings
from openai import OpenAI

from app.models import Email
from app.settings import OPENAI_API_KEY

ACTION_FETCH_ORDER = "fetch_order_detail"
ACTION_FETCH_CLIENT = "fetch_client_detail"
ACTION_REFUND_ORDER = "refund_order"

DETERMINE_ACTION_PROMPT = """You are an assistant that analyzes customer support email threads.

Your job is to determine which Shopify actions are relevant and extract the parameters needed to execute them.

Available actions and their required parameters:
- fetch_order_detail: requires "order_id" (extract the order number from the email, digits only e.g. "4821")
- fetch_client_detail: requires "customer_email" (extract the customer email address)
- refund_order: requires "order_id" (same order number as above)

Rules:
- Return ONLY a JSON object — no explanation, no extra text.
- Include only actions that are clearly relevant.
- Extract parameters from the email content as accurately as possible.
- If a required parameter cannot be found, still include the action but set the value to null.
- If no actions are relevant, return an empty actions list.

Response format:
{{
  "actions": [
    {{"type": "fetch_order_detail", "order_id": "4821"}},
    {{"type": "fetch_client_detail", "customer_email": "john@example.com"}},
    {{"type": "refund_order", "order_id": "4821"}}
  ]
}}

Email thread:
{email_thread}
"""

SUMMARIZE_THREAD_PROMPT = """You are a helpful assistant that summarizes customer support email threads.

Write a concise, clear summary of the email thread below. Include:
- The main issue or request from the customer
- Any key details (order numbers, dates, amounts, product names if mentioned)
- The current status or outcome if apparent

Keep the summary to 3-5 sentences.

Email thread:
{email_thread}
"""


class OpenAIClient:
    def __init__(self):
        if not OPENAI_API_KEY:
            raise Exception("OPENAI_API_KEY is not set")
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = "gpt-4o-mini"

    def menu_summary_chat(self, session_id):
        messages = get_messages(session_id)
        prompt = DETERMINE_ACTION_PROMPT.format(email_thread=thread_formatted)

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages
            temperature=0,
            response_format={"type": "json_object"},
        )

        parsed = json.loads(response.choices[0].message.content)
        actions = parsed.get("actions", [])

        valid_types = {ACTION_FETCH_ORDER, ACTION_FETCH_CLIENT, ACTION_REFUND_ORDER}
        return [a for a in actions if a.get("type") in valid_types]

