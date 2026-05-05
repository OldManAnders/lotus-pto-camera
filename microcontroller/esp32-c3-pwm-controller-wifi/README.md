# ESP32-C3 PWM Controller (Wi‑Fi TCP)
This PlatformIO project runs on an ESP32‑C3 and accepts JSON messages over TCP to control sensors and pwm outputs remotely.

**Protocol Summary**
- **Framing:** Each message is a JSON object prefixed by a 4‑byte big‑endian unsigned length.
- **Supported `type` values:** `ping`, `status`, `set`, `get`, `cmd`.

Examples: (See communication.md for more details)
- Ping: { "type": "ping" }
- Set channel 1: { "type": "set", "set": { "pwm.1": 128 } }
- Get channel 2: { "type": "get", "get": "pwm.2" }

**Key files**
- **Config:** [src/config.h](src/config.h)
- **Wi‑Fi manager:** [src/wifi_manager.h](src/wifi_manager.h) / [src/wifi_manager.cpp](src/wifi_manager.cpp)
- **TCP server:** [src/tcp_server.h](src/tcp_server.h) / [src/tcp_server.cpp](src/tcp_server.cpp)
- **Message handling:** [src/message_handler.h](src/message_handler.h) / [src/message_handler.cpp](src/message_handler.cpp)
- **PWM controller:** [src/pwm_controller.h](src/pwm_controller.h) / [src/pwm_controller.cpp](src/pwm_controller.cpp)
