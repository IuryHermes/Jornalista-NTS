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
from googletrans import Translator

translator = Translator()

async def translate_text(text, dest='pt'):
    try:
        translated = await asyncio.to_thread(translator.translate, text, dest=dest)
        return translated.text
    except Exception as e:
        logger.error(f"Erro ao traduzir texto: {e}", exc_info=True)
        return text

# Configuração inicial
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
load_dotenv()

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot.log"),
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

# Palavras que devem ser excluídas
KEYWORDS_EXCLUDE = [
    "smartphone", "venda", 
    "carro", "automóvel", "veículo", "montadora",
    "aposta", "cassino", "bet", "jogo de azar", "bingo",
    "futebol", "esporte", "campeonato", "liga", "estádio",
    "novela", "globoplay",
    "celebridade", "famoso", "fofoca", "revista",
    "moda", "beleza", "maquiagem", "cosmético", "shopping",
    "culinária", "receita", "comida", "restaurante", "chef",
    "dieta", "emagrecimento", "academia", "personal trainer",
    "saúde", "doença", "remédio", "médico", "hospital",
    "gravidez", "maternidade", "bebê", "criança",
    "cassino", "currículo", "entrevista",
    "finanças", "bolsa", "investimento",
    "política", "eleição", "partido", "candidato",
    "imóvel", "apartamento", "aluguel", "venda",
    "viagem", "turismo", "hotel", "resort", "passagem",
     "netflix", "música", "show", "festival", "cantor",
    "religião", "igreja", "deus", "fé", "bispo"
]

DAILY_NEWS_LIMIT = 15
OPERATING_START_HOUR = 8
OPERATING_END_HOUR = 21

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# Variáveis globais
news_queue = asyncio.Queue()
sent_articles = {}
last_sources = deque(maxlen=10)
is_running = True
http_session = None
daily_sent_count = 0
last_reset_date = None

async def init_http_session():
    global http_session
    if http_session is None or http_session.closed:
        connector = aiohttp.TCPConnector(limit=MAX_CONCURRENT_FEEDS)
        http_session = aiohttp.ClientSession(connector=connector, timeout=FEED_TIMEOUT)

