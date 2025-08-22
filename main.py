import asyncio
import aiohttp
import discord
import feedparser
import yaml
import logging
from datetime import datetime, time, timedelta
from discord.ext import tasks, commands
import os
from dotenv import load_dotenv
import sqlite3

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# Carregar variáveis de ambiente
load_dotenv()

# Configurações
TOKEN = os.getenv('DISCORD_TOKEN')
CHANNEL_ID = int(os.getenv('DISCORD_CHANNEL_ID'))
CONFIG_FILE = 'config.yaml'

# Inicializar bot com intents
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

class NewsBot:
    def __init__(self):
        self.session = None
        self.load_config()
        self.init_database()

    def init_database(self):
        """Inicializa banco de dados SQLite para evitar links repetidos"""
        self.conn = sqlite3.connect('news_bot.db', check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS sent_links (
                link TEXT PRIMARY KEY,
                title TEXT,
                sent_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        self.conn.commit()
        logging.info("✅ Banco de dados inicializado")

    def load_config(self):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                self.config = yaml.safe_load(f)
            logging.info("✅ Configuração carregada com sucesso")
        except Exception as e:
            logging.error(f"❌ Erro ao carregar configuração: {e}")
            self.config = {'feeds': []}

    def is_link_sent(self, link):
        """Verifica se o link já foi enviado"""
        try:
            self.cursor.execute('SELECT link FROM sent_links WHERE link = ?', (link,))
            return self.cursor.fetchone() is not None
        except Exception as e:
            logging.error(f"❌ Erro ao verificar link: {e}")
            return True

    def mark_link_sent(self, link, title):
        """Marca o link como enviado"""
        try:
            self.cursor.execute(
                'INSERT OR IGNORE INTO sent_links (link, title) VALUES (?, ?)',
                (link, title[:200])  # Limita título para evitar overflow
            )
            self.conn.commit()
        except Exception as e:
            logging.error(f"❌ Erro ao salvar link: {e}")

    async def fetch_feed(self, url):
        try:
            if not self.session:
                self.session = aiohttp.ClientSession()
            
            timeout = aiohttp.ClientTimeout(total=30)
            async with self.session.get(url, timeout=timeout) as response:
                if response.status == 200:
                    content = await response.text()
                    return feedparser.parse(content)
                else:
                    logging.error(f"❌ Erro ao buscar feed {url}: Status {response.status}")
                    return None
        except asyncio.TimeoutError:
            logging.error(f"⏰ Timeout ao buscar feed {url}")
            return None
        except Exception as e:
            logging.error(f"❌ Erro ao buscar feed {url}: {e}")
            return None

    async def check_feeds(self):
        new_articles = []
        
        for feed_config in self.config.get('feeds', []):
            try:
                feed_url = feed_config['url']
                logging.info(f"🔍 Verificando feed: {feed_url}")
                
                feed = await self.fetch_feed(feed_url)
                if feed and feed.entries:
                    for entry in feed.entries[:15]:  # Últimas 15 notícias
                        link = entry.get('link', '').strip()
                        title = entry.get('title', 'Sem título').strip()
                        
                        if link and link.startswith('http') and not self.is_link_sent(link):
                            new_articles.append({
                                'title': title,
                                'link': link,
                                'emoji': feed_config.get('emoji', '📰')
                            })
                            self.mark_link_sent(link, title)
                            
            except Exception as e:
                logging.error(f"❌ Erro ao processar feed: {e}")

        return new_articles

    async def close(self):
        """Fecha conexões"""
        try:
            if self.session:
                await self.session.close()
            if self.conn:
                self.conn.close()
            logging.info("✅ Conexões fechadas")
        except Exception as e:
            logging.error(f"❌ Erro ao fechar conexões: {e}")

news_bot = NewsBot()

def dentro_do_horario_funcionamento():
    """Verifica se está dentro do horário de funcionamento (8h às 21h)"""
    agora = datetime.now().time()
    hora_inicio = time(8, 0)   # 8h da manhã
    hora_fim = time(21, 0)     # 21h da noite
    
    return hora_inicio <= agora <= hora_fim

async def esperar_proximo_horario_funcionamento():
    """Aguarda até o próximo horário de funcionamento"""
    agora = datetime.now()
    hora_inicio = time(8, 0)
    
    if agora.time() > time(21, 0):
        amanha = agora.date() + timedelta(days=1)
        proximo_inicio = datetime.combine(amanha, hora_inicio)
    else:
        proximo_inicio = datetime.combine(agora.date(), hora_inicio)
        if proximo_inicio < agora:
            proximo_inicio += timedelta(days=1)
    
    tempo_espera = (proximo_inicio - agora).total_seconds()
    logging.info(f"⏰ Bot em pausa. Próxima execução às {proximo_inicio.strftime('%d/%m às %H:%M')}")
    await asyncio.sleep(tempo_espera)

@bot.event
async def on_ready():
    logging.info(f'✅ Bot conectado como {bot.user}')
    logging.info(f'⏰ Horário de funcionamento: 8h às 21h')
    check_feeds_loop.start()
    heartbeat_loop.start()

@tasks.loop(hours=1)
async def check_feeds_loop():
    try:
        # Verifica se está dentro do horário
        if not dentro_do_horario_funcionamento():
            logging.info("⏰ Fora do horário de funcionamento (8h-21h)")
            await esperar_proximo_horario_funcionamento()
            return
            
        logging.info("🔍 Iniciando verificação de feeds...")
        articles = await news_bot.check_feeds()
        
        if articles:
            channel = bot.get_channel(CHANNEL_ID)
            if channel:
                logging.info(f"📨 Enviando {len(articles)} nova(s) notícia(s)...")
                for i, article in enumerate(articles, 1):
                    try:
                        message = f"{article['emoji']} **{article['title']}**\n{article['link']}"
                        await channel.send(message)
                        logging.info(f"✅ [{i}/{len(articles)}] Notícia enviada")
                        await asyncio.sleep(2)  # Espera 2s entre mensagens
                    except discord.Forbidden:
                        logging.error("❌ Permissão negada para enviar mensagem")
                    except Exception as e:
                        logging.error(f"❌ Erro ao enviar mensagem: {e}")
                logging.info("✅ Todas as notícias enviadas com sucesso!")
        else:
            logging.info("ℹ️ Nenhuma nova notícia encontrada")
            
    except Exception as e:
        logging.error(f"💥 Erro crítico na verificação: {e}")

@tasks.loop(minutes=10)
async def heartbeat_loop():
    try:
        if dentro_do_horario_funcionamento():
            status = "as últimas notícias 📰"
            activity_type = discord.ActivityType.watching
        else:
            status = "⏰ Volto às 8h"
            activity_type = discord.ActivityType.custom
            
        await bot.change_presence(activity=discord.Activity(
            type=activity_type,
            name=status
        ))
    except Exception as e:
        logging.error(f"❌ Erro no heartbeat: {e}")

@check_feeds_loop.before_loop
@heartbeat_loop.before_loop
async def before_loops():
    await bot.wait_until_ready()

async def main():
    try:
        await bot.start(TOKEN)
    except KeyboardInterrupt:
        logging.info("🛑 Bot interrompido pelo usuário")
    except Exception as e:
        logging.error(f"💥 Erro fatal: {e}")
    finally:
        await news_bot.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("🛑 Programa encerrado")
    except Exception as e:
        logging.error(f"💥 Erro inesperado: {e}")
