from flask import Flask, request, jsonify, render_template_string
import os, psycopg2, datetime

app = Flask(__name__)
DB = os.environ.get("DATABASE_URL")

def get_c():
    u = DB
    if "sslmode" not in u: u += "?sslmode=require"
    return psycopg2.connect(u)

@app.route("/")
def h():
    c=get_c();cur=c.cursor();cur.execute("CREATE TABLE IF NOT EXISTS sospesi (id SERIAL PRIMARY KEY, cognome TEXT, nome TEXT, prodotto TEXT, quantita INTEGER, note TEXT, pagato BOOLEAN, stato TEXT, updated_at TIMESTAMP)");c.commit();c.close()
    return render_template_string(PAGE_HTML)

@app.route("/api/list")
def ls():
    c=get_c();cur=c.cursor();cur.execute("DELETE FROM sospesi WHERE stato='ritirati' AND updated_at < %s", (datetime.datetime.now()-datetime.timedelta(days=7),))
    cur.execute("SELECT id,cognome,nome,prodotto,quantita,note,pagato,stato FROM sospesi ORDER BY cognome ASC");r=cur.fetchall();c.close()
    return jsonify([{"id":x,"cognome":x,"nome":x,"prodotto":x,"quantita":x,"note":x,"pagato":x,"stato":x} for x in r])

@app.route("/api/new", methods=["POST"])
def nw():
    d=request.json;c=get_c();cur=c.cursor()
    for p in d['prodotti']: cur.execute("INSERT INTO sospesi (cognome,nome,prodotto,quantita,note,pagato,stato,updated_at) VALUES (%s,%s,%s,%s,%s,%s,'ordinati',%s)",(d['cognome'].upper(),d['nome'],p['prodotto'].upper(),p['quantita'],p['note'],p['pagato'],datetime.datetime.now()))
    c.commit();c.close();return "ok"

@app.route("/api/move", methods=["POST"])
def mv():
    d=request.json;c=get_c();cur=c.cursor();cur.execute("UPDATE sospesi SET stato=%s,updated_at=%s WHERE id=%s",(d['stato'],datetime.datetime.now(),d['id']));c.commit();c.close();return "ok"

@app.route("/api/delete", methods=["POST"])
def dl():
    d=request.json;c=get_c();cur=c.cursor();cur.execute("DELETE FROM sospesi WHERE id=%s",(d['id'],));c.commit();c.close();return "ok"

