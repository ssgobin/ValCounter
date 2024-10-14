import os
import json
from twitchio.ext import commands
import firebase_admin
from firebase_admin import credentials, firestore
import asyncio
from datetime import datetime, timedelta
import pytz

# Inicializa o Firebase
try:
    service_account_info = json.loads(os.environ['FIREBASE_SERVICE_ACCOUNT_KEY'])
    service_account_info['private_key'] = service_account_info['private_key'].replace('\\n', '\n')
    cred = credentials.Certificate(service_account_info)
    firebase_admin.initialize_app(cred)
    db = firestore.client()
    print("Firebase inicializado com sucesso.")  # Log de sucesso do Firebase
except Exception as e:
    print(f"Erro ao inicializar o Firebase: {e}")  # Log de erro do Firebase

# Inicializa o bot
class Bot(commands.Bot):

    def __init__(self):
        self.initial_channels = []  # Lista de canais iniciais
        super().__init__(token='gno2xk9rdd28u8io39tydoci6eaftj', prefix='!')
        print("Bot inicializado.")  # Log ao inicializar o bot

    async def event_ready(self):
        print(f'Bot conectado como {self.nick}')
        await self.ler_canais_iniciais()  # Lê os canais iniciais
        await self.add_channels()  # Adiciona os canais ao bot
        asyncio.create_task(self.resetar_diariamente())  # Inicia o reset diário
        # Inicia o listener para monitorar adição de novos canais
        self.iniciar_listener_novos_canais()

    def iniciar_listener_novos_canais(self):
        """Inicia o listener do Firestore para detectar quando novos canais forem adicionados."""
        db.collection('channels').on_snapshot(self.on_channels_snapshot)

    def on_channels_snapshot(self, col_snapshot, changes, read_time):
        """Callback acionado quando há mudanças na coleção 'channels'."""
        for change in changes:
            if change.type.name == 'ADDED':
                print(f'Novo canal adicionado: {change.document.id}')
                self.initial_channels.append(change.document.id)
                asyncio.create_task(self.add_channels())  # Atualiza a lista de canais adicionando o novo

    async def add_channels(self):
        """Adiciona os canais do Firestore ao bot."""
        await self.join_channels(self.initial_channels)  # Adiciona os canais ao bot
        print(f'Canais ativos: {self.initial_channels}')  # Log dos canais ativos

    async def resetar_diariamente(self):
        """Função para resetar as contagens de vitórias e derrotas diariamente."""
        fuso_brt = pytz.timezone('America/Sao_Paulo')
        while True:
            now = datetime.now(fuso_brt)
            proximo_reset = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
            tempo_ate_reset = (proximo_reset - now).total_seconds()

            print(f"Próximo reset em {tempo_ate_reset / 3600:.2f} horas.")  # Log para indicar o tempo até o próximo reset

            await asyncio.sleep(tempo_ate_reset)  # Espera até meia-noite do próximo dia
            await self.resetar_contagens()  # Reseta as contagens ao alcançar a meia-noite

    async def resetar_contagens(self):
        """Função que reseta a contagem de vitórias e derrotas no Firestore."""
        try:
            print("Resetando contagem de vitórias e derrotas para todos os streamers.")  # Log antes de resetar
            streamers_ref = db.collection('streamers').stream()

            for streamer in streamers_ref:
                doc_ref = db.collection('streamers').document(streamer.id)
                doc_ref.update({'vitorias': 0, 'derrotas': 0})
                print(f"Contagem resetada para {streamer.id}.")  # Log de sucesso ao resetar cada streamer
        except Exception as e:
            print(f"Erro ao resetar contagens: {e}")  # Log de erro

    async def ler_canais_iniciais(self):
        """Lê os canais do Firestore e carrega os canais iniciais."""
        try:
            print("Lendo canais iniciais do Firestore...")  # Log antes de acessar o Firestore
            channels_ref = db.collection('channels').stream()
            self.initial_channels = [channel.id for channel in channels_ref]  # Coleta os IDs dos documentos como nomes dos canais
            print(f'Canais que podem usar o bot: {self.initial_channels}')  # Log para mostrar quais canais podem usar o bot
        except Exception as e:
            print(f"Erro ao ler canais do Firestore: {e}")
            self.initial_channels = []

    async def event_message(self, message):
        """Função que lida com mensagens recebidas no chat."""
        if message.author is None or message.author.name.lower() == self.nick.lower():
            return

        print(f"Mensagem recebida de {message.author.name}: {message.content}")  # Log de mensagem recebida
        await self.handle_commands(message)

    @commands.command(name='status')
    async def status(self, ctx):
        """Comando para mostrar o status de vitórias e derrotas."""
        streamer = ctx.channel.name
        streamer_ref = db.collection('streamers').document(streamer)
        streamer_doc = streamer_ref.get()

        if streamer_doc.exists:
            streamer_data = streamer_doc.to_dict()
            victoryCount = streamer_data.get('vitorias', 0)
            lossCount = streamer_data.get('derrotas', 0)
            await ctx.send(f'{streamer} tem {victoryCount} vitórias e {lossCount} derrotas!')
        else:
            await ctx.send(f'{streamer} ainda não está registrado no sistema.')

    @commands.command(name='vitoria')
    async def ganhar(self, ctx):
        """Comando para adicionar uma vitória."""
        user = ctx.author.name
        streamer = ctx.channel.name
        if user == streamer or ctx.author.is_mod:
            await self.atualizar_contagem(streamer, 'vitorias')
            streamer_ref = db.collection('channels').document(streamer)
            streamer_doc = streamer_ref.get()

            if streamer_doc.exists:
                streamer_data = streamer_doc.to_dict()
                win_message = streamer_data.get('winMessage', ' ganhou uma partida!')
                await ctx.send(f'{streamer} {win_message}')
        else:
            await ctx.send(f'Desculpe, {user}, apenas administradores podem usar este comando.')

    @commands.command(name='derrota')
    async def perder(self, ctx):
        """Comando para adicionar uma derrota."""
        user = ctx.author.name
        streamer = ctx.channel.name
        if user == streamer or ctx.author.is_mod:
            await self.atualizar_contagem(streamer, 'derrotas')
            streamer_ref = db.collection('channels').document(streamer)
            streamer_doc = streamer_ref.get()

            if streamer_doc.exists:
                streamer_data = streamer_doc.to_dict()
                defeat_message = streamer_data.get('defeatMessage', ' perdeu uma partida!')
                await ctx.send(f'{streamer} {defeat_message}')
        else:
            await ctx.send(f'Desculpe, {user}, apenas administradores podem usar este comando.')

    async def atualizar_contagem(self, user, tipo):
        """Função para atualizar as contagens de vitórias ou derrotas."""
        print(f"Atualizando contagem de {tipo} para {user}...")  # Log antes de atualizar contagem
        doc_ref = db.collection('streamers').document(user)

        try:
            doc = doc_ref.get()
            
            if doc.exists:
                data = doc.to_dict()
                if tipo == 'vitorias':
                    data['vitorias'] += 1
                else:
                    data['derrotas'] += 1
                doc_ref.update(data)
                print(f"Contagem de {tipo} atualizada para {user}.")  # Log de sucesso
            else:
                print(f"Streamer {user} não encontrado, registrando antes de atualizar contagem.")  # Log para não encontrado
                await self.adicionar_streamer(user)
                await self.atualizar_contagem(user, tipo)
        except Exception as e:
            print(f"Erro ao atualizar contagem para {user}: {e}")  # Log de erro

if __name__ == '__main__':
    print("Iniciando bot...")  # Log ao iniciar o bot
    bot = Bot()
    bot.run()
