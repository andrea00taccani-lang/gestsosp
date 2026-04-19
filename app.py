from flask import Flask, request, jsonify, render_template_string
import os, psycopg2, datetime

app = Flask(__name__)
DATABASE_URL = os.environ.get("DATABASE_URL")

def get_conn():
    url = DATABASE_URL
    if "sslmode" not in url: url += "?sslmode=require"
    return psycopg2.connect(url)

def init_db():
    conn = get_conn(); cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS sospesi (id SERIAL PRIMARY KEY, cognome TEXT, nome TEXT, prodotto TEXT, quantita INTEGER, note TEXT, pagato BOOLEAN, stato TEXT, updated_at TIMESTAMP)")
    conn.commit(); conn.close()

@app.route("/")
def home():
    init_db()
    return render_template_string(PAGE_HTML)

@app.route("/api/list")
def list_items():
    conn = get_conn(); cur = conn.cursor()
    cur.execute("DELETE FROM sospesi WHERE stato='ritirati' AND updated_at < %s", (datetime.datetime.now() - datetime.timedelta(days=7),))
    cur.execute("SELECT id, cognome, nome, prodotto, quantita, note, pagato, stato FROM sospesi ORDER BY cognome ASC, nome ASC")
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
    # Logica di raggruppamento automatica durante lo spostamento
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
    <meta charset="UTF-8"><title>Gestionale Farmacia</title>
    <style>
        body{font-family:'Segoe UI',sans-serif;background:#f8fafc;margin:0;padding:10px;color:#1e293b}
        .container{max-width:1600px;margin:0 auto}
        .header{background:white;padding:10px 20px;border-radius:10px;display:flex;justify-content:space-between;align-items:center;box-shadow:0 1px 3px rgba(0,0,0,0.1);margin-bottom:10px}
        .entry-box{background:white;padding:15px;border-radius:10px;box-shadow:0 4px 6px rgba(0,0,0,0.05);margin-bottom:15px;border-top:4px solid #16a34a}
        .prod-row{display:grid;grid-template-columns:2fr 80px 1.5fr 130px 40px;gap:8px;margin-bottom:8px;background:#f1f5f9;padding:6px;border-radius:6px}
        input,select{padding:10px;border:1px solid #cbd5e1;border-radius:6px;font-size:14px}
        .btn-main{background:#16a34a;color:white;border:none;padding:14px;border-radius:8px;font-weight:bold;cursor:pointer;width:100%;font-size:16px}
        .btn-ssn{background:#ec4899;color:white;border:none;padding:8px 15px;border-radius:6px;font-weight:bold;cursor:pointer;font-size:13px;width:120px}
        .column{background:#f1f5f9;padding:12px;border-radius:12px;min-height:75vh;border:1px solid #e2e8f0}
        .column h3{text-align:center;font-size:13px;color:#64748b;text-transform:uppercase;margin:0 0 10px 0}
        .client-group{background:white;border-radius:10px;padding:10px;margin-bottom:15px;box-shadow:0 2px 4px rgba(0,0,0,0.05);border:1px solid #e2e8f0}
        .client-name{font-size:18px;font-weight:900;color:#0f172a;text-transform:uppercase;border-bottom:2px solid #f1f5f9;padding-bottom:5px;margin-bottom:10px;display:flex;justify-content:space-between;align-items:center}
        .item-row{padding:8px;border-bottom:1px solid #f8fafc;position:relative}
        .item-row:last-child{border-bottom:none}
        .item-prod{font-weight:700;color:#16a34a;font-size:15px}
        .is-ssn{background:#fff1f2;border-radius:6px;padding:4px}
        .badge-pay{font-size:10px;font-weight:800;padding:3px 8px;border-radius:4px;text-transform:uppercase}
        .p-ok{background:#dcfce7;color:#166534}.p-no{background:#fee2e2;color:#991b1b}
        .actions{display:flex;gap:5px;margin-top:8px}
        .btn-v{flex:1;padding:6px;font-size:11px;font-weight:bold;cursor:pointer;border:1px solid #e2e8f0;background:white;border-radius:4px;color:#475569}
        .btn-v:hover{background:#f8fafc}
    </style>
</head>
<body>
<div class="container">
    <div class="header">
        <h2 style="margin:0;color:#16a34a">🏥 SOSPESI FARMACIA</h2>
        <div id="clock" style="font-weight:bold;color:#64748b"></div>
    </div>
    <div class="entry-box">
        <div style="display:flex;gap:10px;margin-bottom:12px">
            <input id="m_c" placeholder="COGNOME" style="flex:1;font-weight:bold;font-size:16px"><input id="m_n" placeholder="Nome" style="flex:1">
        </div>
        <div id="rows_cont"></div>
        <div style="display:flex;justify-content:space-between;align-items:center;margin-top:10px">
            <button onclick="addRow()" style="background:#f1f5f9;border:1px solid #cbd5e1;padding:8px 15px;border-radius:6px;cursor:pointer;font-weight:600">+ Prodotto</button>
            <button class="btn-ssn" onclick="saveSSN()">💊 RICETTE</button>
        </div>
        <button class="btn-main" onclick="save()" style="margin-top:15px">REGISTRA ORDINE</button>
    </div>
    <input type="text" id="search" placeholder="🔍 Ricerca rapida per cognome o farmaco..." oninput="renderAll()" style="width:100%;padding:14px;border-radius:10px;border:2px solid #e2e8f0;margin-bottom:15px;box-sizing:border-box;font-weight:bold">
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(400px,1fr));gap:15px">
        <div class="column"><h3>📦 DA ORDINARE</h3><div id="col_1"></div></div>
        <div class="column"><h3>🚚 IN FARMACIA</h3><div id="col_2"></div></div>
        <div class="column"><h3>✅ RITIRATI</h3><div id="col_3"></div></div>
    </div>
</div>
<script>
    let data = [];
    function addRow(){
        let d=document.createElement('div');d.className='prod-row';
        d.innerHTML='<input class="pn" placeholder="Farmaco"><input type="number" class="pq" value="1"><input class="nt" placeholder="Note"><select class="pp"><option value="false">DA PAGARE</option><option value="true">PAGATO</option></select><button onclick="this.parentElement.remove()" style="border:none;background:none;color:red;cursor:pointer;font-weight:bold">X</button>';
        document.getElementById('rows_cont').appendChild(d);
    }
    async function load(){ data=await(await fetch('/api/list')).json(); renderAll(); }
    function renderAll(){
        let t=document.getElementById('search').value.toLowerCase();
        let f=data.filter(x=>x.cognome.toLowerCase().includes(t)||x.prodotto.toLowerCase().includes(t));
        draw("col_1",f.filter(x=>x.stato=='ordinati'),"arrivati","ARRIVATO");
        draw("col_2",f.filter(x=>x.stato=='arrivati'),"ritirati","RITIRATO");
        draw("col_3",f.filter(x=>x.stato=='ritirati'),null,null);
    }
    function draw(id,items,next,lbl){
        let h=""; let groups={};
        items.forEach(r=>{ let k=r.cognome+r.nome; if(!groups[k])groups[k]=[]; groups[k].push(r); });
        for(let k in groups){
            let g=groups[k];
            h+=`<div class="client-group"><div class="client-name"><span>${g[0].cognome} ${g[0].nome}</span></div>`;
            g.forEach(r=>{
                let ssn=r.prodotto.includes('RICETTE')?'is-ssn':'';
                h+=`<div class="item-row ${ssn}">
                    <div style="display:flex;justify-content:space-between;align-items:center">
                        <span class="item-prod">${r.quantita}x ${r.prodotto}</span>
                        <span class="badge-pay ${r.pagato?'p-ok':'p-no'}">${r.pagato?'PAGATO':'DA PAGARE'}</span>
                    </div>
                    ${r.note?`<div style="font-size:11px;color:#64748b;margin-top:2px">Note: ${r.note}</div>`:''}
                    <div class="actions">
                        ${next?`<button class="btn-v" onclick="move(${r.id},'${next}')">${lbl}</button>`:''}
                        <button class="btn-v" style="color:#ef4444" onclick="del(${r.id})">ELIMINA</button>
                    </div></div>`;
            });
            h+=`</div>`;
        }
        document.getElementById(id).innerHTML=h;
    }
    async function save(){
        let p=[]; document.querySelectorAll('.prod-row').forEach(r=>{
            let n=r.querySelector('.pn').value; if(n)p.push({prodotto:n,quantita:r.querySelector('.pq').value,note:r.querySelector('.nt').value,pagato:r.querySelector('.pp').value=='true'});
        });
        await fetch('/api/new',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({cognome:document.getElementById('m_c').value,nome:document.getElementById('m_n').value,prodotti:p})});
        reset();
    }
    async function saveSSN(){
        await fetch('/api/new',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({cognome:document.getElementById('m_c').value,nome:document.getElementById('m_n').value,prodotti:[{prodotto:'RICETTE CARTACEE',quantita:1,note:'',pagato:false}]})});
        reset();
    }
    function reset(){document.getElementById('m_c').value="";document.getElementById('m_n').value="";document.getElementById('rows_cont').innerHTML="";addRow();load();}
    async function move(id,stato){await fetch('/api/move',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id,stato})});load();}
    async function del(id){if(confirm("Elimina?")){await fetch('/api/delete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id})});load();}}
    addRow();load();setInterval(load,30000);
    setInterval(()=>{document.getElementById('clock').innerText=new Date().toLocaleTimeString('it-IT')},1000);
</script>
</body>
</html>
"""

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
