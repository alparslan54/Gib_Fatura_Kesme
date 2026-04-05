import requests
import json

import logging
import re
import os


import hashlib
from requests.utils import cookiejar_from_dict
from http.cookiejar import Cookie
import secrets
import uuid
import pdfkit
from dataclasses import dataclass
from datetime import datetime
import time
from typing import Dict, Optional
import redis
from gib_client import GibClient

from fastapi import FastAPI, HTTPException, Body, Response, Header, Depends
# Redis bağlantısı
r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

app = FastAPI()

GIB_ENV = os.getenv("GIB_ENV", "test")  # test|prod
GIB_BASE_URL = (
    "https://earsivportaltest.efatura.gov.tr" if GIB_ENV == "test"
    else "https://earsivportal.efatura.gov.tr"
)


logger = logging.getLogger("gibapi")
logging.basicConfig(level=logging.INFO)

SESSION_TTL_SECONDS = 15 * 60  # 15 dakika
LOGIN_LOCK_TTL_SEC = 10  # aynı kullanıcı için login denemesi kilidi (saniye)


def cookiejar_to_list(jar):
    out = []
    for c in jar:
        out.append({
            "name": c.name,
            "value": c.value,
            "domain": c.domain,
            "path": c.path,
            "secure": c.secure,
            "expires": c.expires,
        })
    return out

def serialize_cookies(cookiejar) -> list[dict]:
    out = []
    for c in cookiejar:
        out.append({
            "name": c.name,
            "value": c.value,
            "domain": c.domain,
            "path": c.path,
            "secure": c.secure,
            "expires": c.expires,
        })
    return out


def restore_cookies(session: requests.Session, cookies: list[dict]) -> None:
    for d in cookies:
        ck = Cookie(
            version=0,
            name=d["name"],
            value=d["value"],
            port=None,
            port_specified=False,
            domain=d.get("domain") or "",
            domain_specified=bool(d.get("domain")),
            domain_initial_dot=(d.get("domain") or "").startswith("."),
            path=d.get("path") or "/",
            path_specified=True,
            secure=bool(d.get("secure")),
            expires=d.get("expires"),
            discard=False,
            comment=None,
            comment_url=None,
            rest={},
            rfc2109=False,
        )
        session.cookies.set_cookie(ck)

def list_to_cookiejar(lst):
    jar = requests.cookies.RequestsCookieJar()
    for c in lst:
        jar.set(
            c["name"],
            c["value"],
            domain=c.get("domain"),
            path=c.get("path", "/"),
        )
    return jar

def user_ref_from_username(username: str) -> str:
    return hashlib.sha256(username.strip().encode("utf-8")).hexdigest()

def sess_key(session_id: str) -> str:
    return f"sess:{session_id}"

def active_key(user_ref: str) -> str:
    return f"active:{user_ref}"


def lock_key(user_ref: str) -> str:
    return f"lock:{user_ref}"

def get_active_session_id(user_ref: str) -> Optional[str]:
    sid = r.get(active_key(user_ref))
    return sid if sid else None

def set_active_session_id(user_ref: str, session_id: str):
    r.setex(active_key(user_ref), SESSION_TTL_SECONDS, session_id)