async def safe_fetch_feed(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36',
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
    today = datetime.now().date()
    for channel_id in list(sent_articles.keys()):
        sent_articles[channel_id] = [h for h in sent_articles[channel_id] if isinstance(h, str)]

def is_source_repeated(source):
    if len(last_sources) < MAX_SAME_SOURCE_IN_ROW:
        return False
    return all(s == source for s in list(last_sources)[-MAX_SAME_SOURCE_IN_ROW:])

async def process_feed(rss_url, feed_items, source_counts):
    added = 0
    source_name = get_source_name(rss_url)
    try:
        feed = await fetch_feed_with_retry(rss_url)
        if feed:
            for entry in feed.entries:
                if is_recent(entry):
                    title = entry.get("title", "N/A")
                    link = entry.get("link", "N/A")
                    news_hash = generate_hash(title, link)
                    
                    already_sent = False
                    for channel_history in sent_articles.values():
                        if news_hash in channel_history:
                            already_sent = True
                            break

                    if not already_sent:
                        if any(keyword.lower() in title.lower() for keyword in KEYWORDS_EXCLUDE):
                            logger.info(f"Notícia ignorada por palavra-chave: {title}")
                            continue

                        feed_items[source_name].append((title, link, news_hash))
                        source_counts[source_name] += 1
                        added += 1

            modo_data_texto = "do dia" if DATE_MODE == 1 else "das últimas 24h"
            logger.info(f"{source_name}: {added} notícias {modo_data_texto}")

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
    global sent_articles, daily_sent_count

    sent_count = 0
    while sent_count < BATCH_SIZE and not news_queue.empty():
        try:
            title, link, news_hash = await news_queue.get()

            for channel_id in DISCORD_CHANNEL_IDS:
                channel = client.get_channel(channel_id)
                if channel is None:
                    try:
                        channel = await client.fetch_channel(channel_id)
                    except Exception as e:
                        logger.warning(f"Não consegui acessar canal {channel_id}: {e}")
                        continue

                str_channel_id = str(channel_id)
                channel_history = sent_articles.setdefault(str_channel_id, [])

                if news_hash not in channel_history:
                    if daily_sent_count < DAILY_NEWS_LIMIT:
                        try:
                            translated_title = await translate_text(title)
                            await channel.send(f"{EMOJI} **{translated_title}**\n{link}")
                            channel_history.append(news_hash)
                            sent_count += 1
                            daily_sent_count += 1
                            logger.info(f"Notícia enviada para o canal {channel_id}: {title}")
                            await asyncio.sleep(1.5)
                        except discord.Forbidden:
                            logger.error(f"Permissão negada para enviar no canal {channel_id}")
                        except discord.HTTPException as e:
                            logger.error(f"HTTPException ao enviar para {channel_id}: {e}")
                        except Exception as e:
                            logger.error(f"Erro inesperado ao enviar para {channel_id}: {e}", exc_info=True)
                            await asyncio.sleep(5)
                    else:
                        logger.info(f"Limite diário de {DAILY_NEWS_LIMIT} notícias atingido para o canal {channel_id}. Notícia não enviada: {title}")
                else:
                    logger.info(f"Notícia já enviada para o canal {channel_id}: {title}")
        except Exception as e:
            logger.error(f"Erro ao processar item da fila: {e}", exc_info=True)

async def news_cycle():
    try:
        logger.info("\n" + "="*50)
                logger.info(f"{datetime.now().strftime("%H:%M:%S")} - Iniciando ciclo")
        success = await fetch_all_entries()
        if not success:
            logger.info("Tentando novamente no próximo ciclo...")
            return
        
        await send_batch()
        
        try:
            with open(SENT_FILE, \'w\', encoding=\'utf-8\') as f:
                yaml.dump(sent_articles, f)
            logger.info("Histórico salvo com sucesso.")
        except Exception as e:
            logger.error(f"Erro ao salvar histórico: {str(e)}", exc_info=True)
    except Exception as e:
        logger.error(f"Erro crítico no ciclo: {str(e)}", exc_info=True)
    finally:
        await asyncio.sleep(1)

async def news_cycle_task():
    """Tarefa contínua que roda a cada 30 minutos"""
    global daily_sent_count, last_reset_date

    while is_running:
        now = datetime.now()
        if last_reset_date is None or now.date() != last_reset_date:
            last_reset_date = now.date()
            daily_sent_count = 0
            logger.info("Contador de notícias diárias resetado.")

        if OPERATING_START_HOUR <= now.hour < OPERATING_END_HOUR:
            if daily_sent_count < DAILY_NEWS_LIMIT:
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
            else:
                logger.info(f"Limite diário de {DAILY_NEWS_LIMIT} notícias atingido. Aguardando o próximo dia.")
                await asyncio.sleep(INTERVAL)
        else:
            logger.info(f"Fora do horário de operação ({OPERATING_START_HOUR}h às {OPERATING_END_HOUR}h). Aguardando o próximo ciclo.")
            await asyncio.sleep(INTERVAL)

@client.event
async def on_ready():
    logger.info(f"\nBot conectado como {client.user}")
    modo_texto = "Dia exato" if DATE_MODE == 1 else "Últimas 24h"
    logger.info(f"Modo: {modo_texto}")
    
    global RSS_FEED_URLS
    if os.path.exists("config.yaml"):
        try:
            with open("config.yaml", \'r\', encoding=\'utf-8\') as f:
                cfg = yaml.safe_load(f)
                if cfg and \'feeds\' in cfg:
                    RSS_FEED_URLS = [f[\'url\'] for f in cfg.get(\'feeds\', []) if \'url\' in f]
                    logger.info(f"Fontes carregadas do config.yaml ({len(RSS_FEED_URLS)}):")
                else:
                    logger.warning("config.yaml encontrado, mas sem a chave \'feeds\' ou feeds vazios.")
        except Exception as e:
            logger.error(f"Erro ao carregar config.yaml: {e}", exc_info=True)
    
    logger.info(f"Fontes ativas ({len(RSS_FEED_URLS)}):")
    for url in RSS_FEED_URLS:
        logger.info(f"  - {url} -> {get_source_name(url)}")

    global sent_articles, daily_sent_count, last_reset_date
    try:
        if not os.path.exists(SENT_FILE):
            with open(SENT_FILE, \'w\', encoding=\'utf-8\') as f:
                yaml.dump({}, f)
            logger.info(f"Arquivo de histórico \'{SENT_FILE}\' criado.")

        with open(SENT_FILE, \'r\', encoding=\'utf-8\') as f:
            sent_articles = yaml.safe_load(f) or {}
            logger.info(f"Histórico carregado: {sum(len(v) for v in sent_articles.values())} links")
    except Exception as e:
        logger.error(f"Erro ao carregar ou criar histórico: {e}", exc_info=True)

    now = datetime.now()
    last_reset_date = now.date()
    daily_sent_count = 0
    clean_old_entries()

    tasks = [t for t in asyncio.all_tasks(loop=client.loop) if t.get_name() == "news_cycle_task"]
    if not tasks:
        client.loop.create_task(news_cycle_task(), name="news_cycle_task")
        logger.info("Tarefa de ciclo de notícias iniciada")
    else:
        logger.info("Tarefa de ciclo de notícias já está rodando.")

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


