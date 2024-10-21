# Project Ρομποτικής 2024

# ΑΛΕΞΟΠΟΥΛΟΥ ΑΔΑΜΑΝΤΙΑ <ice19390008@uniwa.gr>
# ΒΑΣΙΛΕΙΟΣ ΣΙΔΕΡΗΣ <ice20390209@uniwa.gr>

# Definitions
MOTOR_MAX = 32000  # Do not boost more than this as to not trigger overcurrent
JOLT_SPD = 10000
JOLT_TIME = 0.1
DEBUG = True

# Load core libraries
import board, pwmio, time, wifi

# Initialize motors

fl = pwmio.PWMOut(board.IO6, frequency=5000, duty_cycle=65535)
fr = pwmio.PWMOut(board.IO5, frequency=5000, duty_cycle=65535)
bl = pwmio.PWMOut(board.IO4, frequency=5000, duty_cycle=65535)
br = pwmio.PWMOut(board.IO3, frequency=5000, duty_cycle=65535)
# 65535 is stopped, 0 is max


# Define motor functions
def _sm(left: bool, reverse: bool, value: int) -> None:
    """
    Backend function that actually does the motor control.
    """
    if left:
        if reverse:
            bl.duty_cycle = value
        else:
            fl.duty_cycle = value
    else:
        if reverse:
            br.duty_cycle = value
        else:
            fr.duty_cycle = value


def move(left: bool, percent: int = 0) -> None:
    """
    Frontend function to set a motor's speed -100% to +100%, defaults to 0%.
    The left boolean sets if it's the left or right motor.
    """
    # Limit bind the variable
    percent = max(min(percent, 100), -100)

    reverse = percent < 0
    value = int(65535 - ((65535 - MOTOR_MAX) * abs(percent) / 100))

    if DEBUG:
        print(
            "Setting "
            + ("left" if left else "right")
            + " to "
            + ("" if not reverse else "-")
            + str(value)
        )

    # return # Use this to test the code without running the motors
    _sm(left, reverse, value)


def jolt(left: bool, reverse: bool) -> None:
    """
    Frontend function to begin motion.
    The left boolean sets if it's the left or right motor.
    The reverse boolean sets direction.
    """

    if DEBUG:
        print(
            "Jolting "
            + ("left" if left else "right")
            + " to "
            + ("" if not reverse else "-")
            + str(JOLT_SPD)
        )

    # return # Use this to test the code without running the motors
    _sm(left, reverse, JOLT_SPD)
    time.sleep(JOLT_TIME)
    _sm(left, reverse, 65535)


# Wi-Fi handling
if not wifi.radio.connected:
    from cptoml import keys, fetch

    stored_networks = keys("IWD")
    if stored_networks and DEBUG:
        print("Trying to connect to Wi-Fi with settings.toml")

    available_networks = []
    for i in wifi.radio.start_scanning_networks():
        available_networks.append(i.ssid)
    wifi.radio.stop_scanning_networks()
    for i in stored_networks:
        if i in available_networks:
            try:
                wifi.radio.connect(i, fetch(i, "IWD"))
                if wifi.radio.connected:
                    if DEBUG:
                        print("Successfully connected to " + i)
                    break
            except:
                pass

if not wifi.radio.connected:
    if DEBUG:
        print("Wifi was not connected!")
else:
    # Load telnet
    from telnet_console import telnet_console
