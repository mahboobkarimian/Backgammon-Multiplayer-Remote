import copy
from datetime import datetime, timezone
import string
import time
import tkinter as tk
from tkinter import ttk
from tkinter import *
from tkinter import messagebox
from PIL import Image, ImageTk
import random
from ttkthemes import ThemedTk
import socketio
import ipaddress
import threading
from flask import Flask
import json, pickle
from base64 import b64encode, b64decode
from Crypto.Cipher import ChaCha20
import jwt


# No TLS as we only use IP.
# Using socket.io meit only data can be encrypted and not events,
# so one should use send function if he/she wants full encryption.
key = b'weareplayingtogetherdearfriends!'
cipher = ChaCha20.new(key=key)
used_tokens=set()

game_started = -1
thread_started = False
last_1st_dice = ""

global_bg = "gray90"

conn_port = 5000
conn_ip = "0.0.0.0"

sio = None
is_server = False
#################################################
def authenticate(rx_token=""):
    timestamp = int(datetime.now(timezone.utc).timestamp())
    payload = str(timestamp)
    secret = ackey.get()
    token = jwt.encode({"someinfo": payload}, secret, algorithm="HS256")
    if not is_server:
        # generated token for client auth
        return token
    else:
        # check token validity
        try:
            dec_rx_token = jwt.decode(rx_token, secret, algorithms=["HS256"])
        except:
            print("Can't decode token!")
            return False
        
        # check OT token
        if rx_token not in used_tokens:
            used_tokens.add(rx_token)
        else:
            print("One time token is used before")
            return False

        # check token age (must not be older than 5 sec)
        if timestamp - int(dec_rx_token['someinfo']) < 5:
            #print(timestamp, int(dec_rx_token['someinfo']))
            return True
        else:
            return False

def enc_dec(data, dec=False):
    global cipher
    if not dec:
        data = pickle.dumps(data)
        ciphertext = cipher.encrypt(data)
        nonce = b64encode(cipher.nonce).decode('utf-8')
        ct = b64encode(ciphertext).decode('utf-8')
        result = json.dumps({'nonce':nonce, 'ciphertext':ct})
        return result
    else:
        try:
            b64 = json.loads(data)
            nonce = b64decode(b64['nonce'])
            ciphertext = b64decode(b64['ciphertext'])
            cipher = ChaCha20.new(key=key, nonce=nonce)
            plaintext = cipher.decrypt(ciphertext)
            print("The message was " + plaintext)
            return pickle.loads(plaintext)
        except (ValueError, KeyError):
            print("Incorrect decryption")
            return None

client_authed = False
def set_client_authed(flag):
    global client_authed
    client_authed = flag
def get_client_flag():
    print(client_authed, "is this")
    return client_authed

def conn_sock():
    global sio
    global is_server
    global thread_started
    thread_started = True

    if ipaddress.ip_address(conn_ip).is_private:
    # Server
        print("Creating a server")
        is_server = True
        sio = socketio.Server(async_mode='threading')
        app = Flask(__name__)
        app.wsgi_app = socketio.WSGIApp(sio, app.wsgi_app)

        @sio.event
        def connect(sid, environ):
            print('connect ', sid)
            return
            ip = environ['REMOTE_ADDR']
            Statuslabel.config(text=f"Connection: Opponent Connected {ip}")

        @sio.event
        def connect(sid, environ, auth):
            print('connect ', sid)
            ip = environ['REMOTE_ADDR']
            token = environ.get('HTTP_AUTHORIZATION')
            print('connect ', sid, ip, token, auth)
            if not authenticate(auth):
                print("invalid token")
                sio.disconnect(sid)
                return
            sio.emit("authed", "True", to=sid)
            Statuslabel.config(text=f"Connection: Opponent Connected {ip}")

        @sio.event
        def pos(sid, data):
            print('pos rx', data)
            ip = sio.get_environ(sid)['REMOTE_ADDR']
            print(ip, data)
            move_opponent(data[0], data[1], data[2], data[3])

        @sio.event
        def dice(sid, data):
            print("dice rx", data)
            start_dice(data[0], data[1])

        @sio.event
        def disconnect(sid):
            print('disconnect ', sid)
            Statuslabel.config(text=f"Connection: Opponent Disconnected")
        Statuslabel.config(text=f"Connection: Server Created")
        app.run(host='0.0.0.0', port=5000)

    else:
        # Client
        is_server = False
        print("Connecting to a server")
        sio = socketio.Client()
        @sio.event
        def pos(data):
            print('Client: I received a message!')
            print(data)
            move_opponent(data[0], data[1], data[2], data[3])

        @sio.event
        def dice(data):
            print("dice rx", data)
            start_dice(data[0], data[1])

        @sio.event
        def reset(data):
            print("reset cmd rx")
            reset_game()
        
        @sio.event
        def connect():
            print("Connect")
            if get_client_flag():
                Statuslabel.config(text=f"Connection: Connected")
            else:
                Statuslabel.config(text=f"Connection: Connecting ...")

        @sio.event
        def authed(data):
            print("Authed")
            set_client_authed(flag=True)
            Statuslabel.config(text=f"Connection: Authed")

        @sio.event
        def connect_error(data):
            print("The connection failed!")
            Statuslabel.config(text=f"Connection: Error")

        @sio.event
        def disconnect():
            print("I'm disconnected!")
            Statuslabel.config(text=f"Connection: Disconnected")
        
        sio.connect(f"http://{conn_ip}:{int(conn_port)}", auth=authenticate)

