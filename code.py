# Project Ρομποτικής 2024

# ΑΛΕΞΟΠΟΥΛΟΥ ΑΔΑΜΑΝΤΙΑ <ice19390008@uniwa.gr>
# ΒΑΣΙΛΕΙΟΣ ΣΙΔΕΡΗΣ <ice20390209@uniwa.gr>

# Definitions
MOTOR_MAX = 32768  # Do not boost more than this as to not trigger overcurrent
MOTOR_FREQ = 10000 # PWM Frequency
JOLT_SPD = 0       # Boost speed
JOLT_TIME = 0.1    # Boost time
RAMP_INC = 1024    # Speed increments
RAMP_TICK = 0.001  # Time per speed step
PORT = 5225        # Socket port
DEBUG = True

# Load core libraries
import board, digitalio, pwmio, time, wifi
from usb_cdc import console as usbcon
from socketpool import SocketPool
from neopixel_write import neopixel_write
import microcontroller

# Static allocations


class Socket_Communication_Client:
    def __init__(self):
        self._sock = sp.socket(
            sp.AF_INET,
            sp.SOCK_STREAM,
        )
        self._sock.settimeout(timeout)
        self._sock.bind((str(wifi.radio.ipv4_address), PORT))
        self._sock.listen(8)

        self.rx_buf = bytearray(512)  # Receive buffer, static allocation
        self.ps_buf = bytearray()     # Parse buffer
        self.tx_buf = bytearray()     # Send buffer

        self.socket = []    #list to store the connected sockets
        self.connections=[] #list to store client connections
        self.data=[]        #client connection data (e.g. ip's)

    def _background_task() -> None: #function w no args that returns None
        try:
            sock_conn, sock_client = self._socket.accept()
            self._conn.settimeout(10)
            self._conn.setblocking(True)
        except OSError:  # No connection took place.
            pass


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

fl = pwmio.PWMOut(board.IO6, frequency=MOTOR_FREQ, duty_cycle=65535)
fr = pwmio.PWMOut(board.IO5, frequency=MOTOR_FREQ, duty_cycle=65535)
bl = pwmio.PWMOut(board.IO4, frequency=MOTOR_FREQ, duty_cycle=65535)
br = pwmio.PWMOut(board.IO3, frequency=MOTOR_FREQ, duty_cycle=65535)

# Last set state
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


# Triple terminal muxer
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
        elif espcon.connected and espcon.in_waiting:
            dat += espcon.read(no if no is not None else espcon.in_waiting)
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
    if espcon.connected:
        espcon.write(data.encode("UTF-8"))


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
                microcontroller.reset()
            elif cmd in ["set", "s"]:
                try:
                    motor = int(dat[1])
                    spd = int(dat[2])
                    move(bool(motor), spd)
                    if motor == 2:  # Do both
                        move(False, spd)
                except:
                    terminal_write("Invalid arguments.\n\rExample: `set 0 100`\n\r")
            elif cmd in ["view", "v"]:
                terminal_write(
                    f"Front Left: {fls}\n\rFront Right: {frs}\n\rBack Left: {bls}\n\rBack Right: {brs}\n\r"
                )
            elif cmd in ["stop", "st"]:
                stop()
                terminal_write("Stopped!\n\r")
            elif cmd in ["quit", "q"]:
                terminal_write("Exiting..\n\r")
                break
            elif cmd in ["temp", "t"]:
                terminal_write(str(microcontroller.cpu.temperature) + "℃\n\r")
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
        microcontroller.reset()
