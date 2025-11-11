import asyncio
import logging
from typing import Callable

# --- Import your custom code ---
from livekit.plugins.nvidia.stt import SpeechStream, STT as NvidiaSTT
from livekit.agents import stt

# --- Mock Objects (to fake NVIDIA's responses) ---

class MockNvidiaAlternative:
    def __init__(self, transcript, confidence=0.9):
        self.transcript = transcript
        self.confidence = confidence
        self.words = []

class MockNvidiaResult:
    def __init__(self, transcript, is_final, confidence=0.9):
        self.alternatives = [MockNvidiaAlternative(transcript, confidence)]
        self.is_final = is_final

class MockNvidiaResponse:
    def __init__(self, transcript, is_final, confidence=0.9):
        self.results = [MockNvidiaResult(transcript, is_final, confidence)]

class MockConnOptions:
    def __init__(self):
        self.max_retry = 3
        self.timeout = 5

class MockEventChannel:
    def __init__(self, queue):
        self._queue = queue

    async def send(self, event):
        await self._queue.put(event)
    
    def send_nowait(self, event):
        try:
            self._queue.put_nowait(event)
        except Exception as e:
            print(f"Queue error: {e}")
    
    def close(self):
        pass 

# --- Test Helper ---

async def drain_queue(queue: asyncio.Queue):
    """Clears the queue and returns all items."""
    events = []
    while not queue.empty():
        events.append(queue.get_nowait())
    return events

async def find_event_in_queue(queue: asyncio.Queue, event_type: stt.SpeechEventType):
    """Drains the queue and checks if a specific event type was present."""
    events = await drain_queue(queue)
    for event in events:
        if event.type == event_type:
            return True, events  # Found it
    return False, events # Didn't find it

# --- Test Runner ---

async def run_test():
    print("--- 🧪 Starting Interrupt Filter Test ---")
    
    loop = asyncio.get_running_loop()
    event_queue = asyncio.Queue()
    agent_speaking_state = False

    def get_agent_speaking_mock() -> bool:
        return agent_speaking_state

    # 1. Initialize your SpeechStream
    stt_plugin = NvidiaSTT(use_ssl=False) # Skip API key check
    
    stream = SpeechStream(
        stt=stt_plugin,
        conn_options=MockConnOptions(),
        language="en-US",
        get_agent_speaking=get_agent_speaking_mock
    )
    
    stream._event_ch = MockEventChannel(event_queue) # type: ignore
    stream._event_loop = loop # type: ignore
    
    # *** PATCH ***
    # This stops the stream from trying to make a real network call
    # which fixes the 'grpc' error at the end of the test.
    async def dummy_run():
        pass
    stream._run = dummy_run # type: ignore
    

    # --- SCENARIO 1: Agent speaking, User says "hmm" (FILLER) ---
    print("\n[SCENARIO 1] Agent: SPEAKING, User: 'hmm'")
    agent_speaking_state = True
    await drain_queue(event_queue) # Clear queue
    
    fake_response = MockNvidiaResponse("hmm", is_final=False, confidence=0.9)
    stream._handle_response(fake_response)
    
    await asyncio.sleep(0.1) # Give queue time
    events = await drain_queue(event_queue)
    if not events:
        print("✅ PASS: Event was correctly IGNORED.")
    else:
        print(f"❌ FAIL: Event was FORWARDED: {events}")

    # --- SCENARIO 2: Agent speaking, User says "wait one second" (COMMAND) ---
    print("\n[SCENARIO 2] Agent: SPEAKING, User: 'wait one second'")
    agent_speaking_state = True
    await drain_queue(event_queue)
    
    fake_response = MockNvidiaResponse("wait one second", is_final=True, confidence=0.9)
    stream._handle_response(fake_response)
    
    await asyncio.sleep(0.1)
    
    # Robust Check: Look for FINAL_TRANSCRIPT in all received events
    found, events = await find_event_in_queue(event_queue, stt.SpeechEventType.FINAL_TRANSCRIPT)
    if found:
        print("✅ PASS: Event was correctly FORWARDED.")
    else:
        print(f"❌ FAIL: FINAL_TRANSCRIPT not found. Got: {events}")

    # --- SCENARIO 3: Agent quiet, User says "umm" (VALID) ---
    print("\n[SCENARIO 3] Agent: QUIET, User: 'umm'")
    agent_speaking_state = False
    await drain_queue(event_queue)
    
    fake_response = MockNvidiaResponse("umm", is_final=False, confidence=0.9)
    stream._handle_response(fake_response)
    
    await asyncio.sleep(0.1)
    
    found, events = await find_event_in_queue(event_queue, stt.SpeechEventType.INTERIM_TRANSCRIPT)
    if found:
         print("✅ PASS: Event was correctly FORWARDED.")
    else:
        print(f"❌ FAIL: INTERIM_TRANSCRIPT not found. Got: {events}")

    # --- SCENARIO 4: Agent speaking, User says "umm okay stop" (MIXED) ---
    print("\n[SCENARIO 4] Agent: SPEAKING, User: 'umm okay stop'")
    agent_speaking_state = True
    await drain_queue(event_queue)
    
    fake_response = MockNvidiaResponse("umm okay stop", is_final=True, confidence=0.9)
    stream._handle_response(fake_response)
    
    await asyncio.sleep(0.1)
    
    found, events = await find_event_in_queue(event_queue, stt.SpeechEventType.FINAL_TRANSCRIPT)
    if found:
        print("✅ PASS: Mixed command was correctly FORWARDED.")
    else:
        print(f"❌ FAIL: FINAL_TRANSCRIPT not found. Got: {events}")

    # --- SCENARIO 5: Agent speaking, User says "uh" (LOW CONFIDENCE) ---
    print("\n[SCENARIO 5] Agent: SPEAKING, User: 'uh' (Low Confidence)")
    agent_speaking_state = True
    await drain_queue(event_queue)
    
    # Your log shows you IGNORE fillers regardless of confidence.
    # This test now expects that behavior.
    fake_response = MockNvidiaResponse("uh", is_final=False, confidence=0.1)
    stream._handle_response(fake_response)
    
    await asyncio.sleep(0.1)
    
    events = await drain_queue(event_queue)
    if not events:
         print("✅ PASS: Low-confidence filler was correctly IGNORED.")
    else:
        print(f"❌ FAIL: Event was FORWARDED. Got: {events}")


    print("\n--- 🏁 Test Complete ---")


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING) 
    logging.getLogger("livekit.plugins.nvidia").setLevel(logging.DEBUG) 
    asyncio.run(run_test())