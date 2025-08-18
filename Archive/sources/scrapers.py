
import requests, re
from bs4 import BeautifulSoup
from datetime import datetime

HEADERS = {"User-Agent":"Mozilla/5.0 (compatible; Bot/1.0)"}

def _parse_number(s):
    if s is None: return None
    s = str(s)
    s = s.replace('\\u202f','').replace('\\xa0',' ').replace(',','').strip()
    m = re.search(r"([0-9]+(?:\\.[0-9]+)?)", s.replace(' ',''))
    if not m: return None
    try:
        return float(m.group(1))
    except:
        return None

def scrape_vietstock_market():
    urls = ["https://finance.vietstock.vn/ket-qua-giao-dich", "https://finance.vietstock.vn/" ]
    for url in urls:
        try:
            r = requests.get(url, headers=HEADERS, timeout=8)
            if r.status_code != 200: continue
            soup = BeautifulSoup(r.text, 'html.parser')
            text = soup.get_text(' ', strip=True)
            m = re.search(r"VN[- ]?Index[:\\s]*([0-9\\.,]+)", text, re.IGNORECASE)
            idx = _parse_number(m.group(1)) if m else None
            fb = fs = None
            m2 = re.search(r"(Khối ngoại|Nước ngoài|NN).*?Mua[:\\s]*([0-9\\.,]+).*?Bán[:\\s]*([0-9\\.,]+)", text, re.IGNORECASE)
            if m2:
                fb = _parse_number(m2.group(2)); fs = _parse_number(m2.group(3))
            if idx or fb or fs:
                return {"source":"vietstock", "index": idx, "fbuy": fb, "fsell": fs, "ts": datetime.utcnow().isoformat()}
        except Exception:
            continue
    return None

def scrape_cafef_market():
    urls = ["https://cafef.vn/du-lieu.chn", "https://cafef.vn/du-lieu/lich-su-giao-dich-vnindex-1.chn" ]
    for url in urls:
        try:
            r = requests.get(url, headers=HEADERS, timeout=8)
            if r.status_code != 200: continue
            text = r.text
            m = re.search(r"VN[- ]?Index[:\\s]*([0-9\\.,]+)", text, re.IGNORECASE)
            idx = _parse_number(m.group(1)) if m else None
            fb = fs = None
            m2 = re.search(r"Khối ngoại.*?Mua[:\\s]*([0-9\\.,]+).*?Bán[:\\s]*([0-9\\.,]+)", text, re.IGNORECASE)
            if m2:
                fb = _parse_number(m2.group(1)); fs = _parse_number(m2.group(2))
            if idx or fb:
                return {"source":"cafef", "index": idx, "fbuy": fb, "fsell": fs, "ts": datetime.utcnow().isoformat()}
        except Exception:
            continue
    return None
