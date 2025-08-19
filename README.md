📰 Jornalista NTS – Bot de Notícias para Discord






O Jornalista NTS é um bot para Discord que envia automaticamente notícias de várias fontes de tecnologia, segurança e entretenimento diretamente para os canais configurados no servidor.

✨ Funcionalidades

📡 Coleta notícias de múltiplas fontes RSS.

⏰ Publica dentro de horários configurados.

📌 Permite escolher os canais onde as notícias serão postadas.

🔒 Configuração via arquivo .env para manter segurança do token.

🖥️ Código 100% em Python.

🚀 Instalação e Configuração
1. Clonar o repositório
git clone https://github.com/IuryHermes/Jornalista-NTS.git
cd Jornalista-NTS

2. Criar ambiente virtual (opcional, mas recomendado)
python -m venv venv
source venv/bin/activate   # Linux/Mac
venv\Scripts\activate      # Windows

3. Instalar dependências
pip install -r requirements.txt

4. Configurar variáveis no .env

Crie um arquivo .env na raiz do projeto (ou edite o existente) com os dados do bot:

DISCORD_TOKEN=seu_token_aqui
CHANNEL_IDS=123456789012345678,987654321098765432


DISCORD_TOKEN → Token do seu bot no Discord Developer Portal
.

CHANNEL_IDS → IDs dos canais onde as notícias serão postadas (separados por vírgula).

5. Executar o bot
python main.py

📡 Fontes de Notícias

Atualmente o bot publica notícias de:

🌐 Canaltech

🎮 UOL Jogos

🔒 SegInfo

🎬 Anime United

📂 Outros feeds configurados

📷 Exemplo no Discord:<img width="907" height="456" alt="image" src="https://github.com/user-attachments/assets/350061ae-3887-41cb-a06e-fc71639162e4" />

🤝 Contribuição

Quer sugerir novas fontes de notícias ou melhorar o bot?
Faça um fork do repositório, crie uma branch e abra um Pull Request!

📜 Licença

Este projeto está sob a licença MIT – fique à vontade para usar e modificar.
