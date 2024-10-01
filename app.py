from flask import Flask, request, jsonify
import json

app = Flask(__name__)

# Caminho para o arquivo de configuração dos canais iniciais
channels_file = 'initial_channels.json'

# Função para ler os canais do arquivo
def read_channels():
    try:
        with open(channels_file, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return []

# Função para escrever os canais no arquivo
def write_channels(channels):
    with open(channels_file, 'w') as f:
        json.dump(channels, f)

@app.route('/add_channel', methods=['POST'])
def add_channel():
    data = request.json
    channel_name = data.get('channel')

    if channel_name:
        channels = read_channels()
        if channel_name not in channels:
            channels.append(channel_name)
            write_channels(channels)
            return jsonify({'message': f'Canal {channel_name} adicionado com sucesso!'}), 200
        else:
            return jsonify({'message': f'O canal {channel_name} já está na lista.'}), 400
    else:
        return jsonify({'message': 'Nome do canal não fornecido.'}), 400

if __name__ == '__main__':
    app.run(debug=True)
