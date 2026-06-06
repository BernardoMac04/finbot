import os
from typing import Dict, List, Optional

from groq import Groq
from dotenv import load_dotenv

load_dotenv()

MODEL_NAME = "llama-3.3-70b-versatile"

SYSTEM_PROMPT = """Você é um analista financeiro especializado em ações brasileiras listadas na B3.
Sua função é analisar dados técnicos e fornecer análises objetivas em português brasileiro.

Diretrizes:
- Seja direto, claro e use terminologia financeira adequada
- Destaque riscos e oportunidades baseados apenas nos dados fornecidos
- Não faça recomendações absolutas de compra ou venda
- Contextualize brevemente com o cenário macro brasileiro quando relevante
- Formate a resposta com seções bem definidas usando markdown"""

_client: Optional[Groq] = None


def _get_client() -> Groq:
    global _client
    if _client is None:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "GROQ_API_KEY não encontrada. Configure o arquivo .env."
            )
        _client = Groq(api_key=api_key)
    return _client


def _format_signals(signals: dict) -> str:
    lines = []
    for indicator, data in signals.items():
        signal = data.get("signal", "neutro").upper()
        reason = data.get("reason", "")
        value = data.get("value")
        value_str = f" ({value})" if value is not None else ""
        lines.append(
            f"- **{indicator.upper().replace('_', ' ')}**{value_str}: {signal} — {reason}"
        )
    return "\n".join(lines)


def analyze(ticker: str, quote: dict, signals: dict) -> str:
    price = quote.get("price")
    change_pct = quote.get("change_pct") or 0.0
    volume = quote.get("volume")
    name = quote.get("name") or ticker

    price_str = f"R$ {float(price):.2f}" if price is not None else "N/D"
    change_str = f"{float(change_pct):+.2f}%"
    volume_str = f"{int(volume):,}" if volume is not None else "N/D"
    signals_text = _format_signals(signals) if signals else "Nenhum sinal disponível."

    prompt = f"""Analise a ação **{ticker}** ({name}) com os dados abaixo:

**Cotação atual:** {price_str} ({change_str} no dia)
**Volume:** {volume_str}

**Sinais técnicos:**
{signals_text}

Forneça:
1. **Resumo Executivo** — situação atual em 2–3 frases
2. **Análise Técnica** — interpretação dos indicadores acima
3. **Pontos de Atenção** — riscos e oportunidades identificados
4. **Perspectiva** — tendência de curto/médio prazo com base nos dados"""

    response = _get_client().chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
    )
    return response.choices[0].message.content


class StockChat:
    """Interactive chat session with persistent history about a specific stock."""

    def __init__(self, ticker: str, context: Optional[dict] = None):
        self.ticker = ticker.upper()
        self.context = context or {}
        self._history: List[dict] = []
        self._msg_count: int = 0
        self._build_initial_history()

    def _build_initial_history(self) -> None:
        quote = self.context.get("quote", {})
        signals = self.context.get("signals", {})
        if not quote and not signals:
            return

        lines = [f"Contexto atual de {self.ticker}:"]
        if quote:
            price = quote.get("price")
            chg = quote.get("change_pct") or 0
            if price is not None:
                lines.append(f"Preço: R$ {float(price):.2f} ({float(chg):+.2f}%)")
        for ind, data in signals.items():
            lines.append(
                f"{ind.replace('_', ' ').title()}: "
                f"{data.get('signal', 'neutro')} — {data.get('reason', '')}"
            )

        ctx_text = "\n".join(lines)
        self._history = [
            {"role": "user", "content": ctx_text},
            {
                "role": "assistant",
                "content": (
                    f"Contexto de {self.ticker} recebido. "
                    "Pode perguntar sobre análise técnica, fundamentalista, comparações ou estratégias."
                ),
            },
        ]

    def chat(self, message: str) -> str:
        self._history.append({"role": "user", "content": message})
        response = _get_client().chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}] + self._history,
        )
        reply = response.choices[0].message.content
        self._history.append({"role": "assistant", "content": reply})
        self._msg_count += 1
        return reply

    def reset(self) -> None:
        self._history = []
        self._msg_count = 0
        self._build_initial_history()

    @property
    def message_count(self) -> int:
        return self._msg_count
