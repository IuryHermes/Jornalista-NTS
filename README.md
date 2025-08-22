# 📰 Jornalista NTS - Bot de Notícias para Discord

Bot automático que coleta e envia notícias de tecnologia, segurança, Linux e games para canais do Discord.

## ✨ Funcionalidades
- 📡 Coleta notícias de 16 fontes RSS em português
- ⏰ Funciona das 8h às 21h (horário brasileiro)
- 🔄 Verifica a cada 1 hora
- 🚫 Não repete notícias (banco de dados SQLite)
- 📊 Logs detalhados para monitoramento

## 🚀 Instalação Rápida

```bash
# Clone o repositório
git clone https://github.com/IuryHermes/Jornalista-NTS.git
cd Jornalista-NTS

# Instale dependências
pip install -r requirements.txt

# crie e Configure o arquivo .env
echo 'DISCORD_TOKEN=seu_token_aqui' > .env
echo 'DISCORD_CHANNEL_ID=id_do_canal' >> .env

# Execute o bot
python main.py
