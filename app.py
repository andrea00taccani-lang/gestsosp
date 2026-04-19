from flask import Flask, request, jsonify, render_template_string
import os, psycopg2, datetime

app = Flask(__name__)
DATABASE_URL = os.environ.get("DATABASE_URL")

def get_conn():
    url = DATABASE_URL
    if "sslmode" not in url: url += "?sslmode=require"
    return psycopg2.connect(url)

def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS sospesi (id SERIAL PRIMARY KEY, cognome TEXT, nome TEXT, prodotto TEXT, quantita INTEGER, note TEXT, pagato BOOLEAN, stato TEXT, updated_at TIMESTAMP)")
    conn.commit()
    conn.close()

@app.route("/")
def home():
    init_db()
    return render_template_string(PAGE_HTML)

@app.route("/api/list")
def list_items():
    conn = get_conn(); cur = conn.cursor()
    cur.execute("DELETE FROM sospesi WHERE stato='ritirati' AND updated_at < %s", (datetime.datetime.now() - datetime.timedelta(days=7),))
    cur.execute("SELECT id, cognome, nome, prodotto, quantita, note, pagato, stato FROM sospesi ORDER BY cognome ASC")
    rows = cur.fetchall()
    conn.commit(); conn.close()
    return jsonify([{"id":r[0],"cognome":r[1],"nome":r[2],"prodotto":r[3],"quantita":r[4],"note":r[5],"pagato":r[6],"stato":r[7]} for r in rows])

@app.route("/api/new", methods=["POST"])
def new():
    data = request.json
    conn = get_conn(); cur = conn.cursor()
    for p in data['prodotti']:
        cur.execute("INSERT INTO sospesi (cognome, nome, prodotto, quantita, note, pagato, stato, updated_at) VALUES (%s,%s,%s,%s,%s,%s,'ordinati',%s)",
            (data['cognome'].upper(), data['nome'], p['prodotto'].upper(), p['quantita'], p['note'], p['pagato'], datetime.datetime.now()))
    conn.commit(); conn.close()
    return "ok"

@app.route("/api/move", methods=["POST"])
def move():
    d = request.json
    conn = get_conn(); cur = conn.cursor()
    cur.execute("SELECT cognome, nome, prodotto, note, pagato, quantita FROM sospesi WHERE id=%s", (d['id'],))
    i = cur.fetchone()
    cur.execute("SELECT id FROM sospesi WHERE cognome=%s AND nome=%s AND prodotto=%s AND note=%s AND pagato=%s AND stato=%s", (i[0],i[1],i[2],i[3],i[4],d['stato']))
    ex = cur.fetchone()
    if ex:
        cur.execute("UPDATE sospesi SET quantita=quantita+%s, updated_at=%s WHERE id=%s", (i[5], datetime.datetime.now(), ex[0]))
        cur.execute("DELETE FROM sospesi WHERE id=%s", (d['id'],))
    else:
        cur.execute("UPDATE sospesi SET stato=%s, updated_at=%s WHERE id=%s", (d['stato'], datetime.datetime.now(), d['id']))
    conn.commit(); conn.close()
    return "ok"

@app.route("/api/split", methods=["POST"])
def split():
    d = request.json
    conn = get_conn(); cur = conn.cursor()
    cur.execute("SELECT cognome, nome, prodotto, note, pagato, quantita FROM sospesi WHERE id=%s", (d['id'],))
    i = cur.fetchone()
    qm = int(d['qty'])
    if qm >= i[5]: return move()
    cur.execute("UPDATE sospesi SET quantita=quantita-%s WHERE id=%s", (qm, d['id']))
    cur.execute("SELECT id FROM sospesi WHERE cognome=%s AND nome=%s AND prodotto=%s AND note=%s AND pagato=%s AND stato=%s", (i[0],i[1],i[2],i[3],i[4],d['next']))
    ex = cur.fetchone()
    if ex: cur.execute("UPDATE sospesi SET quantita=quantita+%s WHERE id=%s", (qm, ex[0]))
    else: cur.execute("INSERT INTO sospesi (cognome, nome, prodotto, note, pagato, quantita, stato, updated_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)", (i[0],i[1],i[2],i[3],i[4],qm,d['next'],datetime.datetime.now()))
    conn.commit(); conn.close()
    return "ok"

@app.route("/api/delete", methods=["POST"])
def delete():
    d = request.json
    conn = get_conn(); cur = conn.cursor()
    cur.execute("DELETE FROM sospesi WHERE id=%s", (d['id'],))
    conn.commit(); conn.close()
    return "ok"