# LA GRAFICA (PAGE_HTML) INIZIA QUI
PAGE_HTML = """
<!DOCTYPE html><html><head><meta charset="UTF-8"><style>
body{font-family:sans-serif;background:#f8fafc;margin:0;padding:10px}
.box{background:white;padding:15px;border-radius:10px;margin-bottom:15px;box-shadow:0 2px 5px rgba(0,0,0,0.1);border-top:4px solid #16a34a}
.row{display:grid;grid-template-columns:2fr 80px 1.5fr 130px 40px;gap:8px;margin-bottom:8px;background:#f1f5f9;padding:6px;border-radius:6px}
input,select{padding:10px;border:1px solid #ccc;border-radius:6px}
.btn-m{background:#16a34a;color:white;border:none;padding:15px;border-radius:8px;font-weight:bold;width:100%;cursor:pointer}
.btn-r{background:#ec4899;color:white;border:none;padding:8px;border-radius:6px;font-weight:bold;cursor:pointer}
.col{background:#f1f5f9;padding:10px;border-radius:10px;min-height:70vh}
.group{background:white;border-radius:8px;padding:10px;margin-bottom:10px;border:1px solid #ddd}
.name{font-size:18px;font-weight:900;text-transform:uppercase;border-bottom:2px solid #eee;margin-bottom:8px}
.item{padding:5px;border-bottom:1px solid #eee;margin-bottom:5px}.ssn{background:#fff1f2}
.pay{font-size:12px;font-weight:800;padding:5px 10px;border-radius:6px;float:right}
.ok{background:#dcfce7;color:#166534}.no{background:#fee2e2;color:#991b1b}
.btn-v{padding:8px;font-size:11px;font-weight:bold;cursor:pointer;border:1px solid #ccc;background:white;border-radius:4px;margin-right:5px}
</style></head><body>
<div style="display:flex;justify-content:space-between;background:white;padding:10px;border-radius:8px;margin-bottom:10px">
<h2 style="margin:0;color:#16a34a">🏥 SOSPESI</h2><b id="clock"></b></div>
<div class="box"><div style="display:flex;gap:10px;margin-bottom:10px"><input id="mc" placeholder="COGNOME" style="flex:1;font-weight:bold"><input id="mn" placeholder="Nome" style="flex:1"></div>
<div id="rc"></div><button onclick="ar()">+ Prodotto</button> <button class="btn-r" onclick="sr()">💊 RICETTE</button>
<button class="btn-m" style="margin-top:10px" onclick="sv()">REGISTRA ORDINE</button></div>
<input id="sh" placeholder="🔍 Cerca..." oninput="ld()" style="width:100%;padding:12px;border-radius:8px;margin-bottom:10px;box-sizing:border-box">
<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(350px,1fr));gap:15px">
<div class="col"><h3>📦 ORDINATI</h3><div id="c1"></div></div><div class="col"><h3>🚚 IN FARMACIA</h3><div id="c2"></div></div><div class="col"><h3>✅ RITIRATI</h3><div id="c3"></div></div></div>
<script>
let dt=[]; function ar(){let d=document.createElement('div');d.className='row';d.innerHTML='<input class="pn" placeholder="Farmaco"><input type="number" class="pq" value="1"><input class="nt" placeholder="Note"><select class="pp"><option value="false">DA PAGARE</option><option value="true">PAGATO</option></select><button onclick="this.parentElement.remove()">X</button>';document.getElementById('rc').appendChild(d)}
async function ld(){dt=await(await fetch('/api/list')).json();dr()}
function dr(){
let t=document.getElementById('sh').value.toLowerCase();let f=dt.filter(x=>x.cognome.toLowerCase().includes(t)||x.prodotto.toLowerCase().includes(t));
w("c1",f.filter(x=>x.stato=='ordinati'),"arrivati","ARRIVATO");w("c2",f.filter(x=>x.stato=='arrivati'),"ritirati","RITIRATO");w("c3",f.filter(x=>x.stato=='ritirati'),null,null)}
function w(id,it,nx,lb){
let h="";let g={};it.forEach(r=>{let k=r.cognome+r.nome;if(!g[k])g[k]=[];g[k].push(r)});
for(let k in g){h+=`<div class="group"><div class="name">${g[k][0].cognome} ${g[k][0].nome}</div>`;g[k].forEach(r=>{
let s=r.prodotto.includes('RICETTE')?'ssn':'';let q=r.prodotto.includes('RICETTE')?'':r.quantita+'x ';
h+=`<div class="item ${s}"><span class="pay ${r.pagato?'ok':'no'}">${r.pagato?'PAGATO':'DA PAGARE'}</span>
<b style="color:#16a34a">${q}${r.prodotto}</b><br><small>${r.note||''}</small><br>
${nx?`<button class="btn-v" onclick="mv(${r.id},'${nx}')">${lb}</button>`:''}<button class="btn-v" style="color:red" onclick="dl(${r.id})">ELIMINA</button></div>`});h+=`</div>`}document.getElementById(id).innerHTML=h}
async function sv(){let p=[];document.querySelectorAll('.row').forEach(r=>{let n=r.querySelector('.pn').value;if(n)p.push({prodotto:n,quantita:r.querySelector('.pq').value,note:r.querySelector('.nt').value,pagato:r.querySelector('.pp').value=='true'})});await fetch('/api/new',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({cognome:document.getElementById('mc').value,nome:document.getElementById('mn').value,prodotti:p})});rs()}
async function sr(){await fetch('/api/new',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({cognome:document.getElementById('mc').value,nome:document.getElementById('mn').value,prodotti:[{prodotto:'RICETTE CARTACEE',quantita:1,note:'',pagato:false}]})});rs()}
function rs(){document.getElementById('mc').value="";document.getElementById('mn').value="";document.getElementById('rc').innerHTML="";ar();ld()}
async function mv(id,stato){await fetch('/api/move',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id,stato})});ld()}
async function dl(id){if(confirm("Elimina?")){await fetch('/api/delete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id})});ld()}}
ar();ld();setInterval(ld,30000);setInterval(()=>{document.getElementById('clock').innerText=new Date().toLocaleTimeString('it-IT')},1000);
</script></body></html>
"""

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
