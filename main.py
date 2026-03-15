"""
SofaScore API Proxy v2
Usa curl_cffi per bypassare Cloudflare (simula TLS fingerprint di Chrome)
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from curl_cffi import requests as cffi_requests
import asyncio
import random
import time
from concurrent.futures import ThreadPoolExecutor

app = FastAPI(title="SofaScore API Proxy", version="2.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

BASE_URL = "https://www.sofascore.com/api/v1"
BROWSERS = ["chrome120", "chrome119", "chrome116", "chrome110"]
last_request_time = 0
MIN_DELAY = 2.0
executor = ThreadPoolExecutor(max_workers=3)


def _sync_fetch(endpoint: str) -> dict:
    global last_request_time
    url = f"{BASE_URL}/{endpoint.lstrip('/')}"
    browser = random.choice(BROWSERS)
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://www.sofascore.com/",
        "Origin": "https://www.sofascore.com",
    }
    try:
        r = cffi_requests.get(url, headers=headers, impersonate=browser, timeout=30)
        if r.status_code == 403:
            time.sleep(2)
            b2 = random.choice([b for b in BROWSERS if b != browser])
            r = cffi_requests.get(url, headers=headers, impersonate=b2, timeout=30)
        if r.status_code != 200:
            return {"_error": True, "_status": r.status_code, "_body": r.text[:300]}
        return r.json()
    except Exception as e:
        return {"_error": True, "_status": 0, "_body": str(e)}


async def fetch(endpoint: str) -> dict:
    global last_request_time
    now = time.time()
    if now - last_request_time < MIN_DELAY:
        await asyncio.sleep(MIN_DELAY - (now - last_request_time) + random.uniform(0.2, 0.8))
    last_request_time = time.time()
    result = await asyncio.get_event_loop().run_in_executor(executor, _sync_fetch, endpoint)
    if isinstance(result, dict) and result.get("_error"):
        raise HTTPException(status_code=result.get("_status", 502), detail=result.get("_body", "errore"))
    return result


@app.get("/")
async def root():
    return {"service": "SofaScore Proxy", "version": "2.0.0", "engine": "curl_cffi"}

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/test")
async def test():
    try:
        data = await fetch("sport/football/events/live")
        return {"ok": True, "live_events": len(data.get("events", []))}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.get("/search/all/{query}")
async def search_all(query: str):
    return await fetch(f"search/all?q={query}")

@app.get("/search/players/{query}")
async def search_players(query: str):
    data = await fetch(f"search/all?q={query}")
    players = []
    for r in data.get("results", []):
        if r.get("type") == "player":
            e = r.get("entity", {})
            players.append({
                "id": e.get("id"), "name": e.get("name", ""), "shortName": e.get("shortName", ""),
                "position": e.get("position", ""), "team": (e.get("team") or {}).get("name", ""),
                "teamId": (e.get("team") or {}).get("id"), "country": (e.get("country") or {}).get("name", ""),
                "imageUrl": f"https://api.sofascore.app/api/v1/player/{e['id']}/image" if e.get("id") else None,
            })
    return {"results": players, "count": len(players)}

@app.get("/search/teams/{query}")
async def search_teams(query: str):
    data = await fetch(f"search/all?q={query}")
    teams = []
    for r in data.get("results", []):
        if r.get("type") == "team":
            e = r.get("entity", {})
            teams.append({"id": e.get("id"), "name": e.get("name", ""), "country": (e.get("country") or {}).get("name", "")})
    return {"results": teams, "count": len(teams)}

@app.get("/player/{pid}")
async def get_player(pid: int):
    return await fetch(f"player/{pid}")

@app.get("/player/{pid}/statistics/{tid}/{sid}")
async def get_player_stats(pid: int, tid: int, sid: int):
    return await fetch(f"player/{pid}/unique-tournament/{tid}/season/{sid}/statistics/overall")

@app.get("/player/{pid}/transfer-history")
async def get_player_transfers(pid: int):
    return await fetch(f"player/{pid}/transfer-history")

@app.get("/player/{pid}/events")
async def get_player_events(pid: int, page: int = 0):
    return await fetch(f"player/{pid}/events/last/{page}")

@app.get("/player/{pid}/heatmap/{tid}/{sid}")
async def get_player_heatmap(pid: int, tid: int, sid: int):
    return await fetch(f"player/{pid}/unique-tournament/{tid}/season/{sid}/heatmap/overall")

@app.get("/player/{pid}/characteristics")
async def get_player_chars(pid: int):
    return await fetch(f"player/{pid}/characteristics")

@app.get("/team/{tid}")
async def get_team(tid: int):
    return await fetch(f"team/{tid}")

@app.get("/team/{tid}/players")
async def get_team_players(tid: int):
    return await fetch(f"team/{tid}/players")

@app.get("/team/{tid}/statistics/{toid}/{sid}")
async def get_team_stats(tid: int, toid: int, sid: int):
    return await fetch(f"team/{tid}/unique-tournament/{toid}/season/{sid}/statistics/overall")

@app.get("/tournament/{tid}/seasons")
async def get_seasons(tid: int):
    return await fetch(f"unique-tournament/{tid}/seasons")

@app.get("/tournament/{tid}/season/{sid}/standings")
async def get_standings(tid: int, sid: int):
    return await fetch(f"unique-tournament/{tid}/season/{sid}/standings/total")

@app.get("/tournament/{tid}/season/{sid}/top-players")
async def get_top(tid: int, sid: int, stat: str = "rating", limit: int = 100, offset: int = 0):
    return await fetch(f"unique-tournament/{tid}/season/{sid}/statistics?limit={limit}&offset={offset}&order=-{stat}&accumulation=total&group=summary&fields={stat}")

@app.get("/event/{eid}")
async def get_event(eid: int):
    return await fetch(f"event/{eid}")

@app.get("/event/{eid}/statistics")
async def get_event_stats(eid: int):
    return await fetch(f"event/{eid}/statistics")

@app.get("/event/{eid}/lineups")
async def get_event_lineups(eid: int):
    return await fetch(f"event/{eid}/lineups")

@app.get("/live")
async def get_live():
    return await fetch("sport/football/events/live")

@app.get("/raw/{path:path}")
async def raw(path: str):
    return await fetch(path)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
