# Tutorial: Configuração do Gemini CLI em WSL

**Autor:** Daniel Polónia · **Data:** 28 de fevereiro de 2026  
**Ambiente:** WSL2 Ubuntu + Conda (base) · **Projeto:** `202602-fct-proposal-engine`

---

## 0. Pré-requisitos verificados

Já tens WSL2 a funcionar com conda. Confirma antes de avançar:

```bash
# Deves ver "2" na coluna VERSION
wsl -l -v          # (executar no PowerShell do Windows)

# Dentro do WSL, confirma que tens git e conda
git --version
conda --version
```

---

## 1. Instalar Node.js via NVM (recomendado)

O Gemini CLI é uma aplicação Node.js. A forma mais segura de instalar
Node.js em WSL — sem conflitos com conda — é via NVM (Node Version Manager).

```bash
# 1a. Descarregar e instalar NVM
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | bash

# 1b. Carregar NVM na sessão actual (ou fechar e reabrir o terminal)
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"

# 1c. Instalar Node.js 22 LTS (estável)
nvm install 22

# 1d. Verificar
node -v    # deve mostrar v22.x.x
npm -v     # deve mostrar 10.x.x ou superior
```

> **Nota:** NVM adiciona automaticamente linhas ao teu `~/.bashrc`.
> Se usas zsh, verifica `~/.zshrc`.

---

## 2. Instalar o Gemini CLI

```bash
# 2a. Instalar globalmente via npm
npm install -g @google/gemini-cli

# 2b. Verificar instalação
gemini --version
```

Se receberes erros de permissão, **nunca uses `sudo`**. Em vez disso:

```bash
mkdir -p ~/.npm-global
npm config set prefix '~/.npm-global'
echo 'export PATH="$HOME/.npm-global/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
npm install -g @google/gemini-cli
```

### Alternativa sem instalação permanente

```bash
# Executar directamente sem instalar
npx @google/gemini-cli
```

---

## 3. Obter a API Key do Gemini

### 3a. Ir ao Google AI Studio

1. Abrir no browser: **https://aistudio.google.com**
2. Iniciar sessão com a tua conta Google (`dpolonia@gmail.com` ou `dpolonia@ua.pt`)
3. Aceitar os Termos de Serviço (na primeira vez, cria automaticamente um projecto GCP e uma chave)

### 3b. Criar/copiar a API Key

1. No AI Studio, clicar em **"Get API Key"** (menu lateral esquerdo)
2. Clicar em **"Create API Key"**
3. Seleccionar o projecto GCP (ou criar um novo)
4. **Copiar a chave** — algo como `AIzaSyB...` (39 caracteres)

### 3c. Restringir a chave (IMPORTANTE para segurança)

