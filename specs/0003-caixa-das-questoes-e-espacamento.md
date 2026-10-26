# 0003 — Questões em caixa, separador entre questões e caixa da coluna mais estreita

**Status:** Concluída
**Responsável:** Kilo
**Criada em:** 2026-10-26

## Objetivo

Ajustar a diagramação do PDF impresso: as questões passam a aparecer como caixa
com borda, sem o bloco azul colorido; duas questões consecutivas ficam separadas
por uma linha, para que a troca de questão seja identificável de relance; e a
caixa que envolve o conteúdo da coluna fica com menos espaço interno, para
aproveitar melhor a largura útil da folha A4.

## Escopo

### Incluído

- [x] `details.comentario[data-bloco="questao"]` deixa de usar o fundo azul e
      passa a usar caixa com borda completa e fundo quase branco.
- [x] A linha divisória aparece somente entre duas questões consecutivas:
      nunca acima da primeira questão, e nunca entre uma questão e outro
      tipo de bloco.
- [x] Padding interno da caixa da coluna (`.estilo-lei`, `.pdf-flow`,
      `.layout-split .estilo-lei`) reduzido de `10px 12px` para `3px 3px`.
- [x] Padding interno dos blocos de comentário reduzido de `2px 4px` para
      `2px 3px`, e margem de `2px 0 3px` para `2px 0`.
- [x] Espaços duplicados do material (marcações de banca com dois espaços)
      removidos antes da renderização, no HTML e no texto limpo.
- [x] Testes que falham se as três mudanças forem revertidas.

### Não incluído

- Mudança de cores ou de bordas nos demais tipos de bloco (doutrina, tabela,
  esquema, nota, jurisprudência).
- Estilos do Anki exportado: o arquivo do Anki usa o CSS do usuário, não o CSS
  do PDF.
- Margem da página do PDF.
- Refatoração do `Formatador_Lei_Anki_Colab.py` em módulos.

## Critérios de aceite

- [x] A regra CSS da questão tem `border` e não usa mais o fundo azul `#e4ecf2`.
- [x] Existe uma regra que aplica linha superior ao bloco de questão quando ele
      vem logo após outro bloco de questão, marcado pelo JavaScript do PDF.
- [x] O padding da caixa da coluna é menor que o anterior (`10px 12px`).
- [x] Os demais tipos de bloco continuam sem borda, como na spec 0002.
- [x] `make gate` passa.

## Plano técnico

Mudança restrita ao `_PDF_CSS`, ao JavaScript do PDF e ao `_render_bloco_tipado`,
em `Formatador_Lei_Anki_Colab.py`.

**Caixa da questão** — a regra `details.comentario[data-bloco="questao"]` troca
`background: #e4ecf2` por `border: 1px solid #9db4c6`, `padding: 2px 3px` e
fundo quase branco (`#fafcfd`). O padding de 2px/3px compensa a borda.

**Separador** — o CSS não resolve sozinho: as questões ficam em artigos
distintos, separadas pelo texto do dispositivo, e não são irmãs no DOM. A
linha é desenhada **dentro** da caixa da questão, no topo do `.bloco-corpo`,
com `border-top: 1px solid #aaa`: é a mesma linha fina e cinza que separa os
artigos (`.pdf-inicio-artigo`). A borda externa da caixa continua com 1px,
sem engrossar.

**Divisória real, marcada no JavaScript** — a marcação final não é "toda
questão menos a primeira da seção": a divisória aparece quando a questão
anterior no DOM é também uma questão. O JavaScript do PDF percorre as
questões e, para cada uma cujo `previousElementSibling` seja
`details.comentario[data-bloco="questao"]`, adiciona `bloco-questao-separada`
à questão e `bloco-questao-fundida` à anterior. As duas caixas são fundidas
visualmente (sem borda compartilhada) e a linha fina fica no meio.

**Várias questões no mesmo bloco** — quando o material traz mais de uma
questão no mesmo bloco `QUESTAO`, `_render_bloco_tipado` emite uma
`.bloco-linha` por questão (a divisão usa a marca da banca entre parênteses
no início da linha, `_dividir_questoes`). O gabarito é anexado à última
questão. A divisória interna vem de `.bloco-linha + .bloco-linha`, ou seja,
sempre a partir da segunda linha e nunca antes da primeira.

**Caixa da coluna** — `.estilo-lei`, `.layout-combined/.layout-three/.pdf-flow`,
`.layout-continuous .pdf-flow` e `.layout-split .estilo-lei` passam de
`padding: 10px 12px` para `padding: 3px 3px`.

**Espaços duplicados** — o material da IA traz as marcações de banca com
espaço duplo entre elas: `(PGM-Fortaleza/CE-2017)  (PGM-POA/RS-2022)`. O
 `_colapsar_espacos` reduz qualquer sequência de dois ou mais espaços a um
