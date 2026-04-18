from flask import Flask, request, jsonify, render_template_string
import os
import psycopg2
from datetime import datetime, timedelta

app = Flask(__name__)

# Configurazione Database
DATABASE_URL = os.environ.get("DATABASE_URL")

def get_conn():
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL non trovata nelle variabili d'ambiente!")
    conn_url = DATABASE_URL
    if "sslmode" not in conn_url:
        conn_url += "?sslmode=require"
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
                pagato BOOLEAN DEFAULT FALSE,
                stato TEXT, 
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)
    print("Database inizializzato.")

def cleanup_old_records():
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
            cur.execute("SELECT id, cognome, nome, prodotto, quantita, note, pagato, stato FROM sospesi ORDER BY updated_at DESC")
            rows = cur.fetchall()
    return jsonify([{
        "id": r[0], "cognome": r[1], "nome": r[2], 
        "prodotto": r[3], "quantita": r[4], "note": r[5], "pagato": r[6], "stato": r[7]
    } for r in rows])

@app.route("/api/new", methods=["POST"])
def new():
    data = request.json
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO sospesi (cognome, nome, prodotto, quantita, note, pagato, stato, updated_at) VALUES (%s,%s,%s,%s,%s,%s,'ordinati',%s)",
                (data["cognome"], data["nome"], data["prodotto"], data["quantita"], data["note"], data["pagato"], datetime.now())
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

