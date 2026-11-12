"""
Lightweight query understanding for the MIICiQ knowledge base.

- normalize / token_key: canonical forms used for answer-cache matching
- expand_query: adds domain synonyms/acronyms (DPA, DOLE, IT products) so that
  keyword and hashed-vector retrieval can match different phrasings
- detect_topic: maps a query to a knowledge area (used for retrieval boosting,
  cache labelling and suggested questions)
- contextualize_query: rewrites short follow-ups using the previous user question
"""
import hashlib
import re
from typing import Dict, List, Optional

STOPWORDS = {
    'a', 'an', 'the', 'is', 'are', 'was', 'were', 'in', 'on', 'at', 'by', 'for', 'with', 'about',
    'to', 'from', 'of', 'and', 'or', 'do', 'does', 'did', 'can', 'could', 'should', 'would', 'will',
    'i', 'me', 'my', 'we', 'our', 'you', 'your', 'it', 'its', 'they', 'them', 'be', 'been', 'am',
    'what', 'which', 'who', 'how', 'when', 'where', 'why', 'please', 'tell', 'explain', 'need',
    'want', 'know', 'there', 'this', 'that', 'these', 'those', 'any', 'if', 'as', 'so', 'than',
    'have', 'has', 'had', 'get', 'got', 'much', 'many', 'ba', 'po', 'ang', 'ng', 'sa', 'na',
}

# Acronym / synonym expansion. Key is matched as a whole word in the lower-cased query.
SYNONYMS: Dict[str, str] = {
    'dpa': 'data privacy act ra 10173 npc',
    'npc': 'national privacy commission data privacy',
    'dpo': 'data protection officer',
    'pia': 'privacy impact assessment',
    'pii': 'personal information sensitive personal information',
    'breach': 'personal data breach notification 72 hours npc',
    'consent': 'consent personal information processing data subject',
    'dole': 'department of labor and employment labor code',
    '13th': '13th month pay presidential decree 851',
    'sil': 'service incentive leave',
    'ot': 'overtime pay',
    'holiday': 'holiday pay regular holiday special non-working day',
    'maternity': 'maternity leave expanded maternity leave ra 11210',
    'paternity': 'paternity leave ra 8187',
    'resign': 'resignation notice separation final pay',
    'resignation': 'resignation notice separation final pay',
    'terminate': 'termination just cause authorized cause due process',
    'termination': 'termination just cause authorized cause due process',
    'fired': 'termination just cause due process',
    'retrenchment': 'authorized cause separation pay',
    'sss': 'social security system contribution',
    'philhealth': 'philhealth contribution health insurance',
    'pagibig': 'pag-ibig hdmf contribution',
    'nsd': 'night shift differential',
    'ups': 'uninterruptible power supply battery backup va watts runtime',
    'nas': 'network attached storage',
    'san': 'storage area network',
    'raid': 'raid redundancy disk array storage',
    'poe': 'power over ethernet switch 802.3af 802.3at',
    'vlan': 'virtual lan network switch',
    'ngfw': 'next generation firewall',
    'utm': 'unified threat management firewall',
    'vpn': 'virtual private network remote access firewall',
    'mfp': 'multifunction printer scanner copier',
    'plotter': 'large format printer wide format a0 a1 roll',
    'toner': 'toner cartridge laser printer',
    'rma': 'return merchandise authorization warranty replacement',
    'cal': 'client access license windows server',
    'os': 'operating system license windows',
    'win11': 'windows 11 requirements tpm',
    'sfp': 'sfp sfp+ transceiver fiber switch',
    'ram': 'memory ram ecc dimm',
    'ssd': 'ssd nvme sata storage',
    'warranty': 'warranty support coverage rma',
}