t_conn = threading.Thread(target=conn_sock)
t_conn.daemon=True
#################################################

# Create the window with the Tk class
root = ThemedTk(theme="arc")
root.configure(bg=global_bg)
root.geometry("1550x850")
player_color = StringVar()

# Define variables for dimensions
w = 1145
h = 800
x = w/2
y = h/2

# Create the canvas and make it visible with pack()
canvas = Canvas(root, width=1145, height=800)
canvas.place(x=250, y=20)
#canvas.pack()  # this makes it visible

# Define list of images for dice
dice1 = ['./images/Dice-1.png', './images/Dice-2.png', './images/Dice-3.png', './images/Dice-4.png', './images/Dice-5.png', './images/Dice-6.png']
dice2 = dice1.copy()


# Create class of stone type
class Stone():

    def __init__(self, x, y, rangex, rangey, rangezx, rangezy, color):

        super().__init__()
        self.x = x
        self.y = y
        self.rangex = rangex
        self.rangey = rangey
        self.rangezx = rangezx
        self.rangezy = rangezy
        self.color = color

    def g_create(self):
        self.img = PhotoImage(
            file="./images/green_stone.PNG")
        img3 = canvas.create_image(self.x, self.y, image=self.img)
        return

    def b_create(self):
        self.img = PhotoImage(
            file="./images/blue_stone.PNG")
        img3 = canvas.create_image(self.x, self.y, image=self.img)
        return

    def get_posrangex(self):
        return self.rangex

    def get_posrangey(self):
        return self.rangey

    def get_posrangezx(self):
        return self.rangezx

    def get_posrangezy(self):
        return self.rangezy

    def get_color(self):
        return self.color


# Load the images of dice
DiceImage1 = None
DiceImage2 = None


# Construct a label widget for image
ImageLabel1 = tk.Label(root, image=DiceImage1, bg=global_bg)
ImageLabel1.image = DiceImage1
ImageLabel2 = tk.Label(root, image=DiceImage2, bg=global_bg)
ImageLabel2.image = DiceImage2


# Place the images in specific position
ImageLabel1.place(x=50, y=70)
ImageLabel2.place(x=50, y=200)


# Loads and create image of the game board
img1 = tk.PhotoImage(file="./images/board.jpg")
image = canvas.create_image(0, 0, anchor=tk.NW, image=img1)

