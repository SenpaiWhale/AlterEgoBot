"""Text formatting helpers for styled Discord embeds."""

import unicodedata

from bot.config import SEP


def _starts_with_symbol(text: str) -> bool:
    """Return True if *text* begins with an emoji or Unicode symbol.

    Parameters
    ----------
    text : str
        The string to inspect.

    Returns
    -------
    bool
        True when the first character is in a Unicode *Symbol* category
        (So, Sk, Sm, Sc) — covers virtually all emoji and decorative glyphs.
    """
    if not text:
        return False
    return unicodedata.category(text[0]).startswith("S")


def format_body(text: str) -> str:
    r"""Format user-supplied body text into styled bullet points.

    Syntax
    ------
    - ``\n``            → new bullet line
    - ``\n\n``          → blank gap
    - ``---``           → styled section divider
    - ``##Title``       → styled sub-header
    - ``[label](url)``  → inline hyperlink (kept as-is)
    - Lines starting with an emoji/symbol are kept as-is
    - Other non-empty lines are auto-bulleted with ✦

    Parameters
    ----------
    text : str
        Raw body text from a slash command parameter.

    Returns
    -------
    str
        Formatted string ready for an embed description.
    """
    text = text.replace("\\n", "\n")
    sections = text.split("---")
    formatted_sections = []
    for section in sections:
        lines = []
        for line in section.splitlines():
            stripped = line.strip()
            if stripped.startswith("##"):
                header_text = stripped[2:].strip().upper()
                lines.append(f"【｡✦｡】 # {header_text} 【｡✦｡】")
            elif stripped and _starts_with_symbol(stripped):
                lines.append(stripped)
            elif stripped:
                lines.append(f"✦ {stripped}")
            else:
                if lines and lines[-1] != "":
                    lines.append("")
        if lines:
            formatted_sections.append("\n".join(lines))
    return f"\n\n{SEP}\n\n".join(formatted_sections)