PAGE_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8"><title>Farmacia Gold</title>
    <style>
        body{font-family:sans-serif;background:#f1f5f9;margin:0;padding:10px}
        .card{background:white;padding:12px;border-radius:8px;margin-bottom:10px;box-shadow:0 2px 4px rgba(0,0,0,0.1);border-left:6px solid #94a3b8}
        .card-ssn{background:#ffe5ec;border-left-color:#ff8fab}
        .badge{display:block;padding:8px;border-radius:4px;font-weight:900;text-align:center;margin-bottom:8px;color:white}
        .bg-p{background:#2dc653}.bg-np{background:#e11d48}
        .btn-v{flex:1;padding:6px;font-size:10px;font-weight:bold;cursor:pointer;border:1px solid #ccc;background:white}
        .column{background:#dfe7ef;padding:10px;border-radius:10px;min-height:70vh}
        .prod-row{display:grid;grid-template-columns:2fr 60px 1fr 120px 30px;gap:5px;margin-bottom:5px}
    </style>
</head>
<body>
    <div style="background:white;padding:10px;border-radius:8px;margin-bottom:10px;display:flex;justify-content:space-between">
        <h2 style="margin:0;color:#1a7431">🏥 SOSPESI FARMACIA</h2><b id="clock"></b>
    </div>
    <input type="text" id="search" placeholder="🔍 CERCA COGNOME O FARMACO..." oninput="renderAll()" style="width:100%;padding:12px;margin-bottom:10px;box-sizing:border-box;font-weight:bold">
    <div style="background:white;padding:15px;border-radius:10px;margin-bottom:10px;border-top:4px solid #1a7431">
        <div style="display:flex;gap:10px;margin-bottom:10px">
            <input id="m_c" placeholder="COGNOME" style="flex:1;font-weight:bold"><input id="m_n" placeholder="Nome" style="flex:1">
        </div>
        <div id="rows"></div>
        <button onclick="addRow()">+ AGGIUNGI PRODOTTO</button>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:10px">
            <button onclick="save()" style="background:#1a7431;color:white;padding:10px;font-weight:bold">✅ REGISTRA</button>
            <button onclick="saveSSN()" style="background:#fb6f92;color:white;padding:10px;font-weight:bold">💊 RICETTE SSN</button>
        </div>
    </div>
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(350px,1fr));gap:10px">
        <div class="column"><h3>📦 DA ORDINARE</h3><div id="col_1"></div></div>
        <div class="column"><h3>🚚 IN FARMACIA</h3><div id="col_2"></div></div>
        <div class="column"><h3>✅ RITIRATI</h3><div id="col_3"></div></div>
    </div>
<script>
    let data = [];
    function addRow(){
        let d = document.createElement('div'); d.className='prod-row';
        d.innerHTML='<input class="pn" placeholder="Farmaco"><input type="number" class="pq" value="1"><input class="nt" placeholder="Note"><select class="pp"><option value="false">DA PAGARE</option><option value="true">PAGATO</option></select><button onclick="this.parentElement.remove()">X</button>';
        document.getElementById('rows').appendChild(d);
    }
    async function load(){ data = await (await fetch('/api/list')).json(); renderAll(); }
    function renderAll(){
        let t = document.getElementById('search').value.toLowerCase();
        let f = data.filter(x => x.cognome.toLowerCase().includes(t) || x.prodotto.toLowerCase().includes(t));
        draw("col_1", f.filter(x=>x.stato=='ordinati'), "arrivati", "ARRIVATO");
        draw("col_2", f.filter(x=>x.stato=='arrivati'), "ritirati", "RITIRATO");
        draw("col_3", f.filter(x=>x.stato=='ritirati'), null, null);
    }
    function draw(id, items, next, lbl){
        let h = "";
        items.forEach(r => {
            h += `<div class="card ${r.prodotto.includes('RICETTE')?'card-ssn':''}">
                <div class="badge ${r.pagato?'bg-p':'bg-np'}">${r.pagato?'PAGATO':'DA PAGARE'}</div>
                <b>${r.cognome} ${r.nome}</b><br><i style="color:#1a7431">${r.quantita}x ${r.prodotto}</i>
                <div style="font-size:10px;color:#666">${r.note||''}</div>
                <div style="display:flex;gap:4px;margin-top:8px">
                    ${next?`<button class="btn-v" onclick="move(${r.id},'${next}')">${lbl}</button>${r.quantita>1?`<button class="btn-v" onclick="split(${r.id},${r.quantita},'${next}')">⚖️ PARZIALE</button>`:''}`:''}
                    <button class="btn-v" style="color:red" onclick="del(${r.id})">Elimina</button>
                </div></div>`;
        });
        document.getElementById(id).innerHTML = h;
    }
    async function save(){
        let p = []; document.querySelectorAll('.prod-row').forEach(r=>{
            let n = r.querySelector('.pn').value; if(n) p.push({prodotto:n,quantita:r.querySelector('.pq').value,note:r.querySelector('.nt').value,pagato:r.querySelector('.pp').value=='true'});
        });
        await fetch('/api/new',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({cognome:document.getElementById('m_c').value,nome:document.getElementById('m_n').value,prodotti:p})});
        reset();
    }
    async function saveSSN(){
        await fetch('/api/new',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({cognome:document.getElementById('m_c').value,nome:document.getElementById('m_n').value,prodotti:[{prodotto:'RICETTE CARTACEE',quantita:1,note:'Cartaceo',pagato:false}]})});
        reset();
    }
    function reset(){ document.getElementById('m_c').value="";document.getElementById('m_n').value="";document.getElementById('rows').innerHTML="";addRow();load(); }
    async function move(id,stato){ await fetch('/api/move',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id,stato})}); load(); }
    async function split(id,q,s){ let n=prompt("Quanti pezzi?"); if(n>0&&n<=q) { await fetch('/api/split',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id,qty:n,next:s})}); load(); } }
    async function del(id){ if(confirm("Elimina?")){ await fetch('/api/delete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id})}); load(); } }
    addRow(); load(); setInterval(load,30000);
    setInterval(()=>{document.getElementById('clock').innerText=new Date().toLocaleTimeString('it-IT')},1000);
</script>
</body>
</html>
"""

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
