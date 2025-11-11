# PokerSP - Texas Hold'em demo (Flask)

Progetto minimo per giocare a Texas Hold'em con amici via browser. L'app è pensata per essere deployata facilmente su Render come Web Service.

ATTENZIONE: questo è un prototipo per test in locale o con amici. Lo stato è mantenuto in memoria e il codice non è pronto per un ambiente di produzione (mancano persistenza, gestione completa dei side-pot, sicurezza e concorrenza thread-safe).

## Contenuto del repository
- `app.py` - server Flask + API REST per creare stanza, joinare, inviare azioni e ottenere stato
- `game.py` - logica del gioco (semplificata)
- `templates/index.html` - client web minimal
- `static/app.js` - client JS che polla lo stato e invia azioni
- `requirements.txt` - dipendenze
- `Procfile` - comando di avvio per Gunicorn
- `.gitignore` - aggiunto

## Eseguire in locale
1. Crea un virtualenv e installa dipendenze:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
2. Avvia in locale:
   ```bash
   python app.py
   ```
   Oppure con Gunicorn (come su Render):
   ```bash
   gunicorn app:app --bind 0.0.0.0:5000
   ```
3. Apri `http://localhost:5000` in più browser/device per far partecipare gli amici (ogni giocatore inserisce nome e room id).

## Deploy su Render (passi rapidi)
1. Assicurati che il repo sia su GitHub (branch `main`).
2. Vai su https://render.com e crea un nuovo "Web Service".
3. Connetti Render al repository `aslfdsnrfcrd/pokersp` e seleziona il branch `main`.
4. Scegli il runtime `Python 3.x`.
5. Build command: (Render installa automaticamente dalle dipendenze se `requirements.txt` è presente; lasciarlo vuoto è ok) oppure:
   ```
   pip install -r requirements.txt
   ```
6. Start command: Render utilizzerà il `Procfile` presente. In alternativa usa:
   ```
   gunicorn app:app --bind 0.0.0.0:$PORT
   ```
7. Crea il servizio: Render costruirà l'immagine e pubblicherà l'URL.
8. Apri l'URL pubblico, crea una stanza, condividi il room id con i tuoi amici e giocate.

Note su Render:
- Render setta la variabile d'ambiente `$PORT` automaticamente; il Procfile la usa già.
- Lo stato è in memoria: se il servizio viene riavviato o se effettui scaling su più istanze, le stanze si perderanno o si desincronizzeranno. Per un deploy persistente, valuta l'uso di Redis/Postgres per memorizzare lo stato del gioco.

## Limitazioni e migliorie consigliate
- Gestione completa dei side-pots per multiple all-in.
- Persistenza delle stanze (Redis o DB) per resilienza e scaling.
- Locking / serializzazione delle azioni per rendere thread-safe l'accesso al Game.
- Autenticazione e protezione delle API (token/session).
- UI migliorata (carte grafiche, log delle azioni, evidenziazione dealer/turno).
- Tests automatici per la logica di valutazione delle mani.

## Come posso aiutarti ancora
- Posso riprovare io il push del README sul ramo principale (se mi confermi riprovo).
- Posso creare una `render.yaml` per l'infrastruttura-as-code di Render.
- Posso implementare side-pot, persistenza o migliorare la UI.
