# SalesCode.ai Challenge: Voice Interruption Handling

This repository contains our submission for the SalesCode.ai Final Round Qualifier. It details the implementation of an intelligent interruption filter for the `livekit-plugins-nvidia` STT (Speech-to-Text) plugin.

-----

## 1\. Project Overview

The goal of this project was to enhance a real-time conversational AI agent to handle user interruptions more naturally. The default behavior, where any user sound (including simple fillers like "uh" or "umm") pauses the agent, leads to a disjointed and unnatural conversational flow.

Our solution implements a modular filtering layer that intercepts STT transcripts. This layer is context-aware (it knows if the agent is speaking) and intelligently decides whether to **ignore** a user's filler word or **forward** a genuine interruption, all without adding any perceptible latency.

## 2\. The Challenge: Problem Statement

[cite\_start]As defined in the challenge[cite: 8], the core problem is that LiveKit's default Voice Activity Detection (VAD) logic is too sensitive. [cite\_start]It pauses the agent's Text-to-Speech (TTS) on *any* user sound, including common fillers like "uh", "umm", "hmm", and "haan"[cite: 7]. [cite\_start]This results in "false interruptions" that break the flow of conversation[cite: 7].

The objective was to build an extension layer that:

  * [cite\_start]**Ignores** a configurable list of filler words, but *only* when the agent is currently speaking[cite: 10].
  * [cite\_start]**Registers** those same filler words as valid speech if the agent is quiet[cite: 11].
  * [cite\_start]**Immediately stops** the agent for genuine interruptions like "wait" or "stop"[cite: 12].
  * [cite\_start]Is implemented **without modifying core SDK code**[cite: 25].
  * [cite\_start]Is **modular and configurable**[cite: 14, 26].

## 3\. Our Solution: Implementation Details

To meet these requirements, we implemented a clean, modular solution that consists of two main parts.

### 3.1. Modular Filter Design (`livekit_interrupt_filter.py`)

First, we created a new, standalone Python module named `livekit_interrupt_filter.py`. This module contains all the core filtering logic, keeping it separate from the plugin's internal code. This makes the solution clean, easy to maintain, and testable.

This module provides two key helper functions:

1.  **`is_filler_only(text, ...)`:** Checks if a given transcript is on a pre-defined list of fillers (e.g., "uh", "umm", "hmm").
2.  **`contains_command(text)`:** Checks if a transcript contains a high-priority interruption command (e.g., "stop", "wait") *anywhere* in the string. This is crucial for handling "fast turn-taking" like *"umm, okay stop"*.

### 3.2. NVIDIA Plugin Integration (`stt.py`)

Second, we modified the `livekit-plugins-nvidia/livekit/plugins/nvidia/stt.py` file to integrate this filter.

1.  **Accepting Agent State:** We upgraded the `STT.stream()` and `SpeechStream.__init__()` methods to accept the `get_agent_speaking` callable. This was a critical change to make our filter context-aware, allowing it to get the agent's real-time speaking status from the `AgentSession`.

2.  **Filter Logic Injection:** We injected our filter logic directly into the `_handle_response` method, which is called for every STT transcript. The new logic flow is as follows:

      * An STT transcript (e.g., "umm") is received.
      * The filter checks: `is_agent_speaking()`?
      * **If `True` (Agent is speaking):**
          * Check: `contains_command(text)`? If `True`, the transcript is **FORWARDED**.
          * Else Check: `is_filler_only(text)`? If `True`, the transcript is **IGNORED**.
      * **If `False` (Agent is quiet):**
          * The transcript (even "umm") is **FORWARDED** as normal.

3.  **Key Bug Fix (`START_OF_SPEECH`):** We identified and fixed a race condition. The original code sent the `START_OF_SPEECH` event *before* our filter ran. This would cause the agent to pause, even if the filter ignored the transcript a millisecond later. We moved the `START_OF_SPEECH` event to fire *after* the filter has confirmed the transcript is valid.

-----

## 4\. Validation & Testing

To prove our solution's correctness and robustness, we developed a local, automated test script: `test_my_filter.py`.

