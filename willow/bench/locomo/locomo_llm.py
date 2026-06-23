"""Pluggable LLM adapter module for LoCoMo QA benchmark evaluation."""

from __future__ import annotations

from typing import List, Protocol, runtime_checkable

QA_PROMPT_TEMPLATE = """You extract short factual answers from context. Output ONLY the answer — nothing else.

FORMAT RULES (mandatory):
- Output the answer as a bare phrase or word. No sentence. No preamble.
- NEVER start with "Based on", "According to", "The context", or any similar phrase.
- Context lines may include session dates in brackets — use them for "when" questions.
- For dates, prefer the exact date phrase from context (e.g. "7 May 2023", "June 2023").
- If the answer is not in the context, output exactly: not mentioned
- After "not mentioned" write NOTHING. No explanation. No "The context says...".
- For questions asking what someone 'would' likely do, prefer, or feel: make a brief reasoned inference (e.g. "yes", "no", "likely yes") if the context gives relevant clues about their personality, interests, or values. Only use "not mentioned" if the context has no relevant information at all.
- Maximum 15 words. Shorter is better.

EXAMPLES:
Context: - Alice studied biology at university. She graduated in 2019.
Question: What did Alice study?
Answer: biology

Context: - Bob enjoys hiking and cooking.
Question: When did Bob get married?
Answer: not mentioned

Context: - Carol loves classical music and attends the symphony regularly.
Question: Would Carol enjoy a Beethoven concert?
Answer: yes

Context: - David is a committed vegan who cares deeply about animal welfare.
Question: Would David eat at a steakhouse?
Answer: likely no

Context:
{context}

Question: {question}
Answer:"""


def build_qa_prompt(question: str, context: List[str]) -> str:
    """Build QA prompt. Format context as bullet list."""
    bullet_list = "\n".join(f"- {item}" for item in context)
    return QA_PROMPT_TEMPLATE.format(context=bullet_list, question=question)


@runtime_checkable
class LLMAdapter(Protocol):
    async def generate_answer(self, question: str, context: List[str]) -> str:
        ...


class MockAdapter:
    """Returns first context line, or 'not mentioned' if empty."""

    async def generate_answer(self, question: str, context: List[str]) -> str:
        if not context:
            return "not mentioned"
        return context[0]


