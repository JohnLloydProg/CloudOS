import pyrebase
from objects import User
from datetime import datetime
from scheduling import Computer, UploadProcess, DownloadProcess
from decorators import connection_try_decorator
from typing import Callable
from threading import Thread
from time import sleep
import atexit
import json
import os

LOCKED_OPERATION = {"write": ["write", "read"], "read":["write"]}

firebaseConfig = {
  "apiKey": "AIzaSyC_DMlTx9Ipc9yx9IPA3lVeITXZD0QhwpE",
  "authDomain": "cloudos-12cdc.firebaseapp.com",
  "databaseURL": "https://cloudos-12cdc-default-rtdb.asia-southeast1.firebasedatabase.app",
  "projectId": "cloudos-12cdc",
  "storageBucket": "cloudos-12cdc.firebasestorage.app",
  "messagingSenderId": "710107657823",
  "appId": "1:710107657823:web:5d2104048a1587b84b4dea",
  "measurementId": "G-VCE7XX9FMR",
  "serviceAccount": "cloudos-12cdc-firebase-adminsdk-fbsvc-9b35e8b6ff.json"
}


class CustomThread(Thread):
    def __init__(self, target, args, on_finish:Callable):
        super().__init__(target=target, args=args, daemon=True)
        self.on_finish = on_finish
        self.target = target
        self.args = args
    
    def run(self):
        result = self.target(*self.args)
        if (self.on_finish):
            self.on_finish(result)


