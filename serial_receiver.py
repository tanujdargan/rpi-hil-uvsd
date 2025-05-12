# hil_tester_cli/serial_receiver.py
import serial
import time
import json
from signal import signal, SIGINT
from sys import exit as sys_exit

DEFAULT_SERIAL_PORT = "/dev/ttyACM0" # You can centralize defaults
DEFAULT_BAUD_RATE = 115200

class SerialReceiver:
    def __init__(self, port=DEFAULT_SERIAL_PORT, baudrate=DEFAULT_BAUD_RATE, timeout=1):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout # Default timeout for individual readline calls
        self.ser = None
        self._original_sigint_handler = None
        print(f"SerialReceiver initialized for port {port}, baudrate {baudrate}")


    def connect(self):
        try:
            self.ser = serial.Serial(self.port, self.baudrate, timeout=self.timeout)
            print(f"SerialReceiver: Successfully connected to {self.port}.")
            time.sleep(0.1) # Allow connection to settle
            self.ser.reset_input_buffer() # Clear any old data
            time.sleep(0.1)
            return True
        except serial.SerialException as e:
            print(f"SerialReceiver Error: Could not open port {self.port}: {e}")
            self.ser = None
            return False

    def disconnect(self):
        if self.ser and self.ser.is_open:
            self.ser.close()
            print(f"SerialReceiver: Port {self.port} closed.")
        self.ser = None

    def read_line(self, timeout_override=None) -> str | None:
        if not (self.ser and self.ser.is_open):
            # print("SerialReceiver Error: Not connected for reading line.") # Can be too noisy
            return None
        
        original_timeout = self.ser.timeout
        if timeout_override is not None:
            self.ser.timeout = timeout_override
        
        try:
            line_bytes = self.ser.readline()
            if timeout_override is not None:
                self.ser.timeout = original_timeout # Restore
            
            if line_bytes:
                return line_bytes.decode('utf-8', errors='replace').strip()
            return "" # Return empty string for timeout on readline if that's desired, or None
        except Exception as e:
            print(f"SerialReceiver Error reading line: {e}")
            if timeout_override is not None:
                self.ser.timeout = original_timeout
            return None


    def receive_data(self, mode="lines", overall_timeout_s=10, stop_condition_line=None, idle_timeout_s=2) -> list[str] | dict | str | None:
        """
        Receives data from serial based on the specified mode.
        - mode="lines": Returns a list of strings (lines).
        - mode="json_object": Attempts to read and parse a single JSON object string. Returns a dict or None.
        - mode="raw_stream": Returns the raw data collected as a single string.
        """
        if not (self.ser and self.ser.is_open):
            print("SerialReceiver Error: Not connected.")
            return None

        print(f"SerialReceiver: Receiving data (Mode: {mode}, Timeout: {overall_timeout_s}s, StopLine: '{stop_condition_line}', IdleTimeout: {idle_timeout_s}s)")
        
        buffer = ""
        lines_received = []
        start_time = time.time()
        last_data_time = time.time()

        while (time.time() - start_time) < overall_timeout_s:
            if (time.time() - last_data_time) > idle_timeout_s and mode != "json_object": # For json_object, wait longer for whole object
                 # For json_object, we might want to rely more on overall_timeout_s unless we implement incremental JSON parsing
                print(f"SerialReceiver: Idle timeout ({idle_timeout_s}s) reached.")
                break

            # Read available bytes, don't block for a full line if in json_object or raw_stream mode
            bytes_to_read = self.ser.in_waiting
            if bytes_to_read > 0:
                try:
                    data_chunk = self.ser.read(bytes_to_read).decode('utf-8', errors='replace')
                    buffer += data_chunk
                    last_data_time = time.time()
                    # print(f"DBG: read chunk: {data_chunk[:50]}... buffer len: {len(buffer)}") # Debug
                except Exception as e:
                    print(f"SerialReceiver: Error reading chunk: {e}")
                    break # Exit loop on read error
            else: # No data in_waiting
                time.sleep(0.02) # Small sleep to prevent busy loop

            if mode == "lines":
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    line = line.strip()
                    if line: # Avoid adding empty lines from multiple newlines
                        lines_received.append(line)
                        print(f"  Line Rcvd: \"{line}\"")
                        if stop_condition_line and line == stop_condition_line:
                            print("  Stop condition line met.")
                            return lines_received
            elif mode == "json_object":
                # Attempt to parse JSON from buffer. This is tricky.
                # A robust way is to find matching braces, but for simplicity here,
                # we might just try parsing the whole buffer on each new data chunk
                # if a potential end of JSON is detected (e.g., '}')
                if '}' in data_chunk: # Heuristic: try to parse if we see a closing brace
                    try:
                        # Find the first '{' and last '}' to extract a potential JSON object
                        # This is still not robust for nested structures or multiple objects.
                        # For true robustness, use a proper streaming JSON parser or framing protocol.
                        first_brace = buffer.find('{')
                        last_brace = buffer.rfind('}')
                        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
                            potential_json_str = buffer[first_brace : last_brace+1]
                            # print(f"DBG: Potential JSON: {potential_json_str[:100]}...") # Debug
                            json_obj = json.loads(potential_json_str)
                            print(f"  JSON Object Rcvd & Parsed. Keys: {list(json_obj.keys()) if isinstance(json_obj, dict) else 'N/A (not a dict)'}")
                            return json_obj # Success
                        # else: print("DBG: Braces not forming a clear object yet.") # Debug
                    except json.JSONDecodeError:
                        # print("DBG: JSONDecodeError, waiting for more data or timeout.") # Debug
                        pass # Not a complete JSON object yet
                    except Exception as e:
                        print(f"SerialReceiver: Error during tentative JSON parsing: {e}")
                        # This might be a non-JSON string if parsing failed badly
                        # Could return buffer here if that's the desired fallback for json_object mode failure.

            # For mode "raw_stream", we just accumulate in buffer

        # Loop ended (timeout or other condition)
        if mode == "lines":
            if buffer.strip(): # Any remaining part in buffer not ending with newline
                lines_received.append(buffer.strip())
                print(f"  Line Rcvd (final buffer): \"{buffer.strip()}\"")
            return lines_received
        elif mode == "json_object":
            # Final attempt to parse whatever is in the buffer as JSON
            print("SerialReceiver: Timeout for JSON object. Final parse attempt on buffer.")
            try:
                first_brace = buffer.find('{')
                last_brace = buffer.rfind('}')
                if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
                    potential_json_str = buffer[first_brace : last_brace+1]
                    json_obj = json.loads(potential_json_str)
                    print(f"  JSON Object Rcvd & Parsed (final attempt). Keys: {list(json_obj.keys()) if isinstance(json_obj,dict) else 'N/A'}")
                    return json_obj
                else:
                    print("SerialReceiver: Could not form a JSON object from final buffer content.")
                    print(f"Final buffer content was: '{buffer}'")
                    return {"error": "incomplete_json_received", "buffer": buffer} # Indicate error
            except json.JSONDecodeError:
                print("SerialReceiver: Final JSON parse attempt failed.")
                print(f"Final buffer content was: '{buffer}'")
                return {"error": "invalid_json_received", "buffer": buffer} # Indicate error
        elif mode == "raw_stream":
            print(f"SerialReceiver: Raw stream reception complete. Length: {len(buffer)}")
            return buffer

        return None # Default if no data or unhandled mode

    def __enter__(self):
        self._original_sigint_handler = signal(SIGINT, self._graceful_exit_handler)
        if not self.connect():
            raise ConnectionError(f"Failed to connect to serial port {self.port}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()
        if self._original_sigint_handler:
            signal(SIGINT, self._original_sigint_handler)

    def _graceful_exit_handler(self, sig, frame):
        print("\nSIGINT or CTRL-C detected by SerialReceiver. Closing port and exiting.")
        self.disconnect()
        sys_exit(1)