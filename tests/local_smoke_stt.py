# tests/local_smoke_stt.py (updated)
import sys
from pathlib import Path

# Ensure repo root on sys.path
repo_root = Path(__file__).resolve().parents[1]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

# Import package module
from livekit.plugins.nvidia import stt as nvidia_stt_module
import asyncio
from types import SimpleNamespace

SpeechStream = nvidia_stt_module.SpeechStream

# Synchronous event-loop shim: call the callback right away
class ImmediateLoop:
    def call_soon_threadsafe(self, cb, *a, **k):
        cb(*a, **k)

# Minimal fake event channel
class FakeEventCh:
    def send_nowait(self, ev):
        print("EVENT_SENT:", ev)

def make_alt(text, conf=0.95):
    a = SimpleNamespace()
    a.transcript = text
    a.confidence = conf
    a.words = []
    return a

def make_res(alt, is_final=False):
    r = SimpleNamespace()
    r.alternatives = [alt]
    r.is_final = is_final
    return r

# Create SpeechStream object without running its __init__
ss = SpeechStream.__new__(SpeechStream)

# Replace event loop with immediate executor so events are delivered synchronously
ss._event_loop = ImmediateLoop()
ss._event_ch = FakeEventCh()

# Provide get_agent_speaking hook used by your filter logic
# We'll change this between cases
ss._get_agent_speaking = lambda: False

# Helper to show what _convert_to_speech_data returns and filter checks
def inspect_and_handle(text, confidence, is_final):
    alt = make_alt(text, confidence)
    # call _convert_to_speech_data if available
    try:
        speech_data = ss._convert_to_speech_data(alt)
    except Exception as e:
        speech_data = SimpleNamespace(text=text, confidence=confidence, start_time=0.0, end_time=0.0)
    print("\n--- INSPECT ---")
    print("text:", repr(speech_data.text))
    print("confidence:", getattr(speech_data, "confidence", None))
    print("is_final arg:", is_final)
    print("agent_speaking:", ss._get_agent_speaking())
    # If the repo provides livekit_interrupt_filter, show its decisions
    try:
        from livekit_interrupt_filter import is_filler_only, contains_command
        print("is_filler_only:", is_filler_only(speech_data.text, speech_data.confidence))
        print("contains_command:", contains_command(speech_data.text))
    except Exception:
        print("livekit_interrupt_filter not available for inspection")
    # Call the normal handler (this will schedule/send events immediately via ImmediateLoop)
    ss._handle_response(make_res(alt, is_final=is_final))

# CASE 1
print("CASE 1 — agent speaking; filler interim -> should be IGNORED")
ss._get_agent_speaking = lambda: True
inspect_and_handle("uh", 0.95, is_final=False)

# CASE 2
print("\nCASE 2 — agent speaking; contains command final -> should be FORWARDED")
ss._get_agent_speaking = lambda: True
inspect_and_handle("umm okay stop", 0.98, is_final=True)

# CASE 3
print("\nCASE 3 — agent quiet; filler final -> should be FORWARDED")
ss._get_agent_speaking = lambda: False
inspect_and_handle("umm", 0.95, is_final=True)

print("\nSMOKE TEST DONE")
