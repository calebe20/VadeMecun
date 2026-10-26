# 0002 — Infraestrutura de testes, auditorias e specs

**Status:** Concluída
**Responsável:** Codex
**Criada em:** 2026-10-25

## Objetivo


## Escopo

### Incluído

- [x] Diretório `specs/` com `TEMPLATE.md`, `README.md` e specs numeradas.
- [x] `AGENTS.md` com as regras de trabalho (spec obrigatória, gate antes de publicar).
- [x] Suíte de testes unitários em `tests/`, executável sem dependências externas do projeto.
- [x] `scripts/complexity_audit.py`: complexidade ciclomática estimada por função, com gate.
- [x] `scripts/dependency_audit.py`: grafo de dependências entre módulos, com detecção de ciclos.
- [x] `Makefile` com os alvos `test`, `audit`, `gate` e `spec`.
- [x] `tests/conftest.py` carregando o formatador sem depender do Colab.

### Não incluído

- Testes de navegador da interface do Colab (depende do runtime do Colab).
- Relatório de cobertura de linhas com threshold (o código é um notebook, a cobertura não é um bom sinal aqui).
- Mutation testing.
- Modularização do `Formatador_Lei_Anki_Colab.py` — depende do resultado das auditorias.

## Critérios de aceite

- [x] `make test` roda a suíte inteira e falha se qualquer teste falhar.
- [x] `make audit` roda as duas auditorias e falha se houver violação de gate.
- [x] `make gate` executa `audit` e `test` em sequência, serve como portão único.
- [x] A suíte roda sem internet e sem instalar nada além de `pytest`.
- [x] A auditoria de complexidade reporta as funções acima do limite e aponta a linha.
- [x] A auditoria de dependências detecta ciclo de importação.
- [x] Cada regra de negócio corrigida nesta sessão tem ao menos um teste que falharia sem a correção.
- [x] `AGENTS.md` descreve o fluxo de trabalho de forma executável, não apenas descritiva.

## Plano técnico

**`tests/conftest.py`** — carrega `Formatador_Lei_Anki_Colab.py` como módulo. O arquivo é um notebook: executa `IPython.display` e chama `google.colab` no topo. O `conftest` injeta stubs para esses dois módulos antes do import, de modo que o arquivo possa ser importado fora do Colab.

**`scripts/complexity_audit.py`** — usa `ast` do Python. Conta, por função, os predicados (`if`, `for`, `while`, `except`, `case`, ternário, `and`, `or`, comprehension) e estima `M = predicados + 1`. A contagem para na fronteira de função aninhada, de modo que cada função seja medida de forma independente, como na auditoria do EstudoPro. Gate: falha acima de `M > 15`.

**`scripts/dependency_audit.py`** — extrai as funções de topo de cada módulo do projeto, monta o grafo de chamadas entre elas e procura ciclos por DFS. Também detecta funções de tamanho desproporcional.

**`Makefile`** — alvos `test`, `audit`, `gate`, `spec`. `gate` é o que deve passar antes de qualquer entrega.

**Decisões relevantes**

- Os stubs do `conftest` são o ponto mais frágil: o arquivo do formatador muda, e o stub pode parar de bater. Mitigação: o `conftest` valida que os símbolos esperados existem após o import e falha com mensagem clara.
- A complexidade é estimada, não medida por ferramenta externa, para não adicionar dependência. O risco é divergir do radon/mccabe; aceitável, porque o objetivo é relative (comparar funções entre si) e não um número canônico.

## Validação

### Automatizada

- [x] `make test` — resultado: 29 testes aprovados
- [x] `make audit` — resultado: complexidade dentro do baseline, 0 ciclos de dependência
- [x] `make gate` — resultado: exit code 0

### Manual

- [x] Regressão 1 (remoção da extração de incidência) — resultado: 3 testes falham, gate bloqueia
- [x] Regressão 2 (reintrodução do título no `<summary>`) — resultado: 1 teste falha, gate bloqueia
- [x] Regressão 3 (inflar complexidade de `_separar_incidencia`) — resultado: auditoria acusa M=16, exit 1
- [x] Regressão 4 (ciclo entre `_dividir_fontes` e `_parece_lista_de_bancas`) — resultado: ciclo detectado, exit 1
- [x] Arquivo restaurado byte a byte após as regressões — resultado: sha256 idêntico

