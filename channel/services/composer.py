import logging
from contracts.models import Diagnosis

logger = logging.getLogger("channel.composer")

class AdvisoryComposerService:
    def compose_text_advisory(self, diagnosis: Diagnosis) -> str:
        """Compose a structured, formatted text message for WhatsApp."""
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

    def compose_marathi_script(self, diagnosis: Diagnosis) -> str:
        """Compose a direct 4-sentence Marathi spoken voice note script."""
        disease = diagnosis.disease_name
        cost = diagnosis.estimated_cost_inr

        if not diagnosis.is_action_needed:
            return (
                f"नमस्कार. तुमच्या पिकावर {disease} ची लक्षणे दिसत आहेत. "
                f"ही हवामानातील बदलामुळे झालेली पोषण कमतरता आहे. "
                f"कोणतीही रासायनिक फवारणी करण्याची गरज नाही. यामुळे तुमचे ₹{cost or 500} वाचतील."
            )

        dosage_str = f" १ लिटर पाण्यात {diagnosis.dosage} मिसळून फवारणी करा." if diagnosis.dosage else ""
        return (
            f"नमस्कार. तुमच्या पिकावर {disease} चा प्रादुर्भाव झाला आहे. "
            f"{diagnosis.action_text}.{dosage_str} "
            f"याचा अंदाजे खर्च ₹{cost} येईल. फवारणी पुढील {diagnosis.urgency_hours} तासांत पूर्ण करा."
        )

composer_service = AdvisoryComposerService()
