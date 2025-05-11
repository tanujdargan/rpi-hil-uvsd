A **Python‑based orchestration framework** that turns a Raspberry Pi (RPi) into the central test controller for an STM32 (or any UART‑capable) embedded target. The script automates the full HIL workflow—fetching the latest test assets, injecting emulated inputs, collecting serial output, and delegating pass/fail decisions—so you can focus on authoring high‑value test logic rather than plumbing.

```text

+--------------------+       USB/UART       +-----------------------+

| Raspberry Pi 4/5   |<-------------------->|      STM32 Board      |

| • Python 3 driver  |                     |  (Target μC + FW)     |

| • Git repository   |                     |                       |

| • GitHub Actions   |                     |  Sends DUT responses  |

| • HIL orchestrator |                     |  via printf()/UART    |

+--------------------+                     +-----------------------+

         |

         |  (optional)

         |  GPIO/SPI/I²C to additional

         |  stimulation hardware

         v

  +--------------------+

  |   Emulation Layer  |

  |  (custom scripts)  |

  +--------------------+

```


### Data Flow


1. **Fetch** latest commit from *main* (or CI copies repo).

2. **Discover** test vectors inside `hardware_in-loop-testing/tests/`.

3. **For each test**:

	   1. Parse the JSON descriptor.

	   2. Call *Emulation Hook* to drive inputs.

	   3. Read serial output from STM32 until `TEST_COMPLETE` (or timeout).

	   4. Call *Confirmation Hook* to decide pass/fail.

4. **Aggregate** results and exit with a POSIX code suitable for CI.

```

hardware_in-loop-testing/

├─ orchestrator/                  # <‑‑ This folder (Python entry point)

│  └─ rpi_hil_orchestrator.py     # Main script described below

├─ tests/                         # JSON or test_*.py cases live here

│  ├─ basic_blink.json            # Example vector

│  └─ ...

├─ test_repo/                     # (optional) additional source artefacts

│  └─ ...

└─ .github/workflows/hil.yml      # CI pipeline

```

## Quick Start

  
```bash

# 0) Flash Raspberry Pi OS Lite, boot and enable UART

sudo raspi-config      # Interface Options ▶ Serial Port ▶ Disable shell, Enable hw

  

# 1) Clone and install Python deps

sudo apt update && sudo apt install -y git python3-pip

  

git clone https://github.com/tanujdargan/hardware_in-loop-testing.git

cd hardware_in-loop-testing

pip3 install -r requirements.txt

  

# 2) Edit config constants if your serial device is different

nano orchestrator/rpi_hil_orchestrator.py   # SERIAL_PORT, BAUD_RATE

  

# 3) Wire RPi ↔ STM32 and power on the target

  

# 4) Run the entire test suite

python3 orchestrator/rpi_hil_orchestrator.py

```

  

Successful run prints something like:

  

```

Serial port /dev/ttyACM0 opened successfully at 115200 baud.

Found 3 test(s). Starting test execution...

--- Executing Test Case: basic_blink.json ---

[...]

--- Test Case basic_blink.json Finished ---

Serial port closed at the end of testing.

All tests completed.

```
  
The script exits **0** if every case passes, otherwise a non‑zero code for CI
## Configuration

  
| Variable           | Location                      | Description                                       |
|--------------------|-------------------------------|---------------------------------------------------|
| `SERIAL_PORT`      | `rpi_hil_orchestrator.py`     | `/dev/ttyUSB0`, `/dev/ttyACM0`, or GPIO.          |
| `BAUD_RATE`        | `rpi_hil_orchestrator.py`     | Match your `printf()` baud (115200 Bd).           |
| `TEST_REPO_PATH`   | `rpi_hil_orchestrator.py`     | Path to local clone; CI mounts here.              |
| `TESTS_SUBFOLDER`  | `rpi_hil_orchestrator.py`     | Usually `tests`.                                  |
| Git credentials    | Pi‑wide git config / deploy keys | Needed if the Pi pulls from a private repo.       |
| Timeout constants  | `execute_test_case()`         | `max_receive_time_seconds`, etc.                  |



You may also export environment variables and read them in the script if you prefer fully code‑free config.

## Writing Tests

Tests live in `hardware_in-loop-testing/tests/` and can be expressed as **JSON** (recommended for pure data) or a **Python script** (`test_*.py`) when you need dynamic logic.

### JSON Schema (simplified)