# Create the stones in the starting position
B_List = [Stone(655, 50, 655+32, 50+32, 655-32, 50-32, "green"),
          Stone(655, 115, 655+32, 115+32, 655-32, 115-32, "green"),
          Stone(655, 180, 655+32, 180+32, 655-32, 180-32, "green"),
          Stone(655, 245, 655+32, 245+32, 655-32, 245-32, "green"),
          Stone(655, 310, 655+32, 310+32, 655-32, 310-32, "green"),

          Stone(400, 50, 400+32, 50+32, 400-32, 50-32, "green"),
          Stone(400, 115, 400+32, 115+32, 400-32, 115-32, "green"),
          Stone(400, 180, 400+32, 180+32, 400-32, 180-32, "green"),

          Stone(57, 750, 57+32, 750+32, 57-32, 750-32, "green"),
          Stone(57, 685, 57+32, 685+32, 57-32, 685-32, "green"),
          Stone(57, 620, 57+32, 620+32, 57-32, 620-32, "green"),
          Stone(57, 555, 57+32, 555+32, 57-32, 555-32, "green"),
          Stone(57, 490, 57+32, 490+32, 57-32, 490-32, "green"),

          Stone(1088, 750, 1088+32, 750+32, 1088-32, 750-32, "green"),
          Stone(1088, 685, 1088+32, 685+32, 1088-32, 685-32, "green"),

          Stone(655, 750, 655+32, 750+32, 655-32, 750-32, "blue"),
          Stone(655, 685, 655 + 32, 685 + 32, 655 - 32, 685 - 32, "blue"),
          Stone(655, 620, 655 + 32, 620 + 32, 655 - 32, 620 - 32, "blue"),
          Stone(655, 555, 655 + 32, 555 + 32, 655 - 32, 555 - 32, "blue"),
          Stone(655, 490, 655 + 32, 490 + 32, 655 - 32, 490 - 32, "blue"),

          Stone(400, 750, 400+32, 750+32, 400-32, 750-32, "blue"),
          Stone(400, 685, 400+32, 685+32, 400-32, 685-32, "blue"),
          Stone(400, 620, 400+32, 620+32, 400-32, 620-32, "blue"),

          Stone(57, 50, 57+32, 50+32, 57-32, 50-32, "blue"),
          Stone(57, 115, 57+32, 115+32, 57-32, 115-32, "blue"),
          Stone(57, 180, 57+32, 180+32, 57-32, 180-32, "blue"),
          Stone(57, 245, 57+32, 245+32, 57-32, 245-32, "blue"),
          Stone(57, 310, 57+32, 310+32, 57-32, 310-32, "blue"),

          Stone(1088, 50, 1088+32, 50+32, 1088-32, 50-32, "blue"),
          Stone(1088, 115, 1088+32, 115+32, 1088-32, 115-32, "blue"),

          Stone(1600, 1600, 1600+65, 1600+65, 0, 0, "dummy")]

B_List_bkp = copy.deepcopy(B_List)

# Put the stones in game board (by slicing-green stones 0-15, blue stones 15-31)
def setgame():
    for obj in B_List[0:15]:
        obj.g_create()

    for obj in B_List[15:31]:
        obj.b_create()
    
setgame()

def reset_game():
    global B_List
    if messagebox.askokcancel("Reset", "A reset has been requested, agreed?"):
        B_List.clear()
        B_List = copy.deepcopy(B_List_bkp)
        setgame()
        if is_server and sio:
            sio.emit("reset", "")


def connect():
    global conn_port
    global conn_ip
    ipport = ntp.get()
    if ipport:
        ip = str(ipport).split(":")[0]
        port = str(ipport).split(":")[1]
        conn_ip = ip
        conn_port = port
        #connect_to(ip, port)
        if thread_started:
            print("Closing socket and stoping worker thread")
            sio.disconnect()
            sio.connect(f"http://{conn_ip}:{int(conn_port)}", auth=authenticate())
            return
        t_conn.start()
        if is_server:
            button.config(state=NORMAL)
            Resetbutton.config(state=NORMAL)
            button1.config(state=DISABLED)
            letters = string.ascii_uppercase
            strkey = ''.join(random.choice(letters) for _ in range(8))
            ackey.delete(0, END)
            ackey.insert(0, f"{strkey}")
    else:
        print("At least a port shoud be provided e.g. 0.0.0.0:5000")

def start_dice(value1, value2):
    global game_started
    global last_1st_dice

    if value2 == 0:
        DiceImage1 = ImageTk.PhotoImage(Image.open(value1))
        ImageLabel1.configure(image=DiceImage1)
        ImageLabel1.image = DiceImage1
        last_1st_dice = value1
        game_started = game_started + 1

    elif value1 == 0:
        DiceImage2 = ImageTk.PhotoImage(Image.open(value2))
        ImageLabel2.configure(image=DiceImage2)
        ImageLabel2.image = DiceImage2
        game_started = game_started + 1
        
    else:
        game_started = game_started + 1
        DiceImage1 = ImageTk.PhotoImage(Image.open("./images/Rolling.PNG"))
        DiceImage2 = ImageTk.PhotoImage(Image.open("./images/Rolling.PNG"))
        ImageLabel1.configure(image=DiceImage1)
        ImageLabel2.configure(image=DiceImage2)
        root.update_idletasks() 
        time.sleep(0.2)
        DiceImage1 = ImageTk.PhotoImage(Image.open(value1))
        DiceImage2 = ImageTk.PhotoImage(Image.open(value2))
        ImageLabel1.configure(image=DiceImage1)
        ImageLabel2.configure(image=DiceImage2)
        ImageLabel1.image = DiceImage1
        ImageLabel2.image = DiceImage2
    if not is_server:
        button.config(state=NORMAL)
    if game_started > 1:
        button.config(state=NORMAL)
    print("game_started", game_started)

