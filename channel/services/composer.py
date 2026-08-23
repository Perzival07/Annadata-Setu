import logging
from typing import Optional

from contracts.models import Diagnosis
from contracts.languages import (
    DEFAULT_LANGUAGE,
    get,
    has_foreign_script,
    localize_digits,
    strip_to_speakable,
)
from channel.services.phrasebook import label, phrases, voice
from channel.services.render import disease_name, dosage_phrase

logger = logging.getLogger("channel.composer")


class AdvisoryComposerService:
    def compose_text_advisory(
        self, diagnosis: Diagnosis, code: str = DEFAULT_LANGUAGE
    ) -> str:
        """The structured WhatsApp message, in the farmer's language.

        Unlike the voice script this may carry Latin script even in a
        non-Latin language: the disease name and the dose are read, not spoken,
        and the farmer needs the exact strings to buy the right product. That
        is the division of labour — precision here, speakability in the voice.
        """
        # Escalation is a third state, checked before anything else. It is
        # neither "spray this" nor "you're fine" — rendering it through the
        # is_action_needed branch would tell a farmer with a real infection
        # that they need not spray.
        if diagnosis.escalate_to_human:
            return phrases(code)["escalation_text"]

        status_icon = "⚠️" if diagnosis.is_action_needed else "✅"
        lines = [
            label("header", code),
            "",
            f"{label('diagnosis', code)} {diagnosis.disease_name}",
            f"{label('confidence', code)} {int(diagnosis.confidence * 100)}%",
            "",
        ]

        if diagnosis.reasoning_context:
            lines.append(label("context", code))
            for ctx in diagnosis.reasoning_context:
                lines.append(f"  • {ctx}")
            lines.append("")

        lines.append(f"{status_icon} {label('action', code)}")
        lines.append(diagnosis.action_text)

        if diagnosis.is_action_needed and diagnosis.dosage:
            lines.append(f"{label('dosage', code)} {diagnosis.dosage}")
            lines.append(f"{label('cost', code)} ₹{diagnosis.estimated_cost_inr}")
            lines.append(label("urgency", code).format(hours=diagnosis.urgency_hours))
        else:
            lines.append(label("no_spray", code))

        if diagnosis.sources:
            lines.append(f"\n{label('sources', code)} {', '.join(diagnosis.sources)}")

        return "\n".join(lines)

    def compose_voice_script(
        self,
        diagnosis: Diagnosis,
        code: str = DEFAULT_LANGUAGE,
        action_translated: Optional[str] = None,
    ) -> str:
        """Spoken script in the farmer's language, in that language's script only.

        This is the FALLBACK. The primary path asks brain to generate the script
        directly (BRAIN.md §11, 15:30) — see pipeline.py. This template runs when
        brain is unreachable, and its one hard requirement is that nothing in a
        foreign script reaches the voice: the original version interpolated the
        English disease_name, action_text and dosage straight in, so ~45% of the
        spoken script was English read aloud by a Marathi voice.

        "Foreign" is relative to `code` — Latin for Marathi, Hindi and Bengali;
        Devanagari and Bengali for English. Where a value cannot be rendered it
        is omitted, and the text message still carries it exactly.

        `action_translated` is the farmer-facing instruction already rendered in
        this language — Cloud Translate's output, vetted by translate.py, or
        action_text itself when the target is English. Callers must never pass
        raw English here for a non-Latin language.
        """
        lang = get(code)

        if diagnosis.escalate_to_human:
            return voice("escalation", lang.code)

        rendered = disease_name(diagnosis.disease_name, lang.code)
        # No safe rendering: name the symptom generically rather than speaking a
        # foreign-script disease name mid-sentence.
        subject = (
            voice("subject_known", lang.code).format(disease=rendered)
            if rendered
            else voice("subject_unknown", lang.code)
        )

        # A translated instruction goes in as its own sentence rather than
        # replacing a template line, so the guarantees the template already
        # makes about dose and cost are untouched by it.
        advice = f"{action_translated.rstrip('.')}. " if action_translated else ""

        if not diagnosis.is_action_needed:
            saved = localize_digits(str(diagnosis.estimated_cost_inr or 500), lang.code)
            script = voice("dont_spray", lang.code).format(
                subject=subject, advice=advice, saved=saved
            )
            return self._guard(script, lang.code)

        dose_rendered = dosage_phrase(diagnosis.dosage, lang.code)
        dose = (
            voice("dose_known", lang.code).format(dosage=dose_rendered)
            if dose_rendered
            else voice("dose_unknown", lang.code)
        )
        script = voice("treatment", lang.code).format(
            subject=subject,
            advice=advice,
            dose=dose,
            cost=localize_digits(str(diagnosis.estimated_cost_inr or 0), lang.code),
            hours=localize_digits(str(diagnosis.urgency_hours or 24), lang.code),
        )
        return self._guard(script, lang.code)

    @staticmethod
    def _guard(script: str, code: str) -> str:
        """Belt and braces: nothing in a foreign script may reach the voice."""
        return strip_to_speakable(script, code) if has_foreign_script(script, code) else script

    # Kept because channel/tests/test_marathi.py and older callers use this name.
    def compose_marathi_script(
        self, diagnosis: Diagnosis, action_mr: Optional[str] = None
    ) -> str:
        """compose_voice_script pinned to Marathi."""
        return self.compose_voice_script(diagnosis, DEFAULT_LANGUAGE, action_mr)


composer_service = AdvisoryComposerService()
