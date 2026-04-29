"""LLM explanation service.

Generates a human-readable thesis for each ranked candidate. Uses Anthropic
Claude when ANTHROPIC_API_KEY is set; otherwise falls back to a deterministic
template that draws from the structured score breakdown.

Per spec §8: the LLM does NOT decide the score, it only explains it.
It receives structured data and must NOT invent facts.
"""
from __future__ import annotations

from typing import Optional

from app.core.config import get_settings
from app.core.logging import get_logger
from app.scoring.engine import FinalScore

log = get_logger(__name__)
settings = get_settings()


SYSTEM_PROMPT = """You are a sell-side equity analyst writing a concise short-thesis brief.

You receive a STRUCTURED snapshot of a stock, with technical, fundamental, news,
macro, liquidity and squeeze-risk breakdowns. Each breakdown lists the specific
reasons that contributed to the score.

Rules:
- Do NOT invent any data. If something is missing, say so or skip it.
- Do NOT recommend a position. State the bear thesis as an analytical view only.
- Do NOT use disclaimers — the application adds them automatically.
- Keep it tight: 5-8 sentences total, no headers, no bullet lists.
- Always mention what would invalidate the thesis.
- If squeeze risk is high or extreme, lead with that warning.

Write in the same language the application is configured in (default: Spanish)."""


def _template_explanation(ticker: str, fs: FinalScore) -> str:
    """Deterministic Spanish-language fallback when no LLM key is available."""
    lines = []
    lines.append(f"{ticker}: score bajista {fs.total:.0f}/100, setup '{fs.setup_type}', convicción {fs.conviction}.")

    # Technical
    tech_reasons = ", ".join(fs.technical.reasons[:3]) or "sin señales técnicas claras"
    lines.append(f"Técnico ({fs.technical.score:.0f}): {tech_reasons}.")

    # News
    if fs.news.has_negative_catalyst and fs.news.top_negative_titles:
        lines.append(f"Catalizadores: {fs.news.top_negative_titles[0][:120]}.")
    elif fs.news.has_positive_catalyst:
        lines.append("Aviso: hay noticias positivas recientes que pueden invalidar la tesis.")
    else:
        lines.append("Sin catalizadores recientes destacables.")

    # Fundamental
    fund_reasons = ", ".join(fs.fundamental.reasons[:2])
    if fund_reasons:
        lines.append(f"Fundamental ({fs.fundamental.score:.0f}): {fund_reasons}.")

    # Macro
    if fs.macro.reasons:
        lines.append(f"Macro: {fs.macro.reasons[0][:140]}.")

    # Squeeze warning
    if fs.squeeze.classification in ("high", "extreme"):
        squeeze_reasons = ", ".join(fs.squeeze.reasons[:2])
        lines.append(f"⚠ Riesgo de squeeze {fs.squeeze.classification}: {squeeze_reasons}.")

    # Trade plan
    p = fs.trade_plan
    if p.entry and p.stop and p.target_1:
        lines.append(
            f"Plan: entrada ~{p.entry}, stop {p.stop}, T1 {p.target_1}"
            + (f", T2 {p.target_2}" if p.target_2 else "")
            + (f" (R:R {p.risk_reward})" if p.risk_reward else "")
            + f". Invalidación: {p.invalidation}."
        )

    return " ".join(lines)


def explain_with_claude(ticker: str, name: str, fs: FinalScore) -> str:
    """Call Anthropic API. Returns text or raises on failure."""
    from anthropic import Anthropic
    client = Anthropic(api_key=settings.anthropic_api_key)

    user_payload = {
        "ticker": ticker,
        "name": name,
        "score": fs.to_dict(),
    }

    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=400,
        system=SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": (
                f"Datos estructurados para {ticker} ({name}):\n\n"
                f"{user_payload}\n\n"
                "Escribe la tesis bajista en español siguiendo las reglas del sistema."
            ),
        }],
    )
    parts = []
    for block in msg.content:
        if hasattr(block, "text"):
            parts.append(block.text)
    return "\n".join(parts).strip() or _template_explanation(ticker, fs)


def explain(ticker: str, name: str, fs: FinalScore) -> str:
    """Public entry point. Always returns a string."""
    if settings.has_llm:
        try:
            return explain_with_claude(ticker, name, fs)
        except Exception as e:
            log.warning("LLM explanation failed for %s, using template: %s", ticker, e)
    return _template_explanation(ticker, fs)
