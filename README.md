# Chat Terminal Pro

<p align="center">
<strong>Chat local e LAN para terminal</strong>  

  Comunicação simples, hospedagem integrada e controle administrativo.
</p> <p align="center">
  <img src="https://img.shields.io/badge/Python-3.11%2B-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/Rede-LAN-2ea44f?style=for-the-badge" alt="Rede LAN">
  <img src="https://img.shields.io/badge/Status-Experimental-orange?style=for-the-badge" alt="Experimental">
</p>

> **Aviso:** este projeto é experimental e deve ser usado somente em ambientes controlados. Leia a seção [Segurança, privacidade e limitações](#seguran%C3%A7a-privacidade-e-limita%C3%A7%C3%B5es) antes de colocar o servidor em funcionamento.

## Sobre o projeto

O **Chat Terminal Pro** é uma aplicação de conversas para redes locais. O projeto oferece criação de salas, descoberta de servidores na LAN, autenticação de usuários, painel administrativo e modo de hospedagem integrado ao chat.

No modo **Hospedar e conversar**, o servidor roda em segundo plano e o host entra automaticamente na própria sala usando o mesmo terminal. Não é necessário abrir duas janelas de terminal.

## Funcionalidades

| Área | Recursos |
| --- | --- |
| Conversas | Mensagens em tempo real, histórico local, comandos `/help`, `/list`, `/stats`, `/me` e `/clear` |
| Conexão | QuickServer, descoberta LAN, conexão manual por IP e porta, retentativas e keepalive |
| Hospedagem | Configuração completa da sala, limite de usuários, porta, visibilidade e mensagem de entrada |
| Administração | Usuários online, avisos, expulsão, banimento, promoção e alteração de configurações |
| Segurança | Criptografia de mensagens, hashes de senha, tokens de sessão, rate limit e validação de payloads |
| Integridade | Manifesto SHA-256 para detectar arquivos Python alterados antes da abertura da rede |

## Requisitos

- Python **3.11 ou superior**.

- Dependência `cryptography`.

- Rede local com portas TCP e UDP permitidas pelo firewall, quando a descoberta LAN for usada.

## Instalação

Clone o repositório e entre na pasta do projeto:

```bash
git clone URL_DO_SEU_REPOSITORIO
cd CMD_Chating
```

Instale as dependências:

```bash
python -m pip install -r requirements.txt
```

No Windows, se o comando `python` não estiver disponível, use:

```
py -m pip install -r requirements.txt
```

## Iniciar o aplicativo

Para abrir o menu principal:

```bash
python main.py
```

No Windows:

```
py main.py
```

O menu é dividido em três áreas:

| Área | Opções |
| --- | --- |
| Entrar em uma sala | Conectar automaticamente, Procurar salas, Conectar por endereço |
| Criar uma sala | Hospedar e conversar, Hospedar sem conversar |
| Conta | Perfil |

## Comandos principais

```
python main.py quickserver       conecta automaticamente no melhor servidor
python main.py host              configura, hospeda e entra no chat
python main.py list-servers      procura salas na rede local
python main.py connect IP PORTA  conecta a um endereço específico
python main.py serve PORTA       configura e hospeda sem abrir o chat
python main.py reset-profile     remove o perfil local
```

Ao hospedar uma sala, a aplicação sempre solicita a configuração. Salas novas são privadas por padrão. O host pode escolher torná-las públicas para aparecerem na descoberta da LAN.

## Comandos do chat

| Comando | Função |
| --- | --- |
| `/help` | Mostra a ajuda contextual. |
| `/whoami` | Exibe o usuário e o cargo atual. |
| `/list` | Lista os usuários online. |
| `/stats` | Mostra ocupação e tempo de atividade da sala. |
| `/me texto` | Envia uma ação estilizada. |
| `/clear` | Limpa a tela local. |
| `/time` | Mostra data e hora local. |
| `/logout` | Remove o login automático do servidor atual. |
| `/sair` | Encerra a sessão. |
| `!!` | Repete a última mensagem enviada. |

## Painel administrativo

Inicie o painel local com:

```bash
python admin.py
```

O painel possui opções para abrir o aplicativo, consultar usuários, acessar o console remoto, promover usuários, banir, desbanir e alterar a senha do painel.

Comandos do console remoto:

```
/online       lista usuários conectados
/aviso texto  envia um aviso para a sala
/expulsar ID  desconecta um usuário
/status       mostra o status do servidor
/parar        encerra o servidor
/promover ID  concede administração
/banir ID     bloqueia um usuário
/desbanir ID  remove o bloqueio
/ajuda        mostra os comandos disponíveis
/voltar       retorna ao painel
```

## Verificação de integridade

O arquivo `integrity.json` contém hashes SHA-256 dos arquivos Python. O `main.py` verifica o manifesto antes de iniciar o aplicativo. Se detectar arquivo alterado, removido ou adicionado, a execução é interrompida antes da abertura de sockets.

Gere o manifesto apenas em uma cópia revisada e confiável:

```bash
CHAT_INTEGRITY_BUILD=1 python main.py --generate-integrity
```

No Windows:

```
set CHAT_INTEGRITY_BUILD=1
py main.py --generate-integrity
```

Depois de gerar o manifesto, não modifique os arquivos Python. Qualquer alteração exige a geração de um novo manifesto em ambiente confiável.

> O verificador detecta alterações acidentais e adulterações simples. Ele não consegue proteger um executável contra alguém que tenha controle total sobre o próprio executável, pois essa pessoa pode modificar ou remover o verificador. Para releases públicos, use assinatura digital do executável e publique o hash ou a assinatura oficial.

## Gerar executáveis no Windows

Instale o PyInstaller:

```
py -m pip install pyinstaller
```

Gere o aplicativo principal:

```
py -m PyInstaller --noconfirm --clean --onefile --console --name ChatTerminal --add-data "integrity.json;." --add-data "main.py;." --add-data "admin.py;." --add-data "core;core" --add-data "ui;ui" main.py
```

Gere o painel administrativo:

```
py -m PyInstaller --noconfirm --clean --onefile --console --name ChatTerminalAdmin --add-data "integrity.json;." --add-data "main.py;." --add-data "admin.py;." --add-data "core;core" --add-data "ui;ui" admin.py
```

Os executáveis serão criados na pasta `dist`:

```
dist\ChatTerminal.exe
dist\ChatTerminalAdmin.exe
```

Use `--console`, pois o projeto é uma aplicação de terminal.

## Segurança, privacidade e limitações

O projeto aplica criptografia de mensagens, hashes de senha com salt individual, tokens de sessão, limite de tentativas de login, limite de cadastro por IP, limite de mensagens, handshake com timeout e validação de payloads.

Essas medidas reduzem riscos comuns, mas não transformam o projeto em uma solução de segurança profissional ou anônima.

### IP e anonimato

Uma conexão TCP direta revela o IP do cliente ao servidor e o IP do servidor à rede. Um programa executado no próprio computador não consegue esconder o endereço de um servidor ao qual ele se conecta diretamente.

Para privacidade de rede, use uma VPN confiável, Tor ou um relay/proxy separado. Não exponha a porta do servidor diretamente à internet sem firewall, autenticação forte e uma arquitetura intermediária adequada.

### Arquivos e malware

O Chat Terminal Pro não possui funcionalidade de upload, download ou execução de arquivos recebidos pelo chat. Ainda assim, nenhum aplicativo pode garantir proteção absoluta contra uma versão modificada, um executável adulterado ou um computador já comprometido.

Baixe releases somente de fontes confiáveis. Verifique a assinatura digital ou o hash do executável quando disponível. Mantenha o sistema operacional, o firewall e o antivírus atualizados.

## Disclaimer e isenção de responsabilidade

> **LEIA COM ATENÇÃO:** este software é fornecido **“no estado em que se encontra”**, sem garantias expressas ou implícitas. Os autores, mantenedores e colaboradores não se responsabilizam por qualquer dano direto ou indireto, perda de dados, falha de conexão, invasão, malware, roubo de informações, exposição de endereço IP, abuso de usuários, conteúdo enviado por terceiros, indisponibilidade, prejuízo financeiro ou qualquer outro problema decorrente do uso, da configuração, da distribuição ou da modificação da plataforma.O usuário é integralmente responsável por avaliar o código, configurar corretamente o ambiente, proteger suas credenciais, controlar quem pode acessar o servidor, manter o firewall ativo e cumprir as leis aplicáveis. O projeto não autoriza, incentiva ou garante proteção contra atividades ilícitas praticadas por usuários ou terceiros.Nenhuma informação neste repositório constitui promessa de anonimato, segurança absoluta ou adequação a finalidade específica. Ao instalar, compilar, executar ou distribuir o software, você reconhece esses riscos e concorda em utilizá-lo por sua própria conta e risco.

Esse disclaimer é informativo e não substitui uma revisão jurídica para a jurisdição em que o projeto será distribuído.

## Contribuição

Contribuições são bem-vindas. Antes de abrir um pull request, verifique a sintaxe do projeto, não inclua bancos, tokens, perfis ou configurações privadas e atualize o manifesto de integridade apenas a partir de uma cópia revisada.

```bash
python -m compileall -q .
```

## Licença

Defina uma licença antes de publicar o repositório. Se nenhuma licença for adicionada, os direitos autorais permanecem reservados por padrão. Uma opção comum para projetos permissivos é a [3], mas a escolha deve refletir a intenção dos autores.

## Referências

[1]: https://docs.python.org/3/ "Documentação oficial do Python"

[2]: https://pyinstaller.org/en/stable/ "Documentação oficial do PyInstaller"

[3]: https://choosealicense.com/licenses/mit/ "MIT License e guia de escolha de licença"
