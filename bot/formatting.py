"""Text formatting helpers for styled Discord embeds."""

from bot.config import SEP


def format_body(text: str) -> str:
    r"""Format user-supplied body text into styled bullet points.

    Syntax
    ------
    - ``\n``        → new bullet line
    - ``\n\n``      → blank gap
    - ``---``       → styled section divider
    - ``##Title``   → styled sub-header
    - ``[label](url)`` → inline hyperlink (kept as-is)
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
            elif stripped and not stripped.startswith("✦"):
                lines.append(f"✦ {stripped}")
            elif stripped:
                lines.append(stripped)
            else:
                if lines and lines[-1] != "":
                    lines.append("")
        if lines:
            formatted_sections.append("\n".join(lines))
    return f"\n\n{SEP}\n\n".join(formatted_sections)
