# Implementation Brief — Hybrid Local-Vision + Cloud-Reasoning

## 🎯 **STATUS UPDATE (Latest)**

### ✅ **COMPLETED** 
- **Core Architecture**: Full `hybrid_agent.py` with all major components implemented
- **Data Models**: Complete Pydantic schemas for VisionState, Action, PlannerRequest/Response, HistoryStep
- **Local Action Execution**: Comprehensive local handlers for click, type, scroll, navigate actions with fallback strategies
- **Cloud Integration**: CloudPlannerClient with Gemini 2.0 Flash integration and structured output
- **Handoff Manager**: Intelligent routing between local/cloud with failure tracking and escalation logic
- **Browser Integration**: Full browser-use session management and controller integration
- **Error Handling**: Robust exception handling with multiple fallback strategies per action type
- **CLI Interface**: Complete command-line interface with task execution loop
- **Local VLM wired via Ollama (Llava-Phi3)**: VisionStateBuilder returns caption/elements/fields/affordances; both tests passing

### 🔄 **IN PROGRESS**
- **Testing**: Basic functionality confirmed, but full end-to-end workflow testing needed

### ❌ **REMAINING**
- **selector_hint quality**: Improve CSS/XPath selector generation from vision analysis
- **Visual diff caching**: Optimize repeated screenshot processing 
- **Visual diff optimization**: Change detection between screenshots   
- **Acceptance fixtures**: Login, search, comparison, ambiguity, failure recovery scenarios

## 🚀 **NEXT IMMEDIATE STEPS**

1. **Complete VisionStateBuilder**: Replace placeholder with actual Llava-Phi3 integration
   - Set up local Ollama server with Llava-Phi3 model
   - Implement HTTP client to call local VLM and parse structured output
   - Add screenshot preprocessing and vision prompt engineering

2. **End-to-End Testing**: Test full hybrid_agent.py workflow
   - Simple tasks (click, type, navigate) via local execution
   - Complex tasks that trigger cloud escalation 
   - Failure scenarios and recovery paths

3. **Integration Fixes**: Address any issues discovered during testing
   - Browser session lifecycle management
   - Vision state confidence thresholds
   - Action execution error handling

---

## **Original Brief**

Create a new file hybrid_agent.py that integrates the hybrid vision system into the agent.py framework.

Start with agent.py as the base - Keep all its good features:

The CLI interface and query loop
Cost tracking and logging
Serper search integration
The user experience flow

Replace the browser automation logic with the hybrid system. The ultimate goal is a new script called hybrid_agent.py that the user will run instead of agent.py. 

Models
* Local VLM (always on): Llava-Phi3 (single download). Provide a thin client that can call a local server (e.g., HTTP endpoint) and return compact JSON. The runtime may be GPU or CPU; prefer int4/gguf quantization if needed. OllamaGitHub
* Cloud Reasoner (rare calls): Gemini 2.0 Flash (model id per vendor docs) via google api key. Must support structured outputs / function calling and 1M-token context. Google AI for Developers
Objectives
1. Local Vision Loop (every action): Take a screenshot → summarize UI into structured JSON (“VisionState”) + a short caption.
2. Local Simple Actions: If the next step is obvious (click, type, scroll, navigate) and target is unambiguous, execute locally without cloud.
3. Cloud Reasoning (escalate sparingly): When the step is ambiguous or multi-hop (checkout, comparison, recovery from failure), send task + recent history + latest VisionState to Gemini 2.0 Flash; get back a small, ordered action plan. Google AI for Developers
New Components (add to your codebase)
* VisionStateBuilder (local): Given a screenshot, call Llava-Phi3 and return:
    * caption (≤200 chars)
    * elements[] with {role, visible_text, attributes, selector_hint, bbox, confidence}
    * fields[] with {name_hint, value_hint, bbox, editable}
    * affordances[] with {type: "button|link|tab|menu|icon", label, selector_hint, bbox}
    * meta with {url, title, scrollY, timestamp}
* LocalActionHeuristics: Decide if the requested step is “simple” and can be handled locally (click/type/scroll/navigate) using selector_hint + fuzzy text match.
* CloudPlannerClient: Wrap Gemini 2.0 Flash with a constrained schema for actions.
* HandoffManager: Route between local and cloud; maintain rolling History (last N steps with compact diffs).
* Confidence & Backoff: If VisionState confidence < threshold or two consecutive local failures, escalate to cloud.
Data Contracts (schemas to enforce)
* VisionState (from Llava-Phi3):



{
*   "caption": "string",
*   "elements": [ { "role": "button|link|text|image|other",
*                   "visible_text": "string",
*                   "attributes": {"ariaLabel": "...", "type": "..."},
*                   "selector_hint": "string",
*                   "bbox": [x,y,w,h],
*                   "confidence": 0.0 } ],
*   "fields": [ { "name_hint": "email", "value_hint": "", "bbox": [x,y,w,h], "editable": true } ],
*   "affordances": [ { "type": "button", "label": "Sign in", "selector_hint": "string", "bbox": [x,y,w,h] } ],
*   "meta": { "url": "string", "title": "string", "scrollY": 0, "timestamp": "iso8601" }
* }
* 