## Entregas seguintes

### 0003 — Caixas dos blocos sem barra lateral

**Status:** Concluída
**Responsável:** Codex
**Criada em:** 2026-10-25

#### Objetivo

Remover a barra vertical colorida que ficava à esquerda de cada bloco de comentário e manter apenas a cor de fundo. A jurisprudência passa a ficar dentro de uma caixa com borda completa, para se destacar do restante.

#### Escopo

##### Incluído

- [x] Remover `border-left` da regra base `details.comentario`.
- [x] Remover `border-left` da regra `details.comentario[data-bloco]`.
- [x] Remover os `border-left-color` por tipo, que existiam só para colorir a barra.
- [x] Dar borda completa (`1px solid #b9b3d0`) e padding próprio à jurisprudência.
- [x] Testes que impedem a volta da barra lateral.

##### Não incluído

- Bordas nos demais tipos de bloco.
- Alterar as cores de fundo dos blocos.
- O separador de colunas do PDF (`column-rule`), que é outro elemento e foi mantido.

#### Critérios de aceite

- [x] Nenhuma regra do CSS do PDF usa `border-left`.
- [x] A jurisprudência tem borda completa e continua com o fundo lilás.
- [x] Os demais tipos mantêm apenas a cor de fundo, sem borda.
- [x] A densidade da página não muda: 13.540 caracteres na página 1, 2 páginas para 100 artigos.
- [x] `make gate` passa.

#### Plano técnico

Mudança restrita ao `_PDF_CSS` em `Formatador_Lei_Anki_Colab.py`.

As regras por tipo (`questao`, `doutrina`, `tabela`, `esquema`, `nota`) usavam `border-left-color` apenas para dar cor à barra. Com a barra removida, essas declarações ficaram sem efeito e foram removidas.

A jurisprudência ganhou `border: 1px solid #b9b3d0` e `padding: 3px 5px` (um pixel a mais que os outros blocos, para compensar a borda).

#### Validação

##### Automatizada

- [x] `make test` — resultado: 32 testes aprovados
- [x] `make audit` — resultado: complexidade dentro do baseline, 0 ciclos
- [x] `make gate` — resultado: exit code 0

##### Manual

- [x] PDF real renderizado e inspecionado com `pdfplumber` — resultado: a caixa da jurisprudência envolve exatamente o texto (tribunal e ementa); as barras verticais restantes no PDF são o separador de colunas, não as barras dos blocos

#### Resultado da entrega

A barra vertical saiu de todos os blocos. A jurisprudência agora aparece como caixa com borda, e o resto fica só com o fundo colorido.

## Resultado da entrega

O projeto passa a ter o mesmo portão de qualidade do EstudoPro: spec antes do código, `make gate` antes da entrega.

**29 testes** cobrem as correções da spec 0001: extração e posicionamento da incidência, sobrevivência da incidência em todos os artigos do documento, inserção dos sete tipos de bloco nos cinco caminhos de saída, remoção dos títulos, justificação, hifenização, checkbox do PDF, margens, e o parser do arquivo exportado do Anki com e sem coluna `#guid`.

**Auditoria de complexidade** — o `BASELINE` registra as nove funções que já excediam M=15. A regra é não piorar. Como efeito colateral da spec 0001, cinco dessas funções *melhoraram*: `mesclar_comentarios` de 38 para 21, `_empacotar_cartoes` de 29 para 18, `_parse_blocos_tipados` de 24 para 21, `atualizar_arquivo_anki` de 21 para 16, `_parse_secoes_artigos` de 37 para 35. O baseline deve tender a zero a cada refatoração.

**Auditoria de dependências** — 86 funções, 137 arestas, zero ciclos. Aponta as três funções grandes: `gerar_html_pdf` (301 linhas), `formatar_para_anki` (203) e `mesclar_comentarios` (131). São as candidatas naturais à modularização.

**Gate verificado por regressão** — quatro regressões foram introduzidas deliberadamente e todas bloquearam a entrega com o código de saída correto. O arquivo foi restaurado e conferido por sha256.

**Limitações** — os testes não cobrem a interface do Colab (depende do runtime) nem a renderização real do PDF (depende do Chromium). A auditoria de complexidade estima em vez de usar radon/mccabe: serve para comparar funções entre si, não como número canônico.
