from ast import Dict
from typing import TypedDict, Optional, List
import firebase_admin
from firebase_admin import credentials, firestore, auth

from enum import Enum

cred = credentials.Certificate("agents/firebase_adminsdk.json")
firebase_admin.initialize_app(cred)

class AppStatus(str, Enum):
    INFO_COLLECTION = "info_collection"
    STRATEGIZING = "strategizing"
    NEGOTIATING = "negotiating"
    ANALYSING = "analyzing"
    COMPLETED = "completed"

class CallStatus(str, Enum):
    CALL_INITIATED = "CALL_INITIATED"
    CALL_INPROGRESS = "CALL_INPROGRESS"
    CALL_COMPLETED = "CALL_COMPLETED"

class User(TypedDict):
    uid: str
    user_id: str
    email: str

class SessionData(TypedDict):
    status: AppStatus
    strategy: Optional[str]
    movers: Optional[List[str]]
    transcripts: Optional[List[str]]
    callSummaries: Optional[List[str]]
    recommendation: Optional[str]

db = firestore.client()

def update_data(user_id: str, data: SessionData, merge = True):
    db.collection('users').document(user_id).set(data, merge=merge)

def update_status(user_id: str, status: AppStatus):
    update_data(user_id, {"status": status})

def update_call_data(user_id: str, call_sid: str, data: Dict, merge=True):
    """
    Update the Firestore document at the path 'users/{user_id}/calls/{call_sid}' with the provided data.
    
    :param user_id: The ID of the user.
    :param call_sid: The SID of the call.
    :param data: The data to update in the Firestore document.
    :param merge: Whether to merge the data with existing data.
    """
    db.collection('users').document(user_id).collection('calls').document(call_sid).set(data, merge=merge)

def get_call_data_as_json(user_id: str, call_sid: str) -> Optional[Dict]:
    """
    Retrieve the Firestore document at the path 'users/{user_id}/calls/{call_sid}' and return it as JSON.
    
    :param user_id: The ID of the user.
    :param call_sid: The SID of the call.
    :return: The document data as a dictionary, or None if the document does not exist.
    """
    doc_ref = db.collection('users').document(user_id).collection('calls').document(call_sid)
    doc = doc_ref.get()
    
    if doc.exists:
        return doc.to_dict()
    else:
        return None