* Action (used both locally and from cloud):



{ "op": "click|type|scroll|navigate|wait|select|hover",
*   "target": { "selector_hint": "string", "text": "optional" },
*   "value": "optional string",
*   "notes": "optional string" }
* 


* PlannerRequest (to Gemini):



{ "task": "user goal",
*   "history": [ { "action": "...", "result": "ok|fail", "summary": "..." } ],
*   "vision": VisionState,
*   "constraints": { "max_actions": 5, "avoid": ["login if already logged in"] } }
* 


* PlannerResponse (from Gemini; must be strict JSON):



{ "plan": [ Action, ... ],
*   "reasoning_summary": "≤300 chars",
*   "needs_more_context": false }
* 


Control Flow (per step)
1. Capture screenshot of active tab; build VisionState.
2. If a simple intent is pending (click/type/scroll/navigate) and there’s a single high-confidence match in elements/affordances/fields, execute locally; log result.
3. Else create PlannerRequest and call Gemini 2.0 Flash. Apply returned plan actions sequentially.
4. After each action, re-screenshot and compare to prior VisionState; store diff in History.
5. Failure handling: on 2 consecutive failures or needs_more_context=true, escalate again to cloud with latest VisionStateand History.
Handoff Rules (enforce)
* Local handles: click, type, scroll, hover, navigate when the target is unambiguous (single match ≥ confidence threshold) and no multi-step reasoning required.
* Cloud handles: multi-page flows (checkout/login recovery), price/feature comparisons, disambiguation when multiple similar targets exist, any nontrivial planning.
* Never send images to cloud by default. Send only VisionState JSON; allow an override flag to include a one-off image if cloud explicitly requests it.
Configuration
* Local model: set default local VLM to Llava-Phi3. Provide a single place to swap the model tag/path if needed. (Reference: Llava-Phi3 available via Ollama; supports llama.cpp/GGUF.) OllamaGitHub
* Cloud model: set default to Gemini 2.0 Flash model id available in your SDK (see Google’s model list). Include a config knob to switch to 2.5 Flash/Flash-Lite if quota/rate limits require it. Google AI for Developers
* Rate limiting: implement per-minute cap on cloud calls; prefer batching decisions into short plan lists.
* Logging/Telemetry: store every VisionState (hashed), every action, and planner responses; redact PII in logs.
Acceptance Tests (build these fixtures)
1. Login page: local loop identifies email/password fields; fills and clicks sign-in with no cloud calls.
2. Search + paginate: local executes search term entry and pagination clicks using selector_hint.
3. Comparison flow: force cloud planning to choose between two vendors; verify it returns a 3–5 action plan.
4. Ambiguity: two “Add to cart” buttons; ensure local escalates to cloud.
5. Failure recovery: intentionally break a selector; confirm two local failures → cloud escalation with a revised plan.


Suggested Enhancements
1. Add Visual Diff Optimization


python
# In VisionStateBuilder, add:
"changes_from_last": {
    "elements_added": [...],
    "elements_removed": [...],
    "fields_changed": [...]
}
# This helps cloud understand what happened from last action
1. Cache Local Model Inference


python
# Llava-Phi3 can be slow on CPU
class VisionStateCache:
    def get_or_compute(screenshot_hash, viewport_dims):
        # Cache identical screenshots (common in loading states)
        # Cache similar viewports (minor scroll differences)
1. Add "Interaction Zones"


python
# In VisionState, group nearby elements:
"zones": [
    {
        "type": "form",
        "bbox": [x,y,w,h],
        "element_ids": [0,1,2],  # indices into elements[]
        "completeness": 0.5  # helpful for forms
    }
]
1. Failure Classification


python
# In HandoffManager, classify failures:
failure_types = {
    "element_not_found": escalate_immediately,
    "page_load_timeout": retry_locally,
    "interaction_failed": escalate_after_2,
    "unexpected_page": escalate_immediately
}
1. Batch Planning Mode


python
# When calling cloud, option to get multiple contingent plans:
PlannerResponse = {
    "primary_plan": [...],
    "fallback_if_fail": [...],  # Preemptive fallback
    "checkpoint_after": 3  # Re-evaluate after N steps
}
Implementation Priority
1. Start with VisionStateBuilder - This is your core innovation
2. Get LocalActionHeuristics working for click/type only initially
3. Add CloudPlannerClient with minimal planning first
4. Then add sophistication (confidence, zones, batching)
Critical Success Factor
The selector_hint generation quality will make or break this. Consider:


python
def generate_selector_hint(element, vision_context):
    # Prioritize in order:
    1. Unique visible text: "button:contains('Sign In')"
    2. Aria labels: "[aria-label='Search']"
    3. Position + type: "header button:first"
    4. Visual position: "button near 'Email' field"
    5. Bbox fallback: "element at 400,300"
One Architectural Question
Should VisionState include semantic relationships?


python
"relationships": [
    {"from": 0, "to": 1, "type": "label_for"},
    {"from": 2, "to": 3, "type": "error_message_for"}
]
This would help the cloud model understand form structures better.
