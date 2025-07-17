# Study Buddy Prototype —  Design Specification

## 1. Overview

A compact desk “study buddy” (~5–10cm³) that:
- Local Q&A: General/programming questions via quantized on‑device model (<2s latency)
- Mobility: Hidden wheels, IR-based edge detection, ultrasonic obstacle avoidance 
- UI: 2.4" TFT LCD (touch-enabled), speaker, microphone 
- Power: USB‑C power/pass-through & charging; internal 2× Panasonic NCR18650A (3.1 Ah each) for ~3–4 h (with sleep modes)
- Connectivity: BLE (ESP32) for provisioning; Wi‑Fi soft-AP for bulk transfers; USB‑C for direct updates 
- Software: Buildroot Linux; core application in Rust; optional Python bindings for rapid prototyping

## 2. Hardware Components

| Category      | Component               | Rationale & Notes                                                           |
|---------------|-------------------------|-----------------------------------------------------------------------------|
| SBC           | Raspberry Pi Zero 2W    | 4× cores, 512MB RAM; small footprint; USB‑C modifiable                      |
| _Alternative_ | Orange Pi Zero2L        | 1GB RAM if more memory needed; similar form factor                          |
| Co‑proc       | ESP32                   | Offloads UI, touch, BLE; runs Rust via esp-rs or Arduino for sensor control |
| _Display_     | 2.4" TFT LCD            | Cost-effective, fast refresh; SPI interface                                 |
| Mobility      | 2× micro DC‑gear motors | Hidden chassis; PWM curves tuned per motor                                  |
|               | TB6612FNG dual H‑bridge | Drives both motors; requires per-channel calibration                        |
| Sensors       | IR reflectance (2–4)    | Edge detection                                                              |
|               | HC‑SR04 ultrasonic      | Obstacle avoidance                                                          |
| Audio         | MEMS mic + mini speaker | + PAM8302A amp (if needed)                                                  |
| Power         | 2× Panasonic NCR18650A  | ~7.4V pack; TP4056 USB‑C charger + boost → 5V rail                          |
| Storage       | microSD (32GB)          | OS and model storage; implement wear leveling, read-only rootfs             |
| _Optional_    | USB→SSD/M.2 (~100NOK)   | Higher endurance, faster I/O                                                |
| Acceleration  | Edge TPU USB (future)   | Lower inference latency                                                     |

Note: GPIO cannot expand RAM. SPI/NAND flash modules can add storage (e.g., external SPI flash or eMMC via adapter), but Pi Zero’s RAM remains fixed. ESP32 runs Rust natively via esp-rs or prebuilt firmware.

## 3. Connectivity Strategy

- Provisioning: BLE on ESP32 exchanges Wi‑Fi credentials 
- Bulk Transfer: Device hosts Wi‑Fi soft-AP; PC connects to push model files (~10MB/s)
- Direct Update: USB‑C tether for firmware & model flashes (FAT32 microSD access)
- Remote Access: VPN unnecessary for local desk use; Wi‑Fi alone suffices

## 4. Software Architecture

- OS: Minimal Linux via Buildroot 
- Core App: Rust (llama-rs crate) for inference; optional Python/ONNX for rapid tests 
- UI & Control: ESP32 firmware in Rust (esp-rs) for display/touch; Pi communicates over UART/SPI 
- Model Management: WSL desktop app → BLE/Wi‑Fi/USB → device microSD

## 5. AI Model Selection

- Primary: 4‑bit quantized LLaMA‑lite (~100–200MB)
- Fallback: TinyLLM (<50MB) for faster loads; acceptable accuracy trade‑off

## 6. Interaction Patterns

- Touch Buttons: Predefined actions (e.g., “cuddle,” “joke,” “explain code”)
- Voice I/O: Microphone prompts; speaker outputs synthesized responses 
- Sleep Modes: Screen off, motors idle, CPU in low‑power when inactive

## 7. Prototype Roadmap

- Inventory Audit: Confirm all listed components in stock 
- Power Module: Assemble TP4056 + boost; bench test idle vs active draw 
- Display & ESP32: Flash Rust firmware; validate UI responsiveness 
- Connectivity: BLE credential exchange; Wi‑Fi soft‑AP throughput test 
- Inference Benchmark: Deploy quantized model on Pi Zero2W; verify <2s latency 
- Mobility Trial: Calibrate PWM per motor; validate edge/obstacle detection 
- Enclosure Design: Finalize dimensions; 3D-print test chassis 
- Integration & Testing: Combine all subsystems; iterate for stability 

Final Note: RAM expansion via GPIO is not feasible; storage can be extended via SPI/NAND flash, but core memory remains at 512MB. 
Rust provides native performance on both Pi and ESP32; Python remains an option for rapid iteration.

## 8. Full Component List

- Raspberry Pi Zero2W (512MB RAM)
- Orange Pi Zero2L (1GB RAM) [optional]
- ESP32 module 
- 2.4" TFT LCD (SPI, touch-enabled)
- 2× Micro DC‑gear motors 
- TB6612FNG dual H‑bridge motor driver 
- IR reflectance sensors (2–4 units)
- HC‑SR04 ultrasonic sensor 
- MEMS microphone 
- Mini speaker + PAM8302A amplifier 
- 2× Panasonic NCR18650A cells (3.1Ah each)
- TP4056 USB‑C charging module 
- Boost converter (5V output)
- MicroSD card (32GB)
- USB→SSD/M.2 adapter + SSD [optional]
- Edge TPU USB accelerator [future]
- Misc wiring, connectors, and chassis materials

