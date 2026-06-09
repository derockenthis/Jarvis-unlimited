from app.memory.schemas import Observation, PatchOperation


def build_dream_agent(settings: object) -> object:
    """Build the NBAM dreamer agent with the configured lightweight Gemini model."""

    from google.adk.agents import Agent
    from google.adk.models.lite_llm import LiteLlm

    model = getattr(settings, "memory_dreamer_litellm_model")
    return Agent(
        name="nbam_dream_agent",
        model=LiteLlm(model=model),
        instruction=(
            "You are the NBAM dream agent. Convert raw observations into conservative "
            "memory patch proposals only. Never write durable nodes directly. Prefer "
            "discard_observation unless an observation captures a reusable project fact, "
            "decision, rule, or recurring gotcha."
        ),
    )


class DreamerStub:
    """Rule-based placeholder for future stronger-model consolidation."""

    def propose(self, observations: list[Observation]) -> list[PatchOperation]:
        return [
            PatchOperation(
                op="discard_observation",
                payload={"observation_id": observation.id, "reason": "No promotion rule matched."},
            )
            for observation in observations
        ]
