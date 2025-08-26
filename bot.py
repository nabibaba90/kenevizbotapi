#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# VIP Sorgu Paneli - Tüm API'ler eklendi ve cevaplarda sahip/kanal maskelendi
# Sahip: @Keneviiz
# Telegram kanal: https://t.me/KeneviizApiSystem

from flask import Flask, request, jsonify, Response
import requests
import time, re, json
from functools import wraps
from collections import defaultdict

app = Flask(__name__)
app.secret_key = "supersecretkey123"

# ----------------------
# Sabitler
# ----------------------
RATE_LIMIT = 15
rate_cache = defaultdict(list)
SAHIP = "@Keneviiz"
TELEGRAM_KANAL = "https://t.me/KeneviizApiSystem"
REQUEST_TIMEOUT = 10
USER_AGENT = "Keneviiz-Proxy/1.0"

def rate_limit(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        ip = request.remote_addr or "unknown"
        now = time.time()
        # cache temizleme (son 60 saniyeyi tut)
        rate_cache[ip] = [t for t in rate_cache[ip] if now - t < 60]
        if len(rate_cache[ip]) >= RATE_LIMIT:
            return jsonify({"error": "Rate limit aşıldı (dakikada %d istek)" % RATE_LIMIT}), 429
        rate_cache[ip].append(now)
        return f(*args, **kwargs)
    return decorated

# ----------------------
# Basit input temizleme
# ----------------------
def sanitize(val):
    if not isinstance(val, str):
        return val
    v = re.sub(r'[\"\'=<>]', '', val)
    v = v.strip()
    return v

# ----------------------
# Masking / normalization yardımcıları
# ----------------------
_OWNER_PATTERNS = [
    "kahin", "kahinapi", "hexnox", "sowix", "sowixfree", "sowixapi",
    "hexnox.pro", "api.kahin.org", "kahin.org"
]

_OWNER_KEYS = [
    "source", "sahip", "owner", "author", "developer", "maker",
    "kaynak", "site", "kanal", "channel"
]

def looks_like_other_owner(s: str) -> bool:
    if not isinstance(s, str):
        return False
    sl = s.lower()
    for p in _OWNER_PATTERNS:
        if p in sl:
            return True
    return False

def mask_string_value(s: str) -> str:
    if not isinstance(s, str):
        return s
    orig = s
    s_low = s.lower()

    if looks_like_other_owner(s):
        return "Keneviiz systems"

    s = re.sub(r"https?://t\.me/[^\s\"'<>]+", TELEGRAM_KANAL, s, flags=re.IGNORECASE)
    s = re.sub(r"t\.me/[^\s\"'<>]+", TELEGRAM_KANAL, s, flags=re.IGNORECASE)

    s = re.sub(r"@[-\w\.]{2,}", SAHIP, s)

    for p in _OWNER_PATTERNS:
        s = re.sub(re.escape(p), "Keneviiz systems", s, flags=re.IGNORECASE)

    if s == orig and re.search(r"(hexnox|kahin|sowix|api\.)", s_low):
        return "Keneviiz systems"

    return s


def normalize_response_recursive(obj):
    if isinstance(obj, dict):
        for k in list(obj.keys()):
            v = obj[k]
            lk = k.lower()
            if any(ok in lk for ok in _OWNER_KEYS):
                if "kanal" in lk or "channel" in lk or "telegram" in lk:
                    obj[k] = TELEGRAM_KANAL
                else:
                    obj[k] = SAHIP
                continue
            if isinstance(v, str):
                obj[k] = mask_string_value(v)
            elif isinstance(v, (dict, list)):
                normalize_response_recursive(v)
    elif isinstance(obj, list):
        for i in range(len(obj)):
            item = obj[i]
            if isinstance(item, str):
                obj[i] = mask_string_value(item)
            elif isinstance(item, (dict, list)):
                normalize_response_recursive(item)

# ----------------------
# Tüm API'ler (senin verdiğin tüm endpointler eklendi)
# ----------------------
APIS = {
    # kahin.org / api.kahin.org family
    "tc_sorgulama": {"desc": "TC Sorgulama", "url": "https://api.kahin.org/kahinapi/tc", "params": ["tc"]},
    "tc_pro_sorgulama": {"desc": "TC PRO Sorgulama", "url": "https://api.kahin.org/kahinapi/tcpro", "params": ["tc"]},
    "hayat_hikayesi": {"desc": "Hayat Hikayesi Sorgulama", "url": "https://api.kahin.org/kahinapi/hayathikayesi.php", "params": ["tc"]},
    "ad_soyad": {"desc": "Ad Soyad Sorgulama", "url": "https://api.kahin.org/kahinapi/adsoyad", "params": ["ad", "soyad", "il", "ilce"]},
    "ad_soyad_pro": {"desc": "Ad Soyad PRO Sorgulama", "url": "https://api.kahin.org/kahinapi/tapu", "params": ["tc"]},
    "is_yeri": {"desc": "İş Yeri Sorgulama", "url": "https://api.kahin.org/kahinapi/isyeri", "params": ["tc"]},
    "vergi_no": {"desc": "Vergi No Sorgulama", "url": "https://api.kahin.org/kahinapi/vergino", "params": ["vergi"]},
    "yas": {"desc": "Yaş Sorgulama", "url": "https://api.kahin.org/kahinapi/yas", "params": ["tc"]},
    "tc_gsm": {"desc": "TC GSM Sorgulama", "url": "https://api.kahin.org/kahinapi/tcgsm", "params": ["tc"]},
    "gsm_tc": {"desc": "GSM TC Sorgulama", "url": "https://api.kahin.org/kahinapi/gsmtc", "params": ["gsm"]},
    "adres": {"desc": "Adres Sorgulama", "url": "https://api.kahin.org/kahinapi/adres.php", "params": ["tc"]},
    "hane": {"desc": "Hane Sorgulama", "url": "https://api.kahin.org/kahinapi/hane", "params": ["tc"]},
    "apartman": {"desc": "Apartman Sorgulama", "url": "https://api.kahin.org/kahinapi/apartman", "params": ["tc"]},
    "ada_parsel": {"desc": "Ada Parsel Sorgulama", "url": "https://api.kahin.org/kahinapi/adaparsel", "params": ["il", "ada", "parsel"]},
    "adi_il_ilce": {"desc": "Adı İl İlçe Sorgulama", "url": "https://api.kahin.org/kahinapi/adililce.php", "params": ["ad", "il"]},
    "aile": {"desc": "Aile Sorgulama", "url": "https://api.kahin.org/kahinapi/aile", "params": ["tc"]},
    "aile_pro": {"desc": "Aile PRO Sorgulama", "url": "https://api.kahin.org/kahinapi/ailepro", "params": ["tc"]},
    "es": {"desc": "Eş Sorgulama", "url": "https://api.kahin.org/kahinapi/es", "params": ["tc"]},
    "sulale": {"desc": "Sulale Sorgulama", "url": "https://api.kahin.org/kahinapi/sulale", "params": ["tc"]},
    "lgs": {"desc": "LGS Sorgulama", "url": "https://api.kahin.org/kahinapi/lgs", "params": ["tc"]},
    "e_kurs": {"desc": "E-Kurs Sorgulama", "url": "https://api.kahin.org/kahinapi/ekurs", "params": ["tc", "okulno"]},
    "ip": {"desc": "IP Sorgulama", "url": "https://api.kahin.org/kahinapi/ip", "params": ["domain"]},
    "dns": {"desc": "DNS Sorgulama", "url": "https://api.kahin.org/kahinapi/dns", "params": ["domain"]},
    "whois": {"desc": "Whois Sorgulama", "url": "https://api.kahin.org/kahinapi/whois", "params": ["domain"]},
    "subdomain": {"desc": "Subdomain Sorgulama", "url": "https://api.kahin.org/kahinapi/subdomain.php", "params": ["url"]},
    "leak": {"desc": "Leak Sorgulama", "url": "https://api.kahin.org/kahinapi/leak.php", "params": ["query"]},
    "telegram": {"desc": "Telegram Sorgulama", "url": "https://api.kahin.org/kahinapi/telegram.php", "params": ["kullanici"]},
    "sifre_encrypt": {"desc": "Şifre Encrypt", "url": "https://api.kahin.org/kahinapi/encrypt", "params": ["method", "password"]},

    # hexnox / sowix family (senin verdiğin ve mevcut olanlar)
    "prem_ad": {"desc": "Prem Ad Sorgulama", "url": "https://hexnox.pro/sowixapi/premad.php", "params": ["ad", "il", "ilce"]},
    "mhrs_randevu": {"desc": "MHRS Randevu Sorgulama", "url": "https://hexnox.pro/sowixfree/mhrs/mhrs.php", "params": ["tc"]},
    "prem_adres": {"desc": "Prem Adres Sorgulama", "url": "https://hexnox.pro/sowixfree/premadres.php", "params": ["tc"]},
    "sgk_pro": {"desc": "SGK PRO Sorgulama", "url": "https://api.hexnox.pro/sowixapi/sgkpro.php", "params": ["tc"]},
    "vergi_levhasi": {"desc": "Vergi Levhası Sorgulama", "url": "https://hexnox.pro/sowixfree/vergi/vergi.php", "params": ["tc"]},
    "facebook": {"desc": "Facebook Sorgulama", "url": "https://hexnox.pro/sowixfree/facebook.php", "params": ["numara"]},
    "diploma": {"desc": "Diploma Sorgulama", "url": "https://hexnox.pro/sowixfree/diploma/diploma.php", "params": ["tc"]},
    "basvuru": {"desc": "Başvuru Sorgulama", "url": "https://hexnox.pro/sowixfree/basvuru/basvuru.php", "params": ["tc"]},
    "nobetci_eczane": {"desc": "Nöbetçi Eczane Sorgulama", "url": "https://hexnox.pro/sowixfree/nezcane.php", "params": ["il", "ilce"]},
    "randevu": {"desc": "Randevu Sorgulama", "url": "https://hexnox.pro/sowixfree/nvi.php", "params": ["tc"]},
    "internet": {"desc": "İnternet Sorgulama", "url": "https://hexnox.pro/sowixfree/internet.php", "params": ["tc"]},
    "personel": {"desc": "Personel Sorgulama", "url": "https://api.hexnox.pro/sowixapi/personel.php", "params": ["tc"]},
    "interpol": {"desc": "Interpol Arananlar Sorgulama", "url": "https://api.hexnox.pro/sowixfree/interpol.php", "params": ["ad", "soyad"]},
    "sehit": {"desc": "Şehit Sorgulama", "url": "https://api.hexnox.pro/sowixfree/şehit.php", "params": ["Ad", "Soyad"]},
    "arac_parca": {"desc": "Araç Parça Sorgulama", "url": "https://hexnox.pro/sowixfree/aracparca.php", "params": ["plaka"]},
    "universite": {"desc": "Üniversite Sorgulama", "url": "http://hexnox.pro/sowixfree/%C3%BCni.php", "params": ["tc"]},
    "sertifika": {"desc": "Sertifika Sorgulama", "url": "http://hexnox.pro/sowixfree/sertifika.php", "params": ["tc"]},
    "nude": {"desc": "Nude API", "url": "http://hexnox.pro/sowixfree/nude.php", "params": []},
    "arac_borc": {"desc": "Araç Borç Sorgulama", "url": "http://hexnox.pro/sowixfree/plaka.php", "params": ["plaka"]},
    "lgs_2": {"desc": "LGS Sorgulama (2)", "url": "http://hexnox.pro/sowixfree/lgs/lgs.php", "params": ["tc"]},
    "muhalle": {"desc": "Mahalle Sorgulama", "url": "https://api.hexnox.pro/sowixapi/muhallev.php", "params": ["tc"]},
    "vesika": {"desc": "Vesika Sorgulama", "url": "https://hexnox.pro/sowix/vesika.php", "params": ["tc"]},
    "ehliyet": {"desc": "Ehliyet API", "url": "http://api.hexnox.pro/sowixapi/ehlt.php", "params": ["tc"]},
    "hava_durumu": {"desc": "Hava Durumu Sorgulama", "url": "http://api.hexnox.pro/sowixapi/havadurumu.php", "params": ["sehir"]},
    "email": {"desc": "Email Sorgulama", "url": "http://api.hexnox.pro/sowixapi/email_sorgu.php", "params": ["email"]},
    "boy": {"desc": "Boy API", "url": "http://api.hexnox.pro/sowixapi/boy.php", "params": ["tc"]},
    "ayak_no": {"desc": "Ayak No API", "url": "http://api.hexnox.pro/sowixapi/ayak.php", "params": ["tc"]},
    "cm": {"desc": "CM API", "url": "http://api.hexnox.pro/sowixapi/cm.php", "params": ["tc"]},
    "burc": {"desc": "Burç Sorgulama", "url": "http://api.hexnox.pro/sowixapi/burc.php", "params": ["tc"]},
    "cocuk": {"desc": "Çocuk Sorgulama", "url": "https://api.hexnox.pro/sowixapi/cocuk.php", "params": ["tc"]},
    "imei": {"desc": "IMEI Sorgulama", "url": "https://api.hexnox.pro/sowixapi/imei.php", "params": ["imei"]},
    "baba": {"desc": "Baba Sorgulama", "url": "http://hexnox.pro/sowixfree/baba.php", "params": ["tc"]},
    "anne": {"desc": "Anne Sorgulama", "url": "http://hexnox.pro/sowixfree/anne.php", "params": ["tc"]},
    "operator": {"desc": "Operatör Sorgulama", "url": "https://api.hexnox.pro/sowixapi/operator.php", "params": ["gsm"]},

    # senin eklediğin yeni endpointler (doğrudan linkler)
    "fatura": {"desc": "Fatura (hexnox)", "url": "https://hexnox.pro/sowixfree/fatura.php", "params": ["tc"]},
    "hexnox_subdomain": {"desc": "Subdomain (hexnox api)", "url": "https://api.hexnox.pro/sowixapi/subdomain.php", "params": ["url"]},
    "sexgorsel": {"desc": "Sex Görsel Sorgu (hexnox)", "url": "https://hexnox.pro/sowixfree/sexgörsel.php", "params": ["soru"]},
    "meslek_hex": {"desc": "Meslek (hexnox api)", "url": "https://api.hexnox.pro/sowixapi/meslek.php", "params": ["tc"]},
    "sgk_hex": {"desc": "SGK (hexnox)", "url": "http://hexnox.pro/sowixfree/sgk/sgk.php", "params": ["tc"]},

    # fallback: subdomain generic
    "subdomain_generic": {"desc": "Subdomain generic", "url": "https://api.hexnox.pro/sowixapi/subdomain.php", "params": ["url"]}
}

# ----------------------
# API Proxy Route
# ----------------------
@app.route("/api/<api_name>", methods=["GET"])
@rate_limit
def api_proxy(api_name):
    if api_name not in APIS:
        return jsonify({"error": "API bulunamadı", "sahip": SAHIP, "telegram_kanal": TELEGRAM_KANAL}), 404

    api = APIS[api_name]
    params = {}
    for p in api.get("params", []):
        if p not in request.args:
            return jsonify({"error": f"Parametre eksik: {p}", "sahip": SAHIP, "telegram_kanal": TELEGRAM_KANAL}), 400
        params[p] = sanitize(request.args[p])

    try:
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "application/json,text/html;q=0.9,*/*;q=0.8"
        }
        r = requests.get(api["url"], params=params, headers=headers, timeout=REQUEST_TIMEOUT)
        content_type = r.headers.get("Content-Type", "").lower()

        try:
            data = r.json()
            normalize_response_recursive(data)

            if isinstance(data, dict) and "info" in data:
                data["info"] = "Hata alırsanız @Keneviiz Telegram’dan ulaşabilirsiniz."

            if isinstance(data, dict):
                data.setdefault("sahip", SAHIP)
                data.setdefault("telegram_kanal", TELEGRAM_KANAL)

            resp_text = json.dumps(data, indent=4, ensure_ascii=False)
            return Response(response=resp_text, status=200, mimetype='application/json')

        except ValueError:
            text = r.text or ""
            replacements = _OWNER_PATTERNS + ["api.kahin.org", "kahin.org"]
            masked = text
            for p in set(replacements):
                masked = re.sub(re.escape(p), "Keneviiz systems", masked, flags=re.IGNORECASE)
            masked = re.sub(r"https?://t\.me/[^\s\"'<>]+", TELEGRAM_KANAL, masked, flags=re.IGNORECASE)
            masked = re.sub(r"@[-\w\.]{2,}", SAHIP, masked)

            result = {
                "raw": masked,
                "note": "Orijinal metin JSON değil, metin maskelendi.",
                "sahip": SAHIP,
                "telegram_kanal": TELEGRAM_KANAL
            }
            return Response(response=json.dumps(result, indent=4, ensure_ascii=False), status=200, mimetype='application/json')

    except requests.exceptions.RequestException as e:
        err = {
            "error": "Kayıt bulunamadı veya uzak sunucu hatası",
            "detail": "Uzak API erişim hatası",
            "sahip": SAHIP,
            "telegram_kanal": TELEGRAM_KANAL
        }
        return Response(response=json.dumps(err, indent=4, ensure_ascii=False), status=502, mimetype='application/json')
    except Exception as e:
        err = {
            "error": "Bilinmeyen hata oluştu",
            "detail": str(e),
            "sahip": SAHIP,
            "telegram_kanal": TELEGRAM_KANAL
        }
        return Response(response=json.dumps(err, indent=4, ensure_ascii=False), status=500, mimetype='application/json')

# ----------------------
# Ana Sayfa
# ----------------------
@app.route("/")
def index():
    return f"""
    <h1>VIP Sorgu Paneli Çalışıyor</h1>
    <p>Sahip: {SAHIP} — Kanal: <a href=\"{TELEGRAM_KANAL}\">{TELEGRAM_KANAL}</a></p>
    <p>Destek için Telegram: {TELEGRAM_KANAL}</p>
    """

# ----------------------
# Çalıştır
# ----------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)

