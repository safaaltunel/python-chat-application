import threading
import subprocess
import json
import time
import socket
import select


# Get host IP
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.connect(("8.8.8.8", 80))
root_ip = s.getsockname()[0]
s.close()


HOST = root_ip
PORT = 12345

print("Welcome to chat.")

# User name
root_name = input("Please type in your name: ")

# Online users at the chat
online_users = dict()

received_discovers = dict()

def listen_for_discovery():
    """Listen thread for discovery messages. Opens UDP socket and listens for broadcast messages
    """
    global online_users
    global received_discovers
    while True:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.bind(('', PORT))
            s.setblocking(0)
            result = select.select([s],[],[])
            msg = result[0][0].recv(1024)
            message = json.loads(msg.decode('utf-8'))

            # Received message is type of "Discover"
            if message["type"] == 1 and message["IP"] != root_ip: 

                if received_discovers.get(message["name"]) == None:

                    # Add user to the online users dictionary
                    online_users[message["name"]] = message["IP"]
                    received_discovers[message["name"]] = message["ID"]
                    print()
                    print(message["name"], "is discovered you!")

                elif received_discovers[message["name"]] == message["ID"]:
                    # Received discover message before
                    # Do nothing
                    continue

                # Create message packet(JSON)
                packet = dict()
                packet["type"] = 2
                packet["name"] = root_name
                packet["IP"] = root_ip
                packet = json.dumps(packet)

                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                    sock.connect((message["IP"], PORT))
                    sock.sendall(packet.encode('utf-8'))

def listen():
    """Listener thread for incoming messages. In order to prevent socket consuming the console always, when a message is received the so program will be terminated and
    restarted again. It means that when a listener thread receives a message, it will stop listenning to make the console free and immediately start listenning again.
    Otherwise listener thread will always use the console and the user of this program will not be able to send message to other users.
    """
    global online_users
    while True:
        # Start listenning
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((HOST, PORT))
            s.listen()
            conn, addr = s.accept()
            with conn:
                output = conn.recv(1024)
                output = output.decode('utf-8')

                # Parse the message
                message = json.loads(output)

                # Received message is type of "Discover Response"
                if message["type"] == 2:

                    # Add responded user to the online users dictionary
                    online_users[message["name"]] = message["IP"]
                    print()
                    print("######")
                    print("New user has joined to chat!")
                    print(f"List of the online users:")
                    for user in online_users:
                        print(user)
                    print("######")

                # Received message is type of "Chat"
                else:

                    # Print the message to the console
                    name = message["name"]
                    body = message["body"]
                    print()
                    print(f"message from {name}: {body}")

def chat():
    """Chat thread for sending chat messages to online users.
    """
    while True:
        # Prompt user for who to send
        name = input("type name of the receiver: ")

        # The target user is not online. Inform the user.
        if online_users.get(name) == None:
            print()
            print("This user is not online!")
            continue
        
        # Prompt user for the chat message
        message = input("type your message: ")

        # Create message packet(JSON)
        packet = dict()
        packet["type"] = 3
        packet["name"] = root_name
        packet["body"] = message
        packet = json.dumps(packet)

        HOST = online_users[name]  # The server's hostname or IP address

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((HOST, PORT))
            s.sendall(packet.encode('utf-8'))


def discover():
    """Discover thread for sending discover messages
    """
    # Create message packet(JSON)
    packet = dict()
    packet["type"] = 1
    packet["name"] = root_name
    packet["IP"] = root_ip
    packet["ID"] = int(time.time())
    packet = json.dumps(packet)
    packet = str.encode(packet)

    for i in range(10):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.bind(('',0))
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST,1)
            sock.sendto(packet, ('<broadcast>', PORT))





listener_thread = threading.Thread(target=listen, daemon=True)
listener_thread.start()

discover_thread = threading.Thread(target = discover, daemon=True)
discover_thread.start()

listener_for_discovery = threading.Thread(target=listen_for_discovery, daemon=True)
listener_for_discovery.start()

chat_thread = threading.Thread(target = chat, daemon=True)
chat_thread.start()

while True:
    time.sleep(1)