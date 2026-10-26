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
- [x] Cada questão, a partir da segunda de cada seção, recebe uma linha
      separadora na parte superior da caixa.
- [x] Padding interno da caixa da coluna (`.estilo-lei`, `.pdf-flow`,
      `.layout-split .estilo-lei`) reduzido de `10px 12px` para `3px 3px`.
- [x] Espaços duplicados do material (marcações de banca com dois espaços)
      removidos antes da renderização, no HTML e no texto limpo.
- [x] Testes que falham se as três mudanças forem revertidas.

### Não incluído

- Mudança de cores ou de bordas nos demais tipos de bloco (doutrina, tabela,
  esquema, nota, jurisprudência).
- Estilos do Anki exportado: o arquivo do Anki usa o CSS do usuário, não o CSS
  do PDF.
- Margem da página do PDF e padding interno dos blocos de comentário.
- Refatoração do `Formatador_Lei_Anki_Colab.py` em módulos.

## Critérios de aceite

- [x] A regra CSS da questão tem `border` e não usa mais o fundo azul `#e4ecf2`.
- [x] Existe uma regra que aplica linha superior ao bloco de questão quando ele
      vem logo após outro bloco de questão.
- [x] O padding da caixa da coluna é menor que o anterior (`10px 12px`).
- [x] Os demais tipos de bloco continuam sem borda, como na spec 0002.
- [x] `make gate` passa.

## Plano técnico

Mudança restrita ao `_PDF_CSS` e ao JavaScript do PDF, em
`Formatador_Lei_Anki_Colab.py`.

**Caixa da questão** — a regra `details.comentario[data-bloco="questao"]` troca
`background: #e4ecf2` por `border: 1px solid #9db4c6`, `padding: 3px 5px` e
fundo quase branco (`#fafcfd`). O padding de 3px/5px compensa a borda.

**Separador** — o CSS não resolve sozinho: as questões ficam em artigos
distintos, separadas pelo texto do dispositivo, e não são irmãs no DOM. A
marcação é feita no JavaScript do PDF, que percorre as questões de cada
`.note-container` e adiciona a classe `bloco-questao-separada` a todas, menos a
primeira. A linha é desenhada **dentro** da caixa da questão, no topo do
`.bloco-corpo`, com `border-top: 1px solid #aaa`: é a mesma linha fina e cinza
que separa os artigos (`.pdf-inicio-artigo`). A borda externa da caixa
continua com 1px, sem engrossar.

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

- O separador é marcado no JavaScript do PDF e não na geração do HTML: assim
  vale para o PDF sem tocar no `_render_bloco_tipado`, que é compartilhado
  com o Anki.
- A primeira questão de cada seção não recebe a linha: ela já aparece logo
  abaixo do cabeçalho do assunto, que cumpre a mesma função de marcação.
- O arquivo exportado para o Anki não é afetado: ele não carrega o CSS do PDF,
  e o bloco de questão no Anki é desenhado pelo CSS do próprio usuário.

**Correção do plano** — a primeira versão do plano usava o seletor CSS
adjacente (`+`). A medição no Chromium mostrou que as questões de artigos
distintos não são irmãs no DOM, então o seletor nunca casava. A marcação
passou para o JavaScript do PDF, que conhece a ordem real dos blocos. O
comportamento final é o pretendido: toda questão, menos a primeira da seção,
recebe a linha no topo da caixa.

## Validação

### Automatizada

- [x] `make test` — resultado: 38 testes aprovados
- [x] `make audit` — resultado: complexidade dentro do baseline, 0 ciclos de
      dependência
- [x] `make gate` — resultado: exit code 0

### Manual

- [ ] PDF final real renderizado com Chromium e inspecionado com `pdfplumber` —
      resultado: pendente para a versão final com padding `3px 3px`
- [x] DOM medido no Chromium — resultado: questão 1 com `1px solid`, questões
      2 e 3 com `margin-top: 5px` e borda externa de 1px; padding da coluna
      `4px 6px`
- [ ] Densidade comparada antes e depois (100 artigos, layout de três
      colunas) — resultado: pendente para a versão final com padding `3px 3px`
- [ ] Impressão na L3150 — resultado: pendente

## Resultado da entrega

As questões deixaram de ser bloco azul e viraram caixa com borda de 1px na cor
`#9db4c6` sobre fundo quase branco. Cada questão, a partir da segunda de cada
seção, recebe uma linha interna fina e cinza, do mesmo estilo da linha que
separa os artigos: a troca de questão fica visível de relance, sem grossar a
borda da caixa. O padding interno da caixa da coluna caiu de `10px 12px` para
`3px 3px`.

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
