# Expected Values JSON Format Documentation

The Expected Values JSON file defines the anticipated responses from the STM32 device, which will be used to verify the test outcome.

## Root Object

The root of the JSON object should contain the following fields:

-   `test_name` (string, optional): Should match the `test_name` in the input values JSON for consistency.
-   `expected_responses` (array, required): An array of response objects that define the expected data from the STM32.
-   `response_timeout_ms` (integer, optional, default: 5000): Maximum time (in milliseconds) to wait for all expected responses to be received. The listening for responses begins after all emulation inputs have been sent.
-   `stop_condition_line` (string, optional): A specific string that, if received from the STM32, signifies the end of its response sequence, even if not all `expected_responses` have been matched. This can be useful for tests where the STM32 explicitly signals completion.

## Response Object

Each object in the `expected_responses` array defines an expected piece of data.

-   `response_id` (string, required): A unique identifier for this expected response (e.g., "resp1", "temp_reading").
-   `input_action_id_ref` (string, optional): References the `action_id` from the input values JSON that this response is primarily related to. Useful for context.
-   `type` (string, required): The type of matching to perform. Supported types:
    -   `exact_line`: The received serial line must exactly match the `value` string (after stripping leading/trailing whitespace).
    -   `contains_string`: The received serial line must contain the `value` string.
    -   `regex_match`: The received serial line must match the `pattern` (regular expression string).
    -   `ignore_line_count`: Skips a specified number of lines. Useful if the device sends preamble or non-critical data.
-   `description` (string, optional): A human-readable description of what this response represents.

### Type-Specific Fields:

#### For `exact_line` and `contains_string`:
-   `value` (string, required): The string value to match or find.

#### For `regex_match`:
-   `pattern` (string, required): The regular expression pattern.

#### For `ignore_line_count`:
-   `count` (integer, required): The number of lines to ignore.

## Important Considerations:

-   **Order:** The `output_checker` will typically attempt to match received lines against the `expected_responses` in the order they are defined.
-   **Flexibility:** If the STM32 might send additional debug lines between expected responses, the matching logic might need to be robust (e.g., iterate through received lines to find the next expected response, rather than strict sequential matching). The `ignore_line_count` can help with predictable extra lines.

## Example Expected Values JSON:

```json
{
  "test_name": "Sensor Reading Test - Expected Outputs",
  "response_timeout_ms": 10000,
  "stop_condition_line": "TEST_CYCLE_COMPLETE",
  "expected_responses": [
    {
      "response_id": "resp_ack_wake",
      "input_action_id_ref": "step1_wake_sensor",
      "type": "exact_line",
      "value": "SENSOR_AWAKE_ACK",
      "description": "Acknowledgement that sensor is awake."
    },
    {
      "response_id": "resp_temp_value",
      "input_action_id_ref": "step3_request_temp",
      "type": "regex_match",
      "pattern": "^TEMP:-?\\\\d+\\\\.\\\\d+C$",
      "description": "Temperature reading in format TEMP:XX.XC"
    },
    {
      "response_id": "resp_raw_data_block_start",
      "input_action_id_ref": "step4_request_raw_data",
      "type": "contains_string",
      "value": "RAW_DATA_START",
      "description": "Start of raw data block signal."
    },
    {
      "response_id": "resp_ignore_data_lines",
      "type": "ignore_line_count",
      "count": 5,
      "description": "Ignore 5 lines of raw data payload."
    },
    {
      "response_id": "resp_raw_data_block_end",
      "type": "exact_line",
      "value": "RAW_DATA_END",
      "description": "End of raw data block signal."
    }
  ]
}