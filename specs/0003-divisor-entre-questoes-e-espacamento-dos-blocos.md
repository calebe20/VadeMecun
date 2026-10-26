# 0003 — Divisor entre questões e espaçamento dos blocos

**Status:** Concluída
**Responsável:** Arena Agent
**Criada em:** 2026-10-26

## Objetivo

Corrigir dois problemas vistos na impressão do PDF:

1. O divisor horizontal aparecia **acima** da questão, inclusive quando o bloco
   tinha uma única questão. A linha existe para **separar** uma questão da
   seguinte, então não pode abrir o bloco nem sobrando sozinha.
2. O espaço em volta do bloco de questões estava somando dois espaçamentos — o
   padding interno da caixa e a margem externa dela. O PDF ficava com um vão
   grande entre uma questão e a seguinte e entre a caixa e o texto legal.

O resultado esperado: divisores só onde há duas questões para separar, e um
único espaçamento em volta de cada bloco.

## Escopo

### Incluído

- [x] Cada questão de um bloco `QUESTAO` vira um parágrafo próprio
      (`bloco-linha bloco-questao`), para existir onde colocar o divisor.
- [x] Divisor aplicado por seletor de irmão adjacente: só a partir da segunda
      questão; a primeira nunca recebe linha.
- [x] Duas caixas de questão seguidas também ficam separadas por uma linha.
- [x] Limpeza da linha superior imposta pelo CSS do Anki colado no painel
      (estilo inline com `!important` na primeira questão e na linha solta que
      abria a caixa).
- [x] Moldura completa da caixa (borda nos quatro lados) preservada: sai a
      linha solta, não a borda da caixa.
- [x] Margem externa dos blocos reduzida a `1px 0`; o espaço entre blocos vem
      só do padding interno (`padding: 1px 4px`).
- [x] Padding da caixa que acopla os blocos (`.estilo-lei` e `.pdf-flow`) de
      `10px 12px` para `6px 8px`.
- [x] Quebra de linha hifenizada do material remontada (`pre-` + `dominantemente`
      passa a ser `pre-dominantemente`).

### Não incluído

- Alterar as cores de fundo ou as bordas por tipo de bloco (spec 0003 anterior,
  registrada dentro da 0002).
- O separador de artigos (`.pdf-inicio-artigo`), que é outro elemento e segue
  valendo.
- Reflow completo do PDF em duas colunas.

## Critérios de aceite

- [x] Um bloco com uma única questão não recebe nenhuma linha.
- [x] Um bloco com duas ou mais questões recebe linha apenas entre elas.
- [x] A primeira questão de cada caixa nunca recebe linha superior, mesmo com
      CSS do Anki colado no painel.
- [x] Duas caixas de questão seguidas não colam uma na outra.
- [x] Entre um bloco e o seguinte existe um único espaçamento (padding), não
      padding + margem.
- [x] Nenhuma linha do bloco de questão fica com margem externa de 2px/3px.
- [x] `make gate` passa.

## Plano técnico

**Render das questões** — `_render_bloco_tipado` deixa de montar um único
`bloco-linha` com o enunciado inteiro. `_dividir_questoes` separa o enunciado em
questões: uma nova questão começa quando a linha abre com a marca da banca entre
parênteses (`(DPESP-2015-FCC):`, `(PGM-POA/RS-2022-Fundatec):`), que é como o
material transcreve cada enunciado. Linhas de continuação são remontadas no
mesmo parágrafo; se a linha anterior termina em hífen, a palavra é remontada sem
espaço. `_render_questoes` emite um `<div class="bloco-linha bloco-questao">`
por questão e coloca o gabarito inline no fim da última.

**CSS do PDF** — a regra base
`details.comentario[data-bloco="questao"] .bloco-questao` zera borda, margem e
padding; a regra `.bloco-questao + .bloco-questao` é a única que desenha a linha
(`border-top: 1px solid #aaa`), porque o seletor de irmão adjacente não casa a
primeira questão. O mesmo vale para duas caixas de questão seguidas.

**JS do PDF** — `_JS_DIVISOR_QUESTOES` percorre os filhos de cada `.estilo-lei` e
aplica estilo inline com `!important`: `border-top: 0` na primeira
`.bloco-questao` e na caixa que abre a sequência de questões, e a linha de
separação na caixa que vem logo depois de outra caixa de questão. O inline com
`!important` é necessário porque o painel aceita o CSS do Anki, que pode
desenhar essa linha no primeiro bloco.

`semSeparadorNaCaixa` só zera a borda de cima quando ela é **linha solta**: se a
caixa tem borda nos lados, embaixo ou nos dois, a borda de cima é moldura e fica
intacta. Sem essa checagem, um deck com caixa de borda completa (o caso do
usuário) perderia a moldura do bloco de questão.

**Decisões relevantes**

- O divisor não é aplicado pelo tipo do bloco, e sim pela posição (segunda em
  diante). Assim ele nunca aparece "sozinho" e não é preciso contar questões.
- A separação entre duas caixas de questão só acontece quando elas são irmãs
  diretas. Se houver texto legal entre elas, o separador de artigo já cumpre o
  papel e uma segunda linha ficaria duplicada.
- O padding da caixa de texto caiu de `10px 12px` para `6px 8px`; a margem dos
  blocos caiu de `2px 0 3px` para `1px 0`. O espaçamento entre blocos passou a
  vir de um lugar só, como o usuário pediu.

## Validação

### Automatizada

- [x] `make test` — resultado: 39 testes aprovados
- [x] `make audit` — resultado: complexidade dentro do baseline, 0 ciclos
- [x] `make gate` — resultado: exit code 0
- [x] HTML do PDF executado no `jsdom` (JavaScript real, não inspeção de string):
      caixa com duas questões → 1ª sem linha, 2ª com `1px solid #aaa` e 2px de
      respiro; caixa com uma questão → nenhuma linha; duas caixas de questão
      seguidas → linha só na segunda; `details.comentario` com `margin: 1px 0`
      e `padding: 1px 4px`; `.estilo-lei` com `padding: 6px 8px`.
- [x] `jsdom` com CSS do Anki simulado — três cenários: sem CSS extra (1ª caixa
      sem linha, 2ª com linha), moldura completa (moldura preservada nos quatro
      lados) e CSS só com `border-top` (linha solta removida da 1ª caixa).
- [x] Regressão verificada: repondo o divisor na primeira questão, removendo o
      `_JS_DIVISOR_QUESTOES` e voltando ao parágrafo único, 4 testes falham.
      Arquivo restaurado byte a byte (sha256 idêntico) e `make gate` volta a
      passar.

### Manual

- [ ] Reimprimir uma página do material no Colab e conferir o divisor entre
      questões na L3150 — resultado: pendente (depende do runtime do Colab)

## Resultado da entrega

O divisor deixou de abrir a questão: ele aparece apenas entre a primeira e a
segunda questão, e desaparece quando o bloco tem uma só. A linha que o CSS do
Anki colado no painel desenhava no primeiro bloco é removida por estilo inline
com `!important`, então a correção vale também para quem personaliza o PDF.

O espaçamento deixou de ser somado: entre blocos há só o padding interno, e a
caixa que acopla os blocos perdeu 4px de padding em cada lado. Além disso, cada
questão de um mesmo bloco passou a ser um parágrafo próprio — antes duas
questões no mesmo bloco ficavam num parágrafo único, sem ponto natural para o
divisor.

**Limitação** — a renderização real em Chromium não roda neste ambiente; a
verificação foi feita executando o JavaScript do PDF em `jsdom` e conferindo o
CSS calculado. A conferência final na impressora continua manual.
