import argparse
import os
import sys
import time
import json 

from .stm32_flasher import flash_firmware # Assuming this is robust enough for now
from .pin_emulator import emulate_hw_pins_from_file, GPIOControllerError
from .serial_receiver import SerialReceiver, DEFAULT_SERIAL_PORT, DEFAULT_BAUD_RATE, SerialReceiverError
from .gpio_controller import GPIOController, GPIOControllerError as GPIOInitError # Separate init error

# output_checker is not used in this simplified version

def main():
    parser = argparse.ArgumentParser(
        description="Simplified HIL Test Runner: Toggles GPIO, receives serial, prints output.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("--code-to-test", required=True, help="Path to STM32 firmware (.bin/.hex).")
    parser.add_argument("--input-values", required=True, help="Path to JSON for hardware input actions (e.g., GPIO toggle).")
    # --expected-values is now optional and effectively ignored for this simplified run
    parser.add_argument("--expected-values", help="Path to JSON for expected serial output (Currently IGNORED in this simplified version).")
    
    parser.add_argument("--serial-port", default=DEFAULT_SERIAL_PORT, help="Serial port for STM32 communication.")
    parser.add_argument("--baud-rate", type=int, default=DEFAULT_BAUD_RATE, help="Baud rate for serial communication.")
    parser.add_argument("--skip-flash", action="store_true", help="Skip the flashing step.")
    parser.add_argument("--st-flash-cmd", default="st-flash", help="Command for st-flash utility.")
    parser.add_argument("--flash-address", default="0x08000000", help="Flash memory address for st-flash.")
    parser.add_argument("--gpio-mode", default="BCM", choices=["BCM", "BOARD"], help="GPIO pin numbering mode (BCM or BOARD).")
    parser.add_argument("--receive-timeout", type=int, default=5, help="Overall timeout in seconds for receiving serial data.")


    args = parser.parse_args()

    print("--- Simplified HIL Test Run Start ---")
    print(f"Firmware: {args.code_to_test}")
    print(f"Input Actions: {args.input_values}")
    if args.expected_values:
        print(f"Expected Values: {args.expected_values} (Note: This file will be IGNORED for output checking in this run)")
    print(f"Serial: {args.serial_port} @ {args.baud_rate}bps")
    print(f"GPIO Mode: {args.gpio_mode}")

    overall_success = False # Track if all steps complete without critical error

    # Step 1: Flash STM32 (if not skipped)
    if not args.skip_flash:
        print("\n--- Step 1: Flashing STM32 ---")
        if not os.path.exists(args.code_to_test):
            print(f"Fatal Error: Firmware file '{args.code_to_test}' not found.")
            sys.exit(1)
        try:
            if not flash_firmware(args.code_to_test, stlink_command=args.st_flash_cmd, address=args.flash_address):
                print("STM32 flashing reported failure. Aborting.")
                sys.exit(1)
            print("Flashing reported success. Delaying for STM32 boot...")
            time.sleep(2)  # Give STM32 time to reset and boot
        except Exception as e: # Catch any exception from flash_firmware itself
            print(f"Fatal Error during flashing: {e}")
            sys.exit(1)
    else:
        print("\n--- Step 1: Flashing STM32 (Skipped) ---")

    # Use 'with' statements for automatic cleanup of GPIO and Serial
    try:
        with GPIOController(mode_str=args.gpio_mode) as gpio_ctrl:
            print("\n--- Step 2: Emulating Hardware Pin Inputs ---")
            input_actions_config = emulate_hw_pins_from_file(args.input_values, gpio_ctrl)
            if input_actions_config is None: # Indicates error during parsing or critical emulation failure
                print("Hardware pin input emulation failed critically. Aborting.")
                # GPIOController cleanup happens via __exit__
                sys.exit(1)
            
            print("Pin emulation sequence complete. Waiting briefly for STM32 to process...")
            time.sleep(0.5) # Let STM32 react to final pin states

            print("\n--- Step 3: Receiving Output from STM32 (via Serial) ---")
            with SerialReceiver(port=args.serial_port, baudrate=args.baud_rate) as ser_rcv:
                # Check if ser_rcv connected successfully (connect is called in __enter__)
                if not ser_rcv.is_connected():
                     print(f"Fatal Error: Failed to connect to serial port {args.serial_port}. Aborting.")
                     # GPIO & Serial cleanup by __exit__ methods
                     sys.exit(1)

                # For this simplified goal, just receive all lines of text for a duration
                # Or receive a raw stream. Let's use lines.
                print(f"Listening for serial data for up to {args.receive_timeout} seconds...")
                received_data = ser_rcv.receive_data(
                    mode="lines", # or "raw_stream"
                    overall_timeout_s=args.receive_timeout,
                    idle_timeout_s=max(1, args.receive_timeout // 2) # Example idle timeout
                )

                print("\n--- Step 4: Printing Received Serial Data ---")
                if isinstance(received_data, list): # Expected from mode="lines"
                    if received_data:
                        print(f"Received {len(received_data)} lines:")
                        for i, line in enumerate(received_data):
                            print(f"  [{i+1}]: {line}")
                        overall_success = True # Got some data
                    else:
                        print("No lines received from STM32 within the timeout.")
                        # Consider this a pass or fail based on expectations not yet defined
                        overall_success = True # For now, no data isn't a script failure
                elif isinstance(received_data, str): # Expected from mode="raw_stream"
                    if received_data:
                        print("Received Raw Stream Data:")
                        print(received_data)
                        overall_success = True
                    else:
                        print("No raw stream data received from STM32.")
                        overall_success = True
                elif isinstance(received_data, dict) and "error" in received_data: # E.g. from JSON mode error
                    print(f"Error during serial reception: {received_data['error']}")
                    if "buffer" in received_data: print(f"  Buffer content: {received_data['buffer']}")
                    overall_success = False # Reception error
                else:
                    print(f"Received data in unexpected format or None: {type(received_data)}")
                    print(f"Data: {received_data}")
                    overall_success = False # Unexpected format

    except GPIOInitError as e: # Catch errors from GPIOController.__init__
        print(f"Fatal GPIO Initialization Error: {e}")
        sys.exit(1)
    except GPIOControllerError as e:
        print(f"Fatal GPIO Emulation Error: {e}")
        # GPIO cleanup should still be attempted by GPIOController.__exit__ if it was initialized
        sys.exit(1)
    except SerialReceiverError as e: # Catch errors from SerialReceiver methods or __init__
        print(f"Fatal Serial Communication Error: {e}")
        # GPIO cleanup should have happened if that 'with' block completed or exited.
        # SerialReceiver cleanup via its __exit__.
        sys.exit(1)
    except ConnectionError as e: # e.g. Serial connect failed inside 'with'
        print(f"Fatal Connection Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"An Unexpected Fatal Error occurred: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(2)
    finally:
        print("\n--- HIL Test Run End ---")
        if overall_success:
            print("Script completed. Please check printed output for results.")
            # For CI, exit 0 if script ran, actual pass/fail would come from output_checker later
            sys.exit(0) 
        else:
            print("Script encountered errors or did not complete successfully.")
            sys.exit(1)

if __name__ == "__main__":
    main()