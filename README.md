# SofaScore API Proxy

Proxy server per accedere ai dati SofaScore senza blocchi Cloudflare.
Da deployare su Render (o qualsiasi hosting Docker).

## Deploy su Render

1. Fork/carica questo repo su GitHub
2. Su Render → New Web Service → collega il repo
3. Language: Docker
4. Instance: Free
5. Deploy

## Endpoint principali

- `GET /search/players/{nome}` — Cerca giocatori
- `GET /player/{id}` — Profilo giocatore
- `GET /player/{id}/statistics/{tournament_id}/{season_id}` — Statistiche
- `GET /player/{id}/transfer-history` — Trasferimenti
- `GET /team/{id}/players` — Rosa squadra
- `GET /tournament/{id}/seasons` — Stagioni disponibili
- `GET /live` — Partite live

## ID Tornei Italiani

| Lega | ID |
|------|-----|
| Serie A | 23 |
| Serie B | 53 |
| Serie C/A | 421 |
| Serie C/B | 422 |
| Serie C/C | 423 |
| Coppa Italia | 328 |
