import string
import sys
import threading
import socketserver

buff_size = 200
user_dict = {}
dict_lock = threading.Lock()

# Handles client requests
class HandleClient(socketserver.BaseRequestHandler):

    # when connection opens gets client username and adds to dict
    def setup(self):
        self.request.send("Enter username: ".encode())
        self.username = self.request.recv(buff_size).decode()
        while self.username in user_dict: #ensures usernames are unique
            self.request.send("SERVER: Username already in use, enter new username:".encode())
            self.username = self.request.recv(buff_size).decode()
        print(self.username) # DEBUG
        with dict_lock: # locks other threads out of editing dict
            user_dict[self.username] = self.request
        print(user_dict) # DEBUG

    # handles forwarding of messages to receiver
    def handle(self):
            while(True):
                message = self.request.recv(buff_size).decode() # receives message from client
                print(message) # DEBUG
                if len(message) == 0: # if message is empty (client exiting) exit loop and disconnect client
                    break
                
                if message.startswith("@"): # message starts with username
                    print("Proper format, client: " + self.username) # DEBUG
                    rec_user = message.split(None, 1)[0]
                    rec_user = rec_user[1:]
                    
                    if rec_user in user_dict: # username exists in dict
                        print("Receiver exists, client: " + self.username) # DEBUG
                        message = "FROM: " + self.username + "\n" + message[len(rec_user) + 2:] # add from user to message
                        user_dict[rec_user].send(message.encode()) # send message to receiver
                    
                    else: # username is not in dict
                     print("Invalid username, client: " + self.username) # DEBUG
                     self.request.send("Server: ERROR username not found".encode()) # send back error message
                
                else: #message is of invalid format
                     print("Invalid format, client: " + self.username) # DEBUG
                     self.request.send("Server: ERROR format message @username [message]".encode()) #send back error message


    # once connection closes removes client from dict
    def finish(self):
        with dict_lock: # locks other threads out of dict
            user_dict.pop(self.username)
        print(user_dict) # DEBUG
        if not user_dict: # when no users are in dict
            print("Shutting down") # DEBUG
            self.server.shutdown() #shutdown server



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