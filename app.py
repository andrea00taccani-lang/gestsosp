from flask import Flask, request, jsonify, render_template_string
import os
import psycopg2
from datetime import datetime, timedelta

app = Flask(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL")

def get_conn():
    return psycopg2.connect(DATABASE_URL)

def init_db():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
            CREATE TABLE IF NOT EXISTS sospesi (
                id SERIAL PRIMARY KEY,
                nome TEXT,
                prodotto TEXT,
                stato TEXT,
                updated_at TIMESTAMP
            )
            """)

def cleanup():
    limit = datetime.now() - timedelta(days=7)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM sospesi WHERE stato='ritirati' AND updated_at < %s", (limit,))

@app.route("/")
def home():
    return PAGE

@app.route("/api/list")
def list_items():
    cleanup()
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM sospesi")
            rows = cur.fetchall()
    return jsonify([{
        "id": r[0],
        "nome": r[1],
        "prodotto": r[2],
        "stato": r[3]
    } for r in rows])

@app.route("/api/new", methods=["POST"])
def new():
    data = request.json
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO sospesi (nome, prodotto, stato, updated_at) VALUES (%s,%s,'ordinati',%s)",
                (data["nome"], data["prodotto"], datetime.now())
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

PAGE = """
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>Gestionale Farmacia</title>
<style>
body{font-family:Arial;background:#f5f5f5;padding:20px}
input{padding:5px;margin:5px}
button{margin-left:5px}
.box{background:white;padding:10px;margin:5px;border-radius:5px}
</style>
</head>
<body>

<h1>Gestionale Sospesi</h1>

<input id="nome" placeholder="Cliente">
<input id="prodotto" placeholder="Prodotto">
<button onclick="add()">Nuovo</button>

<h2>Ordinati</h2>
<div id="ordinati"></div>

<h2>Arrivati</h2>
<div id="arrivati"></div>

<h2>Ritirati</h2>
<div id="ritirati"></div>

<script>

async function load(){
let res = await fetch("/api/list")
let data = await res.json()

render("ordinati",data.filter(x=>x.stato=="ordinati"))
render("arrivati",data.filter(x=>x.stato=="arrivati"))
render("ritirati",data.filter(x=>x.stato=="ritirati"))
}

function render(id,data){
let html=""
for(let r of data){
html+=`
<div class="box">
${r.nome} - ${r.prodotto}
<button onclick="move(${r.id},'arrivati')">Arrivato</button>
<button onclick="move(${r.id},'ritirati')">Ritirato</button>
<button onclick="del(${r.id})">Elimina</button>
</div>`
}
document.getElementById(id).innerHTML=html
}

async function add(){
await fetch("/api/new",{method:"POST",headers:{"Content-Type":"application/json"},
body:JSON.stringify({
nome:document.getElementById("nome").value,
prodotto:document.getElementById("prodotto").value
})})
load()
}

async function move(id,stato){
await fetch("/api/move",{method:"POST",headers:{"Content-Type":"application/json"},
body:JSON.stringify({id,stato})})
load()
}

async function del(id){
await fetch("/api/delete",{method:"POST",headers:{"Content-Type":"application/json"},
body:JSON.stringify({id})})
load()
}

load()

</script>

</body>
</html>
"""

if __name__ == "__main__":
    init_db()
    app.run()
