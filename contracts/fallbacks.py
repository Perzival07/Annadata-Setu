"""Honest failure values shared by every service.

Lives in contracts/ because `channel` and `brain` both need the identical
"we do not know" Diagnosis, and BRAIN.md §16 forbids one service importing
another's modules. This is additive — no frozen field is renamed or dropped.
"""

from contracts.models import Diagnosis, PlotPassport


def unavailable_diagnosis() -> Diagnosis:
    """A Diagnosis that admits it has no diagnosis.

    Failures must never fall through to mock_data.DIAGNOSIS. That fixture names
    a specific fungicide at a specific dose with 0.88 confidence, so an expired
    API key, a timeout, or an unreachable brain would reach the farmer as a
    confident instruction to spray ₹340 of Mancozeb on a plant nobody looked at.

    Note `is_action_needed=False` here does NOT mean "don't spray, you're fine"
    — that is the separate abiotic path. Anything rendering this must branch on
    `escalate_to_human` FIRST (see channel/services/composer.py and
    web/src/components/DiagnosisCard.jsx).
    """
    return Diagnosis(
        disease_name="Undetermined",
        confidence=0.0,
        differentials=[],
        is_action_needed=False,
        action_text=(
            "We could not examine your photo automatically. Please do not spray "
            "on the strength of this message. An agronomist will review it, and "
            "sending a clearer daylight photo of the affected leaf will help."
        ),
        dosage=None,
        estimated_cost_inr=0,
        urgency_hours=24,
        escalate_to_human=True,
        # Farmer-facing — the underlying error goes to the log, not the handset.
        reasoning_context=["Automated diagnosis unavailable — sent for human review"],
        sources=[],
    )


def context_unavailable_passport(lat: float, lon: float, geohash: str, plot_id: str) -> PlotPassport:
    """A PlotPassport carrying no invented telemetry.

    When `ground` is unreachable we still want a diagnosis attempt, but we must
    not hand Gemini a fabricated "day 58 tomato, RH 87%" context — it would be
    echoed back to the farmer in reasoning_context as if it were measured.
    Empty series and empty dicts let the prompt say "no plot context available".
    """
    return PlotPassport(
        plot_id=plot_id,
        lat=lat,
        lon=lon,
        geohash=geohash,
        district="Unknown",
        state="Unknown",
        ndvi_series=[],
        inferred_crop="Unknown",
        crop_stage_days=0,
        cropping_history=[],
        soil={},
        weather_10d={},
        data_sources=["unavailable: plot telemetry service unreachable"],
        schema_version="1.0",
    )
