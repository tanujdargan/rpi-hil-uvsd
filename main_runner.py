import argparse
import os
import sys # For sys.exit

from .stm32_flasher import flash_firmware
from .value_emulator import emulate_from_file
from .output_checker import check_output
from .serial_utils import SerialConnection, DEFAULT_SERIAL_PORT, DEFAULT_BAUD_RATE

def main():
    parser = argparse.ArgumentParser(description="HIL Test Runner for STM32.")
    parser.add_argument("--code-to-test", required=True, help="Path to the STM32 firmware file (.bin or .hex) to flash and test.")
    parser.add_argument("--input-values", required=True, help="Path to the JSON file defining input values for emulation.")
    parser.add_argument("--expected-values", help="Path to the JSON file defining expected output values. If omitted, assumes input values should be echoed by the STM32.")
    
    parser.add_argument("--serial-port", default=DEFAULT_SERIAL_PORT, help=f"Serial port for STM32 communication (default: {DEFAULT_SERIAL_PORT}).")
    parser.add_argument("--baud-rate", type=int, default=DEFAULT_BAUD_RATE, help=f"Baud rate for serial communication (default: {DEFAULT_BAUD_RATE}).")
    parser.add_argument("--skip-flash", action="store_true", help="Skip the flashing step (assumes firmware is already on device).")
    parser.add_argument("--st-flash-cmd", default="st-flash", help="Command for st-flash utility (default: 'st-flash').")
    parser.add_argument("--flash-address", default="0x08000000", help="Flash memory address for st-flash (default: '0x08000000').")


    args = parser.parse_args()

    print("--- HIL Test Run Start ---")
    print(f"Code to Test: {args.code_to_test}")
    print(f"Input Values JSON: {args.input_values}")
    print(f"Expected Values JSON: {args.expected_values if args.expected_values else 'N/A (Echo mode if applicable)'}")
    print(f"Serial Port: {args.serial_port}, Baud Rate: {args.baud_rate}")

    # 1. Flash the STM32 (unless skipped)
    if not args.skip_flash:
        if not os.path.exists(args.code_to_test):
            print(f"Error: Firmware file '{args.code_to_test}' not found. Cannot flash.")
            sys.exit(1)
        print("\n--- Step 1: Flashing STM32 ---")
        if not flash_firmware(args.code_to_test, stlink_command=args.st_flash_cmd, address=args.flash_address):
            print("STM32 flashing failed. Aborting test.")
            sys.exit(1)
        print("Flashing successful.")
    else:
        print("\n--- Step 1: Flashing STM32 (Skipped) ---")

    # 2. Initialize Serial and Emulate Inputs
    # Using 'with' statement for automatic connection/disconnection and signal handling
    try:
        with SerialConnection(port=args.serial_port, baudrate=args.baud_rate) as ser_conn:
            print("\n--- Step 2: Emulating Input Values ---")
            # Ensure serial connection was successful within the 'with' block context
            if not ser_conn.ser or not ser_conn.ser.is_open:
                 raise ConnectionError("Serial connection failed to establish properly in 'with' block.")

            input_data_parsed = emulate_from_file(args.input_values, ser_conn)
            if input_data_parsed is None:
                print("Input emulation failed. Aborting test.")
                sys.exit(1)

            # 3. Receive Output from STM32
            print("\n--- Step 3: Receiving Output from STM32 ---")
            # Determine overall timeout and stop condition for reading response
            # These could come from expected_values.json if provided
            overall_read_timeout_s = 5 # Default
            stop_line = None
            if args.expected_values and os.path.exists(args.expected_values):
                try:
                    with open(args.expected_values, 'r') as ef:
                        expected_json_content = json.load(ef)
                    overall_read_timeout_s = expected_json_content.get("response_timeout_ms", 5000) / 1000.0
                    stop_line = expected_json_content.get("stop_condition_line")
                except Exception as e:
                    print(f"Warning: Could not read timeout/stop_condition from expected values file: {e}")
            
            print(f"Waiting for STM32 response (Timeout: {overall_read_timeout_s}s, Stop Line: '{stop_line}')...")
            received_lines = ser_conn.read_all_lines(overall_timeout_seconds=overall_read_timeout_s, stop_condition_line=stop_line)
            
            if not received_lines:
                print("No response received from STM32.")
            else:
                print(f"Received {len(received_lines)} lines from STM32.")

            # 4. Check Output
            print("\n--- Step 4: Checking Output ---")
            test_passed = check_output(received_lines, args.expected_values, input_data_parsed, ser_conn)

            print("\n--- HIL Test Run End ---")
            if test_passed:
                print("Overall Test Result: PASSED")
                sys.exit(0)
            else:
                print("Overall Test Result: FAILED")
                sys.exit(1)

    except ConnectionError as e: # Catch connection errors from SerialConnection.__enter__
        print(f"Serial Connection Error: {e}. Aborting test.")
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred during the test run: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(2)


if __name__ == "__main__":
    main()