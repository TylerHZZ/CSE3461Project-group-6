import string
import sys
import threading
import socketserver

buff_size = 200
user_dict = {}
dict_lock = threading.Lock()

# Handles client requests
class HandleClient(socketserver.BaseRequestHandler):
    # gets client username and adds to dict
    def setup(self):
        self.request.send("Enter username: ".encode())
        self.username = self.request.recv(buff_size).decode()
        print(self.username)
        with dict_lock:
            user_dict[self.username] = self.request
        print(user_dict)

    # handles forwarding of messages to receiver
    def handle(self):
            while(True):
                message = self.request.recv(buff_size).decode()
                print(message)
                if len(message) == 0:
                    break
                if message.startswith("@"):
                    print("Proper format, client: " + self.username)
                    rec_user = message.split(None, 1)[0]
                    rec_user = rec_user[1:]
                    if rec_user in user_dict:
                        print("Receiver exists, client: " + self.username)
                        message = "FROM: " + self.username + "\n" + message[len(rec_user) + 2:]
                        user_dict[rec_user].send(message.encode())
                    else:
                     print("Invalid username, client: " + self.username)
                     self.request.send("Server: ERROR username not found".encode())
                else:
                     print("Invalid format, client: " + self.username)
                     self.request.send("Server: ERROR format message @username [message]".encode())


    # once connection closes removes client from dict
    def finish(self):
        with dict_lock:
            user_dict.pop(self.username)
        print(user_dict)
        if not user_dict:
            print("Shutting down")
            self.server.shutdown()



# input must be of given format
if (len(sys.argv) < 3):
    print("Usage: python3 " + sys.argv[0] + " server_ip server_port")
    sys.exit(1)
assert(len(sys.argv) == 3)
# get server ip and port
server_ip = sys.argv[1]
server_port=int(sys.argv[2])
# creates a thread for each new client, handles client in HandleClient class
with socketserver.ThreadingTCPServer((server_ip, server_port), HandleClient) as server:
    print("Waiting for clients")
    server.serve_forever()