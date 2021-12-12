import threading
import subprocess
import json
import time
import socket
import select
import base64


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

received_acks = set()

file_packets = dict()

received_file_string = ""
received_file_name = ""
received_packet_length = 0
received_packets = []
received_packet_ids = set()


packets_to_send = 0

def listen_for_discovery():
    """Listen thread for discovery messages. Opens UDP socket and listens for broadcast messages
    """
    global online_users
    global received_discovers
    global received_file_name
    global received_file_string
    global received_packet_length
    global received_packet_ids
    global received_packets

    while True:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.bind(('', PORT))
            s.setblocking(0)
            result = select.select([s],[],[])
            msg = result[0][0].recv(10240)
            message = json.loads(msg.decode('utf-8'))

            # Received message is type of "Discover"
            if message["type"] == 1: 

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

            # Received message is file transfer
            elif message["type"] == 4:
                received_file_name = message["name"]
                if message["seq"] not in received_packet_ids:
                    received_packet_ids.add(message["seq"])
                    received_packets.append((message["seq"], message["body"]))
                    if message.get("number_of_packets") != None:
                        received_packet_length = message["number_of_packets"]

                    if len(received_packets) == received_packet_length:

                        received_packets.sort()
                        for _id,packet in received_packets:
                            received_file_string += packet
                        # all packets are received
                        with open(received_file_name, mode="wb") as f:
                            f.write(base64.decodebytes(received_file_string.encode('utf-8')))

                        received_packet_ids = set()
                        received_file_string = ""
                        received_packets = []
                        
                        print(f"{received_file_name} is received")

                    # Create message packet(JSON)
                    packet = dict()
                    packet["type"] = 5
                    packet["seq"] = message["seq"]
                    packet["rwnd"] = 10
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
    global received_acks
    while True:
        # Start listenning
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((HOST, PORT))
            s.listen()
            conn, addr = s.accept()
            with conn:
                output = conn.recv(10240)
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

                elif message["type"] == 5:
                    # Received message is type of "Acknowledgement"
                    received_acks.add(message["seq"])

                # Received message is type of "Chat"
                else:

                    # Print the message to the console
                    name = message["name"]
                    body = message["body"]
                    print()
                    print(f"message from {name}: {body}")


def packet_send(i, receiver_name, file_name):
    global received_acks
    global packets_to_send
    global file_packets

    # Create message packet(JSON)
    packet = dict()
    packet["type"] = 4
    packet["name"] = file_name
    packet["seq"] = i
    packet["body"] = file_packets[i]
    packet["IP"] = HOST
    packet = json.dumps(packet)

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        while True:

            # try to send packet
            sock.sendto(packet.encode('utf-8'), (online_users[receiver_name], PORT))

            # wait for one second
            time.sleep(1)

            # receiver received the packet
            if i in received_acks:
                # remove packet
                file_packets.pop(i)
                # we can send one more packet
                packets_to_send += 1

                # we sent all of the packets
                if len(file_packets) == 0:
                    print(f"File {file_name} is sent to {receiver_name}")

                    # reset received acknowledgements and packets to send
                    received_acks = set()
                    packets_to_send = 0
                
                break

def file_send(receiver_name, file_name):
    global file_packets
    global received_acks
    global packets_to_send

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        # Create message packet(JSON)
        packet = dict()
        packet["type"] = 4
        packet["name"] = file_name
        packet["seq"] = 1
        packet["body"] = file_packets[1]
        packet["IP"] = HOST
        packet["number_of_packets"] = len(file_packets)
        packet = json.dumps(packet)

        # send first packet
        while True:    
            sock.sendto(packet.encode('utf-8'), (online_users[receiver_name], PORT))
            time.sleep(1)

            # receiver is received packet 1
            if 1 in received_acks:

                # remove packet 1
                file_packets.pop(1)
                
                # try to send 10 more packets
                for i in range(2,12):

                    # there is no more packet to send
                    if file_packets.get(i) == None:
                        return

                    # send packet
                    packet_send_thread = threading.Thread(target=packet_send, daemon=True, args=(i,receiver_name, file_name,))
                    packet_send_thread.start()
                
                # next packet index to send
                packet_idx_to_send = 12

                # try to send other packets
                while True:

                    # there is no more packet to send
                    if file_packets.get(packet_idx_to_send) == None:
                        break

                    # we can send at least one more packet
                    if packets_to_send > 0:
                        # try to send packet
                        packet_send_thread = threading.Thread(target=packet_send, daemon=True, args=(packet_idx_to_send,receiver_name, file_name,))
                        packet_send_thread.start()

                        # increase packet index to send
                        packet_idx_to_send += 1

                        # decrease allowed packet numbers to send
                        packets_to_send -= 1
                break


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
        
        # Prompt user for selecting chat message or file transfer
        type = input("Type 1 for chat message, 2 for file transfer: ")

        if type == "1":

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

        elif type == "2":
            global file_packets
            if len(file_packets) > 0:
                print("previous file is not completely sent!")
                continue

            # file transfer
            path = input("pass the full path of the file to send: ")

            if '/' in path:
                file_name = path.split('/')[-1]
            else:
                file_name = path.split("\\")[-1]

            with open(path, mode="rb") as f:
                i = 0
                all_file = f.read()
                b64_string = base64.b64encode(all_file)
                b64_string = b64_string.decode('utf-8')

                while i + 1500 < len(b64_string):
                    packet = b64_string[i:i+1500]
                    file_packets[i//1500 + 1] = packet
                    i += 1500
                
                packet = b64_string[i:]
                file_packets[i//1500 + 1] = packet


            file_send_thread = threading.Thread(target=file_send, daemon=True, args=(name, file_name,))
            file_send_thread.start()

        else:
            print("Wrong type!")


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



try:

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
    
except:
    print()
    print("quitting")