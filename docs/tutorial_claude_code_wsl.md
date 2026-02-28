# Tutorial: Configuração do Claude Code em WSL

**Autor:** Daniel Polónia · **Data:** 28 de fevereiro de 2026  
**Ambiente:** WSL2 Ubuntu + Conda (base) · **Projeto:** `202602-fct-proposal-engine`

---

## 0. O que é o Claude Code

O Claude Code é um assistente de programação agêntico da Anthropic que corre
diretamente no terminal. Pode ler ficheiros, editar código, executar comandos,
fazer commits no Git e navegar codebases completas — tudo via conversação
natural. É a ferramenta ideal para operacionalizar o `fct-proposal-engine`.

### Opções de pagamento

| Plano | Preço | Claude Code incluído? | Limites |
|-------|-------|-----------------------|---------|
| **Pro** | $20/mês | Sim | ~45 mensagens/5h, partilhado com claude.ai |
| **Max 5×** | $100/mês | Sim | 5× mais que Pro, acesso a Opus |
| **Max 20×** | $200/mês | Sim | 20× mais que Pro, acesso total a Opus |
| **API** | Pay-per-use | Sim (com API key) | Sem limites fixos, paga por token |

**Recomendação para o nosso caso:** O plano **Pro ($20/mês)** é suficiente
para executar o pipeline do `fct-proposal-engine` (que faz ~50-100 chamadas por
execução completa). Se já tens uma subscrição claude.ai Pro ou Max, o Claude
Code já está incluído — não precisas de pagar mais nada.

---

## 1. Pré-requisitos

Já tens WSL2 a funcionar. Confirma:

```bash
# No terminal WSL
git --version         # deve mostrar 2.x
python3 --version     # deve mostrar 3.x
conda --version       # confirma o (base)
```

---

## 2. Instalar o Claude Code

### Método A — Instalador nativo (RECOMENDADO, sem Node.js)

Este é o método oficial desde 2026. Não precisa de Node.js:

```bash
# Descarregar e instalar
curl -fsSL https://claude.ai/install.sh | bash

# Verificar instalação
claude --version
```

Se o comando `claude` não for encontrado após instalação:

```bash
# O instalador adiciona ao PATH, mas pode ser preciso recarregar
source ~/.bashrc

# Se ainda não funcionar, adicionar manualmente
echo 'export PATH="$HOME/.claude/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

### Método B — Via npm (alternativa, se o A falhar)

Requer Node.js 18+:

```bash
# Se ainda não instalaste NVM/Node (do tutorial Gemini)
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | bash
source ~/.nvm/nvm.sh
nvm install 22

# Configurar directório global npm (evita sudo)
mkdir -p ~/.npm-global
npm config set prefix '~/.npm-global'
echo 'export PATH="$HOME/.npm-global/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc

# Instalar Claude Code (NUNCA usar sudo)
npm install -g @anthropic-ai/claude-code

# Verificar
claude --version
```

> **IMPORTANTE:** Se anteriormente instalaste via npm e agora queres
> migrar para o instalador nativo:
> ```bash
> curl -fsSL https://claude.ai/install.sh | bash
> npm uninstall -g @anthropic-ai/claude-code
> ```

---

## 3. Autenticação — Escolher o método

Tens duas opções de autenticação, dependendo de como queres pagar.

### Opção A — Subscrição Claude Pro/Max (login via browser)

Se já tens uma subscrição claude.ai (Pro $20 ou Max $100/$200):

```bash
cd ~/202602-fct-proposal-engine
claude
```

Na primeira execução:
1. Escolhe o tema (dark/light)
2. Selecciona **"Login with Google"** ou **"Login with email"**
3. Abre-se um URL no browser — autentica-te na tua conta Anthropic
4. Regressa ao terminal — estás autenticado

**Resolver problema do browser em WSL:**

```bash
# Se o browser não abrir automaticamente, configura o browser Windows
echo 'export BROWSER="/mnt/c/Program Files/Google/Chrome/Application/chrome.exe"' >> ~/.bashrc
source ~/.bashrc
```

Alternativa: copia o URL que aparece no terminal e cola no Chrome/Edge do Windows.

### Opção B — API Key (pay-per-use)

Se preferires pagar por token (mais flexível, sem partilha de quota com claude.ai):

**Passo 1: Obter a API Key**

1. Ir a **https://console.anthropic.com**
2. Criar conta ou fazer login
3. Ir a **Settings → API Keys → Create Key**
4. Copiar a chave (começa com `sk-ant-...`)
5. Adicionar créditos em **Settings → Billing** (mínimo ~$5 para começar)

**Passo 2: Configurar no ambiente**

```bash
# Adicionar ao .bashrc para persistir
echo 'export ANTHROPIC_API_KEY="sk-ant-...COLA_A_TUA_CHAVE"' >> ~/.bashrc
source ~/.bashrc

