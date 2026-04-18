from flask import Flask, request, jsonify, render_template_string
import os
import psycopg2
from datetime import datetime, timedelta

app = Flask(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL")

def get_conn():
    conn_url = DATABASE_URL
    if "sslmode" not in conn_url:
        conn_url += "?sslmode=require"
    return psycopg2.connect(conn_url)

def init_db():
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS sospesi (
                        id SERIAL PRIMARY KEY,
                        cognome TEXT, nome TEXT, prodotto TEXT,
                        quantita INTEGER DEFAULT 1, note TEXT,
                        pagato BOOLEAN DEFAULT FALSE, stato TEXT,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
    except Exception as e: print(f"Errore DB: {e}")

@app.route("/")
def home():
    init_db()
    return render_template_string(PAGE_HTML)

@app.route("/api/list")
def list_items():
    limit = datetime.now() - timedelta(days=7)
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM sospesi WHERE stato='ritirati' AND updated_at < %s", (limit,))
                cur.execute("SELECT id, cognome, nome, prodotto, quantita, note, pagato, stato FROM sospesi ORDER BY cognome ASC, nome ASC")
                rows = cur.fetchall()
        return jsonify([{"id":r[0],"cognome":r[1],"nome":r[2],"prodotto":r[3],"quantita":r[4],"note":r[5],"pagato":r[6],"stato":r[7]} for r in rows])
    except: return jsonify([])

@app.route("/api/new_multiple", methods=["POST"])
def new_multiple():
    data = request.json
    with get_conn() as conn:
        with conn.cursor() as cur:
            for p in data.get("prodotti", []):
                cur.execute("INSERT INTO sospesi (cognome, nome, prodotto, quantita, note, pagato, stato, updated_at) VALUES (%s,%s,%s,%s,%s,%s,'ordinati',%s)",
                    (data["cognome"].strip().upper(), data["nome"].strip(), p['prodotto'].strip().upper(), p['quantita'], p['note'], p['pagato'], datetime.now()))
            conn.commit()
    return "ok"

@app.route("/api/split", methods=["POST"])
def split_item():
    data = request.json
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT cognome, nome, prodotto, quantita, note, pagato, stato FROM sospesi WHERE id=%s", (data["id"],))
            orig = cur.fetchone()
            qty_orig = int(orig[3])
            qty_moved = int(data["qty_moved"])
            if qty_moved >= qty_orig:
                cur.execute("UPDATE sospesi SET stato=%s, updated_at=%s WHERE id=%s", (data["next_stato"], datetime.now(), data["id"]))
            else:
                cur.execute("UPDATE sospesi SET quantita=%s WHERE id=%s", (qty_orig - qty_moved, data["id"]))
                cur.execute("INSERT INTO sospesi (cognome, nome, prodotto, quantita, note, pagato, stato, updated_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                    (orig[0], orig[1], orig[2], qty_moved, orig[4], orig[5], data["next_stato"], datetime.now()))
            conn.commit()
    return "ok"

@app.route("/api/move", methods=["POST"])
def move():
    data = request.json
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE sospesi SET stato=%s, updated_at=%s WHERE id=%s", (data["stato"], datetime.now(), data["id"]))
            conn.commit()
    return "ok"

@app.route("/api/delete", methods=["POST"])
def delete():
    data = request.json
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM sospesi WHERE id=%s", (data["id"],))
            conn.commit()
    return "ok"

PAGE_HTML = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Farmacia Sospesi Pro v2.7</title>
    <style>
        :root { --primary: #1a7431; --bg: #f1f5f9; --red: #e11d48; --accent: #219ebc; }
        body { font-family: 'Segoe UI', system-ui, sans-serif; background: var(--bg); margin: 0; padding: 10px; }
        .container { max-width: 1600px; margin: 0 auto; }
        .header { background: white; padding: 10px 20px; border-radius: 8px; display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
        .search-section { background: #fff; padding: 15px; border-radius: 10px; margin-bottom: 15px; border: 3px solid var(--primary); }
        .search-section input { width: 100%; padding: 12px; font-size: 18px; border: 1px solid #ddd; border-radius: 6px; box-sizing: border-box; font-weight: bold; }
        .entry-box { background: white; padding: 15px; border-radius: 10px; margin-bottom: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); border-top: 4px solid var(--primary); }
        .client-inputs { display: flex; gap: 10px; margin-bottom: 10px; }
        .prod-row { display: grid; grid-template-columns: 2fr 70px 1.5fr 130px; gap: 8px; margin-bottom: 5px; }
        input, select { padding: 8px; border: 1px solid #cbd5e1; border-radius: 5px; }
        .btn-add { background: var(--primary); color: white; border: none; padding: 12px; border-radius: 6px; font-weight: bold; cursor: pointer; width: 100%; margin-top: 10px; }
        .board { display: grid; grid-template-columns: repeat(auto-fit, minmax(350px, 1fr)); gap: 12px; align-items: start; }
        .column { background: #e2e8f0; padding: 12px; border-radius: 10px; min-height: 70vh; }
        .column h2 { text-align: center; font-size: 13px; color: #475569; text-transform: uppercase; margin: 0 0 10px 0; font-weight: 800; border-bottom: 2px solid #cbd5e1; padding-bottom: 5px; }
        .card { background: white; padding: 10px; border-radius: 8px; margin-bottom: 8px; border-left: 5px solid #94a3b8; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
        .card-name { font-weight: 800; font-size: 14px; color: #000; text-transform: uppercase; }
        .card-prod { color: var(--primary); font-weight: 700; margin: 3px 0; }
        .badge { font-size: 9px; padding: 2px 5px; border-radius: 4px; font-weight: 800; }
        .bg-paid { background: #dcfce7; color: #166534; }
        .bg-unpaid { background: #fee2e2; color: #991b1b; }
        .actions { display: flex; gap: 4px; margin-top: 8px; }
        .btn-v { flex: 1; padding: 6px 2px; font-size: 10px; cursor: pointer; border: 1px solid #e2e8f0; border-radius: 4px; background: #fff; font-weight: 700; }
        .btn-split { color: var(--accent); border-color: var(--accent); }
    </style>
</head>
<body>
<div class="container">
    <div class="header">
        <h1 style="margin:0; font-size:18px; color:var(--primary)">🏥 GESTIONE SOSPESI FARMACIA</h1>
        <div id="clock" style="font-weight:bold; color:#64748b"></div>
    </div>

    <div class="search-section">
        <input type="text" id="main_search" placeholder="🔍 CERCA PER COGNOME O PER PRODOTTO..." oninput="filterAndRender()">
    </div>

    <div class="entry-box">
        <div class="client-inputs">
            <input type="text" id="m_cog" placeholder="COGNOME CLIENTE" style="flex:1; font-weight:bold; text-transform: uppercase;">
            <input type="text" id="m_nom" placeholder="Nome" style="flex:1">
        </div>
        <div id="p_rows"></div>
        <button class="btn-add" onclick="save()">REGISTRA NUOVO ORDINE</button>
    </div>

    <div class="board">
        <div class="column" style="border-top:4px solid #f59e0b"><h2>📦 DA ORDINARE</h2><div id="col_ordinati"></div></div>
        <div class="column" style="border-top:4px solid var(--accent)"><h2>🚚 IN FARMACIA</h2><div id="col_arrivati"></div></div>
        <div class="column" style="border-top:4px solid var(--primary)"><h2>✅ RITIRATI</h2><div id="col_ritirati"></div></div>
    </div>
</div>

<script>
let currentData = [];

function createRows() {
    let h = "";
    for(let i=0; i<5; i++) h += `<div class="prod-row"><input type="text" class="p_n" placeholder="Prodotto" style="text-transform: uppercase;"><input type="number" class="p_q" value="1" min="1"><input type="text" class="p_nt" placeholder="Note"><select class="p_p"><option value="false">DA PAGARE</option><option value="true">PAGATO</option></select></div>`;
    document.getElementById("p_rows").innerHTML = h;
}

async function load() {
    const res = await fetch("/api/list");
    currentData = await res.json();
    filterAndRender();
}

function filterAndRender() {
    const term = document.getElementById("main_search").value.toLowerCase();
    
    const filtered = currentData.filter(x => 
        x.cognome.toLowerCase().includes(term) || 
        x.prodotto.toLowerCase().includes(term) ||
        (x.nome && x.nome.toLowerCase().includes(term))
    );
    
    render("col_ordinati", filtered.filter(x=>x.stato=="ordinati"), "arrivati", "ARRIVATO");
    render("col_arrivati", filtered.filter(x=>x.stato=="arrivati"), "ritirati", "RITIRATO");
    render("col_ritirati", filtered.filter(x=>x.stato=="ritirati"), null, null);
}

function render(id, items, next, label) {
    let h = "";
    items.forEach(r => {
        const showSplit = next && r.quantita > 1;
        h += `<div class="card">
            <div class="card-name">${r.cognome} ${r.nome || ''}</div>
            <div class="card-prod">${r.quantita}x ${r.prodotto}</div>
            <div style="font-size:10px; color:#64748b; margin-bottom:5px">${r.note || ''}</div>
            <span class="badge ${r.pagato?'bg-paid':'bg-unpaid'}">${r.pagato?'PAGATO':'DA PAGARE'}</span>
            <div class="actions">
                ${next ? `<button class="btn-v" onclick="move(${r.id},'${next}')">TUTTO ${label}</button>` : ''}
                ${showSplit ? `<button class="btn-v btn-split" onclick="split(${r.id},${r.quantita},'${next}')">⚖️ PARZIALE</button>` : ''}
                <button class="btn-v" style="color:var(--red)" onclick="del(${r.id})">ELIMINA</button>
            </div>
        </div>`;
    });
    document.getElementById(id).innerHTML = h;
}

async function split(id, currentQty, nextStato) {
    let n = prompt(`Quanti pezzi su ${currentQty} sono ${nextStato == 'arrivati' ? 'ARRIVATI' : 'RITIRATI'}?`);
    if(!n || n <= 0) return;
    if(parseInt(n) >= currentQty) return move(id, nextStato);
    await fetch("/api/split", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({id, qty_moved:n, next_stato:nextStato})});
    load();
}

async function save() {
    const prodotti = [];
    document.querySelectorAll(".prod-row").forEach(r => {
        let n = r.querySelector(".p_n").value;
        if(n) prodotti.push({prodotto:n.trim(), quantita:r.querySelector(".p_q").value, note:r.querySelector(".p_nt").value, pagato:r.querySelector(".p_p").value=="true"});
    });
    const cog = document.getElementById("m_cog").value;
    if(!cog || prodotti.length==0) return alert("Cognome e almeno un prodotto!");
    await fetch("/api/new_multiple", {
        method:"POST", 
        headers:{"Content-Type":"application/json"}, 
        body:JSON.stringify({cognome:cog, nome:document.getElementById("m_nom").value, prodotti})
    });
    document.getElementById("m_cog").value=""; 
    document.getElementById("m_nom").value=""; 
    createRows(); 
    load();
}

async function move(id, stato) {
    await fetch("/api/move", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({id, stato})});
    load();
}

async function del(id) { if(confirm("Eliminare definitivamente?")) { await fetch("/api/delete", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({id})}); load(); } }

createRows(); 
load();
setInterval(load, 30000);
setInterval(() => { document.getElementById("clock").innerText = new Date().toLocaleTimeString('it-IT'); }, 1000);
</script>
</body>
</html>
