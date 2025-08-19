# Guia de Migração e Execução do Bot Discord no CasaOS (Debian 13)

## Autor: Manus AI

Este guia detalha o processo de migração e configuração do seu bot Discord de notícias para ser executado continuamente em um servidor CasaOS com base Debian 13. O objetivo é simplificar ao máximo as etapas, garantindo que o bot funcione de forma autônoma e eficiente 24 horas por dia.




## 2. Pré-requisitos

Antes de iniciar a migração do bot, certifique-se de que seu servidor CasaOS com Debian 13 atenda aos seguintes pré-requisitos:

### 2.1. Acesso SSH ao Servidor

Você precisará de acesso SSH ao seu servidor Debian 13 para transferir os arquivos do bot, instalar dependências e configurar o ambiente. Certifique-se de ter um cliente SSH configurado em sua máquina local (como o Terminal no Linux/macOS ou PuTTY no Windows) e as credenciais de login (nome de usuário e senha ou chave SSH) para o seu servidor.

### 2.2. Python 3 e Pip

O bot é escrito em Python 3, portanto, é essencial que o Python 3 e seu gerenciador de pacotes, `pip`, estejam instalados no servidor. O Debian 13 geralmente vem com Python 3 pré-instalado. Você pode verificar a instalação e a versão com os seguintes comandos:

```bash
python3 --version
pip3 --version
```

Se o Python 3 ou o pip3 não estiverem instalados, você pode instalá-los usando o gerenciador de pacotes `apt`:

```bash
sudo apt update
sudo apt install python3 python3-pip
```

### 2.3. Git (Opcional, mas Recomendado)

Embora você possa transferir os arquivos manualmente, o Git é altamente recomendado para gerenciar o código do seu bot, especialmente se você planeja fazer atualizações futuras. Para instalar o Git:

```bash
sudo apt install git
```

### 2.4. Variáveis de Ambiente

O bot utiliza variáveis de ambiente para armazenar informações sensíveis, como o token do Discord e os IDs dos canais. O arquivo `.env` fornecido é crucial para isso. Certifique-se de que essas variáveis estejam corretamente configuradas no servidor. Isso será abordado em detalhes na seção de configuração.

### 2.5. Dependências Python

O bot depende de algumas bibliotecas Python externas, listadas no arquivo `requirements.txt`. Estas serão instaladas usando `pip` durante o processo de configuração.

### 2.6. Permissões de Arquivo

Certifique-se de que o usuário que executará o bot no servidor tenha as permissões adequadas para ler e escrever nos diretórios onde os arquivos do bot serão armazenados, especialmente para o arquivo `sent_articles.yaml` e o `bot.log`.




## 3. Configuração do Ambiente

Esta seção detalha como configurar o ambiente no seu servidor Debian 13 para que o bot Discord possa ser executado corretamente.

### 3.1. Transferência dos Arquivos do Bot

Primeiro, você precisa transferir todos os arquivos do seu bot (incluindo `main.py`, `.env`, `requirements.txt`, `sent_articles.yaml`, `README.md`, `.gitignore` e `bot.log`) para o seu servidor CasaOS. Você pode fazer isso usando `scp` (Secure Copy Protocol) ou `git`.

#### 3.1.1. Usando SCP (Recomendado para Primeira Transferência)

No seu terminal local, navegue até o diretório onde os arquivos do bot estão salvos e execute o seguinte comando. Substitua `seu_usuario` pelo seu nome de usuário no servidor e `seu_ip_servidor` pelo endereço IP do seu servidor CasaOS.

```bash
scp -r . seu_usuario@seu_ip_servidor:/caminho/para/o/diretorio/do/bot
```

Por exemplo, se você quiser colocar os arquivos em `/home/seu_usuario/discord_bot`:

```bash
scp -r . seu_usuario@seu_ip_servidor:/home/seu_usuario/discord_bot
```

Após a transferência, conecte-se ao seu servidor via SSH:

```bash
ssh seu_usuario@seu_ip_servidor
```

E navegue até o diretório onde os arquivos foram transferidos:

```bash
cd /home/seu_usuario/discord_bot
```

#### 3.1.2. Usando Git (Recomendado para Atualizações Futuras)