```jsonc

{

	"$schema": "https://example.com/hil.schema.json",

	"name": "basic_blink",

	"description": "Verify LED toggles every 500 ms and firmware replies PASS.",

	"inputs_to_emulate": ["START_TEST", 2000],

	"expected_outputs": ["LED_ON", "LED_OFF", "LED_ON", "LED_OFF", "TEST_COMPLETE"],

	"meta": {

		"timeout_s": 10,

		"board_voltage": 3.3

	}
}

```

Fields you can rely on inside **`execute_test_case()`**:
| Key                 | Type   | Purpose                                                            |
|---------------------|--------|--------------------------------------------------------------------|
| `inputs_to_emulate` | array  | Tokens passed to the *Emulation Hook*.                             |
| `expected_outputs`  | array  | Lines – in order – that must appear on UART.                       |
| `meta`              | object | Free‑form hints (custom timeout, supply rails, etc.).              |


### Python‑based Vector

If JSON is too rigid you may drop a `tests/test_pwm_sweep.py` containing a `run(ser)` function that uses the raw PySerial object and returns `True/False`.

```python

# tests/test_pwm_sweep.py

import time

  

def run(ser):

    ser.write(b"START_PWM\n")

    deadline = time.time() + 5

    while time.time() < deadline:

        if b"TEST_COMPLETE" in ser.readline():

            return True

    return False

```

The orchestrator will automatically `importlib`‑load and execute it.
## Integration Points

The core script purposefully leaves **two stub functions** where teammates can inject their domain logic without touching the orchestrator:


| Stub section | What to implement |
|--------------|-------------------|
| **Emulate Values** | Translate `inputs_to_emulate` → real stimuli. <br>Possible strategies: <br>• `ser.write()` UART tokens <br>• Bit‑banging RPi GPIOs <br>• Driving a USB‑CAN adapter |
| **Confirm Tests** | Compare `received_data_lines` vs. `expected_outputs`. <br>Feel free to add filtering, regex, or timing checks &nbsp;— return **True** on pass, **False** on fail. |

  

> **Design Guideline**: Keep *hooks* in separate **modules** under `orchestrator/hooks/` so you can unit‑test them in isolation.
### Hook API Contract

```python

# emulate.py

  

def emulate(test_config: dict, ser: serial.Serial) -> None:

    """Inject inputs; must be blocking but predictable."""

  

# confirm.py

  

def confirm(test_config: dict, received: list[str]) -> bool:

    """Return True on pass, False on fail."""

```

The orchestrator will import and call these automatically if present.
## Continuous Integration ( GitHub Actions )

A sample workflow **`.github/workflows/hil.yml`** installs Python, copies the repo onto the RPi (self‑hosted runner or `ssh-action`), and triggers the orchestrator:

```yaml

name: HIL Regression Suite

on:

  push:

    branches: [main]

  

jobs:

  hil:

    runs-on: [self-hosted, rpi]

    steps:

      - uses: actions/checkout@v4

      - name: Install deps

        run: pip3 install -r requirements.txt

      - name: Run HIL Suite

        run: python3 orchestrator/rpi_hil_orchestrator.py

```

The job fails if the exit code ≠ 0, protecting the `main` branch from firmware regressions.
## Troubleshooting

| Symptom                         | Likely cause / fix                                                                                    |
|---------------------------------|--------------------------------------------------------------------------------------------------------|
| `Error opening serial port`     | Wrong `SERIAL_PORT`; run `dmesg \| grep tty` after plugging the device.                               |
| Script hangs on read            | Firmware not sending newline; adjust the `ser.readline()` logic.                                      |
| “No test files found”           | Path typo; confirm `TESTS_SUBFOLDER` exists on the Pi.                                                |
| Git pull fails on Pi            | SSH key missing; add a deploy key or use HTTPS + token.                                               |
| Random garbled UART characters  | Mismatched baud or voltage level; scope the RX line and verify it’s 3.3 V.                            |

## Roadmap

* [ ] JUnit‑xml or Allure result export for nicer dashboards.

* [ ] Parallel test execution across multiple RPis.

* [ ] Web UI with live logs (Flask + websockets).

* [ ] YAML schema validation for test vectors.

* [ ] Hardware abstraction layer for SPI/I²C/CAN emulation.

## Contributing

1. Fork the repo & create feature branch

2. Add/Update **unit tests** for your changes.

3. Open a PR—GitHub Actions must go green.
---
**Made with ❤️ & caffeine (White Monster W).**