This approach was chosen because it:

  * Requires **zero API keys** or network access.
  * Is **100% reproducible** by the evaluation team.
  * Directly tests the filter logic in isolation, providing clear, pass/fail results for every scenario.

### 4.1. Test Scenarios

Our script validates all 5 key scenarios derived from the challenge PDF:

1.  **Agent Speaking + Filler:** `(Agent: SPEAKING, User: 'hmm')` -\> **Expected: IGNORE**
2.  **Agent Speaking + Command:** `(Agent: SPEAKING, User: 'wait one second')` -\> **Expected: FORWARD**
3.  **Agent Quiet + Filler:** `(Agent: QUIET, User: 'umm')` -\> **Expected: FORWARD**
4.  **Agent Speaking + Mixed Command:** `(Agent: SPEAKING, User: 'umm okay stop')` -\> **Expected: FORWARD**
5.  **Agent Speaking + Low-Confidence Filler:** `(Agent: SPEAKING, User: 'uh' conf=0.10)` -\> **Expected: IGNORE**

### 4.2. Test Results (Reproducible)

The output below confirms that our solution **passes all 5 scenarios**. The `[INTERRUPT_FILTER]` debug logs clearly show the filter's decision-making process, satisfying the "log ignored and valid interruptions separately" requirement.

```bash
(agents) C:\Desktop\agents>python test_my_filter.py
--- 🧪 Starting Interrupt Filter Test ---
INFO:livekit.plugins.nvidia.stt:Initializing NVIDIA STT with model: parakeet-1.1b-en-US-asr-streaming-silero-vad-sortformer, server: grpc.nvcf.nvidia.com:443
DEBUG:livekit.plugins.nvidia.stt:Function ID: 1598d209-5e27-4d3c-8079-4751568b1081, Language: en-US, Sample rate: 16000

[SCENARIO 1] Agent: SPEAKING, User: 'hmm'
DEBUG:livekit.plugins.nvidia.stt:[INTERRUPT_FILTER] IGNORED_FILLER: 'hmm' conf=0.90 speaking=True
✅ PASS: Event was correctly IGNORED.

[SCENARIO 2] Agent: SPEAKING, User: 'wait one second'
DEBUG:livekit.plugins.nvidia.stt:[INTERRUPT_FILTER] FORWARDED: 'wait one second' is_final=True speaking=True
✅ PASS: Event was correctly FORWARDED.

[SCENARIO 3] Agent: QUIET, User: 'umm'
DEBUG:livekit.plugins.nvidia.stt:[INTERRUPT_FILTER] FORWARDED: 'umm' is_final=False speaking=False
✅ PASS: Event was correctly FORWARDED.

[SCENARIO 4] Agent: SPEAKING, User: 'umm okay stop'
DEBUG:livekit.plugins.nvidia.stt:[INTERRUPT_FILTER] FORWARDED: 'umm okay stop' is_final=True speaking=True
✅ PASS: Mixed command was correctly FORWARDED.

[SCENARIO 5] Agent: SPEAKING, User: 'uh' (Low Confidence)
DEBUG:livekit.plugins.nvidia.stt:[INTERRUPT_FILTER] IGNORED_FILLER: 'uh' conf=0.10 speaking=True
✅ PASS: Low-confidence filler was correctly IGNORED.

--- 🏁 Test Complete ---
```

-----

## 5\. How to Reproduce Our Results

1.  **Install Dependencies:**

      * Ensure you are in the project's Conda environment (`agents`).
      * Make sure the local packages are installed in editable mode:
        ```bash
        pip install -e .
        pip install -e livekit-agents
        ```

2.  **Run the Validation Script:**

      * From the root `C:\Desktop\agents` directory, run:
        ```bash
        python test_my_filter.py
        ```

-----

## 6\. Environment Details

  * **Python:** 3.11 (via Anaconda)
  * **Main Dependencies:** `livekit-agents`, `livekit-plugins-nvidia` (installed from the repo in editable mode).
  * **Testing:** No API keys or external services are required to run the `test_my_filter.py` validation script.