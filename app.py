from flask import Flask, request, jsonify
import os
import re
import time
import json
import requests
from bs4 import BeautifulSoup

app = Flask(__name__)

# Config
TARGET_BASE = os.getenv("TARGET_BASE", "https://pakistandatabase.com")
TARGET_PATH = os.getenv("TARGET_PATH", "/databases/sim.php")
POLICE_PATH = os.getenv("POLICE_PATH", "/databases/police.php")
LANDLINE_PATH = os.getenv("LANDLINE_PATH", "/databases/landline.php")
MIN_INTERVAL = float(os.getenv("MIN_INTERVAL", "1.0"))
LAST_CALL = {"ts": 0.0}

COPYRIGHT_HANDLE = "@sakib01994"
COPYRIGHT_NOTICE = "👉🏻 " + COPYRIGHT_HANDLE

def is_mobile(value: str) -> bool:
    return bool(re.fullmatch(r"92\d{9,12}", (value or "").strip()))

def is_cnic(value: str) -> bool:
    return bool(re.fullmatch(r"\d{13}", (value or "").strip()))

def validate_mobile(value: str):
    value = value.strip()
    if not value:
        raise ValueError("Mobile number cannot be empty")
    if not value.startswith('92'):
        raise ValueError("Mobile number must start with 92")
    if not value[2:].isdigit():
        raise ValueError("Mobile number must contain only digits after 92")
    if len(value) < 11 or len(value) > 13:
        raise ValueError("Mobile number must be 11-13 digits total (including 92)")
    return value

def validate_cnic(value: str):
    value = value.strip()
    if not value:
        raise ValueError("CNIC cannot be empty")
    if not value.isdigit():
        raise ValueError("CNIC must contain only digits")
    if len(value) != 13:
        raise ValueError("CNIC must be exactly 13 digits")
    return value

def validate_police_query(value: str):
    value = value.strip()
    if not value:
        raise ValueError("Query cannot be empty")
    
    # Check if it's a mobile number (with 92 or 0)
    if value.startswith('92') and value[2:].isdigit() and len(value) >= 11:
        return "mobile", value
    elif value.startswith('0') and value[1:].isdigit() and len(value) >= 10:
        return "mobile", value
    # Check if it's CNIC
    elif value.isdigit() and len(value) == 13:
        return "cnic", value
    else:
        raise ValueError("Invalid format. Use mobile (92XXXXXXXXXX or 0XXXXXXXXX) or CNIC (13 digits)")

def validate_landline(value: str):
    value = value.strip()
    if not value:
        raise ValueError("Landline number cannot be empty")
    if not value.isdigit():
        raise ValueError("Landline number must contain only digits")
    if len(value) < 9 or len(value) > 12:
        raise ValueError("Landline number must be 9-12 digits")
    return value

def rate_limit_wait():
    now = time.time()
    elapsed = now - LAST_CALL["ts"]
    if elapsed < MIN_INTERVAL:
        time.sleep(MIN_INTERVAL - elapsed)
    LAST_CALL["ts"] = time.time()

def fetch_upstream(query_value: str):
    rate_limit_wait()
    session = requests.Session()
    headers = {
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"),
        "Referer": TARGET_BASE.rstrip("/") + "/",
        "Accept-Language": "en-US,en;q=0.9",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    url = TARGET_BASE.rstrip("/") + TARGET_PATH
    data = {"search_query": query_value}
    resp = session.post(url, headers=headers, data=data, timeout=200)
    resp.raise_for_status()
    return resp.text

def fetch_police_upstream(query_value: str):
    rate_limit_wait()
    session = requests.Session()
    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Mobile Safari/537.36",
        "Referer": TARGET_BASE.rstrip("/") + "/databases/police.php",
        "Accept-Language": "en-US,en;q=0.9",
        "Content-Type": "application/x-www-form-urlencoded",
        "Origin": TARGET_BASE.rstrip("/"),
        "Upgrade-Insecure-Requests": "1",
    }
    url = TARGET_BASE.rstrip("/") + POLICE_PATH
    data = {"search_query": query_value}
    resp = session.post(url, headers=headers, data=data, timeout=200)
    resp.raise_for_status()
    return resp.text

