"""
SofaScore API Proxy
Proxy server per bypassare le restrizioni Cloudflare di SofaScore.
Deploy su Render come Web Service.
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
import httpx
import asyncio
import random
import time
from typing import Optional

app = FastAPI(
    title="SofaScore API Proxy",
    description="Proxy per accedere ai dati SofaScore senza blocchi Cloudflare",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_URL = "https://www.sofascore.com/api/v1"

# Pool di User-Agent realistici
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.2 Safari/605.1.15",
]

# Rate limiting semplice
last_request_time = 0
MIN_DELAY = 1.5  # secondi tra richieste


async def fetch_sofascore(endpoint: str) -> dict:
    """Fetch dati da SofaScore con headers realistici e rate limiting"""
    global last_request_time

    # Rate limiting
    now = time.time()
    elapsed = now - last_request_time
    if elapsed < MIN_DELAY:
        await asyncio.sleep(MIN_DELAY - elapsed + random.uniform(0.1, 0.5))
    last_request_time = time.time()

    url = f"{BASE_URL}/{endpoint.lstrip('/')}"

    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": "https://www.sofascore.com/",
        "Origin": "https://www.sofascore.com",
        "Cache-Control": "no-cache",
        "Sec-Ch-Ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "X-Requested-With": "XMLHttpRequest",
    }

    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=30.0,
        http2=True,
    ) as client:
        try:
            response = await client.get(url, headers=headers)

            if response.status_code == 403:
                # Riprova con un altro User-Agent
                headers["User-Agent"] = random.choice(USER_AGENTS)
                await asyncio.sleep(2)
                response = await client.get(url, headers=headers)

            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"SofaScore ha risposto con {response.status_code}"
                )

            return response.json()
        except httpx.RequestError as e:
            raise HTTPException(status_code=502, detail=f"Errore di connessione: {str(e)}")


# =========================================================================
#  ENDPOINT: RICERCA
# =========================================================================

@app.get("/")
async def root():
    return {
        "service": "SofaScore API Proxy",
        "version": "1.0.0",
        "endpoints": [
            "/search/players/{query}",
            "/search/teams/{query}",
            "/search/all/{query}",
            "/player/{player_id}",
            "/player/{player_id}/statistics/{tournament_id}/{season_id}",
            "/player/{player_id}/transfer-history",
            "/player/{player_id}/events",
            "/team/{team_id}",
            "/team/{team_id}/players",
            "/tournament/{tournament_id}/seasons",
            "/tournament/{tournament_id}/season/{season_id}/standings",
            "/tournament/{tournament_id}/season/{season_id}/top-players",
        ]
    }


@app.get("/search/all/{query}")
async def search_all(query: str):
    """Cerca giocatori, squadre e tornei"""
    data = await fetch_sofascore(f"search/all?q={query}")
    return data


@app.get("/search/players/{query}")
async def search_players(query: str):
    """Cerca solo giocatori — restituisce formato semplificato"""
    data = await fetch_sofascore(f"search/all?q={query}")
    players = []

    for result in data.get("results", []):
        if result.get("type") == "player":
            entity = result.get("entity", {})
            team = entity.get("team", {})
            country = entity.get("country", {})
            players.append({
                "id": entity.get("id"),
                "name": entity.get("name", ""),
                "shortName": entity.get("shortName", ""),
                "position": entity.get("position", ""),
                "team": team.get("name", ""),
                "teamId": team.get("id"),
                "country": country.get("name", ""),
                "dateOfBirthTimestamp": entity.get("dateOfBirthTimestamp"),
                "imageUrl": f"https://api.sofascore.app/api/v1/player/{entity['id']}/image" if entity.get("id") else None,
            })

    return {"results": players, "count": len(players)}


@app.get("/search/teams/{query}")
async def search_teams(query: str):
    """Cerca solo squadre"""
    data = await fetch_sofascore(f"search/all?q={query}")
    teams = []

    for result in data.get("results", []):
        if result.get("type") == "team":
            entity = result.get("entity", {})
            teams.append({
                "id": entity.get("id"),
                "name": entity.get("name", ""),
                "country": entity.get("country", {}).get("name", ""),
                "sport": entity.get("sport", {}).get("name", ""),
            })

    return {"results": teams, "count": len(teams)}


# =========================================================================
#  ENDPOINT: GIOCATORE
# =========================================================================

@app.get("/player/{player_id}")
async def get_player(player_id: int):
    """Profilo completo del giocatore"""
    return await fetch_sofascore(f"player/{player_id}")


@app.get("/player/{player_id}/statistics/{tournament_id}/{season_id}")
async def get_player_stats(player_id: int, tournament_id: int, season_id: int):
    """Statistiche giocatore per torneo e stagione"""
    return await fetch_sofascore(
        f"player/{player_id}/unique-tournament/{tournament_id}/season/{season_id}/statistics/overall"
    )


@app.get("/player/{player_id}/transfer-history")
async def get_player_transfers(player_id: int):
    """Storico trasferimenti"""
    return await fetch_sofascore(f"player/{player_id}/transfer-history")


@app.get("/player/{player_id}/events")
async def get_player_events(player_id: int, page: int = 0):
    """Ultime partite del giocatore"""
    return await fetch_sofascore(f"player/{player_id}/events/last/{page}")


@app.get("/player/{player_id}/heatmap/{tournament_id}/{season_id}")
async def get_player_heatmap(player_id: int, tournament_id: int, season_id: int):
    """Heatmap del giocatore"""
    return await fetch_sofascore(
        f"player/{player_id}/unique-tournament/{tournament_id}/season/{season_id}/heatmap/overall"
    )


@app.get("/player/{player_id}/characteristics")
async def get_player_characteristics(player_id: int):
    """Caratteristiche/attributi del giocatore"""
    return await fetch_sofascore(f"player/{player_id}/characteristics")


# =========================================================================
#  ENDPOINT: SQUADRA
# =========================================================================

@app.get("/team/{team_id}")
async def get_team(team_id: int):
    """Dettaglio squadra"""
    return await fetch_sofascore(f"team/{team_id}")


@app.get("/team/{team_id}/players")
async def get_team_players(team_id: int):
    """Rosa della squadra"""
    return await fetch_sofascore(f"team/{team_id}/players")


@app.get("/team/{team_id}/statistics/{tournament_id}/{season_id}")
async def get_team_stats(team_id: int, tournament_id: int, season_id: int):
    """Statistiche squadra nel torneo"""
    return await fetch_sofascore(
        f"team/{team_id}/unique-tournament/{tournament_id}/season/{season_id}/statistics/overall"
    )


# =========================================================================
#  ENDPOINT: TORNEO / LEGA
# =========================================================================

@app.get("/tournament/{tournament_id}/seasons")
async def get_tournament_seasons(tournament_id: int):
    """Stagioni disponibili per un torneo"""
    return await fetch_sofascore(f"unique-tournament/{tournament_id}/seasons")


@app.get("/tournament/{tournament_id}/season/{season_id}/standings")
async def get_standings(tournament_id: int, season_id: int):
    """Classifica"""
    return await fetch_sofascore(
        f"unique-tournament/{tournament_id}/season/{season_id}/standings/total"
    )


@app.get("/tournament/{tournament_id}/season/{season_id}/top-players")
async def get_top_players(
    tournament_id: int,
    season_id: int,
    stat: str = "rating",
    limit: int = 100,
    offset: int = 0,
):
    """Top giocatori per statistica"""
    return await fetch_sofascore(
        f"unique-tournament/{tournament_id}/season/{season_id}/statistics"
        f"?limit={limit}&offset={offset}&order=-{stat}&accumulation=total&group=summary&fields={stat}"
    )


# =========================================================================
#  ENDPOINT: PARTITE
# =========================================================================

@app.get("/event/{event_id}")
async def get_event(event_id: int):
    """Dettaglio partita"""
    return await fetch_sofascore(f"event/{event_id}")


@app.get("/event/{event_id}/statistics")
async def get_event_statistics(event_id: int):
    """Statistiche partita"""
    return await fetch_sofascore(f"event/{event_id}/statistics")


@app.get("/event/{event_id}/lineups")
async def get_event_lineups(event_id: int):
    """Formazioni"""
    return await fetch_sofascore(f"event/{event_id}/lineups")


@app.get("/live")
async def get_live_events():
    """Partite live"""
    return await fetch_sofascore("sport/football/events/live")


# =========================================================================
#  ENDPOINT: UTILITY
# =========================================================================

@app.get("/health")
async def health():
    """Health check"""
    return {"status": "ok", "timestamp": time.time()}


@app.get("/test")
async def test():
    """Test di connessione a SofaScore"""
    try:
        data = await fetch_sofascore("sport/football/events/live")
        return {
            "status": "ok",
            "sofascore_reachable": True,
            "live_events": len(data.get("events", [])),
        }
    except Exception as e:
        return {
            "status": "error",
            "sofascore_reachable": False,
            "error": str(e),
        }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
