# getex

Editor de texto modal para terminal Linux, inspirado no Vim. Salva documentos organizados por data na sua Área de Trabalho, tem integração com IA (Google Gemini ou OpenAI) e **sincronização opcional com o Firebase** (login por email/senha, funcionando online e offline).

---

> Funciona em **Linux**, **macOS** (Intel e Apple Silicon) e **Windows** (10/11). É Python puro com `curses` — sem framework.

## Instalação rápida (recomendada)

Baixe o repositório (ou os arquivos `getex.py` + o instalador, lado a lado).

### Linux e macOS

```bash
./install.sh
```

### Windows (PowerShell)

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

Os instaladores verificam o Python 3, instalam as dependências (no Windows também o `windows-curses`), instalam o comando `getex` e preparam a pasta da credencial. Depois é só abrir um **novo** terminal e rodar `getex`.

## Instalação manual

### 1. Baixe o script

Salve o arquivo `getex.py` em qualquer lugar da sua máquina (ex.: `~/Downloads/getex.py`).

### 2. Instale como comando global

```bash
sudo cp ~/Downloads/getex.py /usr/local/bin/getex
sudo chmod +x /usr/local/bin/getex
```

Pronto. A partir daí você pode rodar `getex` de qualquer lugar no terminal.

> **macOS:** `/usr/local/bin` já costuma estar no `PATH`. Se o comando não for encontrado depois, adicione ao seu `~/.zshrc`:
> ```bash
> echo 'export PATH="/usr/local/bin:$PATH"' >> ~/.zshrc && source ~/.zshrc
> ```

> **Windows:** não há `/usr/local/bin`. Use o `install.ps1` (recomendado) ou, manualmente, deixe o `getex.py` numa pasta e rode `python getex.py`. Para ter o comando `getex`, crie um `getex.bat` na mesma pasta com o conteúdo:
> ```bat
> @echo off
> python "%~dp0getex.py" %*
> ```
> e adicione essa pasta ao `PATH` do usuário. **É obrigatório** instalar o `windows-curses` (veja Dependências). Rode num terminal real: **Windows Terminal**, PowerShell ou `cmd` (não funciona dentro do output de uma IDE).

### 3. Verifique se funcionou

```bash
getex --help 2>/dev/null || echo "getex instalado com sucesso"
```

### Alternativa: alias no `.zshrc` (macOS) / `.bashrc` (Linux)

Se preferir não usar `sudo`:

```bash
# macOS (zsh é o padrão)
echo "alias getex='python3 ~/Downloads/getex.py'" >> ~/.zshrc && source ~/.zshrc

# Linux (bash)
echo "alias getex='python3 ~/Downloads/getex.py'" >> ~/.bashrc && source ~/.bashrc
```

### Dependências

**Linux/macOS:** para uso local, apenas Python 3 com a biblioteca padrão — o módulo `curses` já vem incluso.

```bash
python3 --version   # precisa ser 3.6 ou superior
```

**Windows:** o `curses` **não** vem no Python — instale o pacote `windows-curses` (mesmo para uso só local):

```powershell
pip install --user windows-curses
```

Para a **sincronização com o Firebase** (opcional), instale o SDK Admin:

```bash
# Linux (e macOS com Homebrew Python)
pip3 install --user --break-system-packages firebase-admin

# Se a sua instalação aceitar sem a flag, este também serve:
pip3 install --user firebase-admin
```

```powershell
# Windows
pip install --user firebase-admin
```

> O `getex` funciona 100% offline sem essa dependência — ela só é necessária para login e sincronização na nuvem. A flag `--break-system-packages` é exigida quando o Python é "externally-managed" (Ubuntu 23.04+ e Homebrew Python no macOS); a instalação `--user` vai para a sua pasta de usuário e não altera os pacotes do sistema. O `./install.sh` já tenta os dois automaticamente.

---

## Primeira execução

Na primeira vez que rodar `getex`, um assistente de configuração aparece no terminal:

```
╔══════════════════════════════════════╗
║   getex — Configuração Inicial       ║
╚══════════════════════════════════════╝

Nome da pasta na Área de Trabalho para os documentos? [GetexDocs]:
Provedor de IA? (gemini/openai) [gemini]:
Chave de API (gemini) [deixe em branco para depois]:
```

As respostas ficam salvas em `~/.getex_config` (arquivo JSON editável). Você pode alterar qualquer configuração depois pelo menu `:config` dentro do editor, editando esse arquivo diretamente ou usando o comando `:set key`.

---

## Sincronização com o Firebase (nuvem)