# --- INTERFACCIA ---
PAGE_HTML = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Farmacia Sospesi Pro</title>
    <link href="https://googleapis.com" rel="stylesheet">
    <style>
        :root { --primary: #1a7431; --accent: #2dc653; --bg: #f0f2f5; --red: #e63946; }
        body { font-family: 'Inter', sans-serif; background: var(--bg); margin: 0; padding: 20px; }
        .container { max-width: 1300px; margin: 0 auto; }
        h1 { text-align: center; color: var(--primary); }
        
        .form-card { background: white; padding: 20px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); margin-bottom: 25px; display: flex; flex-wrap: wrap; gap: 10px; align-items: flex-end; }
        .form-group { display: flex; flex-direction: column; flex: 1; min-width: 140px; }
        label { font-size: 11px; font-weight: 700; color: #555; margin-bottom: 4px; text-transform: uppercase; }
        input, select { padding: 10px; border: 1px solid #ccd0d5; border-radius: 6px; }
        
        .btn-add { background: var(--primary); color: white; border: none; padding: 11px 20px; border-radius: 6px; font-weight: 600; cursor: pointer; height: 41px; }

        .board { display: grid; grid-template-columns: repeat(auto-fit, minmax(380px, 1fr)); gap: 20px; }
        .column { background: #dfe3e8; padding: 15px; border-radius: 12px; min-height: 500px; }
        .column h2 { font-size: 16px; color: #333; text-align: center; border-bottom: 2px solid #ccc; padding-bottom: 10px; }
        
        .item-card { background: white; padding: 15px; border-radius: 10px; margin-bottom: 12px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); position: relative; border-left: 6px solid #ccc; }
        .status-ordinati { border-left-color: #ffb703; }
        .status-arrivati { border-left-color: #219ebc; }
        .status-ritirati { border-left-color: var(--accent); }
        
        .badge-pagato { background: #d8f3dc; color: #1b4332; padding: 3px 8px; border-radius: 5px; font-size: 10px; font-weight: bold; }
        .badge-nonpagato { background: #ffdada; color: #800000; padding: 3px 8px; border-radius: 5px; font-size: 10px; font-weight: bold; }
        
        .card-header { display: flex; justify-content: space-between; align-items: start; margin-bottom: 8px; }
        .card-title { font-weight: 700; font-size: 16px; margin: 0; }
        .card-prodotto { color: var(--primary); font-weight: 600; margin: 5px 0; }
        .card-note { font-size: 13px; color: #666; background: #f9f9f9; padding: 5px; border-radius: 4px; margin-top: 8px; }
        
        .actions { margin-top: 15px; display: flex; gap: 8px; border-top: 1px solid #eee; padding-top: 10px; }
        .btn-action { flex: 1; border: none; padding: 8px; border-radius: 5px; font-size: 12px; font-weight: 600; cursor: pointer; background: #f0f2f5; color: #444; }
        .btn-action:hover { background: #e4e6e9; }
        .btn-del { color: var(--red); background: #fff1f2; }
    </style>
</head>
<body>

<div class="container">
    <h1>🏥 GESTIONALE SOSPESI v2.0</h1>

    <div class="form-card">
        <div class="form-group"><label>Cognome</label><input type="text" id="cognome"></div>
        <div class="form-group"><label>Nome</label><input type="text" id="nome"></div>
        <div class="form-group"><label>Prodotto</label><input type="text" id="prodotto"></div>
        <div class="form-group" style="flex:0.3"><label>Q.tà</label><input type="number" id="quantita" value="1"></div>
        <div class="form-group"><label>Pagamento</label>
            <select id="pagato">
                <option value="false">DA PAGARE</option>
                <option value="true">GIÀ PAGATO</option>
            </select>
        </div>
        <div class="form-group"><label>Note</label><input type="text" id="note"></div>
        <button class="btn-add" onclick="add()">REGISTRA</button>
    </div>

    <div class="board">
        <div class="column"><h2>📦 ORDINATI</h2><div id="ordinati"></div></div>
        <div class="column"><h2>🚚 ARRIVATI IN FARMACIA</h2><div id="arrivati"></div></div>
        <div class="column"><h2>✅ RITIRATI (Auto-clean 7gg)</h2><div id="ritirati"></div></div>
    </div>
</div>

<script>
async function load(){
    const res = await fetch("/api/list");
    const data = await res.json();
    render("ordinati", data.filter(x => x.stato == "ordinati"), "arrivati", "➔ Arrivato");
    render("arrivati", data.filter(x => x.stato == "arrivati"), "ritirati", "➔ Ritirato");
    render("ritirati", data.filter(x => x.stato == "ritirati"), null, null);
}

function render(containerId, items, nextStato, btnLabel){
    let html = "";
    items.forEach(r => {
        const pagatoBadge = r.pagato ? '<span class="badge-pagato">€ PAGATO</span>' : '<span class="badge-nonpagato">€ DA PAGARE</span>';
        html += `
        <div class="item-card status-${r.stato}">
            <div class="card-header">
                <p class="card-title">${r.cognome.toUpperCase()} ${r.nome}</p>
                ${pagatoBadge}
            </div>
            <p class="card-prodotto">${r.quantita}x ${r.prodotto}</p>
            ${r.note ? `<div class="card-note"><b>Nota:</b> ${r.note}</div>` : ''}
            <div class="actions">
                ${nextStato ? `<button class="btn-action" onclick="move(${r.id},'${nextStato}')">${btnLabel}</button>` : ''}
                <button class="btn-action btn-del" onclick="del(${r.id})">Elimina</button>
            </div>
        </div>`;
    });
    document.getElementById(containerId).innerHTML = html;
}

async function add(){
    const data = {
        cognome: document.getElementById("cognome").value,
        nome: document.getElementById("nome").value,
        prodotto: document.getElementById("prodotto").value,
        quantita: document.getElementById("quantita").value,
        pagato: document.getElementById("pagato").value === "true",
        note: document.getElementById("note").value
    };
    if(!data.cognome || !data.prodotto) return alert("Manca Cognome o Prodotto!");
    await fetch("/api/new", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(data)});
    document.querySelectorAll(".form-card input").forEach(i => { if(i.id!='quantita') i.value="" });
    load();
}

async function move(id, stato){
    await fetch("/api/move", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({id, stato})});
    load();
}

async function del(id){
    if(confirm("Eliminare definitivamente?")) {
        await fetch("/api/delete", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({id})});
        load();
    }
}
load();
setInterval(load, 20000);
</script>
</body>
</html>
