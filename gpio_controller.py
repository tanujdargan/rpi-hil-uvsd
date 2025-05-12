import time

# Attempt to import RPi.GPIO and handle cases where it might not be available (e.g., dev machine)
try:
    import RPi.GPIO as GPIO
    HAS_GPIO_LIB = True
except ImportError:
    print("Warning: RPi.GPIO library not found. GPIO operations will be mocked.")
    HAS_GPIO_LIB = False
    # Mock GPIO class for development on non-RPi systems
    class MockGPIO:
        BCM = "BCM_MODE"
        BOARD = "BOARD_MODE"
        OUT = "OUTPUT_MODE"
        IN = "INPUT_MODE"
        HIGH = 1
        LOW = 0
        PUD_UP = "PUD_UP"
        PUD_DOWN = "PUD_DOWN"
        
        def __init__(self):
            self._mode = None
            self._pin_setups = {} # pin: {"mode": OUT/IN, "value": HIGH/LOW, "pud": PUD_UP/DOWN}
            self._warnings_issued = False

        def _check_lib(self, func_name):
            if not self._warnings_issued:
                print(f"MockGPIO: {func_name} called. RPi.GPIO not available. Simulating operation.")
            return True # Allow mocked operation

        def setmode(self, mode):
            self._check_lib("setmode")
            self._mode = mode
            print(f"MockGPIO: Mode set to {mode}")

        def setup(self, pin, direction, initial=None, pull_up_down=None):
            self._check_lib("setup")
            if pin not in self._pin_setups: self._pin_setups[pin] = {}
            self._pin_setups[pin]["direction"] = direction
            if direction == self.OUT:
                value_to_set = initial if initial is not None else self.LOW
                self._pin_setups[pin]["value"] = value_to_set
                print(f"MockGPIO: Pin {pin} setup as {direction}, initial value {value_to_set}")
            elif direction == self.IN:
                self._pin_setups[pin]["pud"] = pull_up_down
                self._pin_setups[pin]["value"] = self.HIGH if pull_up_down == self.PUD_UP else self.LOW # Simplistic mock
                print(f"MockGPIO: Pin {pin} setup as {direction}, pull_up_down {pull_up_down}")


        def output(self, pin, value):
            self._check_lib("output")
            if pin in self._pin_setups and self._pin_setups[pin].get("direction") == self.OUT:
                self_pin_setups[pin]["value"] = value
                print(f"MockGPIO: Pin {pin} set to {value}")
            else:
                print(f"MockGPIO: Error - Pin {pin} not setup as output or not setup at all.")


        def input(self, pin):
            self._check_lib("input")
            if pin in self._pin_setups and self._pin_setups[pin].get("direction") == self.IN:
                val = self._pin_setups[pin].get("value", self.LOW) # Default to LOW if not set
                print(f"MockGPIO: Reading from pin {pin}, returning {val}")
                return val
            print(f"MockGPIO: Error - Pin {pin} not setup as input or not setup at all.")
            return self.LOW # Default return for error

        def cleanup(self, pin=None):
            self._check_lib("cleanup")
            if pin:
                if pin in self._pin_setups:
                    del self._pin_setups[pin]
                print(f"MockGPIO: Cleaned up pin {pin}")
            else:
                self._pin_setups.clear()
                print("MockGPIO: Cleaned up all channels")
        
        def setwarnings(self, state):
            self._warnings_issued = not state # if state is False, warnings are enabled
            print(f"MockGPIO: Warnings set to {state}")

    GPIO = MockGPIO() # Replace actual GPIO with mock if lib not found