# E também ao .env do projecto (para o pipeline Python)
cd ~/202602-fct-proposal-engine
nano .env
```

Adicionar ao `.env`:

```env
ANTHROPIC_API_KEY=sk-ant-...COLA_A_TUA_CHAVE
```

**Passo 3: Testar**

```bash
claude --version
claude    # deve arrancar sem pedir login
```

---

## 4. Primeira sessão — Configuração inicial

```bash
cd ~/202602-fct-proposal-engine
claude
```

### Configuração do tema

```
? Choose a theme:
  ❯ Dark (recommended for dark terminals)
    Light
    Auto
```

Escolhe conforme o teu terminal.

### Aceitar permissões

O Claude Code vai pedir permissão para executar comandos no terminal.
Podes confiar em comandos no directório do projecto:

```
? Allow Claude to run commands in ~/202602-fct-proposal-engine?
  ❯ Yes, for this session
    Yes, always for this project
    No
```

Recomendo **"Yes, always for this project"** para evitar confirmar cada vez.

### Teste básico

No prompt do Claude Code (`>`), experimenta:

```
> What files are in this project? Give me an overview.
> Read drafts/pdspp_pilot_pex.yaml and summarize the proposal.
> Show me the pipeline architecture in src/generators/pipeline.py
```

---

## 5. Comandos essenciais

### Dentro do Claude Code (modo interactivo)

| Comando | Função |
|---------|--------|
| `/help` | Ver todos os comandos |
| `/cost` | Ver custo e tokens da sessão actual |
| `/compact` | Compactar contexto (útil em sessões longas) |
| `/clear` | Limpar conversa, manter ficheiros |
| `/config` | Configurações |
| `/doctor` | Diagnóstico de problemas |
| `/quit` ou `Ctrl+C` | Sair |

### Linha de comando (one-shot, sem modo interactivo)

```bash
# Prompt directo
claude -p "Read CLAUDE.md and list the key conventions"

# Output JSON (útil para scripts)
claude -p "List research questions from drafts/pdspp_pilot_pex.yaml" \
  --output-format json

# Modo silencioso (sem interface interactiva)
claude -p "Fix any linting errors in src/cli.py" --yes
```

---

## 6. Configurar o projecto — CLAUDE.md

O Claude Code lê automaticamente o ficheiro `CLAUDE.md` na raiz do projecto
para entender o contexto. Já existe um no repositório. Verifica que está
actualizado:

```bash
cat ~/202602-fct-proposal-engine/CLAUDE.md
```

Se precisares de editar:

```bash
nano ~/202602-fct-proposal-engine/CLAUDE.md
```

O `CLAUDE.md` deve conter:
- Descrição do projecto
- Estrutura de ficheiros relevante
- Convenções de código
- Comandos úteis (como executar, testar, etc.)

---

## 7. Casos de uso concretos para o fct-proposal-engine

### 7a. Análise e melhoria dos YAMLs

```
> Read all YAML files in drafts/ and compare the active PEX draft 
  with the complete versions. What's missing from the simplified one?

> Suggest 3 improvements to the methodology_notes in 
  drafts/pdspp_pilot_pex.yaml based on FCT evaluation criteria.

> The PI career summary needs to be more compelling. Rewrite it 
  emphasizing the H2020 and INTERREG project coordination experience.
```

### 7b. Desenvolvimento do pipeline

```
> Read src/generators/pipeline.py and src/utils/llm_client.py. 
  Explain how the multi-LLM review works.

> Add error handling and retry logic to the Gemini API calls in 
  src/utils/llm_client.py.

> Create a test in tests/ that validates the YAML schema against 
  data/schemas/draft_idea.json.
```

### 7c. Git workflow

```
> Show me what changed since last commit
> Review my staged changes and write a commit message
> Create a new branch called feature/scopus-integration
```

### 7d. Executar o pipeline (24 prompts do CLAUDE_CODE_PROMPTS.md)

```
> Read docs/CLAUDE_CODE_PROMPTS.md and start executing from prompt 1.
  The active draft is drafts/pdspp_pilot_pex.yaml.
