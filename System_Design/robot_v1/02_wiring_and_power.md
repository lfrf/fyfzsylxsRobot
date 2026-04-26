# Desktop Robot V1 - Wiring and Power Plan

## 1. Power Topology
```
12V DC IN (5A)
   |
   +-- Fuse (5A) -- Main Switch --+-- Buck #1: 5V/5A -> Raspberry Pi 5
                                  |
                                  +-- Buck #2: 6V/6A -> Servos (Pan/Tilt)
                                  |
                                  +-- Buck #3: 5V/2A -> OLED + low-power peripherals (optional)

Common GND between all rails is required.
```

## 2. Primary Interfaces
- Raspberry Pi 5
  - I2C bus (`GPIO2 SDA`, `GPIO3 SCL`)
  - UART (`GPIO14 TXD`, `GPIO15 RXD`) for future motor controller
  - USB for microphone/camera/audio

- PCA9685 servo board
  - Input: 6V rail to `V+`
  - Logic: 3.3V or 5V to `VCC` (prefer 3.3V compatible board if possible)
  - Control: I2C

- Dual OLED eyes
  - Interface: I2C
  - Address:
    - Left eye: `0x3C`
    - Right eye: `0x3D`
  - If both panels only support one fixed address, add `TCA9548A`.

## 3. Wiring Table
| From | To | Signal / Power | Notes |
|---|---|---|---|
| 12V jack + | Fuse IN | 12V | Add reverse polarity protection |
| Fuse OUT | Main switch IN | 12V | Keep wire gauge >= AWG20 |
| Main switch OUT | Buck #1 IN | 12V | Pi rail |
| Main switch OUT | Buck #2 IN | 12V | Servo rail |
| Buck #1 OUT | Pi 5V/GND | 5V | Prefer dedicated Pi power HAT/input |
| Buck #2 OUT | PCA9685 `V+`/GND | 6V | Servo power only |
| Pi GND | PCA9685 GND | GND | Common reference |
| Pi SDA/SCL | PCA9685 SDA/SCL | I2C | Short cable, twisted pair preferred |
| Pi SDA/SCL | OLED-L + OLED-R | I2C | Keep under 25 cm if possible |
| PCA9685 CH0 | Pan servo | PWM | Pulse range calibrated in software |
| PCA9685 CH1 | Tilt servo | PWM | Pulse range calibrated in software |
| Pi USB | Mic array | USB audio input | UAC compliant device |
| Pi USB | Camera | USB video | UVC compliant device |
| Pi audio out/USB | Amplifier IN | Audio | Use shielded cable |
| Amplifier OUT | Speaker | Audio power | 4 ohm or 8 ohm matching |

## 4. Safety Constraints
- Do not power servos directly from Raspberry Pi 5V pins.
- Add one emergency stop button:
  - Hardware mode: cuts servo 6V rail.
  - Software mode: sends immediate "head_center + mute".
- Add brown-out prevention:
  - Pi rail and servo rail are separate.
  - Keep at least 1000 uF capacitor near servo supply entry.

## 5. Cable Routing Rules
- Power cables on one side, signal cables on opposite side.
- Add strain relief at neck pass-through.
- Use detachable JST connectors for head module maintenance.

## 6. Commissioning Checklist
1. Verify no-load voltage for each buck output.
2. Verify common ground continuity.
3. Boot Pi only, confirm stable operation.
4. Connect PCA9685, run servo test at low speed.
5. Connect OLEDs, verify I2C addresses.
6. Connect audio/camera and run end-to-end check.
