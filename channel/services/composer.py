import logging
from typing import Optional

from contracts.models import Diagnosis
from channel.services.marathi import (
    disease_in_marathi,
    dosage_in_marathi,
    has_latin_script,
    strip_to_speakable,
    to_devanagari_digits,
)

logger = logging.getLogger("channel.composer")

class AdvisoryComposerService:
    def compose_text_advisory(self, diagnosis: Diagnosis) -> str:
        """Compose a structured, formatted text message for WhatsApp."""
        # Escalation is a third state, checked before anything else. It is
        # neither "spray this" nor "you're fine" — rendering it through the
        # is_action_needed branch would tell a farmer with a real infection
        # that they need not spray.
        if diagnosis.escalate_to_human:
            return self._compose_escalation_text(diagnosis)

        status_icon = "⚠️" if diagnosis.is_action_needed else "✅"
        lines = [
            f"🌱 *अन्नदाता सेतु | पिक आरोग्य सल्ला*",
            f"",
            f"🔍 *निदान (Diagnosis):* {diagnosis.disease_name}",
            f"📊 *विश्वासार्हता (Confidence):* {int(diagnosis.confidence * 100)}%",
            f""
        ]

        if diagnosis.reasoning_context:
            lines.append("📋 *विश्लेषण (Context):*")
            for ctx in diagnosis.reasoning_context:
                lines.append(f"  • {ctx}")
            lines.append("")

        lines.append(f"{status_icon} *सल्ला (Action):*")
        lines.append(diagnosis.action_text)

        if diagnosis.is_action_needed and diagnosis.dosage:
            lines.append(f"💊 *प्रमाण (Dosage):* {diagnosis.dosage}")
            lines.append(f"💰 *अंदाजे खर्च:* ₹{diagnosis.estimated_cost_inr}")
            lines.append(f"⏳ *कालावधी:* {diagnosis.urgency_hours} तासांच्या आत")
        else:
            lines.append("🎉 *फवारणीची गरज नाही — खताचा/औषधाचा अनावश्यक खर्च वाचवा.*")

        if diagnosis.sources:
            lines.append(f"\n📚 *संदर्भ:* {', '.join(diagnosis.sources)}")

        return "\n".join(lines)

    def _compose_escalation_text(self, diagnosis: Diagnosis) -> str:
        """Render an undetermined diagnosis honestly: no dose, no cost, no all-clear."""
        return "\n".join([
            "🌱 *अन्नदाता सेतु | पिक आरोग्य सल्ला*",
            "",
            "🔍 *निदान (Diagnosis):* अनिश्चित — तपासणी सुरू आहे",
            "",
            "🔬 *सल्ला (Action):*",
            "तुमच्या फोटोवरून आम्ही खात्रीशीर निदान करू शकलो नाही.",
            "",
            "⚠️ *कृपया आत्ता कोणतीही फवारणी करू नका.*",
            "आमचे कृषी तज्ज्ञ तुमचा फोटो तपासून लवकरच सल्ला देतील.",
            "",
            "📷 मदतीसाठी: दिवसाच्या उजेडात, प्रभावित पानाचा जवळून स्पष्ट फोटो पुन्हा पाठवा.",
        ])

    def compose_marathi_script(
        self, diagnosis: Diagnosis, action_mr: Optional[str] = None
    ) -> str:
        """Marathi-only spoken script.

        This is the FALLBACK. The primary path asks brain to generate Marathi
        directly (BRAIN.md §11, 15:30) — see pipeline.py. This template runs when
        brain is unreachable, and its one hard requirement is that nothing Latin
        reaches the mr-IN voice: the previous version interpolated the English
        disease_name, action_text and dosage straight in, so ~45% of the spoken
        script was English read aloud by a Marathi voice.

        Where a value cannot be rendered in Marathi it is omitted. The WhatsApp
        text message still carries the precise English name and dose.

        `action_mr` is the farmer-facing instruction already rendered in Marathi
        — Cloud Translate's output, vetted by channel/services/translate.py. It
        is optional by design: the biggest thing this template drops is
        action_text, and when translation is off or its output was not speakable
        the script is exactly what it was before. Callers must never pass raw
        English here; everything on this path reaches an mr-IN voice.
        """
        if diagnosis.escalate_to_human:
            return (
                "नमस्कार. तुमचा फोटो आम्हाला नीट तपासता आला नाही. "
                "त्यामुळे आत्ता कोणतीही फवारणी करू नका. "
                "आमचे कृषी तज्ज्ञ तुमचा फोटो पाहून लवकरच तुम्हाला सल्ला देतील. "
                "शक्य असल्यास दिवसाच्या उजेडात पानाचा स्पष्ट फोटो पुन्हा पाठवा."
            )

        disease_mr = disease_in_marathi(diagnosis.disease_name)
        # No safe Marathi rendering: name the symptom generically rather than
        # speaking an English disease name mid-sentence.
        subject = f"{disease_mr} दिसत आहे" if disease_mr else "रोगाची लक्षणे दिसत आहेत"
        cost_mr = to_devanagari_digits(str(diagnosis.estimated_cost_inr or 0))

        # A translated instruction goes in as its own sentence rather than
        # replacing a template line, so the guarantees the template already
        # makes about dose and cost are untouched by it.
        advice = f"{action_mr.rstrip('.')}. " if action_mr else ""

        if not diagnosis.is_action_needed:
            saved = to_devanagari_digits(str(diagnosis.estimated_cost_inr or 500))
            script = (
                f"नमस्कार. तुमच्या पिकावर {subject}. "
                "ही रोगाची लागण नसून अन्नद्रव्यांची कमतरता आहे. "
                f"{advice}"
                "त्यामुळे कोणतीही रासायनिक फवारणी करण्याची गरज नाही. "
                f"यामुळे तुमचे अंदाजे ₹{saved} वाचतील."
            )
            return strip_to_speakable(script) if has_latin_script(script) else script

        dosage_mr = dosage_in_marathi(diagnosis.dosage)
        dose_sentence = (
            f"{dosage_mr} या प्रमाणात मिसळून फवारणी करा. "
            if dosage_mr else
            "औषधाच्या पाकिटावर दिलेल्या प्रमाणानुसार फवारणी करा. "
        )
        hours_mr = to_devanagari_digits(str(diagnosis.urgency_hours or 24))
        script = (
            f"नमस्कार. तुमच्या पिकावर {subject}. "
            "हवामानातील आर्द्रतेमुळे याचा प्रसार वेगाने होऊ शकतो. "
            f"{advice}"
            f"{dose_sentence}"
            f"याचा अंदाजे खर्च ₹{cost_mr} येईल आणि ही फवारणी पुढील {hours_mr} तासांत पूर्ण करा."
        )
        # Belt and braces: nothing Latin may reach the voice engine.
        return strip_to_speakable(script) if has_latin_script(script) else script


composer_service = AdvisoryComposerService()
