from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from cryptography.fernet import Fernet
import os, json
import requests
from flask_cors import CORS, cross_origin  # ✅ IMPORTA OS DOIS!
from datetime import datetime, timedelta

app = Flask(__name__)
CORS(app)  # ✅ Habilita CORS para todas as rotas
app.secret_key = 'sua_chave_secreta'

# Substitua por sua token real de produção
ACCESS_TOKEN = "APP_USR-5730059700205068-072418-319a31fb7432463bf92d9a95467b7bb5-103547974"

# Geração da chave simétrica para criptografia
with open("chave.key", "rb") as f:
    chave_criptografia = f.read()
fernet = Fernet(chave_criptografia)


PASTA_LICENCAS = 'licencas'
os.makedirs(PASTA_LICENCAS, exist_ok=True)

# Usuário e senha fixos
USUARIO = 'admin'
SENHA = '1234'



def gerar_licenca_auto(dados):
    json_str = json.dumps(dados)
    licenca_criptografada = fernet.encrypt(json_str.encode())

    nome_arquivo = f"{dados['id_maquina']}.lic"
    with open(os.path.join(PASTA_LICENCAS, nome_arquivo), 'wb') as f:
        f.write(licenca_criptografada)

    # Salva histórico
    historico = []
    if os.path.exists('historico_licencas.json'):
        with open('historico_licencas.json', 'r') as f:
            historico = json.load(f)

    dados['criado_em'] = datetime.now().isoformat()
    historico.append(dados)

    with open('historico_licencas.json', 'w') as f:
        json.dump(historico, f, indent=4, ensure_ascii=False)

    print(f"✅ Licença automática gerada para {dados['cliente']} ({dados['id_maquina']})")


@app.route('/')
def index():
    if not session.get('logado'):
        return redirect(url_for('login'))
    return redirect(url_for('painel'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form['usuario'] == USUARIO and request.form['senha'] == SENHA:
            session['logado'] = True
            return redirect(url_for('gerar_licenca'))
        return "Login inválido"
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/gerar', methods=['GET', 'POST'])
def gerar_licenca():
    if not session.get('logado'):
        return redirect(url_for('login'))

    if request.method == 'POST':
        dados = {
            "tipo": request.form['tipo'],
            "inicio": request.form['inicio'],
            "fim": request.form['fim'],
            "igrejas_max": int(request.form['igrejas_max']),
            "membros_max": int(request.form['membros_max']),
            "modulos_liberados": request.form.getlist('modulos_liberados'),
            "id_maquina": request.form['id_maquina'],
            "cliente": request.form.get('cliente', 'CLIENTE')
        }

        json_str = json.dumps(dados)
        licenca_criptografada = fernet.encrypt(json_str.encode())

        nome_arquivo = f"{dados['id_maquina']}.lic"
        with open(os.path.join(PASTA_LICENCAS, nome_arquivo), 'wb') as f:
            f.write(licenca_criptografada)

        # Salva histórico
        historico = []
        if os.path.exists('historico_licencas.json'):
            with open('historico_licencas.json', 'r') as f:
                historico = json.load(f)

        dados['criado_em'] = datetime.now().isoformat()
        historico.append(dados)

        with open('historico_licencas.json', 'w') as f:
            json.dump(historico, f, indent=4, ensure_ascii=False)

        return f"Licença criada com sucesso para {dados['id_maquina']}!"

    return render_template('gerar.html')

@app.route('/api/verificar_licenca', methods=['POST'])
def verificar_licenca():
    content = request.get_json()
    id_maquina = content.get("id_maquina")

    print(f"[API] Verificação recebida para ID: {id_maquina} em {datetime.now().isoformat()}")

    caminho = os.path.join(PASTA_LICENCAS, f"{id_maquina}.lic")
    if not os.path.exists(caminho):
        return jsonify({"status": "erro", "mensagem": "Licença não encontrada"}), 404

    with open(caminho, 'rb') as f:
        licenca_criptografada = f.read()

    try:
        dados_json = fernet.decrypt(licenca_criptografada).decode()
        dados = json.loads(dados_json)
        hoje = datetime.now().date()
        validade = datetime.strptime(dados['fim'], "%Y-%m-%d").date()

        if hoje > validade:
            return jsonify({"status": "expirada", "dados": dados})
        else:
            return jsonify({"status": "valida", "dados": dados})
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500

# NOVA ROTA PARA REGISTRO EXTERNO DE LICENÇA
@app.route('/api/registrar_licenca', methods=['POST'])
def registrar_licenca():
    dados = request.get_json()
    obrigatorios = ["cliente", "id_maquina", "tipo", "inicio", "fim", "igrejas_max", "membros_max", "modulos_liberados"]

    if not all(campo in dados for campo in obrigatorios):
        return jsonify({"status": "erro", "mensagem": "Dados incompletos"}), 400

    try:
        json_str = json.dumps(dados)
        licenca_criptografada = fernet.encrypt(json_str.encode())

        nome_arquivo = f"{dados['id_maquina']}.lic"
        with open(os.path.join(PASTA_LICENCAS, nome_arquivo), 'wb') as f:
            f.write(licenca_criptografada)

        # Atualizar histórico
        historico = []
        if os.path.exists('historico_licencas.json'):
            with open('historico_licencas.json', 'r') as f:
                historico = json.load(f)

        dados['criado_em'] = datetime.now().isoformat()
        historico.append(dados)

        with open('historico_licencas.json', 'w') as f:
            json.dump(historico, f, indent=4,  ensure_ascii=False)

        return jsonify({"status": "sucesso", "mensagem": "Licença registrada com sucesso."})
    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500


@app.route('/painel')
def painel():
    try:
        with open("historico_licencas.json", "r") as f:
            licencas = json.load(f)
    except Exception:
        licencas = []

    return render_template("painel.html", licencas=licencas[::-1])  # mostra da mais nova pra mais antiga

# --- Criar pagamento Mercado Pago (Checkout Pro) ---
@app.route("/criar_pagamento", methods=["POST"])
@cross_origin(origin='*')  # ou origin='https://gusoftjardel.github.io'
def criar_pagamento():
    try:
        dados = request.json
        descricao = dados.get("descricao", "Licença IGPLUS")
        preco_str = str(dados.get("preco", "0.0"))
        preco = float(preco_str.replace(",", "."))
        email_cliente = dados.get("email", "comprador@email.com")

        payload = {
            "items": [{
                "title": descricao,
                "quantity": 1,
                "unit_price": preco,
                "currency_id": "BRL"
            }],
            "payer": {
                "email": email_cliente
            },
            "back_urls": {
                "success": "https://gusoftjardel.github.io/IgPlus/sucesso.html",
                "failure": "https://gusoftjardel.github.io/IgPlus/erro.html",
                "pending": "https://gusoftjardel.github.io/IgPlus/pendente.html"
            },
            "auto_return": "approved",
            "notification_url": "https://igplus-server.replit.app/webhook"
        }

        headers = {
            "Authorization": f"Bearer {ACCESS_TOKEN}"
        }

        resposta = requests.post(
            "https://api.mercadopago.com/checkout/preferences",
            json=payload,
            headers=headers
        )

        if resposta.status_code == 201:
            return jsonify({"link_pagamento": resposta.json()["init_point"]})
        else:
            print("RESPOSTA MERCADO PAGO:", resposta.status_code)
            print("BODY:", resposta.text)
            return jsonify({"erro": "Erro ao criar pagamento"}), 500

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"erro": f"Erro interno: {str(e)}"}), 500