# Function to rolling the dice (function activated by button)
def rolling_dice():
    global game_started
    global last_1st_dice

    if game_started == -1:
        choice1 = random.choice(dice1)
        DiceImage1 = ImageTk.PhotoImage(Image.open(choice1))
        game_started = game_started + 1
        last_1st_dice = choice1
        ImageLabel1.configure(image=DiceImage1)
        ImageLabel1.image = DiceImage1
        if sio:
            sio.emit("dice", [choice1, 0])
            
    elif game_started == 0:
        while (True):
            choice2 = random.choice(dice2)
            if choice2 != last_1st_dice:
                break
        DiceImage2 = ImageTk.PhotoImage(Image.open(choice2))
        game_started = game_started + 1
        ImageLabel2.configure(image=DiceImage2)
        ImageLabel2.image = DiceImage2
        if sio:
            sio.emit("dice", [0, choice2])

    else:
    # Randomize the dice and load the choice
        game_started = game_started + 1
        choice1 = random.choice(dice1)
        DiceImage1 = ImageTk.PhotoImage(Image.open(choice1))
        choice2 = random.choice(dice2)
        DiceImage2 = ImageTk.PhotoImage(Image.open(choice2))
        if sio:
            sio.emit("dice", [choice1, choice2])
        DiceImage1_wait = ImageTk.PhotoImage(Image.open("./images/Rolling.PNG"))
        DiceImage2_wait = ImageTk.PhotoImage(Image.open("./images/Rolling.PNG"))
        ImageLabel1.configure(image=DiceImage1_wait)
        ImageLabel2.configure(image=DiceImage2_wait)
        root.update_idletasks() 
        time.sleep(0.2)
        # update image
        ImageLabel1.configure(image=DiceImage1)
        ImageLabel2.configure(image=DiceImage2)
        # keep a reference
        ImageLabel1.image = DiceImage1
        ImageLabel2.image = DiceImage2
    if game_started > 1:
        button.config(state=DISABLED)
    print("game_started", game_started)


# Define the global variables of the coordinates
xclick = 0
yclick = 0

# Define global variable to hold the index of specific stone
p = 0


# Function to hold the image updated when the mouse in move
def move(event):

    global xclick
    global yclick
    global t
    global r

    if B_List[p].get_color() != player_color.get():
        return
    if (p != None) and (B_List[p].get_color() == "green"): # p cannot contains None
     t = PhotoImage(file="./images/green_stone.PNG")
     image1 = canvas.create_image(event.x, event.y, image=t)
     for obj in B_List[0:15]: # Refresh the stones after the move event
        obj.g_create()

    if (p != None) and (B_List[p].get_color() == "blue"):
      r = PhotoImage(file="./images/blue_stone.PNG")
      image11 = canvas.create_image(event.x, event.y, image=r)
      for obj in B_List[15:31]:
        obj.b_create()


# Function to save the coordinates after the click
def click(event):

    global p
    global xclick
    global yclick
    xclick = event.x
    yclick = event.y

    print(xclick, yclick) # Status of the coordinates after click

    # Checking which stone it is
    p = isstone(xclick, yclick)

    print(p) # The list number of the stone

    if B_List[p].get_color() != player_color.get():
            return
    # Remove the stone from the canvas after click
    if (p != None) and (B_List[p].get_color() == "green"):
        B_List[p] = Stone(1600, 1600, 0, 0, 0, 0,"green")
    elif (p != None) and (B_List[p].get_color() == "blue"):
        B_List[p] = Stone(1600, 1600, 0, 0, 0, 0, "blue")


# Function to save the coordinates after release the click
def release(event):

        global p
        global xclick
        global yclick
        if B_List[p].get_color() != player_color.get():
            return
        else:
            if xclick == event.x and yclick == event.y:
                move(event)
            xclick = event.x
            yclick = event.y
            print(xclick, yclick)
            # Update the new coordinates after release
            if (p != None) and (B_List[p].get_color() == "green"):
                B_List[p] = Stone(xclick, yclick, xclick + 32, yclick + 32, xclick - 32, yclick - 32,"green")
            elif (p != None) and (B_List[p].get_color() == "blue"):
                B_List[p] = Stone(xclick, yclick, xclick + 32, yclick + 32, xclick - 32, yclick - 32, "blue")
            if sio:
                print("sending the poses")
                sio.emit("pos", [p, xclick, yclick, B_List[p].get_color()])