def fetch_landline_upstream(query_value: str):
    rate_limit_wait()
    session = requests.Session()
    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Mobile Safari/537.36",
        "Referer": TARGET_BASE.rstrip("/") + "/databases/landline.php",
        "Accept-Language": "en-US,en;q=0.9",
        "Content-Type": "application/x-www-form-urlencoded",
        "Origin": TARGET_BASE.rstrip("/"),
        "Upgrade-Insecure-Requests": "1",
    }
    url = TARGET_BASE.rstrip("/") + LANDLINE_PATH
    data = {"search_query": query_value}
    resp = session.post(url, headers=headers, data=data, timeout=20)
    resp.raise_for_status()
    return resp.text

def parse_table(html: str):
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", {"class": "api-response"}) or soup.find("table")
    if not table:
        return []
    tbody = table.find("tbody")
    if not tbody:
        return []
    results = []
    for tr in tbody.find_all("tr"):
        cols = [td.get_text(strip=True) for td in tr.find_all("td")]
        if len(cols) >= 4:
            results.append({
                "mobile": cols[0],
                "name": cols[1],
                "cnic": cols[2],
                "address": cols[3],
            })
    return results

def parse_police_table(html: str):
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", {"class": "api-response"}) or soup.find("table")
    if not table:
        return []
    
    results = []
    
    # Try to find table rows
    rows = table.find_all("tr")
    if not rows:
        return []
    
    # Skip header row and process data rows
    for tr in rows[1:]:
        cols = [td.get_text(strip=True) for td in tr.find_all("td")]
        if len(cols) >= 4:
            results.append({
                "cnic": cols[0] if len(cols) > 0 else "",
                "name": cols[1] if len(cols) > 1 else "",
                "father_name": cols[2] if len(cols) > 2 else "",
                "address": cols[3] if len(cols) > 3 else "",
                "crime_details": cols[4] if len(cols) > 4 else "",
                "police_station": cols[5] if len(cols) > 5 else "",
                "status": cols[6] if len(cols) > 6 else "",
            })
        elif len(cols) == 1:
            # Sometimes results might be in different format
            results.append({
                "info": cols[0],
                "cnic": "",
                "name": "",
                "father_name": "",
                "address": "",
                "crime_details": "",
                "police_station": "",
                "status": "",
            })
    
    return results

def parse_landline_table(html: str):
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", {"class": "api-response"}) or soup.find("table")
    if not table:
        return []
    
    results = []
    
    # Try to find table rows
    rows = table.find_all("tr")
    if not rows:
        return []
    
    # Skip header row and process data rows
    for tr in rows[1:]:
        cols = [td.get_text(strip=True) for td in tr.find_all("td")]
        if len(cols) >= 3:
            results.append({
                "number": cols[0] if len(cols) > 0 else "",
                "name": cols[1] if len(cols) > 1 else "",
                "address": cols[2] if len(cols) > 2 else "",
                "area": cols[3] if len(cols) > 3 else "",
                "type": cols[4] if len(cols) > 4 else "",
            })
    
    return results

@app.route('/')
def home():
    return jsonify({
        "message": "Pakistan Database API - Live Mode",
        "version": "1.0",
        "endpoints": {
            "/api/mobile": "Mobile number lookup (GET/POST)",
            "/api/cnic": "CNIC lookup (GET/POST)", 
            "/api/police": "Crime history lookup (GET/POST)",
            "/api/landline": "Landline lookup (GET/POST)",
            "/health": "Health check"
        },
        "copyright": COPYRIGHT_NOTICE,
        "telegram": "@Bj_devs"
    })

@app.route('/health')
def health():
    return jsonify({
        "status": "healthy",
        "service": "Pakistan Database API",
        "copyright": COPYRIGHT_NOTICE
    })