O getex pode guardar suas notas no **Cloud Firestore** e sincronizá-las entre máquinas, com **login por email e senha**. Tudo funciona **offline**: quando não há internet, você edita normalmente e as mudanças sobem assim que a conexão volta.

> Se o Firebase não estiver configurado, o getex roda em **modo local** (como sempre funcionou), sem pedir login.

### Como funciona

- As notas continuam sendo arquivos `.txt` na sua Área de Trabalho (continuam editáveis offline), agora separadas por workspace em `~/Desktop/<pasta>/<WORKSPACE>/`.
- Cada nota ganha um sidecar `NOME.txt.sync.json` com metadados de sincronização.
- **Online:** o getex empurra as notas alteradas e puxa as do seu workspace no Firestore.
- **Offline:** as mudanças ficam pendentes e sobem no próximo `:sync` (ou na próxima abertura online).
- **Conflitos:** vence a versão mais recente (last-write-wins por horário de edição).

### Workspaces

As notas pertencem a um **workspace**, e cada pessoa tem uma conta **dentro** de um workspace. Quem está no workspace vê as notas daquele workspace — e nada além.

- **Exemplos:** `PESSOAL` (só suas notas) e `UMTI` (notas da equipe). Quem está no `UMTI` vê só as notas do `UMTI`.
- **O nome do workspace é a chave primária** — é único. Não pode existir outro `UMTI`. Por isso **não há chave de acesso**: você não consegue "entrar" sozinho num workspace que já existe.
- **Quem cria o workspace vira o administrador.** É o admin que **adiciona e remove** os usuários daquele workspace (veja `:account` abaixo). Assim o `PESSOAL` continua só seu e o `UMTI` só tem quem você cadastrar.
- **A mesma pessoa pode ter contas em workspaces diferentes** (logins separados). Para trocar de workspace, use `:logout` e entre no outro.
- O nome do workspace é normalizado para maiúsculas (`umti` → `UMTI`).

### Configuração (uma vez)