Se você gerencia seu código com Git (por exemplo, no GitHub ou GitLab), você pode clonar o repositório diretamente no servidor. Primeiro, instale o Git se ainda não o fez (veja a seção de Pré-requisitos).

No seu servidor, navegue até o diretório onde você deseja clonar o repositório e execute:

```bash
git clone <URL_DO_SEU_REPOSITORIO>
cd <NOME_DO_SEU_REPOSITORIO>
```

### 3.2. Instalação das Dependências Python

Com os arquivos do bot no servidor, o próximo passo é instalar as bibliotecas Python listadas no `requirements.txt`. Certifique-se de estar no diretório do bot no terminal do servidor e execute:

```bash
pip3 install -r requirements.txt
```

Este comando lerá o arquivo `requirements.txt` e instalará todas as dependências necessárias, como `discord.py`, `feedparser`, `python-dotenv` e `pyyaml`.

### 3.3. Configuração das Variáveis de Ambiente (.env)

O arquivo `.env` contém as variáveis de ambiente essenciais para o funcionamento do bot. Ele deve estar no mesmo diretório que `main.py`. Abra o arquivo `.env` no servidor para verificar e, se necessário, editar as variáveis. Você pode usar um editor de texto como `nano` ou `vim`:

```bash
nano .env
```

Certifique-se de que as seguintes variáveis estejam configuradas corretamente:

*   `DISCORD_BOT_TOKEN`: O token do seu bot Discord. **Mantenha-o em segredo!**
*   `DISCORD_CHANNEL_IDS`: Uma lista de IDs de canais do Discord, separados por vírgulas, onde o bot enviará as notícias. Exemplo: `1234567890,9876543210`.
*   `RSS_FEED_URLS`: Uma lista de URLs de feeds RSS, separados por vírgulas, dos quais o bot buscará as notícias. Exemplo: `https://www.canaltech.com.br/feed/,https://www.seginfo.com.br/feed/`.
*   `DATE_MODE`: Define como o bot filtra as notícias por data. `1` para notícias do dia exato, `2` para notícias das últimas 24 horas. O padrão é `1`.

Exemplo de `.env`:

```
DISCORD_BOT_TOKEN=SEU_TOKEN_AQUI
DISCORD_CHANNEL_IDS=1234567890,9876543210
RSS_FEED_URLS=https://www.canaltech.com.br/feed/,https://www.seginfo.com.br/feed/
DATE_MODE=1
```

Após fazer as alterações, salve e saia do editor (no `nano`, `Ctrl+X`, `Y`, `Enter`).




## 4. Execução do Bot

Com os arquivos transferidos, dependências instaladas e variáveis de ambiente configuradas, você está pronto para executar o bot. Para garantir que o bot rode continuamente, mesmo após você fechar a sessão SSH, utilizaremos ferramentas como `screen` ou `systemd`.

### 4.1. Testando o Bot (Execução Manual)

Antes de configurar a execução contínua, é uma boa prática testar o bot manualmente para garantir que tudo esteja funcionando corretamente. No diretório do bot no seu servidor, execute:

```bash
python3 main.py
```

Você deverá ver mensagens de log no terminal indicando que o bot está se conectando ao Discord e buscando notícias. Verifique se o bot aparece online no Discord e se as notícias começam a ser enviadas para os canais configurados. Para parar o bot, pressione `Ctrl+C`.

### 4.2. Execução Contínua com `screen` (Método Simples)

`screen` é um multiplexador de terminal que permite que você inicie uma sessão e se desconecte dela, deixando os processos em execução. É uma maneira simples de manter o bot rodando em segundo plano.

#### 4.2.1. Instalar `screen`

Se você ainda não tem o `screen` instalado:

```bash
sudo apt install screen
```

#### 4.2.2. Iniciar o Bot em uma Sessão `screen`

No diretório do bot, inicie uma nova sessão `screen` com um nome descritivo (por exemplo, `discord_bot`):

```bash
screen -S discord_bot
```

Dentro da nova sessão `screen`, execute o bot:

```bash
python3 main.py
```

Agora, para se desconectar da sessão `screen` (deixando o bot rodando), pressione `Ctrl+A` e depois `D`.

Você pode fechar sua sessão SSH e o bot continuará em execução.

#### 4.2.3. Reconectar a uma Sessão `screen`

