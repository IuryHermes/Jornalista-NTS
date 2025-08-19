import os
import asyncio
import discord
import feedparser
import yaml
from dotenv import load_dotenv
import urllib3
from datetime import datetime, timedelta
import random
import hashlib
from collections import defaultdict, deque
import aiohttp
import logging
import signal
import sys

# Configuração inicial
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
load_dotenv()

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Constantes
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
DISCORD_CHANNEL_IDS = [int(cid.strip()) for cid in os.getenv("DISCORD_CHANNEL_IDS", "").split(",") if cid.strip()]
RSS_FEED_URLS = [url.strip() for url in os.getenv("RSS_FEED_URLS", "").split(",") if url.strip()]
DATE_MODE = int(os.getenv("DATE_MODE", 1))

EMOJI = "\U0001F4F0"
SENT_FILE = "sent_articles.yaml"

# Configurações
BATCH_SIZE = 2
PER_FEED_LIMIT = 3
INTERVAL = 1800  # 30 minutos (em segundos)
MAX_SAME_SOURCE_IN_ROW = 1
FEED_TIMEOUT = aiohttp.ClientTimeout(total=15)
MAX_CONCURRENT_FEEDS = 3

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# Variáveis globais
news_queue = asyncio.Queue()
sent_articles = {}
last_sources = deque(maxlen=10)
is_running = True
http_session = None

async def init_http_session():
    global http_session
    if http_session is None or http_session.closed:
        connector = aiohttp.TCPConnector(limit=MAX_CONCURRENT_FEEDS)
        http_session = aiohttp.ClientSession(connector=connector, timeout=FEED_TIMEOUT)

async def safe_fetch_feed(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/rss+xml, application/xml'
    }
    
    try:
        await init_http_session()
        async with http_session.get(url, headers=headers) as response:
            if response.status == 200:
                content = await response.text()
                return feedparser.parse(content)
            logger.warning(f"Erro HTTP {response.status} ao acessar: {url}")
            return None
    except Exception as e:
        logger.warning(f"Erro ao buscar feed {url}: {str(e)[:100]}")
        return None
    finally:
        await asyncio.sleep(0.1)

async def fetch_feed_with_retry(url, retries=2):
    for attempt in range(retries):
        feed = await safe_fetch_feed(url)
        if feed and not feed.bozo and feed.entries:
            return feed
        elif attempt < retries - 1:
            await asyncio.sleep(2)
    return None

def generate_hash(title, link):
    return hashlib.md5(f"{title}{link}".encode()).hexdigest()

def get_source_name(url):
    url_lower = url.lower()
    source_map = {
        'canaltech': 'Canaltech',
        'seginfo': 'SegInfo',
        'minutodaseguranca': 'MinutoSegurança',
        'terminalizando': 'Terminalizando',
        'uol': 'UOL Jogos',
        'animeunited': 'Anime United',
        'feededigno': 'FeedEdigno',
        'raiolaser': 'Raiolaser',
        'tecmundo': 'TecMundo',
        'tecnoblog': 'Tecnoblog',
        'tableless': 'Tableless',
        'linuxdescomplicado': 'Linux Descomplicado'
    }
    for key, name in source_map.items():
        if key in url_lower:
            return name
    return 'Outros'

def is_recent(entry):
    try:
        published = entry.get("published_parsed") or entry.get("updated_parsed")
        if not published:
            return False
            
        entry_time = datetime(*published[:6])
        hoje = datetime.now().date()
        
        if DATE_MODE == 1:
            return entry_time.date() == hoje
        return entry_time >= datetime.now() - timedelta(days=1)
    except Exception as e:
        logger.warning(f"Erro na data: {str(e)[:100]}")
        return False

def clean_old_entries():
    global sent_articles
    for channel_id in list(sent_articles.keys()):
        sent_articles[channel_id] = [h for h in sent_articles[channel_id] if isinstance(h, str)]

def is_source_repeated(source):
    if len(last_sources) < MAX_SAME_SOURCE_IN_ROW:
        return False
    return all(s == source for s in list(last_sources)[-MAX_SAME_SOURCE_IN_ROW:])

async def process_feed(rss_url, feed_items, source_counts):
    try:
        feed = await fetch_feed_with_retry(rss_url)
        if not feed or feed.bozo or not feed.entries:
            logger.warning(f"Feed inacessível ou vazio: {rss_url}")
            return

        source_name = get_source_name(rss_url)
        added = 0

        for entry in feed.entries:
            if added >= PER_FEED_LIMIT:
                break
            
            if is_recent(entry):
                title = entry.get('title', 'Sem título').strip()
                link = entry.get('link', '').strip()
                
                if title and link:
                    news_hash = generate_hash(title, link)
                    feed_items[source_name].append((title, link, news_hash))
                    source_counts[source_name] += 1
                    added += 1
            
            if added % 2 == 0:
                await asyncio.sleep(0.1)

        logger.info(f"{source_name}: {added} notícias {'do dia' if DATE_MODE == 1 else 'das últimas 24h'}")
    except Exception as e:
        logger.error(f"Erro ao processar feed {rss_url}: {str(e)}", exc_info=True)