1. No [console do Firebase](https://console.firebase.google.com/), crie o banco **Cloud Firestore** (modo Production/Native, escolha uma região).
2. Em **Configurações do projeto → Contas de serviço**, gere uma chave privada (JSON do *service account*).
3. Coloque o arquivo em:

   ```bash
   mkdir -p ~/.getex/firebase
   mv ~/Downloads/seu-service-account.json ~/.getex/firebase/service-account.json
   chmod 600 ~/.getex/firebase/service-account.json
   ```

   > O getex também aceita o caminho via variável `GETEX_FIREBASE_CRED`.
   > **Nunca** versione esse arquivo — ele dá acesso total ao banco.

4. Instale o SDK: `pip install --user --break-system-packages firebase-admin`.

### Login e cadastro

Ao abrir o `getex` com o Firebase configurado, aparece a **tela de login**:

- **Entrar:** informe **Workspace**, **Email** e **Senha** e pressione `Enter`.
- **Criar workspace:** pressione `F2` para alternar para o modo de criação (**Workspace / Nome / Email / Senha**) e `Enter`.
  - Cria um **novo** workspace e te torna o **administrador** dele.
  - Se o nome já existir, dá erro (ele é único) — nesse caso, peça ao admin do workspace para te **adicionar** (não há auto-cadastro em workspace existente).
- A sessão fica salva (`~/.getex/session.json`), então **nas próximas vezes você entra direto** no último workspace. Use `:logout` para sair ou trocar de workspace.
- O login **offline** funciona para o último (workspace + usuário) que entrou, usando a sessão em cache.

### Comandos de sincronização

| Onde | Comando | Ação |
|------|---------|------|
| Editor | `:sync` | Sincroniza agora com o Firebase |
| Editor | `:whoami` | Mostra o usuário/workspace e o status (online/offline) |
| Editor | `:account` | Conta: trocar senha, ver/remover membros do workspace |
| Editor | `:passwd` | Troca a sua senha |
| Editor | `:logout` | Encerra a sessão |
| Navegador | `s` | Sincroniza a lista com o Firebase |

### Conta e membros do workspace (`:account`)

- **Trocar senha** (`:passwd` ou pelo menu `:account`): pede a senha atual e a nova. Atualiza no Firebase e na sessão local.
- **Ver membros**: lista quem tem conta no workspace atual.

Para o **administrador** do workspace (quem o criou), aparecem também:

- **Adicionar usuário**: você informa email, nome e uma senha inicial; a conta é criada naquele workspace. Passe essas credenciais ao colega — ele troca a senha depois com `:passwd`.
- **Remover usuário**: escolha o membro e confirme; ele perde o acesso (a conta dele naquele workspace é apagada). Não é possível remover você mesmo nem o criador. As notas permanecem no workspace.

> Não há recuperação de senha esquecida — apenas troca autenticada. Se um membro esquecer a senha, o admin pode removê-lo e adicioná-lo de novo.

> ⚠️ **Segurança:** o *service account* ignora as regras do Firestore (acesso total), então o isolamento entre workspaces é garantido pela aplicação, não pelo banco. É adequado para uma equipe de confiança. O isolamento garantido pelo próprio banco (autenticação Firebase real + regras de segurança, ou um backend) é um endurecimento futuro.

### Dar acesso a um colega de equipe (ex.: um dev no Mac)

Não se compartilha senha: o **admin cadastra** o colega no workspace. Passo a passo para dar acesso ao `UMTI`:

1. O colega **baixa** o `getex.py` e o `install.sh` (lado a lado), roda `./install.sh` e coloca o `service-account.json` em `~/.getex/firebase/` (você envia esse arquivo a ele).
2. **Você (admin)**, dentro do `UMTI`, abre `:account` → **Adicionar usuário** e cria a conta dele (email + senha inicial).
3. Você passa a ele o **email e a senha inicial**.
4. O colega abre `getex` e faz **login**: Workspace = `UMTI`, mais o email/senha que você definiu. Depois ele troca a senha com `:passwd`.

Pronto: ele vê as notas do `UMTI`; as edições dele sobem e aparecem para você após um `:sync`. O seu workspace `PESSOAL` continua invisível para ele (ele não tem conta lá).

> 🔒 Você compartilha apenas a **credencial do projeto** (`service-account.json`) — nunca a sua senha. O acesso ao workspace é controlado por quem o admin cadastra.

---

## Comandos disponíveis

### `getex` — abre o editor

```bash
getex
```

Abre o editor com um buffer vazio pronto para digitação.

### `getex "titulo"` — abre com título

```bash
getex "reuniao de sprint"
getex "ideias produto Q3"
```

O título é incluído no nome do arquivo ao salvar: `DOC_2025-06-15_14-32_reuniao_de_sprint.txt`.

### `getex get all` — navegador de arquivos

```bash
getex get all
```

Abre um painel de dois painéis com todos os documentos salvos. Permite navegar, visualizar e abrir qualquer arquivo para edição.

---

## Usando o editor

O getex tem dois modos, como o Vim.

### Modo Comando (tela inicial)

É o modo padrão ao abrir. O fundo da barra de status fica **amarelo**.

| Tecla | Ação |
|-------|------|
| `i` | Entra no modo de inserção |
| `a` | Entra no modo de inserção após o cursor |
| `o` | Cria nova linha abaixo e entra em inserção |
| `k` ou `↑` | Move cursor para cima |
| `j` ou `↓` | Move cursor para baixo |
| `h` ou `←` | Move cursor para esquerda |
| `l` ou `→` | Move cursor para direita |
| `g` | Vai para a primeira linha |
| `G` | Vai para a última linha |
| `dd` | Apaga a linha atual |
| `F2` ou `2` | Marca/desmarca a linha atual em **verde** ● |
| `F3` ou `3` | Marca/desmarca a linha atual em **vermelho** ● |
| `:` | Abre prompt de comandos |

> 💡 **No Mac**, as teclas de função (`F2`/`F3`) costumam exigir segurar `Fn`. Por isso o getex também aceita **`2`** (verde) e **`3`** (vermelho) no modo comando — funcionam em qualquer teclado.

### Modo Inserção

Ativado pressionando `i`. O fundo da barra de status fica **ciano**.

| Tecla | Ação |
|-------|------|
| Digitar | Insere texto normalmente |
| `Esc` | Volta ao modo comando |
| `Backspace` | Apaga o caractere anterior |
| `Delete` | Apaga o caractere à frente |
| `Enter` | Insere nova linha |
| `↑ ↓ ← →` | Move o cursor |
| `Home` / `End` | Início / fim da linha |

---

## Seleção de texto

A seleção funciona no **modo de inserção**. O texto selecionado fica destacado em ciano.

### Selecionar

| Tecla | Seleciona |
|-------|-----------|
| `Shift + ↑` | Uma linha acima |
| `Shift + ↓` | Uma linha abaixo |
| `Shift + ←` | Um caractere à esquerda |
| `Shift + →` | Um caractere à direita |
| `Shift + Home` | Do cursor até o início da linha |
| `Shift + End` | Do cursor até o fim da linha |
| `Ctrl + Shift + ←` | Palavra inteira à esquerda |
| `Ctrl + Shift + →` | Palavra inteira à direita |
| `Ctrl + Shift + ↑` | Linha inteira para cima |
| `Ctrl + Shift + ↓` | Linha inteira para baixo |
| `Ctrl + A` | Tudo |

### Operar sobre a seleção

| Tecla | Ação |
|-------|------|
| `Ctrl + C` | Copia para o clipboard interno |
| `Ctrl + K` | Recorta |
| `Ctrl + V` | Cola na posição do cursor |
| `Delete` ou `Backspace` | Apaga a seleção |
| Qualquer tecla normal | Substitui a seleção pelo que foi digitado |
| Seta sem Shift ou `Esc` | Cancela a seleção sem apagar nada |

> **Nota:** `Ctrl + X` foi substituído por `Ctrl + K` porque o terminal Linux intercepta `Ctrl + X` antes do editor recebê-lo.

---

## Comandos do prompt `:`

No modo comando, pressione `:` para abrir o prompt. Digite o comando e pressione `Enter`. `Esc` cancela.

| Comando | Ação |
|---------|------|
| `:wq` | Salva e fecha |
| `:q!` | Fecha sem salvar |
| `:q` | Fecha (só funciona se o buffer estiver vazio) |
| `:rename Meu Titulo` | Define ou altera o nome do arquivo |
| `:title Meu Titulo` | Mesmo que `:rename` |
| `:ai` | Envia o texto para a IA e insere a resposta no buffer |
| `:set key SUACHAVE` | Define a chave de API sem sair do editor |
| `:config` | Abre o menu de configurações (pasta, tema, IA, chave) |
| `:theme` | Abre o menu de troca de tema de cores |
| `:sync` | Sincroniza as notas com o Firebase (quando online) |
| `:whoami` | Mostra o usuário logado e o status de conexão |
| `:logout` | Encerra a sessão atual |
| `:help` | Mostra a lista completa de comandos dentro do editor |

---

## Marcação de linhas (F2 / F3)

No modo comando você pode destacar linhas inteiras para revisão, sem alterar o texto:

| Tecla | Ação |
|-------|------|
| `F2` ou `2` | Marca a linha atual em **verde** (ou desmarca, se já estiver verde) |
| `F3` ou `3` | Marca a linha atual em **vermelho** (ou desmarca, se já estiver vermelha) |

- As marcações **acompanham a linha** quando você insere, apaga, recorta ou cola texto acima delas — elas continuam grudadas ao conteúdo original.
- Quando você apaga uma linha marcada (`dd`, junção de linhas, etc.), a marcação dela é removida junto.
- As marcações são **persistidas** num arquivo paralelo `NOME_DO_DOC.txt.marks` (JSON) ao salvar, e reaparecem coloridas tanto no editor quanto no preview do navegador (`getex get all`).

---

## Temas

O getex acompanha 5 temas de cores: `default`, `dark`, `light`, `hacker` e `ocean`.

- Troque pelo menu com `:theme` (use `↑↓` para pré-visualizar ao vivo e `Enter` para aplicar).
- Ou pelo menu de configurações com `:config`.
- O tema escolhido fica salvo em `~/.getex_config` na chave `"theme"`.

---

## Configurações (`:config`)

O comando `:config` abre um menu navegável para ajustar e salvar todas as configurações sem editar o JSON na mão:

| Item | O que faz |
|------|-----------|
| Pasta dos documentos | Define a pasta em `~/Desktop/` onde os documentos são salvos (cria a pasta na hora) |
| Tema de cores | Abre o seletor de temas com pré-visualização |
| Provedor de IA | Alterna entre `gemini` e `openai` |
| Chave de API | Define a chave de API (entrada mascarada) |

Navegue com `↑↓`, pressione `Enter` para alterar o item e `Esc`/`q` para voltar. Tudo é gravado em `~/.getex_config`.

---

## Onde os arquivos são salvos

Todos os documentos ficam em:

```
~/Desktop/
└── GetexDocs/              ← nome que você escolheu na configuração
    ├── DOC_2025-06-13_09-15.txt
    ├── DOC_2025-06-14_11-42_reuniao_sprint.txt
    └── DOC_2025-06-15_14-32_ideias_produto.txt
```

### Formato do nome

```
DOC_YYYY-MM-DD_HH-MM[_titulo].txt
     ───data───  hora  título (opcional)
```

A hora é incluída para evitar colisão quando você cria mais de um arquivo no mesmo dia.

### Comportamento ao salvar

| Situação | O que acontece |
|----------|----------------|
| Novo documento (`getex`) | Cria um arquivo novo com data e hora |
| Editar arquivo existente (`getex get all` → Enter) | **Sobrescreve** o arquivo — edições e exclusões são mantidas |

---

## Navegador de arquivos (`getex get all`)

Abre um painel dividido: lista de arquivos à esquerda, preview à direita.

| Tecla | Ação |
|-------|------|
| `↑` / `↓` ou `k` / `j` | Navegar entre arquivos |
| `n` | **Criar uma nova nota** — pede o nome e abre o editor |
| `Enter` | Abrir o arquivo selecionado no editor |
| `c` | Mostrar/ocultar o **calendário** de filtro por data |
| `←` / `→` ou `h` / `l` | Trocar de dia (com o calendário ativo); dias com arquivos ficam destacados |
| `r` | **Reorganizar o arquivo com IA** (reestrutura e sobrescreve o documento) |
| `s` | **Sincronizar** a lista com o Firebase |
| `PgUp` / `PgDn` | Rolar o preview sem trocar de arquivo |
| `Home` / `End` | Ir ao início / fim do preview |
| `d` | Deletar o arquivo selecionado (pede confirmação `s/n`) — a exclusão também é propagada para a nuvem |
| `Esc` ou `q` | Sair do navegador |

O preview à direita mostra as linhas marcadas com F2/F3 já coloridas.

---

## Integração com IA

### Configurar Google Gemini (gratuito)

1. Acesse [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)
2. Crie uma chave gratuita
3. Configure de um desses jeitos:
   - No wizard da primeira execução
   - Editando `~/.getex_config`
   - Dentro do editor com `:set key SUA_CHAVE`

### Configurar OpenAI

1. Acesse [platform.openai.com/api-keys](https://platform.openai.com/api-keys)
2. Edite `~/.getex_config` e altere `"ai_provider": "openai"`
3. Configure a chave normalmente

### Usar a IA

No modo comando, digite `:ai` e pressione `Enter`. O getex pega as últimas 20 linhas do buffer, envia para a IA e insere a resposta diretamente no texto com um separador visual.

---

## Configuração manual

```bash
nano ~/.getex_config
```

```json
{
  "folder_name": "MeusInsights",
  "ai_provider": "gemini",
  "api_key": "AIzaSy...",
  "theme": "default"
}
```

> Dica: em vez de editar este arquivo na mão, use o comando `:config` dentro do editor — ele ajusta e salva todas essas opções por um menu.

---

## Atualizar o getex

Quando uma nova versão do `getex.py` estiver disponível:

```bash
sudo cp ~/Downloads/getex.py /usr/local/bin/getex
```

As suas configurações em `~/.getex_config` e todos os documentos salvos são preservados.

---

## Desinstalar

```bash
sudo rm /usr/local/bin/getex
rm ~/.getex_config
```

Os documentos em `~/Desktop/GetexDocs/` não são apagados automaticamente.

---

## Resolução de problemas

**`Esc` demora para responder**
Já corrigido internamente com `set_escdelay(25)`. Se ainda ocorrer, verifique se a variável de ambiente `ESCDELAY` está definida no seu shell:
```bash
echo $ESCDELAY   # se retornar um valor alto, remova do seu .bashrc/.zshrc
```

**`Ctrl + Shift + seta` não funciona**
Depende do emulador de terminal enviar as sequências corretas. Funciona no GNOME Terminal, Tilix, Konsole e Alacritty. O `Shift + seta` simples sempre funciona como alternativa.

**Windows: `ModuleNotFoundError: No module named '_curses'` (ou 'curses')**
Falta o pacote `windows-curses`:
```powershell
pip install --user windows-curses
```
Rode o getex num terminal real (Windows Terminal, PowerShell ou `cmd`) — não dentro do painel de output de uma IDE.

**Pasta Desktop / Área de Trabalho**
O getex localiza a Área de Trabalho automaticamente, inclusive quando ela é redirecionada pelo **OneDrive** no Windows (`~/OneDrive/Desktop`) ou tem nome em português no Linux (`~/Área de trabalho`). Se mesmo assim não achar, ele cria `~/Desktop`. No Linux você pode forçar com um symlink:
```bash
ln -s ~/Área\ de\ trabalho ~/Desktop
```

**Erro de permissão ao instalar**
```bash
# Verifique se /usr/local/bin existe e está no PATH
echo $PATH | grep /usr/local/bin

# Se não estiver, adicione ao seu .bashrc
echo 'export PATH="/usr/local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```
