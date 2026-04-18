from flask import Flask, request, jsonify, render_template_string
import os
import psycopg2
from datetime import datetime, timedelta

app = Flask(__name__)

# Configurazione Database
DATABASE_URL = os.environ.get("DATABASE_URL")

def get_conn():
    # Aggiungiamo sslmode per sicurezza su Render
    if "sslmode" not in DATABASE_URL:
        conn_url = f"{DATABASE_URL}?sslmode=require"
    else:
        conn_url = DATABASE_URL
    return psycopg2.connect(conn_url)

def init_db():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
            CREATE TABLE IF NOT EXISTS sospesi (
                id SERIAL PRIMARY KEY,
                cognome TEXT,
                nome TEXT,
                prodotto TEXT,
                quantita INTEGER DEFAULT 1,
                note TEXT,
                stato TEXT, -- 'ordinati', 'arrivati', 'ritirati'
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)
    print("Database inizializzato correttamente.")

def cleanup_old_records():
    # Elimina i ritirati più vecchi di 7 giorni
    limit = datetime.now() - timedelta(days=7)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM sospesi WHERE stato='ritirati' AND updated_at < %s", (limit,))

@app.route("/")
def home():
    return render_template_string(PAGE_HTML)

@app.route("/api/list")
def list_items():
    cleanup_old_records()
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, cognome, nome, prodotto, quantita, note, stato FROM sospesi ORDER BY updated_at DESC")
            rows = cur.fetchall()
    return jsonify([{
        "id": r[0], "cognome": r[1], "nome": r[2], 
        "prodotto": r[3], "quantita": r[4], "note": r[5], "stato": r[6]
    } for r in rows])

@app.route("/api/new", methods=["POST"])
def new():
    data = request.json
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO sospesi (cognome, nome, prodotto, quantita, note, stato, updated_at) VALUES (%s,%s,%s,%s,%s,'ordinati',%s)",
                (data["cognome"], data["nome"], data["prodotto"], data["quantita"], data["note"], datetime.now())
            )
    return "ok"

@app.route("/api/move", methods=["POST"])
def move():
    data = request.json
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE sospesi SET stato=%s, updated_at=%s WHERE id=%s",
                (data["stato"], datetime.now(), data["id"])
            )
    return "ok"

@app.route("/api/delete", methods=["POST"])
def delete():
    data = request.json
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM sospesi WHERE id=%s", (data["id"],))
    return "ok"