async def fetch_all_entries():
    global last_sources
    
    try:
        feed_items = defaultdict(list)
        source_counts = defaultdict(int)
        
        batch_size = 3
        for i in range(0, len(RSS_FEED_URLS), batch_size):
            batch = RSS_FEED_URLS[i:i + batch_size]
            tasks = [process_feed(url, feed_items, source_counts) for url in batch]
            await asyncio.gather(*tasks)
            await asyncio.sleep(1)
        
        balanced_news = []
        sources = list(feed_items.keys())
        random.shuffle(sources)
        
        iteration = 0
        while any(feed_items.values()):
            for source in sources:
                if feed_items[source]:
                    if not is_source_repeated(source):
                        balanced_news.append(feed_items[source].pop(0))
                        last_sources.append(source)
                    
                    iteration += 1
                    if iteration % 3 == 0:
                        await asyncio.sleep(0.1)
        
        for item in balanced_news:
            await news_queue.put(item)
            
        logger.info(f"Total balanceado: {len(balanced_news)} notícias | Distribuição: {dict(source_counts)}")
        return True
    except Exception as e:
        logger.error(f"Erro crítico em fetch_all_entries: {str(e)}", exc_info=True)
        return False

async def send_batch():
    global sent_articles
    
    sent_count = 0
    while sent_count < BATCH_SIZE and not news_queue.empty():
        try:
            title, link, news_hash = await news_queue.get()
            
            for channel_id in DISCORD_CHANNEL_IDS:
                channel = client.get_channel(channel_id)
                if not channel:
                    continue
                    
                str_channel_id = str(channel_id)
                channel_history = sent_articles.setdefault(str_channel_id, [])
                
                if news_hash not in channel_history:
                    try:
                        await channel.send(f"{EMOJI} **{title}**\n{link}")
                        channel_history.append(news_hash)
                        sent_count += 1
                        await asyncio.sleep(1.5)
                    except discord.errors.HTTPException as e:
                        logger.error(f"Erro ao enviar para canal {channel_id}: {str(e)}", exc_info=True)
                    except Exception as e:
                        logger.error(f"Erro inesperado ao enviar mensagem: {str(e)}", exc_info=True)
                        await asyncio.sleep(5)
        except Exception as e:
            logger.error(f"Erro ao processar item da fila: {str(e)}", exc_info=True)

async def news_cycle():
    try:
        logger.info("\n" + "="*50)
        logger.info(f"{datetime.now().strftime('%H:%M:%S')} - Iniciando ciclo")
        
        success = await fetch_all_entries()
        if not success:
            logger.info("Tentando novamente no próximo ciclo...")
            return
        
        await send_batch()
        
        try:
            with open(SENT_FILE, 'w', encoding='utf-8') as f:
                yaml.dump(sent_articles, f)
        except Exception as e:
            logger.error(f"Erro ao salvar histórico: {str(e)}", exc_info=True)
    except Exception as e:
        logger.error(f"Erro crítico no ciclo: {str(e)}", exc_info=True)
    finally:
        await asyncio.sleep(1)

async def news_cycle_task():
    """Tarefa contínua que roda a cada 30 minutos"""
    while is_running:
        try:
            logger.info("Iniciando ciclo de notícias...")
            await news_cycle()
            logger.info(f"Próximo ciclo em {INTERVAL//60} minutos...")
            await asyncio.sleep(INTERVAL)
        except asyncio.CancelledError:
            logger.info("Tarefa de ciclo de notícias cancelada")
            break
        except Exception as e:
            logger.error(f"Erro na tarefa principal: {str(e)}", exc_info=True)
            await asyncio.sleep(60)

@client.event
async def on_ready():
    logger.info(f"\nBot conectado como {client.user}")
    logger.info(f"Modo: {'Dia exato' if DATE_MODE == 1 else 'Últimas 24h'}")
    logger.info(f"Fontes ({len(RSS_FEED_URLS)}):")
    for url in RSS_FEED_URLS:
        logger.info(f"  - {get_source_name(url)}")
    
    global sent_articles
    try:
        if os.path.exists(SENT_FILE):
            with open(SENT_FILE, 'r', encoding='utf-8') as f:
                sent_articles = yaml.safe_load(f) or {}
    except Exception as e:
        logger.error(f"Erro ao carregar histórico: {str(e)}", exc_info=True)
    
    clean_old_entries()
    client.loop.create_task(news_cycle_task())

async def shutdown():
    global is_running, http_session
    is_running = False
    
    if http_session and not http_session.closed:
        await http_session.close()
    
    if not client.is_closed():
        await client.close()

def handle_signal(signal, frame):
    logger.info("Recebido sinal de desligamento...")
    client.loop.create_task(shutdown())

signal.signal(signal.SIGINT, handle_signal)
signal.signal(signal.SIGTERM, handle_signal)

if not DISCORD_BOT_TOKEN:
    logger.error("ERRO: Token do Discord não encontrado!")
    exit(1)

logger.info("\nToken carregado com sucesso")
logger.info(f"Canais: {DISCORD_CHANNEL_IDS}")
logger.info("Iniciando bot...")

try:
    client.run(DISCORD_BOT_TOKEN)
except KeyboardInterrupt:
    logger.info("\nDesligando o bot...")
except Exception as e:
    logger.error(f"Erro fatal: {str(e)}", exc_info=True)
    exit(1)