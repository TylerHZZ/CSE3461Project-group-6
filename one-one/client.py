import string
import sys
import threading
from socket import *

buff_size = 200

# deals with receiving messages
def receive(rec_socket: socket):
    while(True):
        try:
            open = rec_socket.recv(buff_size, MSG_PEEK | MSG_DONTWAIT)
            if len(open) == 0:
                break # if connection was closed by server
        except BlockingIOError:
            continue # nothing in buffer to read
        except OSError:
            break # connection was broken
        message = rec_socket.recv(buff_size).decode()
        print()
        print(message)
        if len(message) == 0:
            print("Server closed connection, press ENTER to exit")
            break

# input must be of given format
if (len(sys.argv) < 3):
    print("Usage: python3 " + sys.argv[0] + " server_ip server_port")
    sys.exit(1)
assert(len(sys.argv) == 3)
# get server ip and port
server_ip = sys.argv[1]
server_port=int(sys.argv[2])
# Create a socket for the client
client_socket=socket(AF_INET, SOCK_STREAM)
# connect socket to server
client_socket.connect((server_ip, server_port))
print("Connected to server " + server_ip)
# wait for server to prompt for username
data = client_socket.recv(buff_size).decode()
# prompt for username
username = input(data)
# send username to server
try:
    client_socket.send(username.encode())
except BrokenPipeError:
    print("Connection failed")
    sys.exit(1)
# create receiving thread
receiving = threading.Thread(target=receive, args=(client_socket,))
# start receiving
receiving.start()
# handles sending messages
while(True):
    message = input()
    if len(message) == 0: #empty message closes connection (and potentially server)
        print("Exiting")
        break
    try:
        client_socket.send(message.encode())
    except BrokenPipeError:
        print("Connection failed")
        break
client_socket.close()
# close receiving thread
receiving.join()