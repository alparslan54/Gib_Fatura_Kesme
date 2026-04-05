import requests
import json
import uuid
import time
import os
import logging 
from datetime import datetime
from logging.handlers import RotatingFileHandler

# Loglama ayarları
HSM_LOG_PATH = os.getenv("HSM_LOG_PATH", "/tmp/gib_hsm.log")

hsm_logger = logging.getLogger("gib_hsm")
hsm_logger.setLevel(logging.INFO)
hsm_logger.propagate = False  # sadece bu dosyaya yazsın

if not any(isinstance(h, RotatingFileHandler) for h in hsm_logger.handlers):
    fh = RotatingFileHandler(HSM_LOG_PATH, maxBytes=5_000_000, backupCount=3, encoding="utf-8")
    fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    fh.setFormatter(fmt)
    hsm_logger.addHandler(fh)
logger = logging.getLogger("gib_client")

class GibClient:
    BASE_URL_TEST = "https://earsivportaltest.efatura.gov.tr"
    BASE_URL_PROD = "https://earsivportal.efatura.gov.tr"

    def __init__(self, username, password, env="test"):
        self.username = username
        self.password = password
        self.base_url = self.BASE_URL_TEST if env == "test" else self.BASE_URL_PROD
        self.token = None
        self.session = requests.Session()
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
            "Referer": f"{self.base_url}/login.jsp",
            "Origin": self.base_url
        }

    def _dispatch_headers(self):
        # index_url login() içinde set ediliyor
        ref = getattr(self, "index_url", f"{self.base_url}/index.jsp?token={self.token}")

        return {
            "User-Agent": self.headers["User-Agent"],
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Origin": self.base_url,
            "Referer": ref,
            "X-Requested-With": "XMLHttpRequest",
            "Connection": "keep-alive",
        }
    
    
    def ensure_portal_context(self):
        """
        Token alındıktan sonra portal session/cookie bağını kurar.
        Bu adım olmadan dispatch 'yetkiniz yok' dönebilir.
        """
        if not self.token:
            raise Exception("Token yok")

        url = f"{self.base_url}/index.jsp?token={self.token}&v={int(time.time()*1000)}"
        r = self.session.get(url, headers={
            "User-Agent": self.headers["User-Agent"],
            "Referer": f"{self.base_url}/login.jsp",
        }, timeout=15)

        logger.info(f"Cookies after index: {self.session.cookies.get_dict()}")
        return r.status_code


    


    def login(self):
        url = f"{self.base_url}/earsiv-services/assos-login"
        payload = f"assoscmd=login&rtype=json&userid={self.username}&sifre={self.password}&parola=1&"

        try:
            response = self.session.post(
                url,
                data=payload,
                headers=self.headers,
                timeout=15
            )

            data = response.json()

            if "token" not in data:
                err = (data.get("messages", [{}]) or [{}])[0].get(
                    "text", "GIB_LOGIN_FAILED"
                )
                self.last_login_error = err
                logger.error(f"Giriş başarısız (GİB): {err}")
                return False

            # ✅ başarılı login
            self.token = data["token"]
            self.last_login_error = None

            # portal context
            self.ensure_portal_context()

            self.index_url = f"{self.base_url}/index.jsp?token={self.token}"
            self.session.get(self.index_url, timeout=15, allow_redirects=True)

            logger.info(f"Giriş başarılı. Token: {self.token[:5]}...")
            return True

        except Exception as e:
            self.last_login_error = str(e)
            logger.error(f"Login exception: {str(e)}")
            return False



    def logout(self):
        try:
            # token varsa agresif logout dene
            if getattr(self, "token", None):
                return self.hard_logout()
        except Exception:
            pass

        # fallback
        try:
            self.session.get(f"{self.base_url}/logout.jsp", timeout=10, allow_redirects=True)
        except Exception:
            pass

        try:
            self.session.cookies.clear()
        except Exception:
            pass

        self.token = None



    def hard_logout(self):
        """
        Test portalda tek-cihaz kilidini kaldırmak için agresif logout.
        Tarayıcı davranışını taklit eder: POST /earsiv-services/assos-login (form-url-encoded)
        """
        # Bazı akışlarda token boş olabilir; varsa kullanacağız
        token = getattr(self, "token", None)

        # Logout öncesi login sayfası bazen cookie set eder (best effort)
        try:
            self.session.get(f"{self.base_url}/login.jsp", timeout=10, allow_redirects=True)
        except Exception:
            pass

        # 1) En kritik: assos-login POST (tarayıcıdaki gibi)
        if token:
            try:
                url = f"{self.base_url}/earsiv-services/assos-login"
                data = {
                    "assoscmd": "logout",
                    "rtype": "json",
                    "token": token,
                }
                resp = self.session.post(
                    url,
                    data=data,
                    timeout=10,
                    allow_redirects=True,
                    headers={
                        "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
                        "Accept": "*/*",
                        "Origin": self.base_url,
                        "Referer": f"{self.base_url}/index.jsp?token={token}",
                    },
                )
                # İstersen log:
                # logger.info("assos-login logout POST -> %s", resp.status_code)
            except Exception:
                pass

        # 2) Diğer best-effort çağrılar (kalabilir)
        for path in ["/earsiv-services/logout", "/logout.jsp"]:
            try:
                self.session.get(f"{self.base_url}{path}", timeout=10, allow_redirects=True)
            except Exception:
                pass

        # 3) Mutlaka cookie temizle
        try:
            self.session.cookies.clear()
        except Exception:
            pass

        self.token = None





    def create_draft_invoice(self, vkn, alici_unvan, urun_adi, miktar, birim_fiyat, kdv_orani=20):
        """Taslak fatura oluşturur ve paylaşılan gerçek GİB yapısıyla tam uyumludur."""
        if not self.token:
            raise Exception("Token yok, önce login olun.")

        # Sayısal hesaplamalar
        miktar = int(miktar)
        birim_fiyat = float(birim_fiyat)
        matrah_tutar = miktar * birim_fiyat
        kdv_tutar = (matrah_tutar * kdv_orani) / 100
        toplam_tutar = matrah_tutar + kdv_tutar

        # TCKN/VKN Ayrımı
        is_tckn = len(str(vkn).strip()) == 11
        if is_tckn:
            parts = alici_unvan.split(" ", 1)
            alici_adi = parts[0]
            alici_soyadi = parts[1] if len(parts) > 1 else "."
            alici_unvan_field = alici_unvan # GİB bazen TCKN'de ünvanı da dolu isteyebilir, ama ad/soyad şarttır
        else:
            alici_adi = ""
            alici_soyadi = ""
            alici_unvan_field = alici_unvan

        # GİB'den aldığınız tam yapı (Skeleton)
        invoice_data = {
            "faturaUuid": str(uuid.uuid4()),
            "belgeNumarasi": "",
            "faturaTarihi": datetime.now().strftime("%d/%m/%Y"),
            "saat": datetime.now().strftime("%H:%M:%S"),
            "paraBirimi": "TRY",
            "dovzTLkur": "0",
            "faturaTipi": "SATIS",
            "hangiTip": "5000/30000", # Sizin örneğinizdeki değer
            "vknTckn": str(vkn),
            "aliciUnvan": alici_unvan_field,
            "aliciAdi": alici_adi,
            "aliciSoyadi": alici_soyadi,
            "vergiDairesi": "",
            "ulke": "Türkiye",
            "bulvarcaddesokak": "",
            "binaAdi": "",
            "binaNo": "",
            "kapiNo": "",
            "kasabaKoy": "",
            "mahalleSemtIlce": "",
            "sehir": " ",
            "postaKodu": "",
            "tel": "",
            "fax": "",
            "eposta": "",
            "websitesi": "",
            "irsaliyeNumarasi": "",
            "irsaliyeTarihi": "",
            "iadeTable": [],
            "ihracKayitliKarsiBelgeNo": "",
            "yatirimTesvikNumarasi": 0,
            "yatirimTesvikTarihi": datetime.now().strftime("%d/%m/%Y"),
            "vergiCesidi": " ",
            "malHizmetTable": [
                {
                    "malHizmet": urun_adi,
                    "miktar": miktar,
                    "birim": "C62", # GİB portalında 'Adet' için kullanılan uluslararası kod C62'dir
                    "birimFiyat": f"{birim_fiyat:.2f}",
                    "fiyat": f"{matrah_tutar:.2f}",
                    "iskontoOrani": 0,
                    "iskontoTutari": "0",
                    "iskontoNedeni": "",
                    "malHizmetTutari": f"{matrah_tutar:.2f}",
                    "kdvOrani": str(kdv_orani),
                    "vergiOrani": 0,
                    "kdvTutari": f"{kdv_tutar:.2f}",
                    "vergininKdvTutari": "0",
                    "ozelMatrahTutari": "0",
                    "hesaplananotvtevkifatakatkisi": "0"
                }
            ],
            "tip": "İskonto",
            "matrah": f"{matrah_tutar:.2f}",
            "malhizmetToplamTutari": f"{matrah_tutar:.2f}",
            "toplamIskonto": "0",
            "hesaplanankdv": f"{kdv_tutar:.2f}", # Portalda küçük harf 'kdv' kullanılmış
            "vergilerToplami": f"{kdv_tutar:.2f}",
            "vergilerDahilToplamTutar": f"{toplam_tutar:.2f}",
            "odenecekTutar": f"{toplam_tutar:.2f}",
            "not": "",
            "siparisNumarasi": "",
            "siparisTarihi": "",
            "fisNo": "",
            "fisTarihi": "",
            "fisSaati": " ",
            "fisTipi": " ",
            "zRaporNo": "",
            "okcSeriNo": ""
        }

        payload = {
            "cmd": "EARSIV_PORTAL_FATURA_OLUSTUR",
            "callid": str(uuid.uuid4()),
            "pageName": "RG_BASITFATURA",
            "token": self.token,
            "jp": json.dumps(invoice_data, ensure_ascii=False)
        }

        url = f"{self.base_url}/earsiv-services/dispatch"
        resp = self.session.post(url, data=payload, headers=self._dispatch_headers(), timeout=15)
        resp_json = resp.json()

        # GİB yanıt kontrolü
        if "data" in resp_json and "başarıyla" in str(resp_json["data"]):
            return invoice_data["faturaUuid"]
        else:
            raise Exception(f"Fatura oluşturma hatası: {resp_json}")
        
    def sign_draft_hsm(self, fatura_uuid: str):
        """
        HSM / e-İmza ile taslak faturayı imzalamayı dener.
        GİB yetkisi yoksa logical error döner.
        """
        url = f"{self.base_url}/earsiv-services/dispatch"

        payload = {
            "cmd": "EARSIV_PORTAL_FATURA_HSM_CIHAZI_ILE_IMZALA",
            "callid": str(uuid.uuid4()),
            "pageName": "RG_BASITTASLAKLAR",
            "token": self.token,
            "jp": json.dumps({"ettn": str(fatura_uuid)}, ensure_ascii=False),
        }

        # --- HSM LOG: request özet ---
        hsm_logger.info("HSM_SIGN_REQ callid=%s ettn=%s base_url=%s", payload["callid"], fatura_uuid, self.base_url)

        try:
            resp = self.session.post(
                url,
                data=payload,
                headers=self._dispatch_headers(),
                timeout=20
            )

            ctype = (resp.headers.get("Content-Type") or "").lower()
            text_snip = (resp.text or "")[:800].replace("\n", " ")

            # --- HSM LOG: response meta + snippet ---
            hsm_logger.info("HSM_SIGN_RESP status=%s ctype=%s snippet=%s", resp.status_code, ctype, text_snip)

            try:
                js = resp.json()
                # --- HSM LOG: json error/messages (varsa) ---
                if isinstance(js, dict) and js.get("error") == "1":
                    msg = (js.get("messages") or [{}])[0].get("text")
                    hsm_logger.warning("HSM_SIGN_GIB_ERROR msg=%s full=%s", msg, json.dumps(js, ensure_ascii=False)[:1200])
                return js
            except Exception:
                hsm_logger.error("HSM_SIGN_NOT_JSON status=%s ctype=%s snippet=%s", resp.status_code, ctype, text_snip)
                return {
                    "error": "1",
                    "messages": [{
                        "text": "HSM_SIGN_RESPONSE_NOT_JSON",
                        "raw": resp.text
                    }]
                }

        except Exception as e:
            hsm_logger.exception("HSM_SIGN_EXCEPTION ettn=%s err=%s", fatura_uuid, str(e))
            raise


        
    def try_sign_with_hsm(self, fatura_uuid: str):
        try:
            resp = self.sign_draft_hsm(fatura_uuid)

            if isinstance(resp, dict) and resp.get("error") == "1":
                msg = (resp.get("messages") or [{}])[0].get("text", "HSM_SIGN_FAILED")
                hsm_logger.warning("HSM_SIGN_RESULT signed=0 ettn=%s reason=%s", fatura_uuid, msg)
                return {"signed": False, "reason": msg}

            hsm_logger.info("HSM_SIGN_RESULT signed=1 ettn=%s", fatura_uuid)
            return {"signed": True, "result": resp}

        except Exception as e:
            hsm_logger.error("HSM_SIGN_RESULT signed=0 ettn=%s exception=%s", fatura_uuid, str(e))
            return {"signed": False, "reason": str(e)}

        
    def test_access(self):
        payload = {
            "cmd": "SICIL_VEYA_MERNISTEN_BILGILERI_GETIR",
            "callid": str(uuid.uuid4()),
            "pageName": "RG_BASITFATURA",
            "token": self.token,
            "jp": json.dumps({"vknTcknn": "11111111111"})
        }
        url = f"{self.base_url}/earsiv-services/dispatch"
        return self.session.post(
            url,
            data=payload,
            headers=self._dispatch_headers(),
            timeout=15
        ).json()



    
    def get_phone_number(self):
        """
        Portalda kayıtlı telefonu sorgular.
        GİB, SMS gönderimi için genelde CEP telefonu ister.
        """
        payload = {
            "cmd": "EARSIV_PORTAL_TELEFONNO_SORGULA",
            "callid": str(uuid.uuid4()),
            "pageName": "RG_BASITTASLAKLAR",
            "token": self.token,
            "jp": "{}",
        }
        url = f"{self.base_url}/earsiv-services/dispatch"
        resp = self.session.post(url, data=payload, headers=self._dispatch_headers(), timeout=15).json()
        try:
            return resp.get("data", {}).get("telefon") or resp.get("data", {}).get("cepTel") or ""
        except Exception:
            return ""

    def get_invoice(self, ettn: str):
        """
        ETTN/Fatura UUID ile fatura detaylarını çeker (belgeNo, onayDurumu vb).
        """
        payload = {
            "cmd": "EARSIV_PORTAL_FATURA_GETIR",
            "callid": str(uuid.uuid4()),
            "pageName": "RG_BASITFATURA",
            "token": self.token,
            "jp": json.dumps({"ettn": ettn}),
        }
        url = f"{self.base_url}/earsiv-services/dispatch"
        return self.session.post(url, data=payload, headers=self._dispatch_headers(), timeout=15).json()

    def send_sms(self):
        """
        SMS onayını tetikler.
        Yeni akış: önce telefon sorgula -> sms gönder.
        Eğer telefon sorgusu boş dönerse (özellikle TEST ortamında), eski akışa fallback yapar.
        """
        url = f"{self.base_url}/earsiv-services/dispatch"

        # 1) Telefon sorgula (yeni yaklaşım)
        try:
            q_payload = {
                "cmd": "EARSIV_PORTAL_TELEFONNO_SORGULA",
                "callid": str(uuid.uuid4()),
                "pageName": "RG_SMS_ONAY",
                "token": self.token,
                "jp": "{}",
            }
            q = self.session.post(url, data=q_payload, headers=self._dispatch_headers(), timeout=15).json()

            phone = None
            # farklı response varyasyonlarına tolerans
            if isinstance(q, dict):
                d = q.get("data")
                if isinstance(d, str) and d.strip():
                    phone = d.strip()
                elif isinstance(d, dict):
                    phone = (d.get("telefon") or d.get("phone") or "").strip()

            if phone:
                # 2) Telefon bulundu → SMS gönder (yeni komut)
                s_payload = {
                    "cmd": "EARSIV_PORTAL_SMSSIFRE_GONDER",
                    "callid": str(uuid.uuid4()),
                    "pageName": "RG_SMS_ONAY",
                    "token": self.token,
                    "jp": json.dumps({"cepTelefon": phone}, ensure_ascii=False),
                }
                s = self.session.post(url, data=s_payload, headers=self._dispatch_headers(), timeout=15).json()
                # debug amaçlı phone’u ekleyelim
                if isinstance(s, dict):
                    s["_phone"] = phone
                return s

        except Exception:
            # yeni akış patlarsa da fallback deneyeceğiz
            pass

        # 3) Telefon yok / boş → ESKİ fallback
        legacy_payload = {
            "cmd": "0",
            "callid": str(uuid.uuid4()),
            "pageName": "RG_SMS_ONAY",
            "token": self.token,
            "jp": json.dumps({"islemTipi": "0"}, ensure_ascii=False),
        }
        legacy = self.session.post(url, data=legacy_payload, headers=self._dispatch_headers(), timeout=15).json()
        if isinstance(legacy, dict):
            legacy["_fallback"] = True
        return legacy


    def verify_sms(self, sms_code: str, fatura_uuid: str, sms_oid: str):
        """
        SMS kodu + OID + fatura UUID ile onayı tamamlar.
        Bu yol SMS varsa %100 doğru yoldur.
        """
        inv = self.get_invoice(fatura_uuid)
        inv_data = inv.get("data") or {}

        belge_no = (
            inv_data.get("belgeNumarasi")
            or inv_data.get("belgeNo")
            or ""
        )
        onay = inv_data.get("onayDurumu") or "Onaylanmadı"

        payload = {
            "cmd": "0lhozfib5410mp",
            "callid": str(uuid.uuid4()),
            "pageName": "RG_SMSONAY",
            "token": self.token,
            "jp": json.dumps({
                "SIFRE": str(sms_code),
                "OID": str(sms_oid),
                "OPR": 1,
                "DATA": [{
                    "ettn": str(fatura_uuid),
                    "belgeNo": str(belge_no),
                    "onayDurumu": str(onay),
                }]
            }, ensure_ascii=False),
        }

        url = f"{self.base_url}/earsiv-services/dispatch"
        resp = self.session.post(
            url,
            data=payload,
            headers=self._dispatch_headers(),
            timeout=15
        )
        return resp.json()


    def get_html(self, fatura_uuid: str, onay_durumu: str = "Onaylanmadi"):
        """
        Portalın 'Görüntüle' butonunun yaptığı çağrıyla aynı:
        cmd=EARSIV_PORTAL_FATURA_GOSTER
        pageName=RG_TASLAKLAR
        jp={"ettn": "...", "onayDurumu":"Onaylanmadi"}
        """
        payload = {
            "cmd": "EARSIV_PORTAL_FATURA_GOSTER",
            "callid": str(uuid.uuid4()),
            "pageName": "RG_TASLAKLAR",
            "token": self.token,
            "jp": json.dumps({"ettn": fatura_uuid, "onayDurumu": onay_durumu}, ensure_ascii=False),
        }

        url = f"{self.base_url}/earsiv-services/dispatch"
        resp = self.session.post(url, data=payload, headers=self._dispatch_headers(), timeout=15)

        ctype = (resp.headers.get("Content-Type") or "").lower()
        text = resp.text or ""

        if "application/json" not in ctype:
            snippet = text[:300].replace("\n", " ")
            raise Exception(f"GIB_NON_JSON_RESPONSE (ctype={ctype}, status={resp.status_code}) snippet={snippet}")

        try:
            js = resp.json()
        except Exception as e:
            snippet = text[:300].replace("\n", " ")
            raise Exception(f"GIB_JSON_PARSE_FAILED status={resp.status_code} snippet={snippet}") from e

        # GİB hata mesajları varsa yakala
        if js.get("error") == "1":
            raise Exception(f"GIB_ERROR: {js}")

        html = js.get("data") or ""
        return html

