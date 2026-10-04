"""Dedicated opaque User list coordinates, never business authority."""
import base64,hashlib,json,os,re
from datetime import datetime,timezone
from uuid import UUID
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from ..application.user_list import UserListQuery,_position
from plm_assistant.modules.platform.application.errors import ApplicationError

_FAMILY='plm-user-list-aesgcm-v1'
_TOKEN=re.compile(r'u1\.[A-Za-z0-9_-]{1,1536}\Z',re.ASCII)
def _json(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode('ascii')
def _b64(value):return base64.urlsafe_b64encode(value).rstrip(b'=').decode('ascii')
def _aad(query):
    if type(query) is not UserListQuery:raise ValueError('Invalid cursor binding')
    query.__post_init__()
    return _json(dict(family=_FAMILY,v=1,session=hashlib.sha256(query.session_token).hexdigest(),page_size=query.page_size))
def _payload(before):
    if not _position(before):raise ValueError('Invalid cursor position')
    return _json(dict(v=1,created_at=before[0].astimezone(timezone.utc).isoformat(timespec='microseconds'),user_id=str(before[1])))


class UserListCursorCodec:
    def __init__(self,key):
        if type(key) is not bytes or len(key)!=32:raise ValueError('Dedicated 32-byte User cursor key required')
        self._aes=AESGCM(key)
    def encode(self,*,query,before):
        aad,payload=_aad(query),_payload(before);nonce=os.urandom(12)
        return 'u1.'+_b64(nonce+self._aes.encrypt(nonce,payload,aad))
    def decode(self,token,*,query):
        try:
            aad=_aad(query)
            if type(token) is not str or _TOKEN.fullmatch(token) is None:raise ValueError()
            encoded=token[3:];packed=base64.urlsafe_b64decode(encoded+'='*(-len(encoded)%4))
            if len(packed)<29 or _b64(packed)!=encoded:raise ValueError()
            value=json.loads((raw:=self._aes.decrypt(packed[:12],packed[12:],aad)).decode('ascii'))
            if type(value) is not dict or set(value)!={'v','created_at','user_id'} or type(value['v']) is not int or value['v']!=1:raise ValueError()
            before=(datetime.fromisoformat(value['created_at']),UUID(value['user_id']))
            if _payload(before)!=raw:raise ValueError()
            return before
        except Exception:raise ApplicationError('REQUEST_MALFORMED') from None