# --- Webhook de pagamento ---
@app.route("/webhook", methods=["POST"])
def webhook():
    info = request.json
    print("Webhook recebido:", info)

    if info.get("type") == "payment":
        payment_id = info.get("data", {}).get("id")

        # Buscar detalhes do pagamento
        headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
        resp = requests.get(
            f"https://api.mercadopago.com/v1/payments/{payment_id}",
            headers=headers
        )

        if resp.status_code == 200:
            dados = resp.json()
            status = dados.get("status")
            email = dados.get("payer", {}).get("email")
            valor = dados.get("transaction_amount")

            if status == "approved":
                gerar_licenca_para(email, valor)

            return "OK", 200

    return "Ignorado", 200


@app.route('/retorno')
def retorno():
    status = request.args.get("status")  # status do Mercado Pago por exemplo
    if status == "approved":
        return render_template("sucesso.html")
    elif status == "pending":
        return render_template("pendente.html")
    else:
        return render_template("erro.html")

# --- Função que gera a licença com base no valor pago ---
def gerar_licenca_para(email, valor):
   
    # Defina os parâmetros da licença com base no valor
    if valor == 29.90:
        dias = 30
        tipo = "TRIAL"
    elif valor == 99.00:
        dias = 365
        tipo = "FULL"
    else:
        dias = 90
        tipo = "TESTE"

    dados = {
        "tipo": tipo,
        "inicio": datetime.now().strftime("%Y-%m-%d"),
        "fim": (datetime.now() + timedelta(days=dias)).strftime("%Y-%m-%d"),
        "igrejas_max": 5 if tipo == "TRIAL" else 999,
        "membros_max": 50 if tipo == "TRIAL" else 9999,
        "modulos_liberados": ["cadastro", "relatorios", "visitantes"],
        "id_maquina": f"EMAIL-{email.replace('@', '_').replace('.', '_')}",  # ou aguarde ele informar o ID real depois
        "cliente": email
    }

    gerar_licenca_auto(dados)


if __name__ == "__main__":
    from os import environ
    app.run(host="0.0.0.0", port=int(environ.get("PORT", 5000)))
