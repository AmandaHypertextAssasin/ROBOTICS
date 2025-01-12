import socket
import threading
import re
import os
import sys
import getpass
import termios
import tty


def input2(value: str = "") -> str:
    old = termios.tcgetattr(sys.stdin)
    tty.setraw(sys.stdin)
    try:
        sys.stdout.write(value)
        sys.stdout.flush()
        data = ""
        while True:
            char = sys.stdin.read(1)
            if char in ["\n", "\r"]:
                break
            elif char in ["\x03", "\x04"]:
                raise KeyboardInterrupt
            elif char == "\x7f":
                if data:
                    sys.stdout.write("\010 \010")  # left, space, left
                    sys.stdout.flush()
                    data = data[:-1]  # Thank god I know how terminals work
            elif char.isalnum() or char in [" ", "."]:
                data += char
                sys.stdout.write(char)
                sys.stdout.flush()
    except KeyboardInterrupt:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old)
        raise KeyboardInterrupt
    except Exception as err:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old)
        raise err
    termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old)
    return data


def ip_validate(ip: str) -> bool:
    pattern = re.compile(
        r"^(25[0-5]|2[0-4][0-9]|[0-1]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[0-1]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[0-1]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[0-1]?[0-9][0-9]?)$"
    )
    return bool(pattern.match(ip))


def ip_input(prompt: str, default: str = "") -> str:
    while True:
        user_input = input2(f"[{default}] {prompt}: ") or default
        if ip_validate(user_input):
            return user_input
        print("\nInvalid IPv4 address. Please try again.")


def handle_incoming(client_socket):
    # Get the local machine's IP address
    local_ip = socket.gethostbyname(socket.gethostname())

    commanding = False
    try:
        while True:
            response = client_socket.recv(1024)
            if not response:
                print("Connection closed by the server.")
                break
            message = response.decode("utf-8")
            match = re.match(r"\[(.*?)\]\s*(.*)", message)
            if match:
                target_ip, command = match.groups()
                if (
                    target_ip == "0.0.0.0"
                    or target_ip == local_ip
                    or (target_ip == "127.0.0.1")
                ):
                    if command == "vote":
                        # Give the server a urandom byte
                        client_socket.sendall(
                            b"[0.0.0.0] "
                            + str(int.from_bytes(os.urandom(1), "big")).encode("utf-8")
                        )
                        commanding = False  # Reset since a new voting proccess started
                    elif command == "master":
                        commanding = True
                        print("I am king!")
                    elif command == "forward":
                        forward(int(cmd[1]))
                    elif command == "move":
                        move(bool(int(cmd[1])), int(cmd[2]))
                    elif command == "stop":
                        stop()
                    elif command == "Unauthorized":
                        pass
                    else:
                        print(f"Unknown command: {command}")

    except (socket.error, ConnectionResetError):
        print("Connection error while receiving messages.")
    finally:
        client_socket.close()
        print("Disconnected from the server.\nPress enter to restart.")


def client(server_ip: str, server_port: int = 5080):
    last_ip = "0.0.0.0"

    try:
        # Create a socket object
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        # Connect to the server
        print(f"\nConnecting to {server_ip}:{server_port}...")
        client_socket.connect((server_ip, server_port))
        print("Connected to the server.")

        # Start a thread to handle incoming messages
        incoming_thread = threading.Thread(
            target=handle_incoming, args=[client_socket], daemon=True
        )
        incoming_thread.start()

        client_socket.sendall(b"[0.0.0.0] slave\n")
        client_socket.sendall(b"[0.0.0.0] vote\n")

        while True:
            try:
                if not incoming_thread.is_alive():
                    break

                getpass.getpass(
                    "\n"
                    + ("-" * 10)
                    + "Press enter to input commands"
                    + ("-" * 10)
                    + "\n"
                )

                if not incoming_thread.is_alive():
                    break

                # Take input from the user in an intervention-based manner
                target_ip = ip_input("Target", last_ip)
                if target_ip:
                    last_ip = target_ip

                # Clear the line (Go home, carriage returt and ansi escape clear following)
                sys.stdout.write("\r\033[K")

                while True:
                    command = input2(f"[{target_ip}] Data: ")
                    if not incoming_thread.is_alive():
                        break
                    if not command.strip():
                        print("\nERROR: Command cannot be empty.")
                        continue
                    else:
                        print()

                    message = f"[{target_ip}] {command}"

                    # Send the message to the server
                    client_socket.sendall(message.encode("utf-8"))
                    break
            except (socket.error, socket.timeout) as e:
                print(f"Error during communication: {e}")

    except ConnectionError as e:
        print(f"Connection error: {e}")
    finally:
        # Close the socket
        client_socket.close()


if __name__ == "__main__":
    try:
        while True:
            server_ip = ip_input(
                "Enter the server IP address to connect to", "127.0.0.1"
            )
            client(server_ip)
    except KeyboardInterrupt:
        print("\nExiting..")
    except Exception as err:
        print("\nERROR: Unhandled exception, aborting!")
        import traceback

        traceback.print_exception(err)
