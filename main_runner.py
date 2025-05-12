# hil_tester_cli/main_test_runner.py
import argparse
import os
import sys
import json # For loading expected_values to get reception_mode

from .stm32_flasher import flash_firmware
from .pin_emulator import emulate_hw_pins_from_file
from .output_checker import check_output
from .serial_receiver import SerialReceiver, DEFAULT_SERIAL_PORT, DEFAULT_BAUD_RATE
from .gpio_controller import GPIOController # For HW pin emulation

def main():
    parser = argparse.ArgumentParser(description="HIL Test Runner for STM32 with Hardware Pin Emulation.")
    parser.add_argument("--code-to-test", required=True, help="Path to STM32 firmware (.bin/.hex).")
    parser.add_argument("--input-values", required=True, help="Path to JSON for hardware input actions.")
    parser.add_argument("--expected-values", required=True, help="Path to JSON for expected serial output.")
    
    parser.add_argument("--serial-port", default=DEFAULT_SERIAL_PORT, help=f"Serial port (default: {DEFAULT_SERIAL_PORT}).")
    parser.add_argument("--baud-rate", type=int, default=DEFAULT_BAUD_RATE, help=f"Baud rate (default: {DEFAULT_BAUD_RATE}).")
    parser.add_argument("--skip-flash", action="store_true", help="Skip flashing.")
    parser.add_argument("--st-flash-cmd", default="st-flash", help="st-flash command (default: 'st-flash').")
    parser.add_argument("--flash-address", default="0x08000000", help="Flash address (default: '0x08000000').")
    parser.add_argument("--gpio-mode", default="BCM", choices=["BCM", "BOARD"], help="GPIO pin numbering mode (BCM or BOARD, default: BCM).")


    args = parser.parse_args()
    print("--- HIL Test Run (Hardware Pin Emulation) Start ---")
    # ... (print args)

    # 1. Flash STM32
    if not args.skip_flash:
        # ... (flashing logic - no change from before)
        print("\n--- Step 1: Flashing STM32 ---")
        if not flash_firmware(args.code_to_test, stlink_command=args.st_flash_cmd, address=args.flash_address):
            print("STM32 flashing failed. Aborting test.")
            sys.exit(1)
        print("Flashing successful. Adding a short delay for STM32 to reset/boot...")
        time.sleep(2) # Delay for STM32 to boot up after flash
    else:
        print("\n--- Step 1: Flashing STM32 (Skipped) ---")


    # Initialize GPIO Controller for pin emulation
    # This will also handle GPIO.cleanup() on exit when used with 'with'
    try:
        with GPIOController(mode_str=args.gpio_mode) as gpio_ctrl:
            # 2. Emulate Hardware Pin Inputs
            print("\n--- Step 2: Emulating Hardware Pin Inputs ---")
            input_action_data = emulate_hw_pins_from_file(args.input_values, gpio_ctrl)
            if input_action_data is None: # Error occurred during parsing or critical emulation step
                print("Hardware pin input emulation failed. Aborting test.")
                # gpio_ctrl.cleanup() already called by __exit__
                sys.exit(1)
            
            # Short delay after emulation before listening, to let STM32 react
            print("Pin emulation sequence complete. Waiting for STM32 to process...")
            time.sleep(0.5) # Adjust as needed

            # 3. Initialize Serial and Receive Output from STM32
            print("\n--- Step 3: Receiving Output from STM32 (via Serial) ---")
            
            reception_mode = "lines" # Default
            overall_read_timeout_s = 10 # Default
            stop_line = None
            
            if args.expected_values and os.path.exists(args.expected_values):
                try:
                    with open(args.expected_values, 'r') as ef:
                        expected_json_content = json.load(ef)
                    reception_mode = expected_json_content.get("reception_mode", "lines")
                    overall_read_timeout_s = expected_json_content.get("response_timeout_ms", 10000) / 1000.0
                    stop_line = expected_json_content.get("stop_condition_line") # Used if mode is 'lines'
                except Exception as e:
                    print(f"Warning: Could not read parameters from expected values file '{args.expected_values}': {e}")
            
            # SerialReceiver also uses 'with' for auto connect/disconnect and signal handling
            with SerialReceiver(port=args.serial_port, baudrate=args.baud_rate) as ser_rcv:
                if not ser_rcv.ser or not ser_rcv.ser.is_open: # Check connection from __enter__
                    raise ConnectionError("Serial receiver failed to connect properly.")

                received_data = ser_rcv.receive_data(
                    mode=reception_mode,
                    overall_timeout_s=overall_read_timeout_s,
                    stop_condition_line=stop_line
                )

                if received_data is None and reception_mode != "json_object": # For json_object, None might mean "not valid JSON" rather than no data
                    print("No data received from STM32 or reception error.")
                elif isinstance(received_data, dict) and "error" in received_data: # Check our custom error dict for JSON mode
                     print(f"Error receiving/parsing JSON from STM32: {received_data['error']}")
                     print(f"Buffer content: {received_data.get('buffer', 'N/A')}")
                elif reception_mode == "json_object" and not isinstance(received_data, dict):
                    print(f"Warning: Expected JSON object, but received data was not successfully parsed into a dict. Type: {type(received_data)}")


                # 4. Check Output
                print("\n--- Step 4: Checking Output ---")
                # Pass the already parsed 'received_data' if it's a dict (from JSON mode)
                # or the list of lines.
                test_passed = check_output(received_data, args.expected_values)
                
                # No explicit ser_rcv.disconnect() or gpio_ctrl.cleanup() needed due to 'with'

    except ConnectionError as e:
        print(f"A connection error occurred: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred during the test run: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(2)


    print("\n--- HIL Test Run End ---")
    if 'test_passed' in locals() and test_passed: # Ensure test_passed was actually set
        print("Overall Test Result: PASSED")
        sys.exit(0)
    else:
        print("Overall Test Result: FAILED or Inconclusive")
        sys.exit(1)

if __name__ == "__main__":
    main()