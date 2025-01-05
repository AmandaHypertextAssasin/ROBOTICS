# Project Ρομποτικής 2024-2025

# ΑΛΕΞΟΠΟΥΛΟΥ ΑΔΑΜΑΝΤΙΑ <ice19390008@uniwa.gr>
# ΒΑΣΙΛΕΙΟΣ ΣΙΔΕΡΗΣ <ice20390209@uniwa.gr>

# Definitions
MOTOR_MAX = 32768  # Do not boost more than this as to not trigger overcurrent
MOTOR_FREQ = 10000  # PWM Frequency
JOLT_SPD = 0  # Boost speed
JOLT_TIME = 0.1  # Boost time
RAMP_INC = 1024  # Speed increments
RAMP_TICK = 0.001  # Time per speed step
PORT = 5225  # Socket port
HOST = "10.42.0.33"
DEBUG = True

# Load libraries
import board, digitalio, pwmio, time, wifi, microcontroller, ipaddress

from neopixel_write import neopixel_write
from traceback import print_exception
from usb_cdc import console as usbcon
from socketpool import SocketPool
from os import urandom
from sys import exit

from cptoml import keys, fetch

# Init neopixel
nx = digitalio.DigitalInOut(board.NEOPIXEL)
nx.switch_to_output()

ledcases = {
    0: (0, 0, 0),  # off
    1: (0, 3, 0),  # Alternative idle, to indicate input
    2: (0, 2, 0),  # Idle
    3: (7, 7, 0),  # Activity
    4: (0, 0, 5),  # Waiting
    5: (50, 0, 0),  # Error
    6: (255, 255, 255),  # Your eyes are gone
    7: (0, 0, 10),  # Alternative waiting
}


def snx(state: int) -> None:
    neopixel_write(nx, bytearray(ledcases[state]))


snx(3)

# Init motors
fl = pwmio.PWMOut(board.IO6, frequency=MOTOR_FREQ, duty_cycle=65535)
fr = pwmio.PWMOut(board.IO5, frequency=MOTOR_FREQ, duty_cycle=65535)
bl = pwmio.PWMOut(board.IO4, frequency=MOTOR_FREQ, duty_cycle=65535)
br = pwmio.PWMOut(board.IO3, frequency=MOTOR_FREQ, duty_cycle=65535)

# Last set state variables
fls = 65535
frs = 65535
bls = 65535
brs = 65535

# 65535 is stopped, 0 is max


# Define motor functions
def _sm(right: bool, reverse: bool, value: int) -> None:
    """
    Ramping speed controller. Madly optimized.
    """
    global fls, frs, bls, brs
    if not right:
        if reverse:
            fl.duty_cycle = 65535
            fls = 65535
            while value < bls:
                bls -= RAMP_INC
                if DEBUG:
                    terminal_write("Ramping.. " + str(bls) + "\n\r")
                bl.duty_cycle = bls
                time.sleep(RAMP_TICK)
            while value > bls:
                bls += RAMP_INC
                if DEBUG:
                    terminal_write("Ramping.. " + str(bls) + "\n\r")
                bl.duty_cycle = bls
                time.sleep(RAMP_TICK)
        else:
            bl.duty_cycle = 65535
            bls = 65535
            while value < fls:
                fls -= RAMP_INC
                if DEBUG:
                    terminal_write("Ramping.. " + str(fls) + "\n\r")
                fl.duty_cycle = fls
                time.sleep(RAMP_TICK)
            while value > fls:
                fls += RAMP_INC
                if DEBUG:
                    terminal_write("Ramping.. " + str(fls) + "\n\r")
                fl.duty_cycle = fls
                time.sleep(RAMP_TICK)
    else:
        if reverse:
            fr.duty_cycle = 65535
            frs = 65535
            while value < brs:
                brs -= RAMP_INC
                if DEBUG:
                    terminal_write("Ramping.. " + str(brs) + "\n\r")
                br.duty_cycle = brs
                time.sleep(RAMP_TICK)
            while value > brs:
                brs += RAMP_INC
                if DEBUG:
                    terminal_write("Ramping.. " + str(brs) + "\n\r")
                br.duty_cycle = brs
                time.sleep(RAMP_TICK)
        else:
            br.duty_cycle = 65535
            brs = 65535
            while value < frs:
                frs -= RAMP_INC
                if DEBUG:
                    terminal_write("Ramping.. " + str(frs) + "\n\r")
                fr.duty_cycle = frs
                time.sleep(RAMP_TICK)
            while value > frs:
                frs += RAMP_INC
                if DEBUG:
                    terminal_write("Ramping.. " + str(frs) + "\n\r")
                fr.duty_cycle = frs
                time.sleep(RAMP_TICK)


def stop() -> None:
    """
    Stop both motor immediately.
    """
    global fls, frs, bls, brs
    fr.duty_cycle = 65535
    frs = 65535
    br.duty_cycle = 65535
    brs = 65535
    fl.duty_cycle = 65535
    fls = 65535
    bl.duty_cycle = 65535
    bls = 65535
    if DEBUG:
        terminal_write("Stopping!\n\r")


