from __future__ import annotations

import json
import re
from uuid import uuid4

from app.memory.schemas import MemoryLink, MemoryNodeFrontmatter, NodeType, Observation, PatchOperation


def _strip_actor_prefix(observation: Observation) -> str:
    text = observation.observation.strip()
    if ": " in text:
        _, content = text.split(": ", 1)
        return content.strip()
    return text

def _slugify(text: str, fallback: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    slug = re.sub(r"-+", "-", slug)
    return slug[:48] if slug else fallback


def _summarize_title(content: str) -> str:
    words = re.findall(r"[a-zA-Z0-9]+", content)
    if not words:
        return "Memory note"
    return " ".join(word.capitalize() for word in words[:6])


def _infer_tree(content: str, node_type: NodeType) -> str:
    normalized = content.lower().strip()
    if normalized.startswith(("project scope:", "scope:", "in scope:", "out of scope:")):
        return "project_scope"
    if node_type == NodeType.SCOPE:
        return "project_scope"
    return "general"


def _default_weight(node_type: NodeType, tree: str) -> float:
    if tree == "project_scope":
        return 0.9
    if node_type == NodeType.ARCHITECTURAL_DECISION:
        return 0.9
    if node_type == NodeType.RULE:
        return 0.8
    if node_type == NodeType.TASK:
        return 0.65
    if node_type == NodeType.ENTITY:
        return 0.6
    return 0.5


def _relationship_for_tree(tree: str) -> str:
    if tree == "project_scope":
        return "related_scope"
    return "related"


def _build_node_frontmatter(
    observation: Observation,
    node_type: NodeType,
    content: str,
    links: list[MemoryLink] | None = None,
) -> MemoryNodeFrontmatter:
    title = _summarize_title(content)
    slug = _slugify(title, observation.id)
    tree = _infer_tree(content, node_type)
    return MemoryNodeFrontmatter(
        id=f"{slug}-{observation.id[-8:]}",
        title=title,
        type=node_type,
        valid_from=observation.timestamp,
        created_at=observation.timestamp,
        updated_at=observation.timestamp,
        weight=_default_weight(node_type, tree),
        tree=tree,
        links=links or [],
        tags=[node_type.value],
        source_observations=[observation.id],
    )


def _build_node_body(observation: Observation) -> str:
    content = _strip_actor_prefix(observation)
    return f"Captured from observation {observation.id}.\n\n{content}".strip()


def _observation_ids_from_patch(patch: PatchOperation) -> set[str]:
    explicit_ids = patch.payload.get("observation_ids")
    if isinstance(explicit_ids, list):
        return {str(item) for item in explicit_ids if str(item).strip()}

    observation_id = patch.payload.get("observation_id")
    if observation_id is not None:
        return {str(observation_id)}

    frontmatter_payload = patch.payload.get("frontmatter")
    if isinstance(frontmatter_payload, dict):
        source_ids = frontmatter_payload.get("source_observations")
        if isinstance(source_ids, list):
            return {str(item) for item in source_ids if str(item).strip()}
    return set()


def _strip_json_fences(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


def build_dreamer_prompt(observations: list[Observation]) -> str:
    serialized_observations = [
        {
            "id": observation.id,
            "timestamp": observation.timestamp.isoformat(),
            "session_id": observation.session_id,
            "message_index": observation.message_index,
            "observation": observation.observation,
        }
        for observation in observations
    ]
    return (
        "Review the following raw session observations and propose conservative memory patch "
        "operations as JSON. Return either a JSON array or an object with a 'patches' field. "
        "Every observation id must be covered exactly once, either by a durable patch that "
        "references it in payload.observation_ids/frontmatter.source_observations or by a "
        "discard_observation patch with payload.observation_id. For create_node patches, set "
        "frontmatter.weight between 0.0 and 1.0, set frontmatter.tree to the logical node "
        "group such as general or project_scope, add frontmatter.links when the node should "
        "reference a related durable node, and use frontmatter.parent_id when creating a child "
        "node under an existing durable node. Do not include commentary.\n\n"
        f"Observations:\n{json.dumps(serialized_observations, indent=2)}"
    )


class AdkDreamer:
    """ADK-backed dreamer runner with a deterministic fallback stub."""

    def __init__(self, settings: object, fallback: DreamerStub | None = None) -> None:
        self.settings = settings
        self.fallback = fallback or DreamerStub()

    async def propose(self, observations: list[Observation]) -> list[PatchOperation]:
        if not observations:
            return []

        prompt = build_dreamer_prompt(observations)
        try:
            response_text = await self._run_adk(prompt)
            parsed_patches = self._parse_patch_response(response_text)
            return self._complete_patch_set(observations, parsed_patches)
        except Exception:
            return self.fallback.propose(observations)

    async def _run_adk(self, prompt: str) -> str:
        from google.adk.runners import Runner
        from google.adk.sessions.in_memory_session_service import InMemorySessionService
        from google.genai import types

        session_service = InMemorySessionService()
        runner = Runner(
            app_name="jarvis-memory-dreamer",
            agent=build_dream_agent(self.settings),
            session_service=session_service,
            auto_create_session=True,
        )

        assistant_chunks: list[str] = []
        async for event in runner.run_async(
            user_id="memory-promoter",
            session_id=f"dreamer-{uuid4().hex}",
            new_message=types.Content(role="user", parts=[types.Part.from_text(text=prompt)]),
        ):
            content = getattr(event, "content", None)
            if content is None or not getattr(content, "parts", None):
                continue
            for part in content.parts:
                text = getattr(part, "text", None)
                if text and not getattr(part, "thought", False):
                    assistant_chunks.append(text)

        return "".join(assistant_chunks).strip()

    def _parse_patch_response(self, response_text: str) -> list[PatchOperation]:
        normalized = _strip_json_fences(response_text)
        payload = json.loads(normalized)
        if isinstance(payload, dict):
            payload = payload.get("patches", [])
        if not isinstance(payload, list):
            raise ValueError("Dreamer response must be a JSON array of patches.")
        return [PatchOperation.model_validate(item) for item in payload]

    def _complete_patch_set(
        self, observations: list[Observation], patches: list[PatchOperation]
    ) -> list[PatchOperation]:
        covered_ids: set[str] = set()
        completed = list(patches)
        for patch in patches:
            covered_ids.update(_observation_ids_from_patch(patch))

        for observation in observations:
            if observation.id in covered_ids:
                continue
            completed.append(
                PatchOperation(
                    op="discard_observation",
                    payload={
                        "observation_id": observation.id,
                        "reason": "Dreamer returned no explicit patch for this observation.",
                    },
                )
            )
        return completed


def build_dream_agent(settings: object) -> object:
    """Build the NBAM dreamer agent with the configured lightweight Gemini model."""

    from google.adk.agents import Agent
    from google.adk.models.lite_llm import LiteLlm

    model = getattr(settings, "memory_dreamer_litellm_model")
    litellm_kwargs: dict[str, str] = {}
    if str(model).startswith("openrouter/"):
        api_key = str(getattr(settings, "openrouter_api_key", "") or "").strip()
        api_base = str(getattr(settings, "openrouter_base_url", "") or "").strip()
        if api_key:
            litellm_kwargs["api_key"] = api_key
        if api_base:
            litellm_kwargs["api_base"] = api_base
    return Agent(
        name="nbam_dream_agent",
        model=LiteLlm(model=model, **litellm_kwargs),
        instruction=(
            "You are the NBAM dream agent. Convert raw observations into conservative "
            "memory patch proposals only. Return a JSON array of patch operations and no "
            "extra commentary. Supported operations are create_node, update_node_body, "
            "update_node_frontmatter, replace_links, deprecate_node, merge_nodes, and "
            "discard_observation. Prefer discard_observation unless an observation captures "
            "a reusable project fact, decision, rule, project scope item, or recurring gotcha. "
            "When creating a node, include a serialized frontmatter object and a markdown body "
            "in the payload. Populate frontmatter.weight with a conservative importance score "
            "from 0.0 to 1.0, use frontmatter.tree for grouping such as general or "
            "project_scope, add frontmatter.links when the node relates to existing durable "
            "nodes, and set frontmatter.parent_id when the node should sit under an existing "
            "parent in that tree."
        ),
    )


class DreamerStub:
    """Rule-based placeholder for future stronger-model consolidation."""

    def propose(self, observations: list[Observation]) -> list[PatchOperation]:
        proposals: list[PatchOperation] = []
        latest_by_tree: dict[str, str] = {}
        latest_scope_node_id: str | None = None
        for observation in observations:
            promoted = self._promote_observation(observation, latest_by_tree, latest_scope_node_id)
            if promoted is None:
                proposals.append(
                    PatchOperation(
                        op="discard_observation",
                        payload={
                            "observation_id": observation.id,
                            "reason": "No promotion rule matched.",
                        },
                    )
                )
                continue

            proposals.append(promoted)
            frontmatter_payload = promoted.payload.get("frontmatter")
            if isinstance(frontmatter_payload, dict):
                tree = str(frontmatter_payload.get("tree", "general"))
                node_id = str(frontmatter_payload.get("id", "")).strip()
                if node_id:
                    latest_by_tree[tree] = node_id
                    if tree == "project_scope":
                        latest_scope_node_id = node_id
        return proposals

    def _promote_observation(
        self,
        observation: Observation,
        latest_by_tree: dict[str, str],
        latest_scope_node_id: str | None,
    ) -> PatchOperation | None:
        content = _strip_actor_prefix(observation)
        normalized = content.lower().strip()
        body = content
        node_type: NodeType | None = None

        if normalized.startswith("decision:"):
            node_type = NodeType.ARCHITECTURAL_DECISION
            body = content.split(":", 1)[1].strip()
        elif normalized.startswith(("project scope:", "scope:", "in scope:", "out of scope:")):
            node_type = NodeType.SCOPE
            body = content.split(":", 1)[1].strip()
        elif normalized.startswith(("rule:", "always ", "never ", "prefer ", "must ", "should ")):
            node_type = NodeType.RULE
            body = content.split(":", 1)[1].strip() if ":" in content else content
        elif normalized.startswith(("remember:", "fact:", "project fact:")):
            node_type = NodeType.ENTITY
            body = content.split(":", 1)[1].strip()
        elif normalized.startswith(("task:", "todo:", "next step:")):
            node_type = NodeType.TASK
            body = content.split(":", 1)[1].strip()

        if node_type is None or not body:
            return None

        tree = _infer_tree(body, node_type)
        links: list[MemoryLink] = []
        if latest_scope_node_id and tree != "project_scope":
            links.append(MemoryLink(target_id=latest_scope_node_id, relationship="scoped_by"))
        prior_node_id = latest_by_tree.get(tree)
        if prior_node_id and prior_node_id != latest_scope_node_id:
            links.append(
                MemoryLink(target_id=prior_node_id, relationship=_relationship_for_tree(tree))
            )

        frontmatter = _build_node_frontmatter(observation, node_type, body, links=links)
        return PatchOperation(
            op="create_node",
            node_id=frontmatter.id,
            payload={
                "frontmatter": frontmatter.model_dump(mode="json"),
                "body": body,
                "observation_ids": [observation.id],
            },
        )
