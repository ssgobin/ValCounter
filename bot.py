import os
import json
from twitchio.ext import commands
import firebase_admin
from firebase_admin import credentials, firestore
import asyncio

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
        self.initial_channels = await self.ler_canais_iniciais()  # Lê os canais iniciais
        print(f'Canais iniciais carregados: {self.initial_channels}')  # Log para mostrar os canais carregados
        await self.add_channels()  # Adiciona os canais ao bot
        asyncio.create_task(self.monitor_channels())  # Inicia monitoramento dos canais

    async def monitor_channels(self):
        while True:
            await asyncio.sleep(10)  # Espera 10 segundos antes de verificar novamente
            new_channels = await self.ler_canais_iniciais()  # Verifica os canais novamente
            if sorted(new_channels) != sorted(self.initial_channels):
                print("Atualizando canais...")
                self.initial_channels = new_channels  # Atualiza a lista de canais
                await self.add_channels()  # Adiciona os novos canais ao bot

    async def add_channels(self):
        await self.join_channels(self.initial_channels)  # Adiciona os canais ao bot
        print(f'Canais ativos: {self.initial_channels}')  # Log dos canais ativos

    async def ler_canais_iniciais(self):
        # Lê os canais do Firestore
        try:
            print("Lendo canais iniciais do Firestore...")  # Log antes de acessar o Firestore
            channels_ref = db.collection('channels').stream()
            channels = [channel.id for channel in channels_ref]  # Coleta os IDs dos documentos como nomes dos canais
            print(f'Canais que podem usar o bot: {channels}')  # Log para mostrar quais canais podem usar o bot
            return channels
        except Exception as e:
            print(f"Erro ao ler canais do Firestore: {e}")
            return []

    async def event_message(self, message):
        # Verifica se o autor da mensagem existe e se não é o próprio bot
        if message.author is None or message.author.name.lower() == self.nick.lower():
            return

        print(f"Mensagem recebida de {message.author.name}: {message.content}")  # Log de mensagem recebida
        await self.handle_commands(message)

    @commands.command(name='vitoria')
    async def ganhar(self, ctx):
        user = ctx.author.name
        streamer = ctx.channel.name
        if user == streamer or ctx.author.is_mod:
            print(f'Comando "ganhar" recebido de {user}.')  # Log para o comando 'ganhar'
            await self.atualizar_contagem(streamer, 'vitorias')
            await ctx.send(f'{streamer} ganhou uma partida!')
        else:
            await ctx.send(f'Desculpe, {user}, apenas administradores podem usar este comando.')

    @commands.command(name='derrota')
    async def perder(self, ctx):
        user = ctx.author.name
        streamer = ctx.channel.name
        if user == streamer or ctx.author.is_mod:
            print(f'Comando "perder" recebido de {user}.')  # Log para o comando 'perder'
            await self.atualizar_contagem(streamer, 'derrotas')
            await ctx.send(f'{streamer} perdeu uma partida!')
        else:
            await ctx.send(f'Desculpe, {user}, apenas administradores podem usar este comando.')

    @commands.command(name='registrar')
    async def registrar(self, ctx):
        user = ctx.author.name
        streamer = ctx.channel.name

        if user == streamer:
            print(f"Tentando registrar o streamer: {streamer}")  # Log de depuração
            await self.adicionar_streamer(streamer)
            await ctx.send(f'{streamer} foi registrado com sucesso!')
        else:
            await ctx.send(f'Desculpe, {user}, apenas o dono do canal pode utilizar esse comando!')

    async def adicionar_streamer(self, user):
        # Adiciona um novo streamer ao Firestore
        print(f"Adicionando streamer {user} ao Firestore...")  # Log antes de adicionar
        doc_ref = db.collection('streamers').document(user)

        try:
            doc = doc_ref.get()

            if not doc.exists:
                print(f"Streamer {user} não encontrado, adicionando ao Firestore...")  # Log de depuração
                doc_ref.set({
                    'vitorias': 0,
                    'derrotas': 0,
                })
                print(f"Streamer {user} registrado com sucesso.")  # Log de sucesso
            else:
                print(f"Streamer {user} já está registrado.")  # Log de depuração
        except Exception as e:
            print(f"Erro ao adicionar streamer {user}: {e}")  # Log de erro

    async def atualizar_contagem(self, user, tipo):
        # Atualiza a contagem no Firestore
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
                # Caso o streamer não esteja registrado, adiciona um novo
                print(f"Streamer {user} não encontrado, registrando antes de atualizar contagem.")  # Log para não encontrado
                await self.adicionar_streamer(user)
                await self.atualizar_contagem(user, tipo)  # Tenta atualizar a contagem novamente
        except Exception as e:
            print(f"Erro ao atualizar contagem para {user}: {e}")  # Log de erro

if __name__ == '__main__':
    print("Iniciando bot...")  # Log ao iniciar o bot
    bot = Bot()
    bot.run()
