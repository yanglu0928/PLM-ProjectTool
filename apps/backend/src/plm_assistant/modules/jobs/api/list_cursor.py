"""Opaque authenticated Job-list position; dedicated key, no authority or plaintext IDs."""
import base64
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from uuid import UUID
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from plm_assistant.modules.platform.application.errors import ApplicationError
from ..application.authorized_list import JobListQuery, _position

_TOKEN = re.compile(r'j1\.[A-Za-z0-9_-]{1,1536}\Z', re.ASCII)
_FAMILY = 'plm-job-list-aesgcm-v1'


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode('ascii')


def _b64(value): return base64.urlsafe_b64encode(value).rstrip(b'=').decode('ascii')


def _aad(q):
    if type(q) is not JobListQuery: raise ValueError('Invalid cursor binding')
    q.__post_init__()
    return _json({'family': _FAMILY, 'v': 1, 'session': hashlib.sha256(q.session_token).hexdigest(),
        'project_id': str(q.project_id) if q.project_id else None, 'scope': q.scope, 'page_size': q.page_size})


def _payload(before):
    if not _position(before): raise ValueError('Invalid cursor position')
    return _json({'v': 1, 'created_at': before[0].astimezone(timezone.utc).isoformat(timespec='microseconds'), 'job_id': str(before[1])})


class JobListCursorCodec:
    def __init__(self, key):
        if type(key) is not bytes or len(key) != 32: raise ValueError('Dedicated 32-byte Job-list cursor key required')
        self._aes = AESGCM(key)

    def encode(self, *, query, before):
        aad, payload = _aad(query), _payload(before)
        nonce = os.urandom(12)
        return 'j1.' + _b64(nonce + self._aes.encrypt(nonce, payload, aad))

    def decode(self, token, *, query):
        try:
            aad = _aad(query)
            if type(token) is not str or _TOKEN.fullmatch(token) is None: raise ValueError()
            encoded = token[3:]
            packed = base64.urlsafe_b64decode(encoded + '=' * (-len(encoded) % 4))
            if len(packed) < 29 or _b64(packed) != encoded: raise ValueError()
            raw = self._aes.decrypt(packed[:12], packed[12:], aad)
            value = json.loads(raw.decode('ascii'))
            if type(value) is not dict or set(value) != {'v', 'created_at', 'job_id'} or type(value['v']) is not int or value['v'] != 1:
                raise ValueError()
            before = (datetime.fromisoformat(value['created_at']), UUID(value['job_id']))
            if _payload(before) != raw: raise ValueError()
            return before
        except Exception:
            raise ApplicationError('REQUEST_MALFORMED') from None