def move_opponent(p_check, xpos, ypos, color):
    check = p_check
    print("opponent move", check, xpos, ypos)
    # Update the new coordinates after release
    s0 = B_List[check]
    x0 = int(s0.x)
    y0 = int(s0.y)
    slope = None
    if xpos - x0: # slope can't be infinte!
        slope = (ypos - y0)/(xpos - x0)
    stepx = -1 if xpos - x0 < 0 else 1
    stepy = -1 if ypos - y0 < 0 else 1
    
    if slope: # moving in x, or both direction
        waypoints = range(x0, xpos+stepx, stepx)
        if abs((xpos - x0)) > 300:
            waypoints = list(range(x0, xpos, stepx*(abs((xpos - x0))//150)))
            waypoints[-1] = xpos
        for x in waypoints:
            y = slope*(x-x0)+y0
            B_List[check] = Stone(x, y, x + 32, y + 32, x - 32, y - 32,color)
            t = PhotoImage(file=f"./images/{color}_stone.PNG")
            canvas.create_image(x, y, image=t)
            #time.sleep(0.01)
    else: # only moving in y direction
        for y in range(y0, ypos+stepy, stepy):
            B_List[check] = Stone(x0, y, x0 + 32, y + 32, x0 - 32, y - 32,color)
            t = PhotoImage(file=f"./images/{color}_stone.PNG")
            canvas.create_image(x0, y, image=t)
    if color == "green":
        for obj in B_List[0:15]: # Refresh the stones after the move event
            obj.g_create()
    elif color == "blue":
        for obj in B_List[15:31]:
            obj.b_create()


# Function to check if the coordinates after the click is belong to the stones or game board
def isstone(xz, yz):
    i = 0
    while i < len(B_List):
        if (B_List[i].get_posrangezx() <= xz) and (B_List[i].get_posrangex() >= xz) and (B_List[i].get_posrangezy() <= yz) and (B_List[i].get_posrangey() >= yz):
            return i
        else:
            i += 1


# This bind window to keys so that move is called when you press a key
canvas.bind('<Button-1>', click)
canvas.bind('<B1-Motion>', move)
canvas.bind('<ButtonRelease-1>', release)


# adding button, and command will use rolling_dice function
button = ttk.Button(root, text='Roll Dice', command=rolling_dice, state=DISABLED)
button.place(x=50, y=350)

Playlabel = ttk.Label(root, text="I play as", background=global_bg)
Playlabel.place(x=20, y=520)
rd1 = ttk.Radiobutton(root, text = "Blue checks", variable = player_color, value = "blue", width=17)
rd2 = ttk.Radiobutton(root, text = "Green checks", variable = player_color, value = "green", width=17)
rd1.place(x=20, y=540)
rd2.place(x=20, y=565)

Portlabel = ttk.Label(root, text="Access KEY", background=global_bg)
Portlabel.place(x=20, y=595)
ackey = ttk.Entry(root, width=18, font=('Arial', 12, 'bold'))
ackey.place(x=20, y=615)
ackey.insert(0, "ACCESS KEY")

Portlabel = ttk.Label(root, text="Server IP:Port", background=global_bg)
Portlabel.place(x=20, y=645)
ntp = ttk.Entry(root, width=20)
ntp.insert(0, f"{conn_ip}:{conn_port}")
ntp.place(x=20, y=665)

button1 = ttk.Button(root, text='Connect / Create Server', command=connect)
button1.place(x=20, y=700)

style = ttk.Style()
style.configure('Custom.TButton' ,background='red', foreground='red')
Resetbutton = ttk.Button(root, text='Reset game', command=reset_game, state=DISABLED, style='Custom.TButton')
Resetbutton.place(x=20, y=740)

Statuslabel = ttk.Label(root, text="Connection: Unknown", background=global_bg)
Statuslabel.place(x=20, y=825)

def on_closing():
    if messagebox.askokcancel("Exit", "Do you really want to exit?"):
        if sio:
            if is_server:
                try:
                    sio.shutdown()
                except:
                    print("Error in shutting down the server")
            elif sio.connected:
                sio.disconnect()
        """ if t_conn.is_alive():
            try:
                t_conn.join()
            except:
                print("Error in shutting down the server") """
        root.destroy()

root.protocol("WM_DELETE_WINDOW", on_closing)
root.resizable(width=False, height=False)
root.title("Backgammon Multiplayer")
# this creates the loop that makes the window stay 'active'
root.mainloop()