# Topic keyword map. Order matters only for tie-breaks (first max wins).
TOPIC_KEYWORDS: Dict[str, List[str]] = {
    'Data Privacy': [
        'privacy', 'dpa', 'npc', 'dpo', '10173', 'personal data', 'personal information', 'data subject',
        'consent', 'breach', 'pii', 'cctv', 'data sharing', 'sensitive personal', 'national privacy',
    ],
    'Labor Law': [
        'dole', 'labor', 'labour', '13th month', 'overtime', 'holiday pay', 'night shift', 'night differential',
        'service incentive', 'sil', 'maternity', 'paternity', 'solo parent', 'separation pay', 'final pay',
        'termination', 'resign', 'resignation', 'retirement', 'probationary', 'regularization', 'sss',
        'philhealth', 'pag-ibig', 'pagibig', 'minimum wage', 'certificate of employment', 'leave', 'harassment',
        'rest day', 'wage',
    ],
    'IT Products': [
        'server', 'storage', 'nas', 'san', 'raid', 'printer', 'plotter', 'toner', 'ups', 'switch', 'poe', 'vlan',
        'firewall', 'utm', 'vpn', 'router', 'access point', 'wifi', 'windows', 'license', 'licence', 'operating system',
        'laptop', 'desktop', 'monitor', 'ssd', 'ram', 'warranty', 'rma', 'datasheet', 'specs', 'compatib',
        'network', 'cabling', 'rack',
    ],
    'Company Policy': [
        'policy', 'expense', 'travel', 'reimburse', 'remote work', 'code of conduct', 'sales order', 'discount',
        'approval', 'credit check', 'so-', 'quotation', 'password', 'security policy',
    ],
}


def normalize(text: str) -> str:
    """Lower-case, strip punctuation and collapse whitespace."""
    text = re.sub(r"[^\w\s\-+.]", ' ', (text or '').lower())
    text = re.sub(r'(?<!\d)\.(?!\d)', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()


def salient_tokens(text: str) -> List[str]:
    tokens = re.findall(r"[a-z0-9][a-z0-9\-+]*", normalize(text))
    return [t for t in tokens if t not in STOPWORDS and len(t) > 1]


def _stem(tok: str) -> str:
    """Very light stemming so 'reported'/'reports'/'reporting' match."""
    for suffix in ('ing', 'ed', 'es', 's'):
        if tok.endswith(suffix) and len(tok) - len(suffix) >= 4:
            return tok[:-len(suffix)]
    return tok


def token_key(text: str) -> str:
    """Order-insensitive key: 'what is the 13th month pay?' ~ '13th month pay, what is it'."""
    return ' '.join(sorted({_stem(t) for t in salient_tokens(text)}))[:250]


def query_hash(text: str) -> str:
    return hashlib.sha256(normalize(text).encode('utf-8')).hexdigest()


def token_similarity(a_key: str, b_key: str) -> float:
    """Jaccard similarity of two token keys."""
    a, b = set(a_key.split()), set(b_key.split())
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def expand_query(query: str) -> str:
    """Append domain synonyms for acronyms/keywords found in the query (retrieval only)."""
    words = set(re.findall(r"[a-z0-9\-+]+", query.lower()))
    extra = [exp for key, exp in SYNONYMS.items() if key in words]
    # multi-word triggers
    q = query.lower()
    if '13th month' in q:
        extra.append(SYNONYMS['13th'])
    if 'night shift' in q or 'night diff' in q:
        extra.append(SYNONYMS['nsd'])
    if 'data privacy' in q:
        extra.append(SYNONYMS['dpa'])
    return (query + ' ' + ' '.join(extra)).strip() if extra else query


def detect_topic(query: str) -> str:
    q = ' ' + normalize(query) + ' '
    best, best_hits = '', 0
    for topic, kws in TOPIC_KEYWORDS.items():
        hits = sum(1 for kw in kws if kw in q)
        if hits > best_hits:
            best, best_hits = topic, hits
    return best


# Maps a detected topic to Document.category values that deserve a retrieval boost.
TOPIC_TO_CATEGORIES = {
    'Data Privacy': {'Data Privacy', 'IT'},
    'Labor Law': {'Labor Law', 'HR'},
    'IT Products': {'IT Products', 'Product Specs & Compatibility', 'IT'},
    'Company Policy': {'Policy', 'HR', 'Finance', 'Sales Order Workflow'},
}


def contextualize_query(query: str, history: Optional[List[Dict[str, str]]]) -> str:
    """
    For short follow-ups ("what about managers?", "how long?") borrow the previous
    user question so retrieval has enough signal. Used for retrieval only; the LLM
    still sees the original question plus the conversation history.
    """
    if not history or len(salient_tokens(query)) > 3:
        return query
    for h in reversed(history):
        if h.get('sender') == 'user' and h.get('content'):
            prev = h['content'].strip()
            if normalize(prev) != normalize(query):
                return f"{prev} {query}"
            break
    return query
