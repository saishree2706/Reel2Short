"""
AI metadata generation service using Google Gemini.

Responsibilities:
- Build context-grounded prompts from user-provided input
- Call Gemini API with structured output (JSON mode)
- Validate and return parsed metadata
- Never expose AI_API_KEY in logs, responses, or error messages
- Never invent locations, people, events, statistics, or claims
  that were not provided by the user
"""
import json
import logging
from typing import Optional

from pydantic import BaseModel, Field, ValidationError

try:
    import google.generativeai as genai
except ImportError:
    genai = None  # type: ignore

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Output schema — validated before returning to caller
# ---------------------------------------------------------------------------

class ThumbnailConcept(BaseModel):
    concept: str = Field(..., max_length=300)
    text: str = Field(..., max_length=100)
    visual_moment: str = Field(..., max_length=200)


class AIMetadataResult(BaseModel):
    titles: list[str] = Field(..., min_length=1, max_length=10)
    description: str = Field(..., max_length=5000)
    hashtags: list[str] = Field(default_factory=list, max_length=20)
    tags: list[str] = Field(default_factory=list, max_length=30)
    category: str = Field(..., max_length=100)
    hook: str = Field(..., max_length=300)
    thumbnail: ThumbnailConcept


# ---------------------------------------------------------------------------
# Input schema — what the caller provides
# ---------------------------------------------------------------------------

class AIMetadataRequest(BaseModel):
    description: str = Field(..., min_length=1, max_length=2000)
    keywords: Optional[list[str]] = Field(default_factory=list)
    content_type: Optional[str] = Field(None, max_length=100)
    target_audience: Optional[str] = Field(None, max_length=200)
    language: Optional[str] = Field("English", max_length=50)
    tone: Optional[str] = Field(None, max_length=100)
    # Context from the video asset (auto-populated by the API endpoint)
    instagram_caption: Optional[str] = Field(None, max_length=2200)
    duration_seconds: Optional[float] = None
    aspect_ratio: Optional[str] = None
    is_converted: Optional[bool] = False


# ---------------------------------------------------------------------------
# Default Gemini model — overridden by AI_MODEL in .env
# ---------------------------------------------------------------------------

_DEFAULT_MODEL = "gemini-1.5-flash"

_SYSTEM_PROMPT = """\
You are a YouTube content metadata assistant. You help creators write compelling,
accurate YouTube Shorts metadata.

IMPORTANT RULES:
- Only use information explicitly provided in the user context.
- Do NOT invent locations, people, events, statistics, experiences, or claims.
- Do NOT promise views, virality, or results.
- Do NOT claim the video contains things that weren't mentioned.
- Generate exactly 5 title alternatives with different styles:
  1. Curiosity-driven
  2. Search-friendly (SEO)
  3. Simple and clear
  4. Emotionally engaging
  5. Action/engagement-focused
- Generate a natural YouTube description (no keyword stuffing).
- Generate 3–8 relevant hashtags (with # prefix).
- Generate relevant YouTube tags (without # prefix, no stuffing).
- Suggest one appropriate YouTube category from: Film & Animation, Autos & Vehicles,
  Music, Pets & Animals, Sports, Travel & Events, Gaming, People & Blogs, Comedy,
  Entertainment, News & Politics, Howto & Style, Education, Science & Technology,
  Nonprofits & Activism.
- Suggest a short hook (under 30 words).
- Suggest a thumbnail concept with: concept (describe the visual), text (overlay text),
  visual_moment (which moment from the description to use).

Always respond with valid JSON matching exactly this structure:
{
  "titles": ["title1", "title2", "title3", "title4", "title5"],
  "description": "...",
  "hashtags": ["#example"],
  "tags": ["example"],
  "category": "...",
  "hook": "...",
  "thumbnail": {
    "concept": "...",
    "text": "...",
    "visual_moment": "..."
  }
}
"""


def _get_model_name() -> str:
    from ..config import settings
    return settings.AI_MODEL.strip() if settings.AI_MODEL.strip() else _DEFAULT_MODEL


def _check_configured() -> None:
    """Raise a clear RuntimeError if AI is not configured."""
    from ..config import settings
    if not settings.AI_API_KEY:
        raise RuntimeError(
            "AI_API_KEY is not configured. "
            "Set AI_API_KEY in your .env file to enable AI metadata generation. "
            "Get a free Gemini API key at https://aistudio.google.com/"
        )


