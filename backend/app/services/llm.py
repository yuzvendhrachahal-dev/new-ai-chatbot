import httpx
from typing import List, Dict, Tuple
from app.core.config import settings
from app.services.knowledge import knowledge_service
from app.services.intent import detect_greeting_intent

ASTROVED_SYSTEM_PROMPT = """You are AstroVed AI, a warm, compassionate, and knowledgeable Vedic Astrology assistant representing AstroVed.
Your goal is to guide seekers regarding Vedic Astrology principles, planetary transits (Gochar), Nakshatras, Dasha cycles, Pooja remedies, Homa, and spiritual gemstone suggestions.
Always speak with reverence and positivity. Encourage spiritual remedies, mantras, and personalized birth chart consultations where appropriate.
If verified reference context is provided, base your answer on it and include the source reference citation.
Never fabricate facts, prices, or booking URLs.
Keep answers concise, insightful, and well-structured."""

HONEST_FALLBACK = (
    "Namaste. Our verified AstroVed knowledge base does not currently contain detailed astrological documentation for this specific query. "
    "According to Vedic principles, every cosmic placement is unique to your exact birth time, date, and coordinate. "
    "Would you like to connect with an AstroVed Astrology Advisor or explore queries about Career, Relationships, Dasha, or Remedial Poojas?"
)

class LLMService:
    @staticmethod
    async def get_response(user_message: str, history: List[Dict[str, str]] = None) -> Tuple[str, bool, List[Dict]]:
        """
        Retrieves approved knowledge from knowledge_service and generates answer.
        Returns: (response_text, is_mock, sources)
        """
        # Guard: Check greeting / gratitude / small talk before RAG retrieval
        greeting = detect_greeting_intent(user_message)
        if greeting:
            return greeting, True, []

        retrieved_docs = knowledge_service.retrieve(user_message, top_k=2)
        api_key = settings.OPENAI_API_KEY.strip()

        # Build citations list
        sources = []
        for doc in retrieved_docs:
            sources.append({
                "title": doc.get("title"),
                "source": doc.get("source"),
                "document_id": doc.get("document_id")
            })

        # If OpenAI API key is NOT configured, use approved retrieved knowledge
        if not api_key:
            if retrieved_docs:
                doc = retrieved_docs[0]
                answer_text = doc["content"]
                
                # Format with source citation matching reference Image 4
                source_links = "\n".join([f"- [{d['title']} | AstroVed.com]({d['source']})" for d in sources])
                full_reply = f"{answer_text}\n\nSource:\n{source_links}"
                return full_reply, True, sources
            else:
                return HONEST_FALLBACK, True, []

        # If OpenAI is configured, call OpenAI with RAG context
        try:
            context_text = "\n\n".join([f"Document: {d['title']}\nContent: {d['content']}\nSource: {d['source']}" for d in retrieved_docs])
            
            system_prompt = ASTROVED_SYSTEM_PROMPT
            if context_text:
                system_prompt += f"\n\nApproved AstroVed Knowledge:\n{context_text}\nPlease incorporate and cite these sources at the end."

            messages = [{"role": "system", "content": system_prompt}]
            if history:
                messages.extend(history)
            messages.append({"role": "user", "content": user_message})

            async with httpx.AsyncClient(timeout=30.0) as client:
                res = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": settings.OPENAI_MODEL,
                        "messages": messages,
                        "temperature": 0.7,
                        "max_tokens": 500
                    }
                )
                if res.status_code == 200:
                    data = res.json()
                    answer = data["choices"][0]["message"]["content"]
                    return answer, False, sources
                else:
                    return f"[AI Provider Notice: Status {res.status_code}].\n" + HONEST_FALLBACK, True, sources
        except Exception:
            if retrieved_docs:
                doc = retrieved_docs[0]
                source_links = "\n".join([f"- [{d['title']} | AstroVed.com]({d['source']})" for d in sources])
                return f"{doc['content']}\n\nSource:\n{source_links}", True, sources
            return HONEST_FALLBACK, True, []

llm_service = LLMService()