Na Google Cloud Console (https://console.cloud.google.com):

1. Ir a **APIs & Services → Credentials**
2. Clicar na chave que acabaste de criar
3. Em **"API restrictions"**, seleccionar **"Restrict key"**
4. Seleccionar apenas **"Generative Language API"**
5. Guardar

Isto garante que mesmo se a chave for exposta, só pode ser usada
para chamadas ao Gemini — não a outros serviços Google.

---

## 4. Configurar a API Key no ambiente WSL

### Opção A — Variável de ambiente persistente (recomendado para CLI)

```bash
# Adicionar ao .bashrc para persistir entre sessões
echo 'export GOOGLE_API_KEY="AIzaSy...COLA_A_TUA_CHAVE_AQUI"' >> ~/.bashrc
source ~/.bashrc

# Verificar
echo $GOOGLE_API_KEY
```

### Opção B — Ficheiro .env do projecto (para o fct-proposal-engine)

```bash
cd ~/202602-fct-proposal-engine

# Editar o .env que já existe
nano .env
```

Garantir que contém:

```env
GOOGLE_API_KEY=AIzaSy...COLA_A_TUA_CHAVE_AQUI
```

> **Segurança:** O `.env` já está no `.gitignore` — nunca será
> enviado para o GitHub. Confirma com `grep ".env" .gitignore`.

---

## 5. Primeira execução e autenticação

```bash
cd ~/202602-fct-proposal-engine

# Lançar o Gemini CLI
gemini
```

Na primeira execução:

1. **Aparência:** Escolhe o tema do terminal (dark/light)
2. **Autenticação:** Escolhe uma das opções:
   - **"Login with Google"** — abre um URL no browser; autentica-te
     e regressa ao terminal (funciona se o WSL tiver WSLg ou se copiares o URL para o browser do Windows)
   - **"Use API Key"** — se já configuraste `GOOGLE_API_KEY` na variável
     de ambiente, é detectada automaticamente

Após autenticação, deves ver o prompt interactivo:

```
  ✦ Welcome to Gemini CLI!
  >
```

### Resolver o problema do browser em WSL

Se o `gemini` tentar abrir um browser Linux e falhar:

```bash
# Configurar o WSL para usar o browser do Windows
echo 'export BROWSER="/mnt/c/Program Files/Google/Chrome/Application/chrome.exe"' >> ~/.bashrc
source ~/.bashrc
```

Alternativa: copiar manualmente o URL que aparece no terminal e colá-lo
no Chrome/Edge do Windows.

---

## 6. Testar com o projecto

### 6a. Teste básico

```bash
cd ~/202602-fct-proposal-engine
gemini
```

No prompt interactivo, experimenta:

```
> Review src/generators/pipeline.py against the Review Mandate in GEMINI.md
> Check src/utils/llm_client.py for missing error handling and retry logic
> Audit all source files for hard-coded preferences that should be in config.yaml
```

### 6b. Prompt one-shot (sem modo interactivo)

```bash
# Rever o último commit
gemini -p "Review the changes in the last commit: $(git diff HEAD~1)"

# Rever um ficheiro específico
gemini -p "Review src/reviewers/panel_reviewer.py — focus on async correctness"

# Melhorar um módulo
gemini -p "Enhance src/utils/llm_client.py — focus on reliability and retry logic"

# Scan de segurança
gemini -p "Check all Python files for leaked secrets or PII in log output"
```

### 6c. Workflow integrado com Claude Code

O fluxo recomendado é: Claude Code implementa, Gemini revê.

```bash
# 1. Claude Code faz alterações
claude -p "Add input validation to pipeline.py"

# 2. Gemini revê as alterações
gemini -p "Review the staged changes: $(git diff --cached). Classify as BLOCKER/ISSUE/SUGGEST"

# 3. Claude Code corrige os blockers
claude -p "Fix the blockers identified: [cola aqui o output do Gemini]"

# 4. Gemini confirma
gemini -p "Re-review: $(git diff --cached). Are all blockers resolved?"
```

---

## 7. Configuração avançada: GEMINI.md

O Gemini CLI lê o ficheiro `GEMINI.md` na raiz do projecto como contexto,
tal como o Claude Code lê o `CLAUDE.md`. No nosso projecto, o `GEMINI.md`
define o papel do Gemini como **code reviewer e enhancer** — não como
construtor de funcionalidades (isso é o papel do Claude Code).

O ficheiro já existe na raiz do repositório. Consulta-o para entender o
mandato completo:

```bash
cat ~/202602-fct-proposal-engine/GEMINI.md
```

Em resumo, o `GEMINI.md` instrui o Gemini CLI a:

- **Rever** código produzido pelo Claude Code contra 7 dimensões
  (correctness, architecture conformance, robustness, security,
  code quality, testing, documentation)
- **Classificar** achados como 🔴 BLOCKER / 🟡 ISSUE / 🟢 SUGGEST
- **Melhorar** módulos com foco em fiabilidade, testabilidade,
  performance e developer experience
- **Nunca** construir funcionalidades novas, reescrever módulos inteiros,
  ou alterar constantes regulatórias

---

## 8. Usar o Gemini CLI com API Key (modo programático)

Para o `fct-proposal-engine` que usa o Gemini como reviewer:

```bash
cd ~/202602-fct-proposal-engine

# Confirmar que o .env tem a chave
grep GOOGLE_API_KEY .env

# Activar o ambiente Python (se tiveres)
conda activate base   # ou o ambiente específico do projecto

# Testar a API key via Python (como o llm_client.py faz)
python3 -c "
from google import genai
import os
from dotenv import load_dotenv
load_dotenv()
client = genai.Client(api_key=os.getenv('GOOGLE_API_KEY'))
response = client.models.generate_content(
    model='gemini-2.5-flash',
    contents='Say hello in Portuguese.'
)
print(response.text)
"
```

Se vires `Olá!` ou equivalente, a API key funciona correctamente.

---

## 9. Quotas e limites (tier gratuito)

| Modelo | Pedidos/min | Pedidos/dia | Tokens input/min |
|--------|-------------|-------------|------------------|
| gemini-2.5-flash | 15 | 1 500 | 1 000 000 |
| gemini-2.5-pro | 5 | 50 | 1 000 000 |

Para o pipeline do `fct-proposal-engine`, o `gemini-2.5-flash`
é suficiente como reviewer (persona `gemini_feasibility` no config.yaml).
Com 3 iterações e 1 draft, consumirás ~15-20 pedidos por execução completa.

Monitoriza o uso em: **https://aistudio.google.com** → **Usage and Limits**

---

## 10. Resolução de problemas

### "command not found: gemini"

```bash
# Verificar se está instalado e onde
npm list -g @google/gemini-cli
which gemini

# Se instalaste via nvm, garantir que está carregado
source ~/.nvm/nvm.sh
```

### "GOOGLE_API_KEY not set"

```bash
# Verificar em ambas as fontes
echo $GOOGLE_API_KEY             # variável de ambiente
grep GOOGLE_API_KEY .env         # ficheiro .env local
```

### "Rate limit exceeded"

O tier gratuito tem limites apertados no `gemini-2.5-pro` (5 rpm, 50 rpd).
Para o pipeline, usa o flash:

```yaml
# No config.yaml, confirmar:
reviewers:
  - id: gemini_feasibility
    provider: google
    model: gemini-2.5-flash    # NÃO usar gemini-2.5-pro
```

### Browser não abre para autenticação

```bash
# Usar autenticação via API key em vez de OAuth
export GOOGLE_API_KEY="a-tua-chave"
gemini    # detecta automaticamente, não pede browser
```

### Erro "Cannot find module"

```bash
# Reinstalar limpo
npm uninstall -g @google/gemini-cli
npm cache clean --force
npm install -g @google/gemini-cli
```

---

## 11. Resumo dos comandos essenciais

```bash
# --- Instalação ---
nvm install 22                          # Node.js
npm install -g @google/gemini-cli       # Gemini CLI

# --- Configuração ---
export GOOGLE_API_KEY="AIzaSy..."       # API key

# --- Uso interactivo ---
cd ~/202602-fct-proposal-engine
gemini                                  # modo interactivo
> /help                                 # ver comandos disponíveis
> /quit                                 # sair

# --- Uso one-shot ---
gemini -p "Explain this codebase"       # prompt directo
gemini -p "..." --output-format json    # output estruturado

# --- No projecto Python ---
python3 -c "from google import genai; ..."  # testar API
```

---

## Referências

- Repositório oficial: https://github.com/google-gemini/gemini-cli
- Documentação: https://geminicli.com/docs/get-started/installation/
- API Keys: https://aistudio.google.com
- Quotas: https://ai.google.dev/gemini-api/docs/rate-limits
