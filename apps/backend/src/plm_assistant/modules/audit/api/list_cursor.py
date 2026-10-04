"""Integrity-protected Audit keyset cursor, never authentication or encryption."""
import base64
from dataclasses import replace
from datetime import datetime,timezone
import hashlib
import hmac
import json
import re
from uuid import UUID
from plm_assistant.modules.platform.application.errors import ApplicationError
from ..application.queries.audit_query import AuditSearch,AuditPosition

_TOKEN=re.compile(r"[A-Za-z0-9_-]{1,2048}\.[A-Za-z0-9_-]{43}\Z",re.ASCII)
_FIELDS={"v","family","scope","project","actor","session","query","start","end","time","event"}
_DOMAIN=b"PLM-AUDIT-CURSOR-V1\x00"


def _b64(value):return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")
def _unb64(value):return base64.urlsafe_b64decode(value+"="*(-len(value)%4))
def _uuid(value):return type(value) is UUID and value.int!=0
def _time(value):return value.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00","Z")
def _parse(value):
    if type(value) is not str:raise ValueError()
    result=datetime.fromisoformat(value.replace("Z","+00:00"))
    if result.tzinfo is None or result.utcoffset() is None or _time(result)!=value:raise ValueError()
    return result.astimezone(timezone.utc)


def _query(search):
    payload=dict(start=_time(search.start_at),end=_time(search.end_at),page_size=search.page_size,
        action=search.action,outcome=search.outcome,actor=str(search.actor_id) if search.actor_id else None,
        object_type=search.target_object_type,object_id=str(search.target_object_id) if search.target_object_id else None,
        trace=str(search.trace_id) if search.trace_id else None)
    return hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode("ascii")).hexdigest()


class AuditListCursorCodec:
    def __init__(self,key):
        if type(key) is not bytes or len(key)!=32:raise ValueError("dedicated 32-byte Audit cursor key required")
        self._key=key

    @staticmethod
    def _input(session_token,actor_id,project_id,search):
        if (type(session_token) is not bytes or len(session_token)!=32 or not _uuid(actor_id)
                or project_id is not None and not _uuid(project_id) or type(search) is not AuditSearch
                or search.after is not None):raise ValueError("invalid Audit cursor")
        search.__post_init__()

    def encode(self,*,session_token,actor_id,project_id,search,position):
        try:
            self._input(session_token,actor_id,project_id,search)
            if type(position) is not AuditPosition:raise ValueError()
            position.__post_init__()
            if not search.start_at<=position.occurred_at<search.end_at:raise ValueError()
            payload=dict(v=1,family="audit-events",scope="DEPLOYMENT" if project_id is None else "PROJECT",
                project=str(project_id) if project_id is not None else None,actor=str(actor_id),
                session=hashlib.sha256(session_token).hexdigest(),query=_query(search),
                start=_time(search.start_at),end=_time(search.end_at),time=_time(position.occurred_at),event=str(position.audit_event_id))
            raw=json.dumps(payload,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode("ascii")
            return _b64(raw)+"."+_b64(hmac.digest(self._key,_DOMAIN+raw,"sha256"))
        except (TypeError,ValueError,OverflowError):
            raise ValueError("invalid Audit cursor") from None

    def decode(self,token,*,session_token,actor_id,project_id,search):
        """Explicit date filters must match. Return signed after position."""
        return self._decode(token,session_token=session_token,actor_id=actor_id,project_id=project_id,search=search,saved_window=False)

    def decode_saved_window(self,token,*,session_token,actor_id,project_id,search):
        """ONLY when client did not specify dates: preserve signed first window.

        Other filters/page_size still match. This method must not be used to
        silently ignore a changed explicit date filter. No authority granted.
        """
        return self._decode(token,session_token=session_token,actor_id=actor_id,project_id=project_id,search=search,saved_window=True)

    def _decode(self,token,*,session_token,actor_id,project_id,search,saved_window):
        try:
            self._input(session_token,actor_id,project_id,search)
            if type(token) is not str or _TOKEN.fullmatch(token) is None:raise ValueError()
            encoded,signature=token.split(".")
            raw,mac=_unb64(encoded),_unb64(signature)
            if (_b64(raw)!=encoded or len(mac)!=32 or _b64(mac)!=signature
                    or not hmac.compare_digest(mac,hmac.digest(self._key,_DOMAIN+raw,"sha256"))):raise ValueError()
            payload=json.loads(raw.decode("ascii"))
            if (type(payload) is not dict or set(payload)!=_FIELDS or type(payload["v"]) is not int or payload["v"]!=1
                    or payload["family"]!="audit-events" or payload["scope"]!=("DEPLOYMENT" if project_id is None else "PROJECT")
                    or payload["project"]!=(str(project_id) if project_id is not None else None)
                    or payload["actor"]!=str(actor_id) or payload["session"]!=hashlib.sha256(session_token).hexdigest()):raise ValueError()
            start,end=_parse(payload["start"]),_parse(payload["end"])
            base=replace(search,start_at=start,end_at=end) if saved_window else search
            if payload["start"]!=_time(base.start_at) or payload["end"]!=_time(base.end_at) or payload["query"]!=_query(base):raise ValueError()
            if type(payload["event"]) is not str:raise ValueError()
            event=UUID(payload["event"])
            if not _uuid(event) or str(event)!=payload["event"]:raise ValueError()
            position=AuditPosition(_parse(payload["time"]),event)
            if self.encode(session_token=session_token,actor_id=actor_id,project_id=project_id,search=base,position=position)!=token:raise ValueError()
            return replace(base,after=position)
        except (TypeError,ValueError,KeyError,OverflowError,UnicodeError,json.JSONDecodeError):
            raise ApplicationError("REQUEST_MALFORMED") from None