Para verificar o status do bot ou pará-lo, você pode se reconectar à sessão `screen`:

```bash
screen -r discord_bot
```

Se você tiver várias sessões `screen`, pode listar todas elas com `screen -ls` e depois se reconectar usando o ID da sessão.

Para parar o bot dentro da sessão `screen`, pressione `Ctrl+C`.

### 4.3. Execução Contínua com `systemd` (Método Robusto e Recomendado)

Para uma solução mais robusta e que garante que o bot inicie automaticamente com o sistema e seja reiniciado em caso de falha, é recomendado usar o `systemd`. Isso envolve a criação de um arquivo de serviço.

#### 4.3.1. Criar o Arquivo de Serviço `systemd`

Crie um novo arquivo de serviço para o seu bot. Substitua `seu_usuario` pelo seu nome de usuário no servidor e `/caminho/para/o/diretorio/do/bot` pelo caminho completo para o diretório onde você colocou os arquivos do bot.

```bash
sudo nano /etc/systemd/system/discord_bot.service
```

Cole o seguinte conteúdo no arquivo:

```ini
[Unit]
Description=Discord News Bot
After=network.target

[Service]
User=seu_usuario
WorkingDirectory=/caminho/para/o/diretorio/do/bot
ExecStart=/usr/bin/python3 main.py
Restart=always
RestartSec=10
StandardOutput=syslog
StandardError=syslog
SyslogIdentifier=discord_bot

[Install]
WantedBy=multi-user.target
```

**Explicação dos campos:**

*   `Description`: Uma breve descrição do seu serviço.
*   `After=network.target`: Garante que o serviço só inicie depois que a rede estiver disponível.
*   `User`: O usuário sob o qual o bot será executado. **É crucial que este seja o usuário que possui os arquivos do bot e tem permissão para executá-los.**
*   `WorkingDirectory`: O diretório onde o `main.py` e o `.env` estão localizados.
*   `ExecStart`: O comando para iniciar o bot. Certifique-se de que o caminho para `python3` esteja correto (você pode verificar com `which python3`).
*   `Restart=always`: Garante que o bot seja reiniciado automaticamente se ele travar ou for encerrado.
*   `RestartSec=10`: Espera 10 segundos antes de tentar reiniciar o bot.
*   `StandardOutput` e `StandardError`: Redireciona a saída do bot para o syslog, o que é útil para depuração.
*   `SyslogIdentifier`: Um identificador para as mensagens de log do seu bot no syslog.
*   `WantedBy=multi-user.target`: Garante que o serviço seja iniciado quando o sistema entrar no modo multiusuário (o que geralmente acontece na inicialização).

Salve e saia do editor.

#### 4.3.2. Habilitar e Iniciar o Serviço

Após criar o arquivo de serviço, você precisa recarregar o `systemd` para que ele reconheça o novo serviço, habilitá-lo para iniciar com o sistema e, em seguida, iniciá-lo:

```bash
sudo systemctl daemon-reload
sudo systemctl enable discord_bot.service
sudo systemctl start discord_bot.service
```

#### 4.3.3. Verificar o Status do Serviço

Para verificar se o bot está rodando e ver os logs:

```bash
sudo systemctl status discord_bot.service
```

Para ver os logs mais detalhados (útil para depuração):

```bash
sudo journalctl -u discord_bot.service -f
```

Para parar o serviço:

```bash
sudo systemctl stop discord_bot.service
```

Para reiniciar o serviço:

```bash
sudo systemctl restart discord_bot.service
```




## 5. Manutenção e Solução de Problemas

Manter seu bot funcionando sem problemas envolve monitoramento e a capacidade de diagnosticar e resolver problemas. Esta seção aborda as práticas comuns de manutenção e dicas de solução de problemas.

### 5.1. Verificando os Logs do Bot

O bot está configurado para registrar suas atividades no arquivo `bot.log` (no mesmo diretório do `main.py`) e, se você estiver usando `systemd`, também no syslog do sistema. Verificar esses logs é o primeiro passo para diagnosticar qualquer problema.

#### 5.1.1. Logs Locais (`bot.log`)

Para ver os logs mais recentes do `bot.log`:

```bash
tail -f bot.log
```

