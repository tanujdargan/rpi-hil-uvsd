# Input Values JSON Format Documentation

The Input Values JSON file defines the sequence of actions the Raspberry Pi will perform to emulate inputs to the STM32 device.

## Root Object

The root of the JSON object should contain the following fields:

-   `test_name` (string, optional): A descriptive name for the test.
-   `emulation_sequence` (array, required): An array of action objects that define the steps for emulation.

## Action Object

Each object in the `emulation_sequence` array defines a single action. All action objects must have:

-   `action_id` (string, required): A unique identifier for this action step (e.g., "step1", "send_init_command").
-   `type` (string, required): Specifies the type of emulation action. Supported types are:
    -   `send_serial_line`: Sends a string payload over the serial port, followed by a newline character (`\n`).
    -   `send_serial_bytes`: Sends a raw byte string payload over the serial port. The payload should be a hex string.
    -   `delay_ms`: Pauses execution for a specified number of milliseconds.
-   `description` (string, optional): A human-readable description of the action.

### Type-Specific Fields:

#### For `send_serial_line`:
-   `payload` (string, required): The string to send. A newline character will be appended automatically.

#### For `send_serial_bytes`:
-   `payload_hex` (string, required): A string of hexadecimal characters representing the bytes to send (e.g., "AABB0011").

#### For `delay_ms`:
-   `duration` (integer, required): The delay duration in milliseconds.


## Example Input JSON:

```json
{
  "test_name": "Sensor Reading Test",
  "emulation_sequence": [
    {
      "action_id": "step1_wake_sensor",
      "type": "send_serial_line",
      "payload": "SENSOR_WAKE",
      "description": "Send wake-up command to the sensor via STM32."
    },
    {
      "action_id": "step2_wait_for_wake",
      "type": "delay_ms",
      "duration": 200,
      "description": "Wait for the sensor to initialize."
    },
    {
      "action_id": "step3_request_temp",
      "type": "send_serial_line",
      "payload": "GET_TEMP",
      "description": "Request temperature reading."
    },
    {
      "action_id": "step4_request_raw_data",
      "type": "send_serial_bytes",
      "payload_hex": "01A3FF",
      "description": "Request raw sensor data block."
    }
  ]
}

## Simple Echo Test:

```json
{
  "test_name": "Simple Echo Test",
  "echo_payloads": [ // For direct input-as-output comparison
    "HELLO",
    "STM32",
    "ECHO THIS"
  ],
  "emulation_sequence": [ // Still needed to actually send these
    {
      "action_id": "echo1",
      "type": "send_serial_line",
      "payload": "HELLO"
    },
    {
      "action_id": "echo2",
      "type": "send_serial_line",
      "payload": "STM32"
    },
    {
      "action_id": "echo3",
      "type": "send_serial_line",
      "payload": "ECHO THIS"
    }
  ]
}