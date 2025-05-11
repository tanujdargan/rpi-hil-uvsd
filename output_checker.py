import json
import re
from .serial_utils import SerialConnection # For type hinting if needed, not direct use here

def check_output(received_lines: list, expected_json_path: str = None, 
                 input_data_for_fallback: dict = None, serial_conn: SerialConnection = None):
    """
    Checks the received serial lines against expected values defined in a JSON file
    or falls back to input=output echo mode if expected_json_path is not provided.

    Args:
        received_lines (list): A list of strings received from the STM32.
        expected_json_path (str, optional): Path to the JSON file defining expected outputs.
        input_data_for_fallback (dict, optional): Parsed input JSON data, used if expected_json_path is None.
        serial_conn (SerialConnection, optional): The serial connection, used to get more lines if needed by stop_condition.

    Returns:
        bool: True if all checks pass, False otherwise.
    """
    print("\n--- Output Checking ---")
    expected_data = None
    is_echo_mode = False

    if expected_json_path:
        try:
            with open(expected_json_path, 'r') as f:
                expected_data = json.load(f)
            print(f"Loaded expected values from: {expected_json_path}")
        except FileNotFoundError:
            print(f"Warning: Expected values JSON file not found at '{expected_json_path}'.")
            if not input_data_for_fallback:
                print("Error: No expected values file and no input data for fallback. Cannot perform checks.")
                return False
            print("Attempting to use input-as-output (echo) mode based on fallback data.")
            is_echo_mode = True
        except json.JSONDecodeError as e:
            print(f"Error: Could not decode Expected JSON file '{expected_json_path}': {e}")
            return False
    elif input_data_for_fallback:
        print("No expected values file provided. Using input-as-output (echo) mode.")
        is_echo_mode = True
    else:
        print("Error: No expected values provided (neither file nor fallback data). Cannot perform checks.")
        return False

    if is_echo_mode:
        # Try to derive expected outputs from input_data_for_fallback
        if input_data_for_fallback.get("echo_payloads"):
            expected_outputs_list = input_data_for_fallback["echo_payloads"]
        elif input_data_for_fallback.get("emulation_sequence"):
            # Basic fallback: expect echoes of 'send_serial_line' payloads
            expected_outputs_list = [
                action["payload"] for action in input_data_for_fallback["emulation_sequence"]
                if action.get("type") == "send_serial_line" and "payload" in action
            ]
            if not expected_outputs_list:
                print("Error (Echo Mode): Could not derive expected echo outputs from input data.")
                return False
        else:
            print("Error (Echo Mode): Input data does not contain 'echo_payloads' or usable 'emulation_sequence'.")
            return False
        
        # Convert this to the standard expected_responses format for the checker logic
        expected_data = {
            "test_name": input_data_for_fallback.get("test_name", "Echo Test") + " (Echo Mode)",
            "expected_responses": [
                {"response_id": f"echo_resp_{i}", "type": "exact_line", "value": str(val)}
                for i, val in enumerate(expected_outputs_list)
            ]
        }
        print(f"Echo Mode: Expecting {len(expected_outputs_list)} lines to be echoed.")

    if not expected_data or not expected_data.get("expected_responses"):
        print("No expected responses defined to check against. Marking as PASSED by default (vacuously true).")
        return True # Or False, depending on desired strictness for empty expectations

    # --- Start actual checking ---
    expected_responses = expected_data.get("expected_responses", [])
    
    overall_pass = True
    num_expected = len(expected_responses)
    num_received = len(received_lines)
    
    print(f"Expected {num_expected} response items. Received {num_received} lines.")
    print("Received Lines:")
    for i, line in enumerate(received_lines):
        print(f"  [{i}]: \"{line}\"")
    
    expected_idx = 0
    received_idx = 0
    
    results_log = []

    while expected_idx < num_expected and received_idx < num_received:
        expected_item = expected_responses[expected_idx]
        current_received_line = received_lines[received_idx]

        resp_id = expected_item.get("response_id", f"exp{expected_idx}")
        exp_type = expected_item.get("type")
        exp_value = expected_item.get("value") # For exact/contains
        exp_pattern = expected_item.get("pattern") # For regex
        exp_ignore_count = expected_item.get("count") # For ignore_line_count

        match = False
        consumed_received_line = True # Most types consume one received line

        log_entry = f"  Checking Exp[{expected_idx}] ('{resp_id}', Type: {exp_type})"
        
        if exp_type == "exact_line":
            if current_received_line == exp_value:
                match = True
            log_entry += f" vs Rec[{received_idx}] ('{current_received_line}'). Expected: '{exp_value}'."
        elif exp_type == "contains_string":
            if exp_value in current_received_line:
                match = True
            log_entry += f" vs Rec[{received_idx}] ('{current_received_line}'). Expected to contain: '{exp_value}'."
        elif exp_type == "regex_match":
            try:
                if re.search(exp_pattern, current_received_line):
                    match = True
            except re.error as e:
                log_entry += f" - Regex error: {e}."
                match = False # Error in pattern
            log_entry += f" vs Rec[{received_idx}] ('{current_received_line}'). Expected regex: '{exp_pattern}'."
        elif exp_type == "ignore_line_count":
            # This type always "matches" its condition of ignoring.
            # It effectively advances received_idx by 'count'.
            log_entry += f" - Ignoring {exp_ignore_count} lines."
            match = True 
            consumed_received_line = False # Does not consume the *current* line for matching itself
            
            # Check if enough lines are left to ignore
            if received_idx + exp_ignore_count <= num_received:
                log_entry += f" (Ignored Rec[{received_idx}] to Rec[{received_idx + exp_ignore_count -1}])."
                received_idx += exp_ignore_count # Advance received index
            else:
                log_entry += f" - Not enough lines left to ignore {exp_ignore_count}. Only {num_received - received_idx} available. FAILED."
                match = False # Cannot fulfill ignore if not enough lines
                received_idx = num_received # Consume all remaining
            expected_idx += 1 # Move to next expected item
            results_log.append(log_entry + (" PASSED (ignored)" if match else " FAILED"))
            if not match: overall_pass = False
            continue # Skip normal increment
        else:
            log_entry += f" - Unknown expected type '{exp_type}'. FAILED."
            match = False
            overall_pass = False # Critical error in test definition

        if match:
            log_entry += " PASSED."
            expected_idx += 1
            if consumed_received_line:
                received_idx += 1
        else:
            log_entry += " FAILED."
            overall_pass = False
            # Decide on failure strategy: stop on first fail, or try to match subsequent?
            # For now, strict: if an expected item isn't found, subsequent matches are harder to align.
            # A more resilient strategy would try to find the current expected_item further down received_lines.
            # For simplicity: advance received_idx to see if the *next* expected matches *this* received.
            # This means this current received line did not match the current expected.
            if consumed_received_line: # Only advance if current line was "used" for the check
                 received_idx += 1 
            # To make it stricter, we could break here or only increment expected_idx if match.
            # For now, this allows an expected item to be "missed" and we still check later ones.
            # But if an expected item is critical, this might not be desired.

        results_log.append(log_entry)

    # After loop, check if all expected items were processed
    if expected_idx < num_expected:
        results_log.append(f"  FAIL: Not all expected responses were matched. Expected {num_expected}, matched {expected_idx}.")
        overall_pass = False
        for i in range(expected_idx, num_expected):
             results_log.append(f"    Missed expected item: ID '{expected_responses[i].get('response_id', 'N/A')}', Type '{expected_responses[i].get('type')}'")


    # Optionally, check if there are unprocessed received lines (STM32 sent more than expected)
    # This might be an error or just verbose output, depending on test strictness.
    if received_idx < num_received and overall_pass: # Only a warning if other tests passed
        results_log.append(f"  Warning: {num_received - received_idx} additional lines received from STM32 that were not checked.")
        for i in range(received_idx, num_received):
            results_log.append(f"    Unchecked Rec[{i}]: \"{received_lines[i]}\"")

    print("\nDetailed Check Results:")
    for log in results_log:
        print(log)

    print(f"\nOutput Checking Summary: {'PASSED' if overall_pass else 'FAILED'}")
    return overall_pass