def move(right: bool, percent: int = 0) -> None:
    """
    Frontend function to set a motor's speed -100% to +100%, defaults to 0%.
    The right boolean sets if it's the left or right motor.
    """
    snx(3)
    # Limit bind the variable
    percent = max(min(percent, 100), -100)

    reverse = percent < 0
    value = int(65535 - ((65535 - MOTOR_MAX) * abs(percent) / 100))

    if DEBUG:
        terminal_write(
            "Setting "
            + ("left" if not right else "right")
            + " to "
            + ("" if not reverse else "-")
            + str(value)
            + "\n\r"
        )

    # return # Use this to test the code without running the motors
    _sm(right, reverse, value)
    snx(2)


def jolt(right: bool, reverse: bool) -> None:
    """
    Frontend function to begin motion.
    The right boolean sets if it's the left or right motor.
    The reverse boolean sets direction.
    """
    snx(3)
    if DEBUG:
        terminal_write(
            "Jolting "
            + ("left" if not right else "right")
            + " to "
            + ("" if not reverse else "-")
            + str(JOLT_SPD)
            + "\n\r"
        )

    # return # Use this to test the code without running the motors
    _sm(left, reverse, JOLT_SPD)
    time.sleep(JOLT_TIME)
    _sm(right, reverse, 65535)
    snx(2)


def is_stopped() -> bool:
    return fls == frs == bls == brs == 65535


def forward(spd: int = 100) -> None:
    if is_stopped():
        jolt()
    move(False, spd)
    move(True, spd)


# Wi-Fi handling
for i in range(3):  # Retry wifi conn 3 times
    if not wifi.radio.connected:
        stored_networks = keys("IWD")
        if stored_networks and DEBUG:
            print("Trying to connect to Wi-Fi with `settings.toml`. (" + str(i) + "/3)")

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
                            snx(2)
                        break
                except:
                    pass
    else:
        break

if not wifi.radio.connected:
    if DEBUG:
        print("Wifi was not connected!")
        exit(1)

LOCAL_IP = str(wifi.radio.ipv4_address) # Our current IPv4 address

# Socket comms
pool = SocketPool(wifi.radio)
sock = pool.socket(pool.AF_INET, pool.SOCK_STREAM)
sock.settimeout(8) # Connection / Transmission timeout

print("Connecting.. ", end="")
try:
    snx(4)
    sock.connect((HOST, 5080)) # Connect to server
    snx(3)
except Exception as err:
    print("FAIL!\n")
    print_exception(err)
    exit(1)
print("Done!")

rx_buf = bytearray(512)  # Receive buffer, static allocation


def sock_recv():
    # Receives data from the server, parses the IPv4 address and data.
    try:
        size = sock.recv_into(rx_buf)
    except:
        return
    raw = rx_buf[:size].decode("utf-8")

    if "]" in raw:
        ip, data = raw.split("]", 1)
        ip = ip.strip("[")  # Remove the leading '['
        data_list = data.strip().split(" ")  # Split the remaining data by spaces
        return ip, data_list
    else:
        raise ValueError("Invalid data format")


def sock_send(data: str, target: str = "0.0.0.0") -> int:
    # Sends a set of data along with an ip header, defaulting to broadcast.
    return sock.send(bytes(f"[{target}] {data}", "UTF-8"))


# Terminal muxer, obsolete
def terminal_waiting() -> int:
    res = 0
    if usbcon.in_waiting:
        res += usbcon.in_waiting
    return res


cbuf = ""


def terminal_write(data: str) -> None:
    if usbcon.connected:
        usbcon.write(data.encode("UTF-8"))


if DEBUG:
    print("Running main loop")

# Main program loop

commanding = False  # We are king
sock_send("slave")
sock_send("vote")

try:
    while True:
        try:
            ip, cmd = sock_recv()
            snx(3)
            if ip in ["0.0.0.0", LOCAL_IP]:  # Only accept bcast / targetted packets
                if cmd[0] == "vote":
                    # Give the server a urandom byte
                    sock_send(str(int.from_bytes(urandom(1), "big")))
                    commanding = False # Reset since a new voting proccess started
                elif cmd[0] == "master":
                    commanding = True
                    print("I am king!")
                elif cmd[0] == "forward":
                    forward(int(cmd[1]))
                elif cmd[0] == "move":
                    move(bool(int(cmd[1])), int(cmd[2]))
                elif cmd[0] == "stop":
                    stop()
                elif cmd[0] == "Unauthorized":
                    pass
                else:
                    print(f"Unknown command: {cmd[0]}")
            snx(2)
        except TypeError:
            pass
except Exception as err:
    # Catchall, reset if no usb
    if usbcon.connected:
        print("\nCrashed!")
        print_exception(err)
    else:
        snx(5)
        microcontroller.reset()
