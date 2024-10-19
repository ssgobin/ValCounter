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
        self.initial_channels = await self.ler_canais_iniciais()  # Lê os canais iniciais
        print(f'Canais iniciais carregados: {self.initial_channels}')  # Log para mostrar os canais carregados
        await self.add_channels()  # Adiciona os canais ao bot
        self.escutar_canais()  # Inicia a escuta por mudanças no Firestore
        asyncio.create_task(self.resetar_diariamente())  # Mantém o reset diário

    # Método para iniciar a escuta no Firestore
    def escutar_canais(self):
        print("Iniciando escuta de canais no Firestore...")  # Log de início da escuta

        # Define um snapshot listener para detectar mudanças em tempo real
        def on_snapshot(doc_snapshot, changes, read_time):
            print("Mudança detectada nos canais.")
            new_channels = [doc.id for doc in doc_snapshot]
            if sorted(new_channels) != sorted(self.initial_channels):
                print("Atualizando canais com base nas mudanças detectadas.")
                self.initial_channels = new_channels  # Atualiza a lista de canais
                # Utilize um loop de eventos para criar a tarefa
                asyncio.run_coroutine_threadsafe(self.add_channels(), self.loop)  # Atualiza os canais do bot

        # Registra o listener no Firestore para o collection 'channels'
        db.collection('channels').on_snapshot(on_snapshot)

    async def add_channels(self):
        await self.join_channels(self.initial_channels)  # Adiciona os canais ao bot
        print(f'Canais ativos: {self.initial_channels}')  # Log dos canais ativos

    async def resetar_diariamente(self):
        fuso_brt = pytz.timezone('America/Sao_Paulo')
        while True:
            now = datetime.now(fuso_brt)
            proximo_reset = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
            tempo_ate_reset = (proximo_reset - now).total_seconds()

            print(f"Próximo reset em {tempo_ate_reset / 3600:.2f} horas.")  # Log para indicar o tempo até o próximo reset

            await asyncio.sleep(tempo_ate_reset)  # Espera até meia-noite do próximo dia
            await self.resetar_contagens()  # Reseta as contagens ao alcançar a meia-noite

    async def resetar_contagens(self):
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

    @commands.command(name='status')
    async def status(self, ctx):
        streamer = ctx.channel.name
        print(f'Comando "status" recebido.')  # Log para o comando 'status'

        streamer_ref = db.collection('streamers').document(streamer)
        streamer_doc = streamer_ref.get()

        if streamer_doc.exists:
            streamer_data = streamer_doc.to_dict()
            victoryCount = streamer_data.get('vitorias', 0)
            lossCount = streamer_data.get('derrotas', 0)
            await ctx.send(f'{streamer} tem {victoryCount} vitórias e {lossCount} derrotas!')
        else:
            await ctx.send(f'O streamer {streamer} não está registrado.')

    @commands.command(name='vitoria')
    async def ganhar(self, ctx):
        await self.atualizar_contagem(ctx, 'vitorias', ' ganhou uma partida!')

    @commands.command(name='derrota')
    async def perder(self, ctx):
        await self.atualizar_contagem(ctx, 'derrotas', ' perdeu uma partida!')

    async def atualizar_contagem(self, ctx, tipo, mensagem):
        user = ctx.author.name
        streamer = ctx.channel.name

        if user == streamer or ctx.author.is_mod:
            print(f'Comando para atualizar {tipo} recebido de {user}.')  # Log do comando
            streamer_ref = db.collection('streamers').document(streamer)

            try:
                doc = streamer_ref.get()
                if doc.exists:
                    data = doc.to_dict()
                    data[tipo] += 1
                    streamer_ref.update(data)
                    print(f"{tipo.capitalize()} atualizada para {streamer}.")
                    await ctx.send(f'{streamer} {mensagem}')
                else:
                    await self.adicionar_streamer(streamer)
                    await ctx.send(f'{streamer} foi registrado e a {tipo} foi atualizada.')
            except Exception as e:
                print(f"Erro ao atualizar {tipo} para {streamer}: {e}")
                await ctx.send(f"Erro ao atualizar {tipo} para {streamer}.")
        else:
            await ctx.send(f'Desculpe, {user}, apenas administradores podem usar este comando.')

    @commands.command(name='registrar')
    async def registrar(self, ctx):
        user = ctx.author.name
        streamer = ctx.channel.name

        streamer_ref = db.collection('blocked_streamers').document(streamer)
        streamer_doc = streamer_ref.get()

        if user == streamer and not streamer_doc.exists:
            print(f"Tentando registrar o streamer: {streamer}")  # Log de depuração
            await self.adicionar_streamer(streamer)
            await ctx.send(f'{streamer} foi registrado com sucesso!')
        elif user == streamer and streamer_doc.exists:
            await ctx.send(f'{streamer} está bloqueado de usar o bot! Entre em contato para desban.')
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

    @commands.command(name='removervitoria')
    async def removeganhar(self, ctx):
        user = ctx.author.name
        streamer = ctx.channel.name
        if user == streamer or ctx.author.is_mod:
            print(f'Comando "removerganhar" recebido de {user}.')  # Log para o comando 'ganhar'
            await self.remover_contagem(streamer, 'vitorias')
    
            # Verifica a contagem atual de vitórias
            streamer_ref = db.collection('streamers').document(streamer)
            streamer_doc = streamer_ref.get()
            streamer_data = streamer_doc.to_dict()
            current_wins = streamer_data.get('vitorias', 0)
    
            if current_wins >= 0:
                await ctx.send(f'{user} removeu uma vitória da contagem!')
            else:
                await ctx.send(f'A contagem de vitórias já é 0 para {streamer}. Não é possível remover mais vitórias.')
    
        else:
            await ctx.send(f'Desculpe, {user}, apenas administradores podem usar este comando.')

    @commands.command(name='resetar')
    async def resetar(self, ctx):
        streamer = ctx.channel.name
        print(f'Comando "resetar" recebido.')  # Log para o comando 'resetar'

        streamer_ref = db.collection('streamers').document(streamer)
        streamer_doc = streamer_ref.get()

        if streamer_doc.exists:
            if streamer_doc.get('resetDiarioAtivado' == False):
                streamer_ref.update({'vitorias': 0, 'derrotas': 0})
                await ctx.send(f'O streamer {streamer} foi resetado.')
            elif streamer_doc.get('resetDiarioAtivado'):
                await ctx.send(f'O streamer {streamer} está com o reset automático ativado.')
            else:
                await ctx.send(f'O streamer {streamer} não está registrado.')  # Mensagem de erro

    @commands.command(name='removerderrota')
    async def removeperder(self, ctx):
        user = ctx.author.name
        streamer = ctx.channel.name
        if user == streamer or ctx.author.is_mod:
            print(f'Comando "removeperder" recebido de {user}.')  # Log para o comando 'perder'
            await self.remover_contagem(streamer, 'derrotas')
    
            # Verifica a contagem atual de derrotas
            streamer_ref = db.collection('streamers').document(streamer)
            streamer_doc = streamer_ref.get()
            streamer_data = streamer_doc.to_dict()
            current_losses = streamer_data.get('derrotas', 0)
    
            if current_losses >= 0:
                await ctx.send(f'{user} removeu uma derrota da contagem!')
            else:
                await ctx.send(f'A contagem de derrotas já é 0 para {streamer}. Não é possível remover mais derrotas.')
    
        else:
            await ctx.send(f'Desculpe, {user}, apenas administradores podem usar este comando.')
            
    async def remover_contagem(self, user, tipo):
        # Atualiza a contagem no Firestore
        print(f"Atualizando contagem de {tipo} para {user}...")  # Log antes de atualizar contagem
        doc_ref = db.collection('streamers').document(user)

        try:
            doc = doc_ref.get()

            if doc.exists:
                data = doc.to_dict()
                if tipo == 'vitorias':
                    if data['vitorias'] > 0:  # Verifica se a contagem é maior que 0
                        data['vitorias'] -= 1
                    else:
                        print(f"Contagem de vitórias já é 0 para {user}. Não pode remover.")  # Log informativo
                else:  # 'derrotas'
                    if data['derrotas'] > 0:  # Verifica se a contagem é maior que 0
                        data['derrotas'] -= 1
                    else:
                        print(f"Contagem de derrotas já é 0 para {user}. Não pode remover.")  # Log informativo
                doc_ref.update(data)
                print(f"Contagem de {tipo} atualizada para {user}.")  # Log de sucesso
            else:
                # Caso o streamer não esteja registrado, adiciona um novo
                print(f"Streamer {user} não encontrado, registrando antes de atualizar contagem.")  # Log para não encontrado
                await self.adicionar_streamer(user)
                await self.atualizar_contagem(user, tipo)  # Tenta atualizar a contagem novamente
        except Exception as e:
            print(f"Erro ao atualizar contagem para {user}: {e}")  # Log de erro

# Função para iniciar o bot
def main():
    print("Iniciando o bot...")  # Log de início do bot
    bot = Bot()
    bot.run()  # Inicia o bot

if __name__ == "__main__":
    main()  # Chama a função principal