class ClaudeAdapter:
    """Uses anthropic SDK. Import anthropic lazily in __init__."""

    def __init__(self, model: str = "claude-sonnet-4-6") -> None:
        try:
            import anthropic  # noqa: F401
        except ImportError as e:
            raise ImportError(
                "anthropic package is required for ClaudeAdapter. "
                "Install it with: pip install anthropic"
            ) from e
        self.model = model
        self._anthropic = anthropic

    async def generate_answer(self, question: str, context: List[str]) -> str:
        if not hasattr(self, "_client"):
            self._client = self._anthropic.AsyncAnthropic()
        prompt = build_qa_prompt(question, context)
        message = await self._client.messages.create(
            model=self.model,
            max_tokens=256,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text.strip()


class OllamaAdapter:
    """Uses aiohttp to call Ollama HTTP API. Import aiohttp lazily."""

    def __init__(
        self, model: str = "llama3", base_url: str = "http://localhost:11434"
    ) -> None:
        try:
            import aiohttp  # noqa: F401
        except ImportError as e:
            raise ImportError(
                "aiohttp package is required for OllamaAdapter. "
                "Install it with: pip install aiohttp"
            ) from e
        self.model = model
        self.base_url = base_url.rstrip("/")
        self._aiohttp = aiohttp

    async def generate_answer(self, question: str, context: List[str]) -> str:
        prompt = build_qa_prompt(question, context)
        url = f"{self.base_url}/api/generate"
        payload = {"model": self.model, "prompt": prompt, "stream": False}
        if not hasattr(self, "_session") or self._session.closed:
            self._session = self._aiohttp.ClientSession()
        async with self._session.post(url, json=payload) as resp:
            resp.raise_for_status()
            data = await resp.json()
            return data.get("response", "").strip()


JUDGE_PROMPT_TEMPLATE = """You are grading a question-answering system against a gold answer.
Decide whether the PREDICTED answer is correct given the GOLD answer.

GRADING RULES:
- The predicted answer is CORRECT if it conveys the same factual information as the gold
  answer, even if phrased differently, more verbose, or with extra correct detail.
- Treat equivalent dates, numbers, names, and paraphrases as matches
  (e.g. "7 May 2023" == "May 7th, 2023"; "biology" == "she studied biology").
- The predicted answer is WRONG if it states different facts, contradicts the gold,
  omits the key fact, or says it is "not mentioned" when the gold gives a real answer.
- If the gold answer is "not mentioned" (or empty) and the prediction also declines to
  answer, that is CORRECT.

Output ONLY one word: CORRECT or WRONG. Nothing else.

QUESTION: {question}
GOLD ANSWER: {gold}
PREDICTED ANSWER: {predicted}

Verdict:"""


def build_judge_prompt(question: str, gold: str, predicted: str) -> str:
    """Build the LLM-as-judge grading prompt."""
    return JUDGE_PROMPT_TEMPLATE.format(
        question=question, gold=gold, predicted=predicted
    )


@runtime_checkable
class JudgeAdapter(Protocol):
    async def judge(self, question: str, gold: str, predicted: str) -> bool:
        ...


class ClaudeJudge:
    """LLM-as-judge using the anthropic SDK. Returns True if predicted is correct.

    This is the LoCoMo-standard scorer the field reports (LLM-judge accuracy),
    distinct from token_f1 string overlap.
    """

    def __init__(self, model: str = "claude-sonnet-4-6") -> None:
        try:
            import anthropic  # noqa: F401
        except ImportError as e:
            raise ImportError(
                "anthropic package is required for ClaudeJudge. "
                "Install it with: pip install anthropic"
            ) from e
        self.model = model
        self._anthropic = anthropic

    async def judge(self, question: str, gold: str, predicted: str) -> bool:
        if not hasattr(self, "_client"):
            self._client = self._anthropic.AsyncAnthropic()
        prompt = build_judge_prompt(question, gold, predicted)
        message = await self._client.messages.create(
            model=self.model,
            max_tokens=8,
            messages=[{"role": "user", "content": prompt}],
        )
        verdict = message.content[0].text.strip().upper()
        return verdict.startswith("CORRECT")


class OllamaJudge:
    """Local LLM-as-judge via Ollama HTTP API. No API key, runs offline.

    A weaker grader than a frontier model, but produces an LLM-judge accuracy
    signal (vs token_f1 string overlap) entirely local-first. Use a frontier
    judge (ClaudeJudge) for the publishable competitive number.
    """

    def __init__(
        self, model: str = "llama3.1:8b", base_url: str = "http://localhost:11434"
    ) -> None:
        try:
            import aiohttp  # noqa: F401
        except ImportError as e:
            raise ImportError(
                "aiohttp package is required for OllamaJudge. "
                "Install it with: pip install aiohttp"
            ) from e
        self.model = model
        self.base_url = base_url.rstrip("/")
        self._aiohttp = aiohttp

    async def judge(self, question: str, gold: str, predicted: str) -> bool:
        prompt = build_judge_prompt(question, gold, predicted)
        url = f"{self.base_url}/api/generate"
        payload = {"model": self.model, "prompt": prompt, "stream": False}
        if not hasattr(self, "_session") or self._session.closed:
            self._session = self._aiohttp.ClientSession()
        async with self._session.post(url, json=payload) as resp:
            resp.raise_for_status()
            data = await resp.json()
            verdict = data.get("response", "").strip().upper()
            return verdict.startswith("CORRECT")


def create_judge(judge_name: str = "claude", model: str = "") -> JudgeAdapter:
    """Factory for LLM-as-judge scorers. Supports 'claude', 'ollama'."""
    name = judge_name.lower().strip()
    if name == "claude":
        return ClaudeJudge(model=model) if model else ClaudeJudge()
    if name == "ollama":
        return OllamaJudge(model=model) if model else OllamaJudge()
    raise ValueError(
        f"Unknown judge adapter: {judge_name!r}. Supported: 'claude', 'ollama'."
    )


def create_adapter(llm_name: str, model: str = "") -> LLMAdapter:
    """Factory. Supports 'claude', 'ollama', 'mock'. Raises ValueError for unknown."""
    name = llm_name.lower().strip()
    if name == "mock":
        return MockAdapter()
    if name == "claude":
        if model:
            return ClaudeAdapter(model=model)
        return ClaudeAdapter()
    if name == "ollama":
        if model:
            return OllamaAdapter(model=model)
        return OllamaAdapter()
    raise ValueError(
        f"Unknown LLM adapter: {llm_name!r}. Supported: 'claude', 'ollama', 'mock'."
    )
