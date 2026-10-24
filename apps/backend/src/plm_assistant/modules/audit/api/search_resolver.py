"""Trusted HTTP adapter, no permission proof or independent identity lookup."""
from .list_cursor import AuditListCursorCodec


class AuditCursorSearchResolver:
    def __init__(self,codec,token=None,*,dates_omitted=False):
        if type(codec) is not AuditListCursorCodec or type(dates_omitted) is not bool:
            raise ValueError("Audit cursor resolver configuration invalid")
        if token is not None and type(token) is not str:
            raise ValueError("Audit cursor must be text")
        self._codec,self._token,self._dates_omitted=codec,token,dates_omitted

    def resolve(self,*,session_token,actor_id,project_id,search):
        if self._token is None:return search
        decode=self._codec.decode_saved_window if self._dates_omitted else self._codec.decode
        return decode(self._token,session_token=session_token,actor_id=actor_id,project_id=project_id,search=search)