def get_session_id(authorization: Optional[str] = Header(default=None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Invalid Authorization scheme")
    token = authorization[7:].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Empty bearer token")
    return token

def acquire_login_lock(user_ref: str) -> bool:
    return bool(r.set(lock_key(user_ref), "1", nx=True, ex=LOGIN_LOCK_TTL_SEC))

def release_login_lock(user_ref: str):
    r.delete(lock_key(user_ref))

@dataclass
class SessionEntry:
    gib: "GibSecureAPI"
    last_seen: float


SESSIONS: Dict[str, SessionEntry] = {}

def save_session_to_redis(session_id, token, cookiejar, uref=None):
    data = {
        "token": token,
        "cookies": cookiejar_to_list(cookiejar),
        "ts": int(time.time()),
        "uref": uref,
    }
    r.setex(f"sess:{session_id}", SESSION_TTL_SECONDS, json.dumps(data))






def get_session_from_redis(session_id):
    data = r.get(f"sess:{session_id}")
    return json.loads(data) if data else None


def get_gib_from_redis(session_id: str):
    data = get_session_from_redis(session_id)
    if not data:
        return None

    gib = GibClient(username="", password="", env=GIB_ENV)
    gib.token = data["token"]
    restore_cookies(gib.session, data.get("cookies", []))
    gib.ensure_portal_context()

    # opsiyonel ama faydalı: session bağlamını tazele
    gib.index_url = f"{gib.base_url}/index.jsp?token={gib.token}"
    gib.session.get(gib.index_url, timeout=15, allow_redirects=True)

    return gib

def get_gib_from_redis_for_logout(session_id: str):
    data = get_session_from_redis(session_id)
    if not data:
        return None

    gib = GibClient(username="", password="", env=GIB_ENV)
    gib.token = data["token"]
    restore_cookies(gib.session, data.get("cookies", []))

    # ÖNEMLİ: logout akışında portal context/index refresh YOK
    return gib






def cleanup_sessions() -> None:
    now = time.time()
    dead = [sid for sid, e in SESSIONS.items() if now - e.last_seen > SESSION_TTL_SECONDS]
    for sid in dead:
        try:
            SESSIONS[sid].gib.session.get(f"{SESSIONS[sid].gib.base_url}/logout.jsp", timeout=5)
        except Exception:
            pass
        SESSIONS.pop(sid, None)


def get_gib(session_id: str) -> Optional["GibSecureAPI"]:
    e = SESSIONS.get(session_id)
    if not e:
        return None

    if time.time() - e.last_seen > SESSION_TTL_SECONDS:
        try:
            e.gib.session.get(f"{e.gib.base_url}/logout.jsp", timeout=5)
        except Exception:
            pass
        SESSIONS.pop(session_id, None)
        return None

    e.last_seen = time.time()
    return e.gib


"""class GibSecureAPI:
    def __init__(self, userid: str, password: str):
        self.userid = userid
        self.password = password
        self.token = None
        self.session = requests.Session()
        self.base_url = GIB_BASE_URL
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"
        }

    def login(self):
        url = f"{self.base_url}/earsiv-services/assos-login"
        data = f"assoscmd=login&rtype=json&userid={self.userid}&sifre={self.password}&parola=1&"
        resp = self.session.post(url, data=data, headers=self.headers, timeout=15)
        js = resp.json()
        if js.get("token"):
            self.token = js["token"]
            return True, self.token
        return False, js.get("messages", [{}])[0].get("text", "Hata")

    @staticmethod
    def mask(s: str) -> str:
        s = str(s or "")
        return s[:2] + "***" + s[-2:] if len(s) >= 4 else "***"

    def alici_sorgula(self, vkn_tckn: str):
        url = f"{self.base_url}/earsiv-services/dispatch"
        payload = {
            "cmd": "SICIL_VEYA_MERNISTEN_BILGILERI_GETIR",
            "callid": str(uuid.uuid4()),
            "pageName": "RG_FATURA",
            "token": self.token,
            "jp": json.dumps({"vknTcknn": vkn_tckn})
        }
        return self.session.post(url, data=payload, headers=self.headers).json()

    def fatura_olustur(self, data: dict):
        fatura_uuid = str(uuid.uuid4())
        kdv = float(data.get("kdv_orani", 20))
        fiyat = float(data["fiyat"])
        matrah = fiyat * int(data["miktar"])
        kdv_tutar = (matrah * kdv) / 100
        
        jp = {
            "faturaUuid": fatura_uuid,
            "faturaTarihi": datetime.now().strftime("%d/%m/%Y"),
            "saat": datetime.now().strftime("%H:%M:%S"),
            "vknTckn": data["vkn"],
            "aliciUnvan": "Stok On Musterisi",
            "malHizmetTable": [{
                "malHizmet": data["urun_adi"],
                "miktar": data["miktar"],
                "birim": "ADET",
                "birimFiyat": str(fiyat),
                "fiyat": str(matrah),
                "kdvOrani": kdv,
                "kdvTutari": f"{kdv_tutar:.2f}",
                "toplamTutar": f"{(matrah + kdv_tutar):.2f}"
            }],
            "odenecekTutar": f"{(matrah + kdv_tutar):.2f}",
            "paraBirimi": "TRY",
            "faturaTipi": "SATIS"
        }
        
        payload = {"cmd": "EARSIV_FATURA_OLUSTUR", "token": self.token, "jp": json.dumps(jp), "callid": str(uuid.uuid4())}
        resp = self.session.post(f"{self.base_url}/earsiv-services/dispatch", data=payload, headers=self.headers)
        return resp.json(), fatura_uuid

    def sms_onay_tetikle(self):
        url = f"{self.base_url}/earsiv-services/dispatch"
        payload = {
            "cmd": "0",
            "callid": str(uuid.uuid4()),
            "pageName": "RG_SMS_ONAY",
            "token": self.token,
            "jp": json.dumps({"islemTipi": "0"})
        }
        return self.session.post(url, data=payload, headers=self.headers).json()

    def fatura_onayla(self, sms_kodu: str, fatura_uuid: str):
        # KRİTİK: oidList içine faturanın UUID'sini koyuyoruz
        onay_verisi = {"sifre": sms_kodu, "oidList": [fatura_uuid]}
        payload = {
            "cmd": "0", "callid": str(uuid.uuid4()), "pageName": "RG_SMS_ONAY",
            "token": self.token, "jp": json.dumps(onay_verisi)
        }
        return self.session.post(f"{self.base_url}/earsiv-services/dispatch", data=payload, headers=self.headers).json()
"""

@app.post("/api/v1/session")
async def create_session(payload: dict = Body(...)):
    auth = payload.get("auth", {}) or {}
    username = (auth.get("username") or "").strip()
    password = auth.get("password") or ""

    if not username or not password:
        raise HTTPException(422, detail="username/password missing")

    uref = user_ref_from_username(username)

    # aynı kullanıcı için login kilidi
    if not acquire_login_lock(uref):
        raise HTTPException(429, detail="LOGIN_IN_PROGRESS")

    try:
        gib = GibClient(username, password, env=GIB_ENV)

        # Normal login'de hard_logout otomatik yapmak PROD'da tartışmalı.
        # Şimdilik senin test akışın bozulmasın diye bırakıyorum.
        # İstersen bunu sadece /session/force içine taşırız.
        try:
            gib.hard_logout()
        except Exception:
            pass

        ok = gib.login()
        if not ok:
            raise HTTPException(401, detail="GIB_LOGIN_FAILED")

        sid = secrets.token_urlsafe(24)
        save_session_to_redis(sid, gib.token, gib.session.cookies, uref=uref)
        set_active_session_id(uref, sid)

        return {"session_id": sid, "reused": False}

    finally:
        release_login_lock(uref)



@app.post("/api/v1/full-process")
async def full_process(payload: dict = Body(...), session_id: str = Depends(get_session_id)):
    gib = get_gib_from_redis(session_id)
    if not gib:
        raise HTTPException(401, detail="SESSION_NOT_FOUND")

    f = payload["fatura"]

    try:
        f_uuid = gib.create_draft_invoice(
            vkn=f["vkn"],
            alici_unvan=f["alici_unvan"],
            urun_adi=f["urun_adi"],
            miktar=f["miktar"],
            birim_fiyat=f["birim_fiyat"],
            kdv_orani=f.get("kdv_orani", 20),
        )
    except Exception as e:
        raise HTTPException(403, detail=str(e))

    sign_result = gib.try_sign_with_hsm(f_uuid)
    
    if sign_result["signed"]:
        approval_type = "SIGNED"
        approval_error = None
    else:
        approval_type = "MANUAL"
        approval_error = sign_result.get("reason")

    return {
        "status": "success",
        "fatura_uuid": f_uuid,
        "approval_type": approval_type,
        "approval_error": approval_error
    }




@app.post("/api/v1/verify-sms")
async def verify_sms(payload: dict = Body(...), session_id: str = Depends(get_session_id)):
    gib = get_gib_from_redis(session_id)
    if not gib:
        raise HTTPException(401, detail="SESSION_NOT_FOUND")

    sms_oid = payload.get("sms_oid")
    if not sms_oid:
        raise HTTPException(422, detail="sms_oid missing (send_sms response must be passed)")

    return gib.verify_sms(payload["sms_kodu"], payload["fatura_uuid"], sms_oid)



@app.post("/api/v1/logout")
async def logout(session_id: str = Depends(get_session_id)):
    data = get_session_from_redis(session_id)
    uref = (data or {}).get("uref")

    gib = get_gib_from_redis_for_logout(session_id)
    if gib:
        try:
            gib.hard_logout()
        except Exception:
            pass

    r.delete(sess_key(session_id))
    if uref:
        r.delete(active_key(uref))

    return {"ok": True}




@app.post("/api/v1/session/force")
async def force_session(payload: dict = Body(...)):
    auth = payload.get("auth", {}) or {}
    username = (auth.get("username") or "").strip()
    password = auth.get("password") or ""

    if not username or not password:
        raise HTTPException(422, detail="username/password missing")

    uref = user_ref_from_username(username)

    if not acquire_login_lock(uref):
        raise HTTPException(429, detail="LOGIN_IN_PROGRESS")

    try:
        # 1) Bizdeki aktif session'ı sil (varsa)
        old_sid = get_active_session_id(uref)
        if old_sid:
            r.delete(sess_key(old_sid))
            # active key TTL zaten var ama temizlemek daha doğru
            r.delete(active_key(uref))

        # 2) Yeni client ile agresif logout dene
        gib = GibClient(username, password, env=GIB_ENV)
        try:
            gib.hard_logout()
        except Exception:
            pass

        # 3) Login dene
        ok = gib.login()
        if not ok:
            detail = getattr(gib, "last_login_error", None) or "GIB_LOGIN_FAILED_OR_LOCKED"
            raise HTTPException(401, detail=detail)


        sid = secrets.token_urlsafe(24)
        save_session_to_redis(sid, gib.token, gib.session.cookies, uref=uref)
        set_active_session_id(uref, sid)

        return {"session_id": sid, "reused": False, "forced": True}

    finally:
        release_login_lock(uref)



@app.get("/api/v1/download-pdf/{uuid}")
async def download_pdf(uuid: str, session_id: str = Depends(get_session_id)):
    UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")

    fatura_uuid = (uuid or "").strip().strip("<>").strip()

    if not UUID_RE.match(fatura_uuid):
        raise HTTPException(400, detail=f"INVALID_FATURA_UUID: {fatura_uuid}")

    gib = get_gib_from_redis(session_id)
    if not gib:
        raise HTTPException(401, detail="SESSION_NOT_FOUND")

    html_content = gib.get_html(fatura_uuid)
    if not html_content:
        raise HTTPException(404, detail="HTML_NOT_FOUND")

    options = {'encoding': "UTF-8"}
    pdf_bin = pdfkit.from_string(html_content, False, options=options)
    return Response(content=pdf_bin, media_type="application/pdf")

