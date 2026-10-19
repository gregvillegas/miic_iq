import json
import time
import re
from typing import List, Dict, Any, Generator, Tuple
import requests
from django.conf import settings
from assistant.models import SystemConfig


SYSTEM_PROMPT = """You are MIICiQ, the internal AI Knowledge Assistant for our company.
Your mission is to assist employees with inquiries regarding:
1. Company policies (HR, annual/sick leave, expenses, travel, code of conduct, remote work)
2. Sales Order (SO) workflows, approval matrices, and step-by-step standard operating procedures
3. General operational workflows based strictly on internal company documentation.

STRICT GROUNDING RULES:
1. Base your answers solely and strictly on the provided "COMPANY CONTEXT DOCUMENTS" below.
2. If the context does not contain the answer, politely respond: "I could not find specific information regarding this in our current company documentation. Please reach out to your department administrator or HR/Sales operations team."
3. Never invent policies, approval thresholds, phone numbers, or dates that are not in the context.
4. Always provide clear, structured formatting (bullet points, numbered steps for workflows).
5. At the end of each key point or at the bottom of your answer, cite the exact source document and page number in this format:
   [Source: DocumentName, Page X]
"""


class LocalLLMService:
    """
    Service communicating with local Ollama instance (e.g. llama3.1:8b-instruct or mistral:7b-instruct)
    with streaming SSE support and high-fidelity grounded fallback.
    """

    @classmethod
    def get_ollama_base_url(cls) -> str:
        db_val = SystemConfig.get_val('ollama_base_url', '')
        return db_val if db_val else getattr(settings, 'OLLAMA_BASE_URL', 'http://127.0.0.1:11434')

    @classmethod
    def get_ollama_model(cls) -> str:
        db_val = SystemConfig.get_val('ollama_model', '')
        return db_val if db_val else getattr(settings, 'OLLAMA_MODEL', 'llama3.1:8b-instruct')

    @classmethod
    def check_health(cls) -> Dict[str, Any]:
        """
        Tests connection to Ollama server and lists installed models.
        """
        base_url = cls.get_ollama_base_url()
        try:
            resp = requests.get(f"{base_url}/api/tags", timeout=1.5)
            if resp.status_code == 200:
                data = resp.json()
                models = [m.get('name') for m in data.get('models', [])]
                configured_model = cls.get_ollama_model()
                is_model_present = any(configured_model in m for m in models)
                return {
                    'connected': True,
                    'status': 'Online',
                    'base_url': base_url,
                    'configured_model': configured_model,
                    'is_model_present': is_model_present,
                    'available_models': models,
                }
        except Exception as e:
            pass

        return {
            'connected': False,
            'status': 'Offline (Using Local Deterministic RAG Synthesizer)',
            'base_url': base_url,
            'configured_model': cls.get_ollama_model(),
            'is_model_present': False,
            'available_models': [],
            'instructions': 'Run `ollama serve` and `ollama run llama3.1:8b-instruct` for local GPU/CPU model inference.'
        }

    @classmethod
    def build_prompt(cls, query: str, context_chunks: List[Dict[str, Any]], chat_history: List[Dict[str, str]] = None) -> str:
        context_parts = []
        for i, c in enumerate(context_chunks, 1):
            title = c.get('title', 'Document')
            page = c.get('page_number', 1)
            cat = c.get('category', 'Policy')
            dept = c.get('department', 'General')
            content = c.get('content', '').strip()
            context_parts.append(f"--- DOCUMENT {i}: {title} (Page {page}, Category: {cat}, Dept: {dept}) ---\n{content}\n")

        context_str = "\n".join(context_parts) if context_parts else "No relevant documents found."

        history_str = ""
        if chat_history:
            history_lines = []
            for h in chat_history[-4:]:  # last 4 turns
                role = "Employee" if h.get('sender') == 'user' else "MIICiQ"
                history_lines.append(f"{role}: {h.get('content')}")
            history_str = "RECENT CONVERSATION HISTORY:\n" + "\n".join(history_lines) + "\n\n"

        prompt = (
            f"{SYSTEM_PROMPT}\n\n"
            f"{history_str}"
            f"COMPANY CONTEXT DOCUMENTS:\n"
            f"{context_str}\n\n"
            f"EMPLOYEE INQUIRY:\n{query}\n\n"
            f"MIICiQ ANSWER (Grounded strictly in the documents above with citations):"
        )
        return prompt

    @classmethod
    def stream_generate(
        cls,
        query: str,
        context_chunks: List[Dict[str, Any]],
        chat_history: List[Dict[str, str]] = None
    ) -> Generator[Dict[str, Any], None, None]:
        """
        Yields streaming dictionary chunks:
        {"type": "token", "token": "..."}
        {"type": "done", "full_answer": "...", "sources": [...], "latency_ms": 120}
        """
        start_time = time.time()
        base_url = cls.get_ollama_base_url()
        model_name = cls.get_ollama_model()

        # Build citations summary
        sources = []
        seen_sources = set()
        for c in context_chunks:
            s_key = (c.get('title'), c.get('page_number'))
            if s_key not in seen_sources:
                seen_sources.add(s_key)
                sources.append({
                    'title': c.get('title', 'Document'),
                    'page_number': c.get('page_number', 1),
                    'category': c.get('category', 'Policy'),
                    'department': c.get('department', 'General'),
                    'version': c.get('version', 'v1.0'),
                    'score': c.get('score', 0.0),
                    'snippet': c.get('content', '')[:280] + '...' if len(c.get('content', '')) > 280 else c.get('content', ''),
                })

        prompt = cls.build_prompt(query, context_chunks, chat_history)

        # Attempt Ollama streaming call
        ollama_succeeded = False
        full_response = ""

        try:
            resp = requests.post(
                f"{base_url}/api/generate",
                json={
                    "model": model_name,
                    "prompt": prompt,
                    "stream": True,
                    "options": {
                        "temperature": 0.1,  # Low temperature for strict factual grounding
                        "num_predict": 1024,
                    }
                },
                stream=True,
                timeout=5
            )

            if resp.status_code == 200:
                for line in resp.iter_lines():
                    if line:
                        chunk = json.loads(line.decode('utf-8'))
                        token = chunk.get('response', '')
                        full_response += token
                        yield {"type": "token", "token": token}
                        if chunk.get('done', False):
                            ollama_succeeded = True
                            break
        except Exception:
            ollama_succeeded = False

        # If Ollama is offline or call failed, use intelligent local grounded synthesis
        if not ollama_succeeded or not full_response.strip():
            full_response = ""
            synthetic_answer = cls._synthesize_grounded_answer(query, context_chunks)
            # Stream tokens with subtle typing cadence
            words = re.split(r'(\s+)', synthetic_answer)
            for w in words:
                full_response += w
                yield {"type": "token", "token": w}
                time.sleep(0.015)

        latency_ms = int((time.time() - start_time) * 1000)
        yield {
            "type": "done",
            "full_answer": full_response,
            "sources": sources,
            "latency_ms": latency_ms,
            "is_low_confidence": len(context_chunks) == 0 or (context_chunks and context_chunks[0].get('score', 0) < 0.25)
        }

    @classmethod
    def _synthesize_grounded_answer(cls, query: str, context_chunks: List[Dict[str, Any]]) -> str:
        """
        High-fidelity, grounded fallback synthesizer that extracts answers directly
        from context chunks when local Ollama is not actively running.
        """
        if not context_chunks or context_chunks[0].get('score', 0) < 0.2:
            return (
                "I could not locate specific policies or workflow instructions matching your inquiry "
                "in the currently indexed company documents.\n\n"
                "**Recommended Action:**\n"
                "• Check if the relevant document has been uploaded by an administrator in the **Admin Panel**.\n"
                "• For urgent inquiries, please contact your department manager or the HR / Sales Operations desk."
            )

        top_chunk = context_chunks[0]
        title = top_chunk.get('title', 'Company Documentation')
        page = top_chunk.get('page_number', 1)
        dept = top_chunk.get('department', 'General')
        cat = top_chunk.get('category', 'Policy')

        # Check for workflow steps
        content = "\n\n".join([c.get('content', '') for c in context_chunks[:3]])
        lines = [line.strip() for line in content.split('\n') if line.strip()]

        key_points = []
        for line in lines:
            if any(term in line.lower() for term in ['step', 'procedure', 'policy', 'require', 'submit', 'approval', 'leave', 'order', 'workflow', 'must', 'eligible', 'allowance', 'limit']):
                if len(line) > 20 and line not in key_points:
                    key_points.append(line)
                    if len(key_points) >= 6:
                        break

        # If specific points found, structure nicely
        if key_points:
            formatted_points = "\n".join([f"• {p.lstrip('•-* ')}" for p in key_points])
            answer = (
                f"Based on **{title}** (Page {page}, {dept} - {cat}), here are the relevant details:\n\n"
                f"{formatted_points}\n\n"
                f"Please refer directly to the official procedure document for complete compliance guidelines."
            )
        else:
            # Fallback to direct excerpt summary
            excerpt = top_chunk.get('content', '').strip()[:600]
            answer = (
                f"Based on **{title}** (Page {page}, {cat}):\n\n"
                f"{excerpt}...\n\n"
                f"For full requirements, please consult the complete document."
            )

        return answer