# --- INTERFACCIA PROFESSIONALE ---
PAGE_HTML = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Gestione Sospesi Farmacia</title>
    <link href="https://googleapis.com" rel="stylesheet">
    <style>
        :root { --primary: #2d6a4f; --accent: #40916c; --bg: #f8f9fa; --card: #ffffff; --text: #1b4332; }
        body { font-family: 'Inter', sans-serif; background: var(--bg); color: var(--text); margin: 0; padding: 20px; }
        .container { max-width: 1200px; margin: 0 auto; }
        h1 { text-align: center; color: var(--primary); font-weight: 600; margin-bottom: 30px; border-bottom: 3px solid var(--primary); padding-bottom: 10px; }
        
        /* Form Styling */
        .form-card { background: var(--card); padding: 25px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); margin-bottom: 30px; display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 15px; align-items: end; }
        .form-group { display: flex; flex-direction: column; }
        label { font-size: 12px; font-weight: 600; margin-bottom: 5px; text-transform: uppercase; color: #666; }
        input, textarea { padding: 10px; border: 1px solid #ddd; border-radius: 6px; font-size: 14px; }
        button.btn-add { background: var(--primary); color: white; border: none; padding: 12px; border-radius: 6px; cursor: pointer; font-weight: 600; transition: 0.3s; }
        button.btn-add:hover { background: var(--accent); }

        /* Board Layout */
        .board { display: grid; grid-template-columns: repeat(auto-fit, minmax(350px, 1fr)); gap: 20px; }
        .column { background: #ebf2ed; padding: 15px; border-radius: 12px; min-height: 400px; }
        .column h2 { font-size: 18px; text-align: center; text-transform: uppercase; letter-spacing: 1px; color: var(--primary); margin-top: 0; }
        
        /* Card Sospeso */
        .item-card { background: white; padding: 15px; border-radius: 8px; margin-bottom: 15px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); border-left: 5px solid var(--accent); position: relative; }
        .item-card b { font-size: 16px; display: block; margin-bottom: 5px; color: #000; }
        .item-card p { margin: 3px 0; font-size: 14px; color: #444; }
        .note { font-style: italic; color: #777; font-size: 13px; margin-top: 8px !important; border-top: 1px solid #eee; padding-top: 5px; }
        .actions { margin-top: 15px; display: flex; gap: 8px; flex-wrap: wrap; }
        .btn { border: none; padding: 6px 12px; border-radius: 4px; font-size: 12px; cursor: pointer; font-weight: 600; transition: 0.2s; }
        .btn-move { background: #d8f3dc; color: var(--primary); }
        .btn-move:hover { background: var(--primary); color: white; }
        .btn-del { background: #ffe5ec; color: #fb6f92; margin-left: auto; }
        .badge-qty { background: var(--primary); color: white; padding: 2px 6px; border-radius: 10px; font-size: 11px; float: right; }
    </style>
</head>
<body>

<div class="container">
    <h1>🏥 GESTIONE SOSPESI FARMACIA</h1>

    <div class="form-card">
        <div class="form-group">
            <label>Cognome</label>
            <input type="text" id="cognome" placeholder="es. Rossi">
        </div>
        <div class="form-group">
            <label>Nome</label>
            <input type="text" id="nome" placeholder="es. Mario">
        </div>
        <div class="form-group">
            <label>Prodotto</label>
            <input type="text" id="prodotto" placeholder="es. Tachipirina 1000">
        </div>
        <div class="form-group" style="flex: 0.5;">
            <label>Q.tà</label>
            <input type="number" id="quantita" value="1" min="1">
        </div>
        <div class="form-group">
            <label>Note</label>
            <input type="text" id="note" placeholder="es. Urgente, paga dopo">
        </div>
        <button class="btn-add" onclick="add()">+ NUOVO SOSPESO</button>
    </div>

    <div class="board">
        <div class="column">
            <h2>📦 Ordinati</h2>
            <div id="ordinati"></div>
        </div>
        <div class="column">
            <h2>🚚 Arrivati</h2>
            <div id="arrivati"></div>
        </div>
        <div class="column">
            <h2>✅ Ritirati</h2>
            <div id="ritirati"></div>
        </div>
    </div>
</div>

<script>
async function load(){
    const res = await fetch("/api/list");
    const data = await res.json();
    render("ordinati", data.filter(x => x.stato == "ordinati"), "arrivati", "📦 Segna Arrivato");
    render("arrivati", data.filter(x => x.stato == "arrivati"), "ritirati", "✅ Segna Ritirato");
    render("ritirati", data.filter(x => x.stato == "ritirati"), null, null);
}

function render(containerId, items, nextStato, btnLabel){
    let html = "";
    items.forEach(r => {
        html += `
        <div class="item-card">
            <span class="badge-qty">Q.tà: ${r.quantita}</span>
            <b>${r.cognome.toUpperCase()} ${r.nome}</b>
            <p>💊 ${r.prodotto}</p>
            ${r.note ? `<p class="note">📝 ${r.note}</p>` : ''}
            <div class="actions">
                ${nextStato ? `<button class="btn btn-move" onclick="move(${r.id},'${nextStato}')">${btnLabel}</button>` : ''}
                <button class="btn btn-del" onclick="del(${r.id})">Elimina</button>
            </div>
        </div>`;
    });
    document.getElementById(containerId).innerHTML = html;
}

async function add(){
    const payload = {
        cognome: document.getElementById("cognome").value,
        nome: document.getElementById("nome").value,
        prodotto: document.getElementById("prodotto").value,
        quantita: document.getElementById("quantita").value,
        note: document.getElementById("note").value
    };
    if(!payload.cognome || !payload.prodotto) return alert("Inserisci almeno Cognome e Prodotto!");
    
    await fetch("/api/new", {
        method:"POST", 
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify(payload)
    });
    
    // Pulisci campi
    document.querySelectorAll("input").forEach(i => { if(i.id != 'quantita') i.value = "" });
    load();
}

async function move(id, stato){
    await fetch("/api/move", {
        method:"POST", 
        headers:{"Content-Type":"application/json"},
        body:JSON.stringify({id, stato})
    });
    load();
}

async function del(id){
    if(confirm("Vuoi davvero eliminare questo sospeso?")){
        await fetch("/api/delete", {
            method:"POST", 
            headers:{"Content-Type":"application/json"},
            body:JSON.stringify({id})
        });
        load();
    }
}

setInterval(load, 30000); // Ricarica ogni 30 secondi per aggiornare i dati
load();
</script>
</body>
</html>
"""

if __name__ == "__main__":
    init_db()
    # Porta dinamica per Render
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
