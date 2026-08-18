"""Creative schema based on the simplicio stage taxonomy: brief -> script -> creative -> caption."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class CreativeBrief:
    """Stage 1: Structured Creative Brief."""

    target_audience: str
    core_angle: str
    pain_point: str
    value_proposition: str
    tone_of_voice: str
    mandatory_disclaimers: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class SceneCue:
    """Scene breakdown for video creative."""

    timestamp_range: str
    visual_cue: str
    audio_spoken: str
    on_screen_text: str


@dataclass(frozen=True, slots=True)
class VideoScript:
    """Stage 2: Video requirements and spoken script."""

    title: str
    duration_seconds: int
    aspect_ratio: str  # "9:16" | "16:9" | "1:1"
    hook_3s: str
    problem_solution: str
    call_to_action: str
    scenes: list[SceneCue] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class AdCreative:
    """Stage 3: Ad copy variants."""

    headline: str
    primary_text: str
    call_to_action: str
    alternative_headlines: list[str] = field(default_factory=list)
    image_prompt: str = ""


@dataclass(frozen=True, slots=True)
class PlatformCaptions:
    """Stage 4: Multi-platform captions."""

    meta_caption: str
    instagram_caption: str
    linkedin_caption: str
    hashtags: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class CreativePackage:
    """Full end-to-end creative package output."""

    brief: CreativeBrief
    script: VideoScript
    creative: AdCreative
    captions: PlatformCaptions
    generation_mode: str = "llm"  # "llm" | "deterministic_fallback"

    def to_dict(self) -> dict[str, Any]:
        return {
            "generation_mode": self.generation_mode,
            "brief": {
                "target_audience": self.brief.target_audience,
                "core_angle": self.brief.core_angle,
                "pain_point": self.brief.pain_point,
                "value_proposition": self.brief.value_proposition,
                "tone_of_voice": self.brief.tone_of_voice,
                "mandatory_disclaimers": self.brief.mandatory_disclaimers,
            },
            "script": {
                "title": self.script.title,
                "duration_seconds": self.script.duration_seconds,
                "aspect_ratio": self.script.aspect_ratio,
                "hook_3s": self.script.hook_3s,
                "problem_solution": self.script.problem_solution,
                "call_to_action": self.script.call_to_action,
                "scenes": [
                    {
                        "timestamp_range": s.timestamp_range,
                        "visual_cue": s.visual_cue,
                        "audio_spoken": s.audio_spoken,
                        "on_screen_text": s.on_screen_text,
                    }
                    for s in self.script.scenes
                ],
            },
            "creative": {
                "headline": self.creative.headline,
                "primary_text": self.creative.primary_text,
                "call_to_action": self.creative.call_to_action,
                "alternative_headlines": self.creative.alternative_headlines,
                "image_prompt": self.creative.image_prompt,
            },
            "captions": {
                "meta_caption": self.captions.meta_caption,
                "instagram_caption": self.captions.instagram_caption,
                "linkedin_caption": self.captions.linkedin_caption,
                "hashtags": self.captions.hashtags,
            },
        }
