"""Inline citation tag: single source of truth for both the system-prompt
instructions and the streaming parser, so they can never drift apart.

Replaces the old ``cite(url, title, quote)`` tool — that required the model
to coordinate two separate actions (write a ``[n]`` marker, then remember to
call a tool in the same order) and was unreliable in practice (skipped or
out-of-order calls, worse the more tool calls happened earlier in the turn).
A single inline tag is one atomic write instead, so there's nothing to
coordinate or forget:

    <cite url="https://example.com/page" title="Example">exact quote</cite>

``CitationStreamFilter`` consumes the model's raw token stream and:
- buffers a span the instant it sees the literal 5-char prefix ``<cite``
  (not bare ``<`` — a lone ``<`` in prose, e.g. "P/E < 15", must flush
  immediately, not hang waiting for a tag that isn't coming)
- on a complete ``<cite ...>...</cite>`` span, emits a numbered ``[n]``
  marker in its place and a parsed ``{"url", "title", "quote"}`` record
- on a malformed tag (missing ``url``, e.g.) drops it silently rather than
  leaking raw markup into the visible answer (fail closed)
- on end-of-stream with an unterminated ``<cite`` still buffered (model cut
  off mid-tag), flushes the raw buffered text as-is via ``flush()`` — losing
  data silently is worse than an ugly leftover fragment
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

TAG = "cite"
_OPEN_PREFIX = f"<{TAG}"  # exact-match trigger for buffering; len() used below
_CLOSE_TAG = f"</{TAG}>"

_OPEN_TAG_RE = re.compile(rf"<{TAG}\s*([^>]*)>", re.IGNORECASE)
_ATTR_RE = re.compile(r'(\w+)\s*=\s*"([^"]*)"')

# Attribute order is intentionally not fixed here (parsed as a dict below) —
# models sometimes emit title before url or vice versa; both work.
PROMPT_INSTRUCTIONS = (
    "Citing sources: for ANY claim sourced from a tool result (web_search, "
    "sharepoint_*, or aivy_search_stock — never your own general knowledge), "
    "write the claim as normal visible text, then append a citation tag inline immediately "
    "after it:\n"
    f'{_OPEN_PREFIX} url="SOURCE_URL" title="SHORT_SOURCE_NAME">exact verbatim '
    f"quote from the source{_CLOSE_TAG}\n"
    "Example: FPT's price is "
    f'{_OPEN_PREFIX} url="https://fireant.vn/ma-chung-khoan/FPT" title="FireAnt">'
    f"67.100 đồng{_CLOSE_TAG}.\n"
    "Write the tag exactly like this, inline, right after the claim it supports — "
    "it is replaced by a numbered marker automatically. NEVER put the tag on its "
    "own line or in its own paragraph (with a blank line before/after it) — that "
    "renders as an ugly standalone block. It must sit in the same sentence, "
    "directly after the words it supports, with no line break in between. Keep "
    "the claim OUTSIDE the tag; the text inside the tag is only the supporting "
    "verbatim quote. NEVER make a bullet or sentence consist only of a cite tag. "
    "the quote short and verbatim (not paraphrased). For sharepoint_* results, "
    "the citation url and title MUST be the labeled SOURCE URL and SOURCE TITLE "
    "from the sharepoint_read header (or the matching SharePoint search result); "
    "never substitute a webpage URL embedded inside the document content. "
    "Never print a URL or a "
    "References/Sources list yourself — the tag is the only place source info goes."
)


def _parse_tag(full_tag: str) -> dict[str, str] | None:
    """Parse one complete ``<cite ...>...</cite>`` span. ``None`` if
    malformed or missing the required ``url`` attribute."""
    if not full_tag.lower().endswith(_CLOSE_TAG):
        return None
    open_match = _OPEN_TAG_RE.match(full_tag)
    if not open_match:
        return None
    attrs = dict(_ATTR_RE.findall(open_match.group(1)))
    url = attrs.get("url", "").strip()
    if not url:
        return None
    quote = full_tag[open_match.end():-len(_CLOSE_TAG)].strip()
    return {"url": url, "title": attrs.get("title", "").strip(), "quote": quote}


class CitationStreamFilter:
    """Incremental ``<cite>`` extractor for a token-by-token text stream.

    One instance per answer segment (a fresh one whenever the model starts a
    new text-generation phase, e.g. after a tool call — see
    ``session.py``'s reset-on-tool_call) — state does not need to survive
    past that point since a stray split tag across segments isn't a
    realistic case (tags are short and generated in one continuous phase).
    """

    def __init__(self) -> None:
        self._buffer = ""
        self._in_tag = False
        self._count = 0
        self._visible_tail = ""

    def _is_bare_citation_position(self, pending_output: str) -> bool:
        """Whether a cite tag is the only content at this line position."""
        current_line = (self._visible_tail + pending_output).rsplit("\n", 1)[-1].strip()
        return current_line in {"", "*", "-", "+"} or bool(
            re.fullmatch(r"\d+[.)]", current_line)
        )

    def feed(self, text: str) -> tuple[str, list[dict[str, str]]]:
        """Process one chunk of raw model output.

        Returns ``(safe_text, citations)`` — ``safe_text`` is display-ready
        (never contains a partial or complete raw ``<cite>`` span — completed
        tags are already replaced by their ``[n]`` marker); ``citations`` is
        the 0+ records completed in this chunk, in order.
        """
        self._buffer += text
        out: list[str] = []
        citations: list[dict[str, str]] = []

        while True:
            if not self._in_tag:
                idx = self._buffer.find("<")
                if idx == -1:
                    out.append(self._buffer)
                    self._buffer = ""
                    break
                out.append(self._buffer[:idx])
                self._buffer = self._buffer[idx:]
                if len(self._buffer) < len(_OPEN_PREFIX):
                    break  # not enough chars yet to confirm/deny — wait for more
                if self._buffer[: len(_OPEN_PREFIX)].lower() != _OPEN_PREFIX:
                    out.append(self._buffer[0])  # false alarm — just a literal '<'
                    self._buffer = self._buffer[1:]
                    continue
                logger.debug("citation: <cite tag start detected, buffering")
                self._in_tag = True
                continue
            else:
                lower = self._buffer.lower()
                close_idx = lower.find(_CLOSE_TAG)
                if close_idx == -1:
                    break  # tag not complete yet — keep buffering
                end = close_idx + len(_CLOSE_TAG)
                full_tag = self._buffer[:end]
                self._buffer = self._buffer[end:]
                self._in_tag = False
                parsed = _parse_tag(full_tag)
                if parsed is not None:
                    self._count += 1
                    citations.append(parsed)
                    # Defensive recovery for models that put the whole claim
                    # inside <cite>. Normally the claim is already visible and
                    # only the marker is emitted; for a bare bullet/sentence,
                    # preserve the quote so the answer cannot collapse to
                    # merely "* [1]".
                    if self._is_bare_citation_position("".join(out)) and parsed["quote"]:
                        out.append(f'{parsed["quote"]} ')
                    out.append(f"[{self._count}]")
                    logger.info(
                        "citation: [%d] url=%r title=%r quote=%r",
                        self._count, parsed["url"], parsed["title"], parsed["quote"][:200],
                    )
                else:
                    # malformed: silently dropped from the visible answer
                    # (fail closed, no raw markup leak) but logged loudly —
                    # this is the case worth debugging if citations go missing.
                    logger.warning("citation: malformed <cite> tag, dropped: %r", full_tag[:300])
                continue

        safe_text = "".join(out)
        self._visible_tail = (self._visible_tail + safe_text)[-1000:]
        return safe_text, citations

    def flush(self) -> str:
        """Call at end of stream — anything still buffered (an unterminated
        ``<cite`` with no closing tag) is returned as plain text rather than
        silently dropped."""
        leftover = self._buffer
        self._buffer = ""
        if self._in_tag:
            logger.warning(
                "citation: stream ended mid-tag, flushing raw leftover: %r", leftover[:300]
            )
        self._in_tag = False
        return leftover
