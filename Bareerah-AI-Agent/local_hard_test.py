import sys
from unittest.mock import MagicMock
import json

# ✅ MOCK DB & LIBRARIES BEFORE IMPORTING main_new
sys.stdout.reconfigure(encoding='utf-8')
sys.modules["psycopg2"] = MagicMock()
sys.modules["psycopg2.pool"] = MagicMock()
sys.modules["psycopg2.extras"] = MagicMock()

# Mock functions in main_new to avoid DB calls during test
import main_new

# Override DB persistence with in-memory dict for testing
mock_db = {}
def mock_save_state(call_sid, state):
    mock_db[call_sid] = state

def mock_load_state(call_sid):
    return mock_db.get(call_sid)

main_new.save_state = mock_save_state
main_new.load_state = mock_load_state
main_new.init_db = MagicMock() # Stop real init

# ✅ TEST RUNNER
def run_hard_test():
    print("🔥 STARTING HARD LOCAL TEST FOR main_new.py")
    print("------------------------------------------------")
    
    call_sid = "TEST_CALL_123"
    
    # 1. Initialize
    initial_state = {
        "flow_step": "customer_name",
        "locked_slots": {},
        "language": "en"
    }
    mock_save_state(call_sid, initial_state)
    
    # SCENARIO: The "Chaos" User
    # 1. User gives name and dropoff, but ignores pickup.
    # 2. User gives pickup but ambiguous time.
    # 3. User changes dropoff.
    # 4. User adds passengers/bags.
    # 5. User confirms.
    
    conversation_steps = [
        "Hi, I am Sarah and I want to go to Dubai Mall.", 
        "Pickup from Marina.",
        "Tomorrow at 5 PM.",
        "Wait, actually change dropoff to Mall of Emirates.",
        "Just me, 2 bags, and I want a BMW.",
        "Yes, confirm it."
    ]
    
    print(f"INITIAL STATE: {json.dumps(initial_state['locked_slots'], indent=2)}\n")

    for i, user_text in enumerate(conversation_steps):
        print(f"🗣️ USER SAYS: '{user_text}'")
        
        # Load current state
        state = mock_load_state(call_sid)
        
        # Determine intent/slots via NLU (REAL CALL TO OPENAI)
        # We are testing the ACTUAL NLU Prompt logic in main_new
        print("   ... AI is thinking ...")
        nlu_result = main_new.process_nlu(user_text, state)
        
        # Simulate the logic inside handle_new
        extracted = nlu_result.get("extracted", {})
        response = nlu_result.get("response")
        
        # Update State
        for slot, val in extracted.items():
            if val:
                state["locked_slots"][slot] = val
                
        # Save back
        mock_save_state(call_sid, state)
        
        print(f"🤖 AI RESPONDS: \"{response}\"")
        print(f"📝 LOCKED INFO: {state['locked_slots']}")
        print("------------------------------------------------")

    print("✅ TEST COMPLETE - Check the flow above to ensure no loops occurred.")

if __name__ == "__main__":
    run_hard_test()