Isso exibirá as últimas linhas do arquivo e continuará mostrando novas linhas à medida que elas são adicionadas. Pressione `Ctrl+C` para sair.

#### 5.1.2. Logs do `systemd` (se estiver usando `systemd`)

Se você configurou o bot com `systemd`, os logs são redirecionados para o `journalctl`:

```bash
sudo journalctl -u discord_bot.service -f
```

Este comando mostrará os logs em tempo real do seu serviço `discord_bot.service`. É extremamente útil para ver o que está acontecendo com o bot no momento em que um problema ocorre.

### 5.2. Problemas Comuns e Soluções

#### 5.2.1. Bot Não Inicia ou Cai Imediatamente

*   **Verifique os logs:** Use `tail -f bot.log` ou `sudo journalctl -u discord_bot.service -f` para identificar mensagens de erro. Erros comuns incluem `DISCORD_BOT_TOKEN not found` ou problemas de importação de módulos Python.
*   **Variáveis de Ambiente:** Certifique-se de que o arquivo `.env` esteja no diretório correto e que todas as variáveis (especialmente `DISCORD_BOT_TOKEN`, `DISCORD_CHANNEL_IDS`, `RSS_FEED_URLS`) estejam preenchidas corretamente e sem erros de digitação. Lembre-se de que o token do bot deve ser mantido em segredo e não deve ser compartilhado publicamente.
*   **Dependências:** Verifique se todas as dependências do `requirements.txt` foram instaladas corretamente com `pip3 install -r requirements.txt`. Se houver erros durante a instalação, resolva-os.
*   **Caminhos:** No arquivo de serviço `systemd`, verifique se `WorkingDirectory` e `ExecStart` apontam para os caminhos corretos.
*   **Permissões:** O usuário que executa o bot (`User` no arquivo `systemd`) deve ter permissão de leitura e escrita no diretório do bot e nos arquivos de log/histórico (`bot.log`, `sent_articles.yaml`).

#### 5.2.2. Bot Não Envia Notícias

*   **Logs:** Verifique os logs para mensagens como `Feed inacessível ou vazio` ou `Erro ao enviar para canal`. Isso pode indicar problemas com os URLs dos feeds RSS ou com a conexão do bot ao Discord.
*   **URLs dos Feeds RSS:** Confirme se os URLs em `RSS_FEED_URLS` no seu `.env` estão corretos e acessíveis. Tente abri-los em um navegador para verificar.
*   **IDs dos Canais:** Verifique se os `DISCORD_CHANNEL_IDS` estão corretos e se o bot tem permissão para enviar mensagens nesses canais no Discord.
*   **Conexão com a Internet:** Certifique-se de que o servidor tenha uma conexão ativa com a internet.
*   **Taxa de Limite do Discord (Rate Limit):** Se o bot tentar enviar muitas mensagens muito rapidamente, o Discord pode impor um limite de taxa. O código do bot já possui `asyncio.sleep` para mitigar isso, mas em casos extremos, pode ser necessário ajustar os intervalos de envio.

#### 5.2.3. Atualizando o Código do Bot

Se você fizer alterações no código do bot (`main.py`) ou nas dependências (`requirements.txt`):

1.  **Transferir os arquivos atualizados:** Use `scp` ou `git pull` para transferir as novas versões dos arquivos para o servidor.
2.  **Reinstalar dependências (se `requirements.txt` mudou):**
    ```bash
    pip3 install -r requirements.txt
    ```
3.  **Reiniciar o bot:**
    *   Se estiver usando `screen`: Reconecte-se à sessão (`screen -r discord_bot`), pare o bot (`Ctrl+C`) e inicie-o novamente (`python3 main.py`).
    *   Se estiver usando `systemd`:
        ```bash
        sudo systemctl restart discord_bot.service
        ```

### 5.3. Monitoramento Contínuo

Para garantir a operação 24/7, considere configurar ferramentas de monitoramento para o seu servidor que possam alertá-lo sobre problemas de conectividade ou falhas no serviço do bot. O CasaOS pode ter funcionalidades de monitoramento integradas que você pode explorar.

Com este guia, você deve ser capaz de migrar e manter seu bot Discord de notícias funcionando de forma autônoma e eficiente no seu servidor CasaOS com Debian 13.



