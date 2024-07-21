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
ONBOARD_LED_PIN = 25

# Constants
OLED_WIDTH = 128
OLED_HEIGHT = 64
PUMP_ACTIVATION_TIME = 2  # seconds
COOLDOWN_PERIOD = 5  # seconds
INITIALIZATION_TIME = 60  # seconds
MAX_ACTIVATIONS_PER_MINUTE = 10  # For error detection
CAT_DISTANCE_THRESHOLD = 100  # cm

# Initialize components
pir = Pin(PIR_PIN, Pin.IN, Pin.PULL_DOWN)
relay = Pin(RELAY_PIN, Pin.OUT)
ultrasonic = HCSR04(trigger_pin=ULTRASONIC_TRIGGER_PIN, echo_pin=ULTRASONIC_ECHO_PIN)
i2c = I2C(0, sda=Pin(OLED_SDA_PIN), scl=Pin(OLED_SCL_PIN))
oled = SSD1306_I2C(OLED_WIDTH, OLED_HEIGHT, i2c)
onboard_led = Pin(ONBOARD_LED_PIN, Pin.OUT)

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

def log_error(error_message):
    with open('error_log.txt', 'a') as f:
        timestamp = utime.localtime()
        log_entry = "{}/{}/{} {}:{:02d}:{:02d} - ERROR: {}\n".format(
            timestamp[0], timestamp[1], timestamp[2],
            timestamp[3], timestamp[4], timestamp[5],
            error_message
        )
        f.write(log_entry)

async def activate_pump():
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
        log_error("Too many activations in one minute")

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

async def read_pir():
    try:
        return pir.value()
    except Exception as e:
        log_error(f"PIR sensor error: {str(e)}")
        return None

async def read_ultrasonic():
    try:
        return ultrasonic.distance_cm()
    except Exception as e:
        log_error(f"Ultrasonic sensor error: {str(e)}")
        return None

async def detect_motion():
    last_detection_time = "Never"

    while True:
        pir_value = await read_pir()
        distance = await read_ultrasonic()
        
        if pir_value is not None or distance is not None:
            cat_detected = False
            
            if pir_value == 1:
                cat_detected = True
            
            if distance is not None and distance < CAT_DISTANCE_THRESHOLD:
                cat_detected = True
            
            if cat_detected:
                display_status("angry", last_detection_time)
                await activate_pump()
                log_event("Motion Detected", distance if distance is not None else -1, pir_value if pir_value is not None else -1)
                last_detection_time = "{:02d}:{:02d}".format(utime.localtime()[3], utime.localtime()[4])
            else:
                display_status("watching", last_detection_time)
        else:
            display_error("Sensor error")
            log_error("Both sensors failed to read")
        
        await asyncio.sleep(0.1)

async def blink_onboard_led():
    while True:
        onboard_led.on()
        await asyncio.sleep(0.5)
        onboard_led.off()
        await asyncio.sleep(0.5)

async def main():
    print("Initializing sensors...")
    oled.fill(0)
    oled.text("Initializing...", 0, 0)
    for i in range(INITIALIZATION_TIME):
        oled.fill_rect(0, 20, int(i * OLED_WIDTH / INITIALIZATION_TIME), 10, 1)
        oled.show()
        await asyncio.sleep(1)
    
    print("Starting detection...")
    asyncio.create_task(detect_motion())
    asyncio.create_task(blink_onboard_led())

    while True:
        await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(main())