class Firebase:
    fb = pyrebase.initialize_app(firebaseConfig)
    auth = fb.auth()
    db = fb.database()
    storage = fb.storage()
    lock_refs = []

    def __init__(self, computer:Computer):
        self.computer = computer

    def clean_at_exit(self, user:User):
        atexit.register(lambda: self.clean_locked_paths(user))

    @connection_try_decorator
    def lock_path(self, user:User, cloud_path:str, operation:str):
        if (operation not in ['write', 'read']):
            raise ValueError(f"{operation} is among the list of operations allowed to lock")

        lock_ref = cloud_path.replace("/", "&456").replace(".", "&123")
        locks:dict[str, dict[str, str]] = self.db.child("locks").child(user.localId).get(token=user.idToken).val()
        if (not locks):
            locks = {}
        while (operation in LOCKED_OPERATION.get(locks.get(lock_ref), [])):
            locks = self.db.child("locks").child(user.localId).get(token=user.idToken).val()
            print(f"Can't process because the path {cloud_path} is locked by a different operation")
            sleep(1)
        locks[lock_ref] = operation
        self.db.child("locks").child(user.localId).update(locks, token=user.idToken)
        self.lock_refs.append(lock_ref)
        return lock_ref

    @connection_try_decorator
    def unlock_path(self, user:User, lock_ref:str):
        self.db.child("locks").child(user.localId).child(lock_ref).set(None, token=user.idToken)

    def clean_locked_paths(self, user:User):
        for lock_ref in self.lock_refs:
            self.unlock_path(user, lock_ref)

    @connection_try_decorator
    def login(self, email:str, password:str) -> User:
        result = self.auth.sign_in_with_email_and_password(email, password)
        if (result):
            user = User(email, password)
            user.setup_account(result)
            return user
        return None
    
    @connection_try_decorator
    def register(self, user:User):
        result = self.auth.create_user_with_email_and_password(user.email, user.password)
        user.setup_account(result)
    
    @connection_try_decorator
    def upload_file(self, user:User, cloud_path:str, file_path:str):
        cloud_path = cloud_path.strip("/")
        path = cloud_path.split("/")
        file_name = path.pop()

        lock_ref = self.lock_path(user, cloud_path, 'write')
        if (not lock_ref):
            return

        upload_process = UploadProcess(firebaseConfig["storageBucket"], user, cloud_path, file_path)
        self.computer.add_process(upload_process)
        while (not upload_process.is_completed()):
            print("Uploading...")
            sleep(0.5)

        data = {file_name.replace(".", "&123"):{'type':'file', 'modified':datetime.now().isoformat()}}
        self.db.child('users').child(user.localId).child('owned_files').child(*tuple(path)).update(data, token=user.idToken)
        self.unlock_path(user, lock_ref)

    @connection_try_decorator
    def get_owned_files(self, user:User) -> dict:
        files = self.db.child('users').child(user.localId).child('owned_files').get(token=user.idToken).val()
        return files if (files) else {}
    
    @connection_try_decorator
    def file_is_owned(self, user:User, file_name:str, d:dict) -> bool:
        found = False
        for key in d.keys():
            if 'type' not in d.get(key):
                print(d.get(key))
                found = self.file_is_owned(user, file_name, d.get(key))
            if key == file_name:
                return True
        return found

    @connection_try_decorator
    def get_access_list_ids(self, user:User) -> list[str]:
        files = self.db.child('users').child(user.localId).child('access_list').get(token=user.idToken).val()
        return files if (files) else []

    @connection_try_decorator
    def update_file(self, user:User, cloud_path:str, file_path:str):
        cloud_path = cloud_path.strip("/")

        #locks the cloud path before processing
        lock_ref = self.lock_path(user, cloud_path, 'write')
        if (not lock_ref):
            return
        
        process = UploadProcess(firebaseConfig["storageBucket"], user, cloud_path, file_path)
        self.computer.add_process(process)
        while (not process.is_completed()):
            print("Uploading...")
            sleep(0.5)
        self.db.child('users').child(user.localId).child('owned_files').child(*tuple(cloud_path.replace(".", "&123").split("/"))).update({'modified':datetime.now().isoformat()}, token=user.idToken)
        
        self.unlock_path(user, lock_ref)

    @connection_try_decorator
    def delete_owned_file(self, user:User, cloud_path:str):
        cloud_path = cloud_path.strip("/")
        if (not self.file_is_owned(user, cloud_path.split("/")[-1], self.get_owned_file_ids(user).get('users'))):
            print("File is not owned by the user. Can't delete it")
            return
        self.storage.delete(f'files/{user.localId}/{cloud_path}', user.idToken)
        self.db.child('users').child(user.localId).child('owned_files').child(*tuple(cloud_path.replace(".", "&123").split("/"))).set(None, token=user.idToken)
        print("File is deleted")

    @connection_try_decorator
    def get_file(self, user:User, cloud_path:str) -> str:
        cloud_path = cloud_path.strip("/")
        file = self.db.child('users').child(user.localId).child('owned_files').child(*tuple(cloud_path.replace(".", "&123").split("/"))).get(token=user.idToken).val()
        if (not file):
            return None
        
        try:
            with open(f"{os.environ.get("CACHE_PATH")}/meta/{cloud_path.replace(".", "&123")}.json", 'r') as f:
                cache_meta:dict = json.loads(f.read())
        except FileNotFoundError:
            cache_meta = {}
        
        if (cache_meta.get("modified") != file.get('modified', '')):
            print('file is outdated')
            url = self.storage.child(f'files/{user.localId}/{cloud_path}').get_url(user.idToken)
            lock_ref = self.lock_path(user, cloud_path, 'read')
            if (not lock_ref):
                return
            process = DownloadProcess(url, user, cloud_path)
            self.computer.add_process(process)
            while (not process.is_completed() and not process.error):
                sleep(0.5)
            self.unlock_path(user, lock_ref)
            if (process.error):
                return None
            try:
                with open(f"{os.environ.get("CACHE_PATH")}/meta/{cloud_path.replace(".", "&123")}.json", 'w') as f:
                    f.write(json.dumps(file))
            except FileNotFoundError:
                os.makedirs(f"{os.environ.get('CACHE_PATH')}/meta/{'/'.join(cloud_path.split('/')[:-1])}", exist_ok=True)
                with open(f"{os.environ.get('CACHE_PATH')}/meta/{cloud_path.replace('.', '&123')}.json", 'w') as f:
                    f.write(json.dumps(file))
        return f"{os.environ.get("CACHE_PATH")}/{cloud_path}"

    def upload_thread(self, user:User, cloud_path:str, file_path:str, on_finish:Callable=None):
        CustomThread(self.upload_file, args=(user, cloud_path, file_path), on_finish=on_finish).start()
    
    def get_thread(self, user:User, cloud_path:str, on_finish:Callable=None):
        CustomThread(self.get_file, args=(user, cloud_path), on_finish=on_finish).start()
    
    def update_thread(self, user:User, cloud_path:str, file_path:str, on_finish:Callable=None):
        CustomThread(self.update_file, args=(user, cloud_path, file_path), on_finish=on_finish).start()


