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
    conn = None
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sospesi (
                id SERIAL PRIMARY KEY,
                cognome TEXT NOT NULL,
                nome TEXT,
                prodotto TEXT NOT NULL,
                quantita INTEGER DEFAULT 1,
                note TEXT,
                pagato BOOLEAN DEFAULT FALSE,
                stato TEXT DEFAULT 'ordinati',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()
    except Exception as e: print(f"DB Error: {e}")
    finally:
        if conn: conn.close()

@app.route("/")
def home():
    init_db()
    return render_template_string(PAGE_HTML)

@app.route("/api/list")
def list_items():
    conn = None
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("DELETE FROM sospesi WHERE stato='ritirati' AND updated_at < %s", (datetime.now() - timedelta(days=7),))
        cur.execute("SELECT id, cognome, nome, prodotto, quantita, note, pagato, stato FROM sospesi ORDER BY cognome ASC, nome ASC")
        rows = cur.fetchall()
        return jsonify([{"id":r[0],"cognome":r[1],"nome":r[2],"prodotto":r[3],"quantita":r[4],"note":r[5],"pagato":r[6],"stato":r[7]} for r in rows])
    except: return jsonify([])
    finally:
        if conn: conn.close()

@app.route("/api/new_multiple", methods=["POST"])
def new_multiple():
    data = request.json
    conn = get_conn()
    cur = conn.cursor()
    for p in data.get("prodotti", []):
        cur.execute("INSERT INTO sospesi (cognome, nome, prodotto, quantita, note, pagato, stato, updated_at) VALUES (%s,%s,%s,%s,%s,%s,'ordinati',%s)",
            (data["cognome"].upper(), data["nome"], p['prodotto'].upper(), p.get('quantita', 1), p.get('note', ''), p.get('pagato', False), datetime.now()))
    conn.commit()
    conn.close()
    return "ok"

@app.route("/api/move", methods=["POST"])
def move():
    data = request.json # id, stato
    conn = get_conn()
    cur = conn.cursor()
    # 1. Recupero dati dell'oggetto da muovere
    cur.execute("SELECT cognome, nome, prodotto, quantita, note, pagato FROM sospesi WHERE id=%s", (data["id"],))
    item = cur.fetchone()
    if item:
        # 2. Controllo se esiste già un oggetto identico nello stato di destinazione
        cur.execute("SELECT id, quantita FROM sospesi WHERE cognome=%s AND nome=%s AND prodotto=%s AND note=%s AND pagato=%s AND stato=%s",
                    (item[0], item[1], item[2], item[4], item[5], data["stato"]))
        exists = cur.fetchone()
        if exists:
            # 3. Unisco le quantità e cancello il vecchio
            cur.execute("UPDATE sospesi SET quantita=quantita+%s, updated_at=%s WHERE id=%s", (item[3], datetime.now(), exists[0]))
            cur.execute("DELETE FROM sospesi WHERE id=%s", (data["id"],))
        else:
            # 4. Spostamento normale
            cur.execute("UPDATE sospesi SET stato=%s, updated_at=%s WHERE id=%s", (data["stato"], datetime.now(), data["id"]))
    conn.commit()
    conn.close()
    return "ok"

@app.route("/api/split", methods=["POST"])
def split_item():
    data = request.json # id, qty_moved, next_stato
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT cognome, nome, prodotto, quantita, note, pagato FROM sospesi WHERE id=%s", (data["id"],))
    orig = cur.fetchone()
    qty_orig = int(orig[3])
    qty_moved = int(data["qty_moved"])
    
    if qty_moved >= qty_orig:
        # Se sposto tutto, uso la logica del move (che raggruppa)
        conn.close()
        return move()
    
    # Sottraggo dall'originale
    cur.execute("UPDATE sospesi SET quantita=quantita-%s WHERE id=%s", (qty_moved, data["id"]))
    
    # Verifico se posso raggruppare nella destinazione
    cur.execute("SELECT id FROM sospesi WHERE cognome=%s AND nome=%s AND prodotto=%s AND note=%s AND pagato=%s AND stato=%s",
                (orig[0], orig[1], orig[2], orig[4], orig[5], data["next_stato"]))
    exists = cur.fetchone()
    if exists:
        cur.execute("UPDATE sospesi SET quantita=quantita+%s, updated_at=%s WHERE id=%s", (qty_moved, datetime.now(), exists[0]))
    else:
        cur.execute("INSERT INTO sospesi (cognome, nome, prodotto, quantita, note, pagato, stato, updated_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            (orig[0], orig[1], orig[2], qty_moved, orig[4], orig[5], data["next_stato"], datetime.now()))
    
    conn.commit()
    conn.close()
    return "ok"

@app.route("/api/delete", methods=["POST"])
def delete():
    data = request.json
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM sospesi WHERE id=%s", (data["id"],))
    conn.commit()
    conn.close()
    return "ok"

PAGE_HTML = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Farmacia Sospesi v3.0 Gold</title>
    <style>
        :root { --primary: #1a7431; --bg: #f1f5f9; --red: #e11d48; --accent: #219ebc; --pink-ssn: #ffe5ec; }
        body { font-family: sans-serif; background: var(--bg); margin: 0; padding: 10px; }
        .container { max-width: 1600px; margin: 0 auto; }
        .header { background: white; padding: 10px 20px; border-radius: 8px; display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .search-section { background: #fff; padding: 12px; border-radius: 10px; margin-bottom: 15px; border: 3px solid var(--primary); }
        .search-section input { width: 100%; padding: 12px; font-size: 18px; border: none; font-weight: bold; outline: none; }
        .entry-box { background: white; padding: 15px; border-radius: 10px; margin-bottom: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); border-top: 4px solid var(--primary); }
        .client-inputs { display: flex; gap: 10px; margin-bottom: 10px; }
        .prod-row { display: grid; grid-template-columns: 2fr 80px 1.5fr 150px 40px; gap: 8px; margin-bottom: 8px; background: #f8fafc; padding: 5px; border-radius: 5px; }
        input, select { padding: 10px; border: 1px solid #ccc; border-radius: 5px; font-size: 14px; }
        .btn-plus { background: #e2e8f0; border: 1px solid #cbd5e1; padding: 8px 15px; border-radius: 5px; cursor: pointer; font-weight: bold; margin-bottom: 15px; }
        .btn-save { background: var(--primary); color: white; border: none; padding: 15px; border-radius: 8px; font-weight: bold; cursor: pointer; width: 100%; font-size: 18px; }
        .btn-ricette { background: #fb6f92; color: white; border: none; padding: 15px; border-radius: 8px; font-weight: bold; cursor: pointer; width: 100%; font-size: 18px; }
        .board { display: grid; grid-template-columns: repeat(auto-fit, minmax(380px, 1fr)); gap: 15px; }
        .column { background: #dfe7ef; padding: 15px; border-radius: 12px; min-height: 80vh; }
        .column h2 { text-align: center; color: #475569; text-transform: uppercase; font-size: 14px; margin-bottom: 15px; border-bottom: 2px solid #cbd5e1; padding-bottom: 10px; }
        .card { background: white; padding: 15px; border-radius: 10px; margin-bottom: 12px; border-left: 6px solid #94a3b8; box-shadow: 0 3px 6px rgba(0,0,0,0.1); position: relative; }
        .card-ssn { background: var(--pink-ssn); border-left-color: #ff8fab; }
        .card-name { font-weight: 900; font-size: 16px; color: #1e293b; text-transform: uppercase; margin-bottom: 5px; }
        .card-prod { color: #1a7431; font-weight: 700; font-size: 15px; margin-bottom: 5px; }
        .card-note { font-size: 12px; color: #64748b; background: rgba(0,0,0,0.03); padding: 5px; border-radius: 4px; margin: 5px 0; font-style: italic; }
        .badge-big { display: block; text-align: center; padding: 8px; border-radius: 6px; font-weight: 900; font-size: 12px; margin-bottom: 10px; letter-spacing: 1px; }
        .bg-paid { background: #2dc653; color: white; }
        .bg-unpaid { background: var(--red); color: white; }
        .actions { display: flex; gap: 6px; margin-top: 10px; }
        .btn-v { flex: 1; padding: 8px 4px; font-size: 11px; cursor: pointer; border: 1px solid #cbd5e1; border-radius: 5px; background: white; font-weight: bold; }
        .btn-v:hover { background: #f8fafc; }
    </style>
</head>
<body>
<div class="container">
    <div class="header"><h1>🏥 GESTIONALE SOSPESI v3.0</h1><div id="clock" style="font-weight:bold; font-size:18px"></div></div>
    <div class="search-section"><input type="text" id="main_search" placeholder="🔍 CERCA COGNOME O FARMACO..." oninput="filterAndRender()"></div>
    <div class="entry-box">
        <div class="client-inputs"><input type="text" id="m_cog" placeholder="COGNOME CLIENTE" style="flex:1; font-weight:bold; font-size:18px"><input type="text" id="m_nom" placeholder="Nome" style="flex:1"></div>
        <div id="p_rows"></div>
        <button class="btn-plus" onclick="addRow()">+ AGGIUNGI ALTRO PRODOTTO</button>
        <div style="display:grid; grid-template-columns: 1fr 1fr; gap:15px;">
            <button class="btn-save" onclick="save()">✅ REGISTRA PRODOTTI</button>
            <button class="btn-ricette" onclick="saveRicette()">💊 AGGIUNGI RICETTE (SSN)</button>
        </div>
    </div>
    <div class="board">
        <div class="column"><h2>📦 DA ORDINARE</h2><div id="col_ordinati"></div></div>
        <div class="column"><h2>🚚 IN FARMACIA</h2><div id="col_arrivati"></div></div>
        <div class="column"><h2>✅ RITIRATI</h2><div id="col_ritirati"></div></div>
    </div>
</div>
<script>
let currentData = [];
function addRow() {
    const div = document.createElement('div');
    div.className = 'prod-row';
    div.innerHTML = `<input type="text" class="p_n" placeholder="Nome Farmaco"><input type="number" class="p_q" value="1" min="1"><input type="text" class="p_nt" placeholder="Note (es. Frigo)"><select class="p_p"><option value="false">DA PAGARE</option><option value="true">PAGATO</option></select><button onclick="this.parentElement.remove()" style="color:red; border:none; background:none; cursor:pointer; font-weight:bold; font-size:18px">×</button>`;
    document.getElementById("p_rows").appendChild(div);
}
async function load() {
    const res = await fetch("/api/list");
    currentData = await res.json();
    filterAndRender();
}
function filterAndRender() {
    const t = document.getElementById("main_search").value.toLowerCase();
    const f = currentData.filter(x => x.cognome.toLowerCase().includes(t) || x.prodotto.toLowerCase().includes(t));
    render("col_ordinati", f.filter(x=>x.stato=="ordinati"), "arrivati", "ARRIVATO");
    render("col_arrivati", f.filter(x=>x.stato=="arrivati"), "ritirati", "RITIRATO");
    render("col_ritirati", f.filter(x=>x.stato=="ritirati"), null, null);
}
function render(id, items, next, label) {
    let h = "";
    items.forEach(r => {
        const isSSN = r.prodotto.includes("RICETTE");
        h += `<div class="card ${isSSN ? 'card-ssn' : ''}">
            <span class="badge-big ${r.pagato?'bg-paid':'bg-unpaid'}">${r.pagato?'€ PAGATO':'€ DA PAGARE'}</span>
            <div class="card-name">${r.cognome} ${r.nome || ''}</div>
            <div class="card-prod">${r.quantita}x ${r.prodotto}</div>
            ${r.note ? `<div class="card-note">Note: ${r.note}</div>` : ''}
            <div class="actions">
                ${next ? `<button class="btn-v" onclick="move(${r.id},'${next}')">TUTTO ${label}</button>${r.quantita>1 ? `<button class="btn-v" style="color:var(--accent)" onclick="split(${r.id},${r.quantita},'${next}')">⚖️ PARZIALE</button>` : ''}` : ''}
                <button class="btn-v" style="color:var(--red)" onclick="del(${r.id})">ELIMINA</button>
            </div>
        </div>`;
    });
    document.getElementById(id).innerHTML = h;
}
async function save() {
    const prodotti = [];
    document.querySelectorAll(".prod-row").forEach(r => {
        let n = r.querySelector(".p_n").value;
        if(n) prodotti.push({prodotto:n.toUpperCase(), quantita:r.querySelector(".p_q").value, note:r.querySelector(".p_nt").value, pagato:r.querySelector(".p_p").value=="true"});
    });
    const cog = document.getElementById("m_cog").value;
    if(!cog || prodotti.length==0) return alert("Inserisci Cognome e Prodotto!");
    await fetch("/api/new_multiple", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({cognome:cog, nome:document.getElementById("m_nom").value, prodotti})});
    resetForm();
}
async function saveRicette() {
    const cog = document.getElementById("m_cog").value;
    if(!cog) return alert("Inserisci Cognome!");
    const prodotti = [{prodotto: "RICETTE CARTACEE", quantita: 1, note: "Cartaceo SSN", pagato: false}];
    await fetch("/api/new_multiple", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({cognome:cog, nome:document.getElementById("m_nom").value, prodotti})});
    resetForm();
}
function resetForm() {
    document.getElementById("m_cog").value=""; document.getElementById("m_nom").value="";
    document.getElementById("p_rows").innerHTML = ""; addRow(); load();
}
async function move(id, stato) { await fetch("/api/move", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({id, stato})}); load(); }
async function split(id, q, s) { 
    let n = prompt("Quanti pezzi?"); 
    if(n>0 && n<=q) { await fetch("/api/split", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({id, qty_moved:n, next_stato:s})}); load(); }
}
async function del(id) { if(confirm("Eliminare?")) { await fetch("/api/delete", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({id})}); load(); } }
addRow(); load();
setInterval(load, 20000);
setInterval(() => { document.getElementById("clock").innerText = new Date().toLocaleTimeString('it-IT'); }, 1000);
</script>
</body>
</html>
