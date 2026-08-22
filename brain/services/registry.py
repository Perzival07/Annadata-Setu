"""Model Registry service managing model versioning, accuracy metrics, and fork lineage across state deployments."""

from typing import List, Dict

MODEL_REGISTRY: List[Dict] = [
    {
        "model_id": "annadata-gemini-mh-tomato-v1.2",
        "name": "Maharashtra Tomato Blight & Abiotic Classifier",
        "base_model": "gemini-2.5-flash",
        "state": "Maharashtra",
        "crop": "Tomato",
        "accuracy_f1": 0.912,
        "calibration_error": 0.043,
        "training_dataset": "ICAR-MH-Tomato-2023-v1",
        "fork_lineage": ["base/gemini-2.5-flash", "annadata/mh-tomato-v1.0"],
        "schema_version": "1.0",
        "updated_at": "2024-03-01T12:00:00Z"
    },
    {
        "model_id": "annadata-gemini-ka-tomato-v1.2.1",
        "name": "Karnataka Tomato Blight & Wilt Variant",
        "base_model": "annadata-gemini-mh-tomato-v1.2",
        "state": "Karnataka",
        "crop": "Tomato",
        "accuracy_f1": 0.898,
        "calibration_error": 0.051,
        "training_dataset": "UAS-Dharwad-Tomato-2023",
        "fork_lineage": ["base/gemini-2.5-flash", "annadata/mh-tomato-v1.2", "annadata/ka-tomato-v1.2.1"],
        "schema_version": "1.0",
        "updated_at": "2024-03-10T09:30:00Z"
    },
    {
        "model_id": "annadata-gemini-mh-onion-v1.0",
        "name": "Maharashtra Onion Purple Blotch Classifier",
        "base_model": "gemini-2.5-flash",
        "state": "Maharashtra",
        "crop": "Onion",
        "accuracy_f1": 0.887,
        "calibration_error": 0.048,
        "training_dataset": "DOGR-Rajgurunagar-Onion-2023",
        "fork_lineage": ["base/gemini-2.5-flash", "annadata/mh-onion-v1.0"],
        "schema_version": "1.0",
        "updated_at": "2024-02-15T16:20:00Z"
    }
]

def get_registered_models() -> List[Dict]:
    return MODEL_REGISTRY

def get_model_by_id(model_id: str) -> Dict | None:
    for model in MODEL_REGISTRY:
        if model["model_id"] == model_id:
            return model
    return None