```

---

## 8. Configuração avançada

### 8a. Ficheiro de configuração local

```bash
# Criar settings para o projecto
mkdir -p ~/202602-fct-proposal-engine/.claude
cat > ~/202602-fct-proposal-engine/.claude/settings.json << 'EOF'
{
  "permissions": {
    "allow": [
      "bash(git *)",
      "bash(python3 *)",
      "bash(pip *)",
      "bash(cat *)",
      "bash(ls *)",
      "bash(grep *)"
    ]
  }
}
EOF
```

### 8b. Configuração global

```bash
cat > ~/.claude/settings.json << 'EOF'
{
  "theme": "dark",
  "verbose": false
}
EOF
```

### 8c. Optimizar WSL para Claude Code

Criar/editar `C:\Users\dpolonia\.wslconfig` no Windows:

```ini
[wsl2]
memory=8GB
processors=4
swap=2GB
localhostForwarding=true
```

Reiniciar WSL após alteração:

```powershell
# No PowerShell do Windows
wsl --shutdown
# Reabrir o terminal WSL
```

### 8d. Performance: usar filesystem Linux

O Claude Code é significativamente mais rápido quando o projecto está
no filesystem Linux nativo (`~/`) em vez de montagens Windows (`/mnt/c/`).
O teu projecto já está em `~/202602-fct-proposal-engine` — correcto.

---

## 9. Custos estimados para o fct-proposal-engine

### Com subscrição Pro ($20/mês)

Uma execução completa do pipeline (24 prompts × 3 iterações × 4 reviewers)
consome aproximadamente 50-100 mensagens. Com o plano Pro tens ~45 mensagens
por janela de 5 horas, pelo que **uma execução completa pode requerer
2-3 janelas** (ou seja, 10-15 horas de espera entre janelas).

### Com subscrição Max 5× ($100/mês)

~225 mensagens por janela de 5 horas — **uma execução completa cabe numa
única janela** confortavelmente.

### Com API Key (pay-per-use)

Estimativa por execução completa usando Sonnet 4.5:
- Input: ~2M tokens × $3/M = ~$6
- Output: ~500k tokens × $15/M = ~$7.50
- **Total: ~$13.50 por execução completa**

Para 3-4 execuções/mês: ~$40-55/mês.

**Veredicto:** Se usas o claude.ai regularmente, o Pro ($20) é a melhor
opção. Se só queres correr o pipeline pontualmente, a API (~$14/execução)
é mais económica.

---

## 10. Resolução de problemas

### "command not found: claude"

```bash
# Verificar instalação
ls ~/.claude/bin/claude 2>/dev/null && echo "Native install found"
which claude
npm list -g @anthropic-ai/claude-code 2>/dev/null

# Recarregar PATH
source ~/.bashrc
```

### "Authentication failed" ou "No API key"

```bash
# Verificar variável
echo $ANTHROPIC_API_KEY

# Re-autenticar via browser
claude logout
claude login
```

### "Rate limit exceeded"

Com subscrição: esperar pela próxima janela de 5 horas.

Com API: verificar o tier em console.anthropic.com e adicionar créditos.

```bash
# Ver custos da sessão actual
# (dentro do Claude Code)
/cost
```

### "Shell not found" ou "POSIX shell required"

```bash
# Garantir que estás no WSL, não no PowerShell
echo $SHELL    # deve mostrar /bin/bash ou /bin/zsh

# Se necessário
export SHELL=/bin/bash
```

### Claude Code lento

```bash
# Verificar que NÃO estás num path /mnt/c/
pwd    # deve ser ~/202602-fct-proposal-engine, NÃO /mnt/c/...

# Limpar cache se necessário
rm -rf ~/.claude/cache
```

### Verificar saúde geral

```bash
claude doctor
```

---

## 11. Resumo dos comandos

```bash
# === INSTALAÇÃO ===
curl -fsSL https://claude.ai/install.sh | bash    # instalar
claude --version                                    # verificar

# === AUTENTICAÇÃO ===
# Opção A: Login (subscrição Pro/Max)
claude login

# Opção B: API Key
export ANTHROPIC_API_KEY="sk-ant-..."

# === SESSÃO INTERACTIVA ===
cd ~/202602-fct-proposal-engine
claude                                # iniciar
> /help                               # ver comandos
> /cost                               # ver custos
> /compact                            # compactar contexto
> /quit                               # sair

# === ONE-SHOT ===
claude -p "Explain this codebase"
claude -p "Fix linting" --yes         # modo automático

# === DIAGNÓSTICO ===
claude doctor                          # verificar saúde
claude logout && claude login          # re-autenticar
```

---

## 12. Próximos passos

1. **Instalar** (Secção 2) — escolhe o instalador nativo
2. **Autenticar** (Secção 3) — Pro é suficiente para o nosso caso
3. **Testar** (Secção 4) — primeira sessão no projecto
4. **Executar o pipeline** (Secção 7d) — seguir os 24 prompts de
   `CLAUDE_CODE_PROMPTS.md`

---

## Referências

- Instalação oficial: https://code.claude.com/docs/en/setup
- Quickstart: https://code.claude.com/docs/en/quickstart
- Pricing: https://claude.com/pricing
- API Console: https://console.anthropic.com
- Repositório do projecto: https://github.com/dpolonia/202602-fct-proposal-engine
