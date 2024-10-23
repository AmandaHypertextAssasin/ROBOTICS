# Project Ρομποτικής 2024

# ΑΛΕΞΟΠΟΥΛΟΥ ΑΔΑΜΑΝΤΙΑ <ice19390008@uniwa.gr>
# ΒΑΣΙΛΕΙΟΣ ΣΙΔΕΡΗΣ <ice20390209@uniwa.gr>

# Definitions
MOTOR_MAX = 9830  # Do not boost more than this as to not trigger overcurrent
JOLT_SPD = 0
JOLT_TIME = 0.1
DEBUG = True

# Load core libraries
import board, digitalio, pwmio, time, wifi
from usb_cdc import console as usbcon
from socketpool import SocketPool
from neopixel_write import neopixel_write

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

# Initialize motors

fl = pwmio.PWMOut(board.IO6, frequency=5000, duty_cycle=65535)
fr = pwmio.PWMOut(board.IO5, frequency=5000, duty_cycle=65535)
bl = pwmio.PWMOut(board.IO4, frequency=5000, duty_cycle=65535)
br = pwmio.PWMOut(board.IO3, frequency=5000, duty_cycle=65535)

# Last set state
fls = 65535
frs = 65535
bls = 65535
brs = 65535

# 65535 is stopped, 0 is max


# Define motor functions
def _sm(right: bool, reverse: bool, value: int) -> None:
    """
    Backend function that actually does the motor control.
    """
    global fls, frs, bls, brs
    if not right:
        if reverse:
            bl.duty_cycle = value
            bls = value
            fl.duty_cycle = 65535
            fls = 65535
        else:
            bl.duty_cycle = 65535
            bls = 65535
            fl.duty_cycle = value
            fls = value
    else:
        if reverse:
            fr.duty_cycle = 65535
            frs = value
            br.duty_cycle = value
            brs = value
        else:
            fr.duty_cycle = value
            frs = value
            br.duty_cycle = 65535
            brs = 65535


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


def stop() -> None:
    move(False, 0)
    move(True, 0)


# Wi-Fi handling
for i in range(3):  # Retry wifi conn 3 times
    if not wifi.radio.connected:
        from cptoml import keys, fetch

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

telnet = None
telnet_active = False
# usb console at usbcon

if not wifi.radio.connected:
    if DEBUG:
        print("Wifi was not connected!")
        snx(7)
else:
    # Load telnet
    from telnet_console import telnet_console

    sp = SocketPool(wifi.radio)
    telnet = telnet_console(
        sp.socket(
            sp.AF_INET,
            sp.SOCK_STREAM,
        ),
        str(wifi.radio.ipv4_address),
    )
    if DEBUG:
        print("Telnet console created at " + str(wifi.radio.ipv4_address))


# Dual terminal muxer
def terminal_waiting() -> int:
    res = 0
    if telnet is not None and telnet.connected:
        res += telnet.in_waiting
    if usbcon.in_waiting:
        res += usbcon.in_waiting
    return res


def telnet_upd() -> bool:
    if telnet is not None:
        global telnet_active
        if telnet_active and not telnet.connected:
            telnet_active = False
        elif (not telnet_active) and telnet.connected:
            telnet_active = True
            return True
    return False


cbuf = ""


def terminal_read(no=None):
    global cbuf
    dat = b""
    if not len(cbuf):
        if telnet_active and telnet.in_waiting:
            dat += telnet.read(no if no is not None else telnet.in_waiting)
        elif usbcon.connected and usbcon.in_waiting:
            dat += usbcon.read(no if no is not None else usbcon.in_waiting)
        if not len(dat):
            dat = None
        else:
            try:
                dat = dat.decode("UTF-8")
            except:
                pass
        if dat is not None and len(dat) > 1:
            cbuf = dat[1:]
            dat = dat[:1]
    else:
        dat = cbuf[:1]
        cbuf = cbuf[1:]
    return dat


def terminal_write(data: str) -> None:
    if telnet is not None and telnet.connected:
        telnet.write(data.encode("UTF-8"))
    if usbcon.connected:
        usbcon.write(data.encode("UTF-8"))


def terminal_cmd() -> list:
    terminal_write("@> ")
    res = ""
    try:
        while True:
            if telnet_upd():
                terminal_write("\n\rTelnet active!\n\r")
                return []
            dat = []
            dat = terminal_read()
            if dat is not None:
                if dat in ["\n", "\r", "\n\r", "\r\n", "\r\x00"]:
                    terminal_write("\n\r")
                    break
                elif dat == "\x7f":  # Backspace
                    if res:
                        res = res[:-1]
                        terminal_write("\010 \010")
                elif dat == "\x04":  # Ctrl + D
                    if telnet is not None and telnet.connected:
                        terminal_write("\n\rDisconnecting..\n\r")
                        telnet.disconnect()
                        return []
                    else:
                        return ["quit"]
                elif dat == "\x03":  # Ctrl + C
                    raise KeyboardInterrupt
                elif dat.isalpha() or dat.isdigit() or dat in [" ", "-"]:
                    res += dat
                    terminal_write(dat)
    except KeyboardInterrupt:
        terminal_write("^C\n\r")
        return []
    res = res.split(" ")
    while "" in res:
        res.remove("")
    return res


if DEBUG:
    print("Running main loop")

# Main program loop
try:
    while True:
        dat = terminal_cmd()
        if len(dat):
            cmd = dat[0].lower()
            if cmd in ["reload", "rel"]:
                import supervisor

                if telnet is not None:
                    telnet.disconnect()
                    telnet.deinit()
                supervisor.reload()
            elif cmd in ["reset", "res", "rst"]:
                import microcontroller

                microcontroller.reset()
            elif cmd in ["set", "s"]:
                try:
                    motor = int(dat[1])
                    spd = int(dat[2])
                    move(bool(motor), spd)
                    if motor == 2:  # Do both
                        move(False, spd)
                except:
                    terminal_write("Invalid arguments.\n\rExample: `set 0 100`")
            elif cmd in ["view", "v"]:
                terminal_write(
                    f"Front Left: {fls}\n\rFront Right: {frs}\n\rBack Left: {bls}\n\rBack Right: {brs}\n\r"
                )
            elif cmd in ["quit", "q"]:
                terminal_write("Exiting..\n\r")
                break
            else:
                terminal_write("Invalid command!\n\r")
except Exception as err:
    # Catchall, reset if no usb
    if usbcon.connected:
        print("\nCrashed!")
        from traceback import print_exception

        print_exception(err)
    else:
        snx(5)
        import microcontroller

        microcontroller.reset()
