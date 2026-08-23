import logging
from contracts.models import Diagnosis

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

    def compose_marathi_script(self, diagnosis: Diagnosis) -> str:
        """Compose a direct 4-sentence Marathi spoken voice note script."""
        disease = diagnosis.disease_name
        cost = diagnosis.estimated_cost_inr

        if diagnosis.escalate_to_human:
            return (
                "नमस्कार. तुमचा फोटो आम्हाला नीट तपासता आला नाही. "
                "त्यामुळे आत्ता कोणतीही फवारणी करू नका. "
                "आमचे कृषी तज्ज्ञ तुमचा फोटो पाहून लवकरच तुम्हाला सल्ला देतील. "
                "शक्य असल्यास दिवसाच्या उजेडात पानाचा स्पष्ट फोटो पुन्हा पाठवा."
            )

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