def _build_user_prompt(request: AIMetadataRequest) -> str:
    """Build a grounded, context-rich prompt from the user's input."""
    lines = [
        f"Description provided by creator: {request.description}",
    ]
    if request.keywords:
        lines.append(f"Keywords: {', '.join(request.keywords)}")
    if request.content_type:
        lines.append(f"Content type: {request.content_type}")
    if request.target_audience:
        lines.append(f"Target audience: {request.target_audience}")
    if request.language:
        lines.append(f"Language preference: {request.language}")
    if request.tone:
        lines.append(f"Tone: {request.tone}")

    # Video context (from asset metadata)
    if request.instagram_caption:
        lines.append(f"\nOriginal Instagram caption: {request.instagram_caption[:500]}")
    if request.duration_seconds:
        dur = int(request.duration_seconds)
        lines.append(f"Video duration: {dur} seconds")
    if request.aspect_ratio:
        lines.append(f"Video orientation: {request.aspect_ratio}")
    if request.is_converted:
        lines.append("Note: This is a converted vertical video (prepared for Shorts).")

    lines.append(
        "\nGenerate YouTube Shorts metadata ONLY from the information above. "
        "Do not invent any facts not mentioned."
    )

    return "\n".join(lines)


def generate_metadata(request: AIMetadataRequest) -> AIMetadataResult:
    """
    Call Gemini to generate YouTube metadata.

    Raises:
        RuntimeError: If AI_API_KEY is missing, Gemini returns an error,
                      or the response cannot be parsed.
    """
    _check_configured()

    if genai is None:
        raise RuntimeError(
            "google-generativeai package is not installed. "
            "Run: pip install google-generativeai"
        )

    from ..config import settings
    # Configure the SDK — never log the key
    genai.configure(api_key=settings.AI_API_KEY)

    model_name = _get_model_name()
    logger.info("Generating AI metadata with model: %s", model_name)

    model = genai.GenerativeModel(
        model_name=model_name,
        system_instruction=_SYSTEM_PROMPT,
        generation_config=genai.types.GenerationConfig(
            temperature=0.7,
            response_mime_type="application/json",
        ),
    )

    user_prompt = _build_user_prompt(request)

    try:
        response = model.generate_content(user_prompt)
    except Exception as e:
        # Mask any potential key leakage in error messages
        err_str = str(e)
        if settings.AI_API_KEY and settings.AI_API_KEY in err_str:
            err_str = err_str.replace(settings.AI_API_KEY, "***")
        logger.error("Gemini API error: %s", err_str)
        raise RuntimeError(f"AI generation failed: {err_str}") from e

    raw_text = response.text.strip()

    # Strip markdown code fences if the model wrapped the JSON
    if raw_text.startswith("```"):
        lines = raw_text.split("\n")
        # Remove opening ``` and closing ```
        raw_text = "\n".join(
            line for line in lines
            if not line.strip().startswith("```")
        ).strip()

    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as e:
        logger.error("Gemini returned non-JSON response (first 200 chars): %s", raw_text[:200])
        raise RuntimeError(
            "AI returned an invalid response. Please try regenerating."
        ) from e

    # Normalise and enforce limits
    # Ensure exactly 5 titles
    if isinstance(data.get("titles"), list):
        if len(data["titles"]) > 5:
            data["titles"] = data["titles"][:5]
        # Pad with fallback if fewer than 5
        while len(data["titles"]) < 1:
            data["titles"].append("My YouTube Short")

    # Ensure hashtags have # prefix
    if isinstance(data.get("hashtags"), list):
        data["hashtags"] = [
            h if h.startswith("#") else f"#{h}"
            for h in data["hashtags"]
        ][:8]

    # Ensure tags don't have # prefix
    if isinstance(data.get("tags"), list):
        data["tags"] = [t.lstrip("#") for t in data["tags"]][:30]

    try:
        result = AIMetadataResult.model_validate(data)
    except ValidationError as e:
        logger.error("AI response failed schema validation: %s", e)
        raise RuntimeError(
            "AI returned unexpected metadata format. Please try regenerating."
        ) from e

    logger.info(
        "AI metadata generated: %d titles, %d tags, %d hashtags",
        len(result.titles),
        len(result.tags),
        len(result.hashtags),
    )
    return result