class GPIOController:
    def __init__(self, mode_str="BCM"):
        if not HAS_GPIO_LIB:
            print("GPIOController: Initializing with Mock RPi.GPIO.")
        
        GPIO.setwarnings(False)
        if mode_str.upper() == "BCM":
            GPIO.setmode(GPIO.BCM)
        elif mode_str.upper() == "BOARD":
            GPIO.setmode(GPIO.BOARD)
        else:
            raise ValueError("Invalid GPIO mode. Choose 'BCM' or 'BOARD'.")
        print(f"GPIOController: Mode set to {mode_str.upper()}")
        self.pin_directions = {} # Store configured direction to avoid re-setup issues

    def setup_pin_direction(self, pin, direction_str, initial_str=None, pull_up_down_str=None):
        print(f"GPIOController: Setting up pin {pin} as {direction_str}")
        direction = GPIO.OUT if direction_str.lower() == "output" else GPIO.IN
        
        initial_val = None
        if initial_str:
            initial_val = GPIO.HIGH if initial_str.lower() == "high" else GPIO.LOW

        pud = None
        if pull_up_down_str:
            if pull_up_down_str.lower() == "pull_up": pud = GPIO.PUD_UP
            elif pull_up_down_str.lower() == "pull_down": pud = GPIO.PUD_DOWN
            # else GPIO.PUD_OFF (or no pull) is default if library supports it explicitly

        if direction == GPIO.OUT:
            if initial_val is not None:
                 GPIO.setup(pin, direction, initial=initial_val)
            else:
                 GPIO.setup(pin, direction) # Default initial usually LOW
        elif direction == GPIO.IN:
            if pud is not None:
                GPIO.setup(pin, direction, pull_up_down=pud)
            else:
                GPIO.setup(pin, direction)
        self.pin_directions[pin] = direction_str.lower()


    def set_pin_output(self, pin, value_str):
        if self.pin_directions.get(pin) != "output":
            print(f"Warning: Pin {pin} not configured as output. Setting up as output now.")
            self.setup_pin_direction(pin, "output", initial_str=value_str)
            # GPIO.setup(pin, GPIO.OUT) # Simple setup if not configured
        
        value = GPIO.HIGH if value_str.lower() == "high" else GPIO.LOW
        GPIO.output(pin, value)
        print(f"GPIOController: Pin {pin} set to {value_str.upper()}")

    def read_pin_input(self, pin):
        if self.pin_directions.get(pin) != "input":
            print(f"Warning: Pin {pin} not configured as input. Setting up as input now.")
            self.setup_pin_direction(pin, "input")
            # GPIO.setup(pin, GPIO.IN) # Simple setup if not configured

        value = GPIO.input(pin)
        state = "HIGH" if value == GPIO.HIGH else "LOW"
        print(f"GPIOController: Pin {pin} read as {state}")
        return state

    def pulse_pin_output(self, pin, duration_ms, pulse_state_str="high", initial_state_str=None):
        if self.pin_directions.get(pin) != "output":
            print(f"Warning: Pin {pin} not configured as output for pulse. Setting up now.")
            # Determine a sensible default for initial if setting up here
            temp_initial = initial_state_str if initial_state_str else ("low" if pulse_state_str=="high" else "high")
            self.setup_pin_direction(pin, "output", initial_str=temp_initial)

        active_state = GPIO.HIGH if pulse_state_str.lower() == "high" else GPIO.LOW
        
        if initial_state_str:
            inactive_state = GPIO.HIGH if initial_state_str.lower() == "high" else GPIO.LOW
        else: # Default inactive is opposite of active
            inactive_state = GPIO.LOW if active_state == GPIO.HIGH else GPIO.HIGH

        GPIO.output(pin, inactive_state) # Ensure starting from inactive
        time.sleep(0.001) # Ensure state settles
        GPIO.output(pin, active_state)   # Start pulse
        print(f"GPIOController: Pin {pin} pulsed to {pulse_state_str.upper()} for {duration_ms}ms (from {initial_state_str or 'opposite'})")
        time.sleep(duration_ms / 1000.0)
        GPIO.output(pin, inactive_state) # End pulse
        print(f"GPIOController: Pin {pin} pulse ended, returned to {'HIGH' if inactive_state == GPIO.HIGH else 'LOW'}")


    def cleanup(self, pin=None):
        print(f"GPIOController: Cleaning up {'pin ' + str(pin) if pin else 'all pins'}.")
        if HAS_GPIO_LIB: # Only call GPIO.cleanup if the library was available
            if pin is None:
                GPIO.cleanup()
                self.pin_directions.clear()
            elif pin in self.pin_directions:
                 GPIO.cleanup(pin)
                 del self.pin_directions[pin]
            else:
                print(f"GPIOController: Pin {pin} was not set up by this controller.")
        else:
            if pin is None: self.pin_directions.clear()
            elif pin in self.pin_directions: del self.pin_directions[pin]


    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()