import machine
import utime
import uasyncio as asyncio
from machine import Pin, I2C
from hcsr04 import HCSR04
from ssd1306 import SSD1306_I2C

# Pin Configurations
PIR_PIN = 15
RELAY_PIN = 2
ULTRASONIC_TRIGGER_PIN = 4
ULTRASONIC_ECHO_PIN = 3
OLED_SDA_PIN = 0
OLED_SCL_PIN = 1

# Constants
OLED_WIDTH = 128
OLED_HEIGHT = 64
PUMP_ACTIVATION_TIME = 2  # seconds
COOLDOWN_PERIOD = 5  # seconds
INITIALIZATION_TIME = 60  # seconds
MAX_ACTIVATIONS_PER_MINUTE = 10  # For error detection

# Initialize components
pir = Pin(PIR_PIN, Pin.IN, Pin.PULL_DOWN)
relay = Pin(RELAY_PIN, Pin.OUT)
ultrasonic = HCSR04(trigger_pin=ULTRASONIC_TRIGGER_PIN, echo_pin=ULTRASONIC_ECHO_PIN)
i2c = I2C(0, sda=Pin(OLED_SDA_PIN), scl=Pin(OLED_SCL_PIN))
oled = SSD1306_I2C(OLED_WIDTH, OLED_HEIGHT, i2c)

# Global variables
last_activation_time = 0
activations_count = 0
last_activation_minute = 0

def log_event(event_type, distance, pir_value):
    with open('detector_log.txt', 'a') as f:
        timestamp = utime.localtime()
        log_entry = "{}/{}/{} {}:{:02d}:{:02d} - {}, Distance: {:.2f}cm, PIR: {}\n".format(
            timestamp[0], timestamp[1], timestamp[2],
            timestamp[3], timestamp[4], timestamp[5],
            event_type, distance, pir_value
        )
        f.write(log_entry)

def activate_pump():
    global last_activation_time, activations_count, last_activation_minute
    current_time = utime.time()
    current_minute = current_time // 60

    if current_minute != last_activation_minute:
        activations_count = 0
        last_activation_minute = current_minute

    if current_time - last_activation_time > COOLDOWN_PERIOD and activations_count < MAX_ACTIVATIONS_PER_MINUTE:
        relay.on()
        await asyncio.sleep(PUMP_ACTIVATION_TIME)
        relay.off()
        last_activation_time = current_time
        activations_count += 1
    elif activations_count >= MAX_ACTIVATIONS_PER_MINUTE:
        display_error("Too many activations")

def display_error(message):
    oled.fill(0)
    oled.text("ERROR:", 0, 0)
    oled.text(message, 0, 10)
    oled.show()

def display_status(status, last_detection):
    oled.fill(0)
    if status == "watching":
        oled.text("^_^", 56, 0)
    elif status == "angry":
        oled.text(">_<", 56, 0)
    oled.text("Status: " + status, 0, 20)
    oled.text("Last: " + last_detection, 0, 30)
    oled.show()

async def detect_motion():
    last_distances = []
    last_detection_time = "Never"

    while True:
        pir_value = pir.value()
        distance = ultrasonic.distance_cm()
        
        last_distances.append(distance)
        if len(last_distances) > 5:
            last_distances.pop(0)
        
        if pir_value == 1:
            if 10 < distance < 100:  # Adjust these values based on your setup
                movement_pattern = max(last_distances) - min(last_distances)
                if movement_pattern > 20:  # Threshold for cat-like movement
                    display_status("angry", last_detection_time)
                    await activate_pump()
                    log_event("Cat Detected", distance, pir_value)
                    last_detection_time = "{:02d}:{:02d}".format(utime.localtime()[3], utime.localtime()[4])
                else:
                    display_status("watching", last_detection_time)
            else:
                display_status("watching", last_detection_time)
        else:
            display_status("watching", last_detection_time)
        
        await asyncio.sleep(0.1)

async def main():
    print("Initializing PIR sensor...")
    oled.fill(0)
    oled.text("Initializing...", 0, 0)
    for i in range(INITIALIZATION_TIME):
        oled.fill_rect(0, 20, int(i * OLED_WIDTH / INITIALIZATION_TIME), 10, 1)
        oled.show()
        await asyncio.sleep(1)
    
    print("Starting detection...")
    asyncio.create_task(detect_motion())

    while True:
        await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(main())