@app.route('/api/mobile', methods=['GET', 'POST'])
def mobile_lookup():
    try:
        if request.method == 'POST':
            data = request.get_json()
            if not data or 'query' not in data:
                return jsonify({"error": "Missing 'query' in JSON body"}), 400
            query = data['query']
        else:
            query = request.args.get('query')
        
        if not query:
            return jsonify({"error": "Missing query parameter"}), 400
        
        normalized = validate_mobile(query)
        
        html = fetch_upstream(normalized)
        results = parse_table(html)
        
        response = {
            "success": True,
            "query": normalized,
            "query_type": "mobile",
            "results_count": len(results),
            "results": results,
            "copyright": COPYRIGHT_NOTICE,
            "credit": "@Bj_devs & ABBAS"
        }
        
        return jsonify(response)
        
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except requests.RequestException as e:
        return jsonify({"error": f"Network error: {str(e)}"}), 500
    except Exception as e:
        return jsonify({"error": f"Server error: {str(e)}"}), 500

@app.route('/api/cnic', methods=['GET', 'POST'])
def cnic_lookup():
    try:
        if request.method == 'POST':
            data = request.get_json()
            if not data or 'query' not in data:
                return jsonify({"error": "Missing 'query' in JSON body"}), 400
            query = data['query']
        else:
            query = request.args.get('query')
        
        if not query:
            return jsonify({"error": "Missing query parameter"}), 400
        
        normalized = validate_cnic(query)
        
        html = fetch_upstream(normalized)
        results = parse_table(html)
        
        response = {
            "success": True,
            "query": normalized,
            "query_type": "cnic",
            "results_count": len(results),
            "results": results,
            "copyright": COPYRIGHT_NOTICE,
            "credit": "@Bj_devs & ABBAS"
        }
        
        return jsonify(response)
        
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except requests.RequestException as e:
        return jsonify({"error": f"Network error: {str(e)}"}), 500
    except Exception as e:
        return jsonify({"error": f"Server error: {str(e)}"}), 500

@app.route('/api/police', methods=['GET', 'POST'])
def police_lookup():
    try:
        if request.method == 'POST':
            data = request.get_json()
            if not data or 'query' not in data:
                return jsonify({"error": "Missing 'query' in JSON body"}), 400
            query = data['query']
        else:
            query = request.args.get('query')
        
        if not query:
            return jsonify({"error": "Missing query parameter"}), 400
        
        qtype, normalized = validate_police_query(query)
        
        html = fetch_police_upstream(normalized)
        results = parse_police_table(html)
        
        response = {
            "success": True,
            "query": normalized,
            "query_type": qtype,
            "results_count": len(results),
            "results": results,
            "copyright": COPYRIGHT_NOTICE,
            "credit": "@Bj_devs & ABBAS"
        }
        
        return jsonify(response)
        
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except requests.RequestException as e:
        return jsonify({"error": f"Network error: {str(e)}"}), 500
    except Exception as e:
        return jsonify({"error": f"Server error: {str(e)}"}), 500

@app.route('/api/landline', methods=['GET', 'POST'])
def landline_lookup():
    try:
        if request.method == 'POST':
            data = request.get_json()
            if not data or 'query' not in data:
                return jsonify({"error": "Missing 'query' in JSON body"}), 400
            query = data['query']
        else:
            query = request.args.get('query')
        
        if not query:
            return jsonify({"error": "Missing query parameter"}), 400
        
        normalized = validate_landline(query)
        
        html = fetch_landline_upstream(normalized)
        results = parse_landline_table(html)
        
        response = {
            "success": True,
            "query": normalized,
            "query_type": "landline",
            "results_count": len(results),
            "results": results,
            "copyright": COPYRIGHT_NOTICE,
            "credit": "@Bj_devs & ABBAS"
        }
        
        return jsonify(response)
        
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except requests.RequestException as e:
        return jsonify({"error": f"Network error: {str(e)}"}), 500
    except Exception as e:
        return jsonify({"error": f"Server error: {str(e)}"}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)