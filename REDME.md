CHAT TERMINAL PRO - Guia rápido
===============================

Chat local/LAN com perfil global, autenticação segura, descoberta de salas e hospedagem em segundo plano.

VERIFICAÇÃO DE INTEGRIDADE:
  Ao iniciar, main.py compara SHA-256 de todos os arquivos Python com integrity.json.
  Se um arquivo for alterado, removido ou adicionado, o aplicativo encerra antes de abrir sockets ou iniciar a rede.
  O manifesto deve ser gerado somente em uma cópia revisada:

    CHAT_INTEGRITY_BUILD=1 python main.py --generate-integrity

  Depois de gerar, revise os arquivos, faça commit do integrity.json e, de preferência, assine o release.
  Não use --generate-integrity em uma máquina ou pasta que você não confia.

LIMITES DO MODELO DE SEGURANÇA:
  Um verificador dentro do mesmo código não consegue impedir um atacante com controle total do executável de remover o próprio verificador.
  Para distribuição forte, compile em ambiente limpo, assine digitalmente o executável e publique o hash ou assinatura por um canal confiável.
  O usuário deve baixar somente releases oficiais e verificar a assinatura antes de executar.
  O manifesto detecta alterações acidentais ou modificações simples; não substitui assinatura digital, antivírus ou sandbox.

PRIVACIDADE E REDE:
  Uma conexão TCP direta revela o IP do cliente ao servidor e o IP do servidor à rede.
  Para anonimato de rede, use VPN, Tor ou um relay/proxy administrado separadamente.
  O programa não envia nem executa arquivos locais.
  Salas novas ficam privadas por padrão.

SEGURANÇA DE PROTOCOLO:
  Handshake de autenticação expira após 12 segundos.
  Frames criptografados são limitados a 64 KB.
  Payloads rejeitam tipos inesperados e campos grandes.
  Cadastro, login e mensagens têm limites contra abuso e spam.

ESTADO DE FÁBRICA:
  Esta cópia não contém banco de usuários, configuração de sala ou credenciais.
  Nenhum Owner vem configurado por padrão.

MENU PRINCIPAL:
  Conectar automaticamente, Procurar salas, Conectar por endereço
  Hospedar e conversar, Hospedar sem conversar
  Perfil

COMANDOS:
  python main.py                 abre o menu
  python main.py quickserver     conexão automática
  python main.py host            configura, hospeda e conversa
  python main.py list-servers    procura salas na rede
  python main.py connect IP PORTA
  python main.py serve PORTA
  python main.py reset-profile   apaga o perfil local

ADMINISTRAÇÃO:
  O primeiro usuário registrado no banco local recebe administração inicial da instalação.
  Use python admin.py para abrir o painel local.
