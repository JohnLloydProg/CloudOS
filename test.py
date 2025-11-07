from firebase import Firebase
from scheduling import Computer, Process
from objects import User
from dotenv import load_dotenv
from threading import Thread
from time import sleep

load_dotenv()

computer = Computer()
thread = Thread(target=computer.run, daemon=True)
thread.start()

firebase = Firebase(computer)
user = firebase.login("johnlloydunida0@gmail.com", "password")


firebase.get_thread(user, 'hotdog.txt', lambda result: print(result))
sleep(3)
firebase.update_thread(user, 'hotdog.txt', './test.txt', lambda result: print(result))

input("waiting... enter to end")