único. Ele é aplicado em três pontos: `_md_para_html` (todo texto que vira
HTML), `_extrair_incidencia` (a linha de incidência do bloco) e
`_mesclar_no_texto` (modo texto limpo). O bloco ESQUEMA fica de fora, porque o
diagrama alinhado depende do espaçamento original.

**Decisões relevantes**

- O separador é marcado no JavaScript do PDF e não na geração do HTML: o
  seletor CSS adjacente (`+`) nunca casava, porque as questões de artigos
  distintos não são irmãs no DOM.
- A linha entra entre duas questões consecutivas, e não "a partir da segunda
  questão da seção": quando a questão anterior é de outro tipo, não há
  divisória. É esse o comportamento pretendido na medição no Chromium.
- A divisão em várias `.bloco-linha` é feita na geração do HTML, porque
  depende do conteúdo do enunciado, e não da ordem dos blocos no DOM. O
  arquivo exportado para o Anki passa a ter uma linha por questão, o que é
  o mesmo conteúdo, quebrado de outra forma.
- A caixa e a divisória do PDF não afetam o arquivo exportado para o Anki: ele
  não carrega o CSS do PDF, e o bloco de questão lá é desenhado pelo CSS do
  próprio usuário. O que muda no Anki é apenas a quebra em uma linha por
  questão, sem efeito visual.

**Correção do plano** — a primeira versão do plano usava o seletor CSS
adjacente (`+`). A medição no Chromium mostrou que as questões de artigos
distintos não são irmãs no DOM, então o seletor nunca casava. A marcação
passou para o JavaScript do PDF, que conhece a ordem real dos blocos. A
segunda correção de plano: a marcação deixou de ser "toda questão menos a
primeira da seção" e passou a ser "a questão cujo irmão anterior também é
questão". A regra antiga produzia linha indevida na primeira questão de cada
artigo; a regra nova põe a divisória só onde há duas questões em sequência.

## Validação

### Automatizada

- [x] `make test` — resultado: 42 testes aprovados
- [x] `make audit` — resultado: complexidade dentro do baseline, 0 ciclos de
      dependência
- [x] `make gate` — resultado: exit code 0

### Manual

- [x] DOM medido no Chromium — resultado: duas questões consecutivas em
      `<details>` distintos: a primeira com `bloco-questao-fundida` (sem borda
      inferior), a segunda com `bloco-questao-separada` (borda superior no
      `.bloco-corpo`, `1px solid rgb(170, 170, 170)`); duas questões no mesmo
      bloco: a segunda `.bloco-linha` com `border-top: 1px solid #aaa` e a
      primeira sem borda
- [ ] PDF final real renderizado com Chromium e inspecionado com `pdfplumber` —
      resultado: pendente para a versão final com padding `3px 3px`
- [ ] Densidade comparada antes e depois (100 artigos, layout de três
      colunas) — resultado: pendente para a versão final com padding `3px 3px`
- [ ] Impressão na L3150 — resultado: pendente

## Resultado da entrega

As questões deixaram de ser bloco azul e viraram caixa com borda de 1px na cor
`#9db4c6` sobre fundo quase branco. A divisória aparece entre duas questões
consecutivas, do mesmo estilo da linha que separa os artigos: a troca de
questão fica visível de relance, sem grossar a borda da caixa. A primeira
questão de um artigo não ganha linha indevida, e uma questão que vem depois
de outro tipo de bloco também não. O padding interno da caixa da coluna caiu
de `10px 12px` para `3px 3px`.

Quando o material traz mais de uma questão no mesmo bloco, cada uma vira uma
linha própria e a divisória aparece a partir da segunda, com o gabarito
anexado à última questão.

Os espaços duplicados das marcações de banca, que vinham do material da IA,
foram removidos antes da renderização: `(PGM-Fortaleza/CE-2017)  (PGM-POA/RS-2022)`
vira `(PGM-Fortaleza/CE-2017) (PGM-POA/RS-2022)`, tanto no HTML quanto no texto
limpo. O bloco ESQUEMA foi preservado, porque o diagrama depende do
espaçamento original.

O separador precisou da marcação no JavaScript do PDF: o seletor CSS adjacente,
que era o plano inicial, nunca casava, porque as questões de artigos distintos
não são irmãs no DOM. A medição no Chromium mostrou isso antes de fechar a
entrega.

**Limitações conhecidas**

- A linha separadora existe apenas no PDF. O arquivo exportado para o Anki não
  carrega o CSS do PDF, e o bloco de questão lá é desenhado pelo CSS do
  próprio usuário.
- A impressão na L3150 continua pendente de conferência manual.
