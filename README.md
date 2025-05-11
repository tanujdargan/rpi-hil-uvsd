# HIL Tester CLI Tool

This command-line tool facilitates Hardware-in-the-Loop (HIL) testing for STM32 microcontrollers using a Raspberry Pi. It automates flashing firmware, emulating input values via serial communication, and checking the STM32's output against expected results.

## Features

-   Firmware flashing to STM32 (via `st-link`).
-   Input emulation based on a flexible JSON format (serial commands, delays).
-   Output verification against expected values defined in JSON.
-   Support for "echo mode" testing (input = output) if expected values are not specified.
-   Configurable serial port, baud rate, and flashing parameters.

## Prerequisites

-   Raspberry Pi with Raspberry Pi OS (or similar Linux).
-   STM32 board connected to the RPi via ST-Link (for flashing) and USB-UART (for serial communication).
-   **Python 3.7+** installed on the RPi.
-   **pyserial** library: `pip3 install pyserial`
-   **stlink-tools**: `sudo apt install stlink-tools` (provides `st-flash` utility). Ensure `st-flash` is in your system's PATH.

## Directory Structure

```
hil_tester_cli/
├── main_test_runner.py       # Main CLI script
├── stm32_flasher.py          # Module for flashing STM32
├── value_emulator.py         # Module for input emulation
├── output_checker.py         # Module for output checking
├── serial_utils.py           # Serial communication utilities
├── schemas/                  # Documentation for JSON formats
│   ├── input_values_format.md
│   └── expected_values_format.md
└── README_cli_tool.md        # This README
```

## JSON Formats

Please refer to the following documents for details on the JSON structures:

-   `schemas/input_values_format.md`: For defining the input emulation sequence.
-   `schemas/expected_values_format.md`: For defining the expected outputs from the STM32.

## Usage

The main script is `main_test_runner.py`.

```bash
python3 main_test_runner.py --code-to-test <path_to_firmware.bin> \
                            --input-values <path_to_input.json> \
                            [--expected-values <path_to_expected.json>] \
                            [OPTIONS]
```

### Command-Line Arguments:

-   `--code-to-test FILE_PATH` (required): Path to the STM32 firmware file (.bin or .hex).
-   `--input-values INPUT_JSON_PATH` (required): Path to the JSON file defining input values for emulation.
-   `--expected-values EXPECTED_JSON_PATH` (optional): Path to the JSON file defining expected output values. If omitted, the tool attempts an "echo mode" where it expects the STM32 to echo back the payloads sent via `send_serial_line` actions (or specified `echo_payloads` in the input JSON).
-   `--serial-port PORT` (optional): Serial port for STM32 communication (default: `/dev/ttyACM0`).
-   `--baud-rate RATE` (optional): Baud rate for serial communication (default: `115200`).
-   `--skip-flash` (optional flag): If set, skips the firmware flashing step.
-   `--st-flash-cmd CMD` (optional): The command for the `st-flash` utility (default: `st-flash`).
-   `--flash-address ADDR` (optional): Flash memory address for `st-flash` (default: `0x08000000`).

### Example:

```bash
# Create example input.json
cat << EOF > example_input.json
{
  "test_name": "Simple STM32 Echo Test",
  "emulation_sequence": [
    {
      "action_id": "send1",
      "type": "send_serial_line",
      "payload": "HELLO_STM32"
    },
    {
      "action_id": "wait1",
      "type": "delay_ms",
      "duration": 100
    },
    {
      "action_id": "send2",
      "type": "send_serial_line",
      "payload": "TESTING_123"
    }
  ],
  "echo_payloads": ["HELLO_STM32", "TESTING_123"] 
}
EOF

# Assume stm32_firmware.bin exists and is programmed to echo serial lines
# Run in echo mode (no --expected-values)
python3 main_test_runner.py --code-to-test stm32_firmware.bin \
                            --input-values example_input.json

# Create example_expected.json
cat << EOF > example_expected.json
{
  "test_name": "Simple STM32 Echo Test - Expected",
  "expected_responses": [
    {
      "response_id": "echo_resp1",
      "type": "exact_line",
      "value": "STM32_ECHO:HELLO_STM32"
    },
    {
      "response_id": "echo_resp2",
      "type": "exact_line",
      "value": "STM32_ECHO:TESTING_123"
    }
  ],
  "response_timeout_ms": 2000,
  "stop_condition_line": "ECHO_TEST_DONE"
}
EOF

# Run with explicit expected values (STM32 firmware would need to send "STM32_ECHO:" prefix and "ECHO_TEST_DONE")
python3 main_test_runner.py --code-to-test stm32_firmware.bin \
                            --input-values example_input.json \
                            --expected-values example_expected.json
```

## Exit Codes

-   `0`: All tests passed.
-   `1`: Test failure (e.g., output mismatch, flashing error, serial error).
-   `2`: Unexpected error during script execution.

## Notes on STM32 Firmware:

-   The STM32 firmware should be configured to communicate over UART at the specified baud rate.
-   For serial input, it should typically read line by line (e.g., until a newline `\n` character).
-   It should `printf` or send its responses back over the same UART, with each distinct piece of information ideally on a new line.

```