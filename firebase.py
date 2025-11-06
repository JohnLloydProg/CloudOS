import pyrebase
from objects import User
from datetime import datetime
from scheduling import Computer, UploadProcess, DownloadProcess
from datetime import datetime
from time import sleep
import json
import os

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

class Firebase:
    fb = pyrebase.initialize_app(firebaseConfig)
    auth = fb.auth()
    db = fb.database()
    storage = fb.storage()

    def __init__(self, computer:Computer):
        self.computer = computer

    def login(self, email:str, password:str) -> User:
        result = self.auth.sign_in_with_email_and_password(email, password)
        user = User(email, password)
        user.setup_account(result)
        return user
    
    def register(self, user:User):
        result = self.auth.create_user_with_email_and_password(user.email, user.password)
        user.setup_account(result)
    
    def upload_file(self, user:User, file_path:str, cloud_path:str):
        path = ['users', user.localId, 'owned_files']
        path.extend(cloud_path.split("/"))
        file_name = path.pop()
        upload_process = UploadProcess(firebaseConfig["storageBucket"], user, file_name, file_path, datetime.now().timestamp())
        self.computer.add_process(upload_process)
        while (not upload_process.is_completed()):
            print("Uploading...")
            sleep(0.5)
        self.storage.child(f'files/{user.localId}/{file_name}').put(file_path, token=user.idToken)

        root = self.db
        files = self.get_owned_files(user)
        for directory in path:
            if (len(directory) > 1 and 'type' not in files):
                root = root.child(directory)
                files = files.get(directory, {})
        files[file_name.replace(".", "&123")] = {'type':'file'}
        root.set(files, token=user.idToken)

        self.db.child('files').child(user.localId).child(file_name.replace(".", "&123")).set({'modified':datetime.now().isoformat()}, token=user.idToken)

    def get_owned_files(self, user:User) -> dict:
        files = self.db.get(token=user.idToken).val()
        return files if (files) else {}
    
    def file_is_owned(self, user:User, file_name:str, d:dict) -> bool:
        found = False
        for key in d.keys():
            if 'type' not in d.get(key):
                print(d.get(key))
                found = self.file_is_owned(user, file_name, d.get(key))
            if key == file_name:
                return True
        return found

    def get_access_list_ids(self, user:User) -> list[str]:
        files = self.db.child('users').child(user.localId).child('access_list').get(token=user.idToken).val()
        return files if (files) else []

    def update_file(self, user:User, file_name:str, file_path:str):
        self.storage.child(f'files/{user.localId}/{file_name}').put(file_path, token=user.idToken)
        self.db.child('files').child(user.localId).child(file_name.replace(".", "&123")).update({'modified':datetime.now().isoformat()}, token=user.idToken)

    def delete_owned_file(self, user:User, file_name:str, cloud_path:str):
        if (not self.file_is_owned(user, file_name, self.get_owned_file_ids(user).get('users'))):
            print("File is not owned by the user. Can't delete it")
            return
        self.storage.delete(f'files/{user.localId}/{file_name}', user.idToken)
        self.db.child('files').child(user.localId).child(file_name.replace(".", "&123")).set(None, token=user.idToken)
        root = self.db
        for directory in cloud_path.split("/"):
            if (len(directory) > 1):
             root = root.child(directory)
        root.child(file_name.replace(".", "&123")).set(None, token=user.idToken)
        print("File is deleted")


    def get_file(self, user:User, file_name:str) -> str:
        file = self.db.child('files').child(user.localId).child(file_name.replace(".", "&123")).get(token=user.idToken).val()
        if (not file):
            return None
        
        try:
            with open(f"./file_cache/meta/{file_name.replace(".", "&123")}.json", 'r') as f:
                cache_meta:dict = json.loads(f.read())
        except FileNotFoundError:
            cache_meta = {}
        
        if (cache_meta.get("modified") != file.get('modified', '')):
            print('file is outdated')
            url = self.storage.child(f'files/{user.localId}/{file_name}').get_url(user.idToken)
            process = DownloadProcess(url, user, file_name, datetime.now().timestamp())
            self.computer.add_process(process)
            while (not process.is_completed()):
                print("Downloading...")
                sleep(0.5)
            with open(f'./file_cache/meta/{file_name.replace(".", "&123")}.json', 'w') as f:
                f.write(json.dumps(file))
        return f"{os.environ.get("CACHE_PATH")}/{file_name}"

