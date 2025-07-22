from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from cryptography.fernet import Fernet
import os, json
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'sua_chave_secreta'

# Geração da chave simétrica para criptografia
chave_criptografia = b'wsXMP8_thOq-F-TT5WtQquoeMFYHQD5j_FffMyymC64='
fernet = Fernet(chave_criptografia)

PASTA_LICENCAS = 'licencas'
os.makedirs(PASTA_LICENCAS, exist_ok=True)

# Usuário e senha fixos
USUARIO = 'admin'
SENHA = '1234'

@app.route('/')
def index():
    if not session.get('logado'):
        return redirect(url_for('login'))
    return redirect(url_for('gerar_licenca'))

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

@app.route('/painel', methods=['GET', 'POST'])
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
            "id_maquina": request.form['id_maquina']
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
            json.dump(historico, f, indent=4)

        return f"Licença criada com sucesso para {dados['id_maquina']}!"

    return render_template('gerar.html')

@app.route('/api/verificar_licenca', methods=['POST'])
def verificar_licenca():
    content = request.get_json()
    id_maquina = content.get("id_maquina")

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

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
