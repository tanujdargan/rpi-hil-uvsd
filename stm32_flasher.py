import subprocess
import os

DEFAULT_STLINK_FLASH_COMMAND = "st-flash"
DEFAULT_FLASH_ADDRESS = "0x08000000"

def flash_firmware(firmware_path, stlink_command=DEFAULT_STLINK_FLASH_COMMAND, address=DEFAULT_FLASH_ADDRESS):
    """
    Flashes the STM32 with the provided firmware file using st-flash.
    Args:
        firmware_path (str): Path to the .bin or .hex firmware file.
        stlink_command (str): The st-flash command (e.g., 'st-flash').
        address (str): The memory address to write to (e.g., '0x08000000').
    Returns:
        bool: True if flashing was successful, False otherwise.
    """
    if not os.path.exists(firmware_path):
        print(f"Error: Firmware file not found at '{firmware_path}'")
        return False

    command = [stlink_command, "write", firmware_path, address]
    
    print(f"Attempting to flash STM32 with command: {' '.join(command)}")
    try:
        # For st-flash, output goes to stderr even on success for progress
        # Using check=True will raise CalledProcessError if st-flash returns non-zero
        process = subprocess.run(command, check=True, capture_output=True, text=True)
        print("STM32 Flashing Output:")
        if process.stdout:
            print("STDOUT:\n" + process.stdout)
        if process.stderr: # st-flash often prints progress to stderr
             print("STDERR:\n" + process.stderr)
        
        # A more robust check could be to see if stderr contains "Flash written and verified successfully"
        # For now, relying on check=True is a good start.
        if "verify success" in process.stderr.lower() or \
           "flash written and verified successfully" in process.stderr.lower() or \
           (process.returncode == 0 and "error" not in process.stderr.lower()): # Fallback for basic success
            print("Firmware successfully flashed to STM32.")
            return True
        else:
            print("Warning: st-flash completed but success message not definitively found in output.")
            # Consider it a success if return code is 0 and no obvious error.
            if process.returncode == 0 and "error" not in process.stderr.lower():
                print("Interpreting as success due to zero return code and no explicit error.")
                return True
            print("Flashing may have failed or had issues. Review output.")
            return False

    except subprocess.CalledProcessError as e:
        print("Error during STM32 flashing:")
        print(f"Command: {' '.join(e.cmd)}")
        print(f"Return code: {e.returncode}")
        print(f"STDOUT:\n{e.stdout}")
        print(f"STDERR:\n{e.stderr}")
        return False
    except FileNotFoundError:
        print(f"Error: Flashing command '{stlink_command}' not found. Is stlink-tools installed and in PATH?")
        return False
    except Exception as e:
        print(f"An unexpected error occurred during flashing: {e}")
        return False