# 0003 — Separador só entre itens e fim do espaçamento duplicado nas caixas

**Status:** Concluída
**Responsável:** Arena
**Criada em:** 2026-10-26

## Objetivo

O PDF mostrava a linha horizontal de separação **acima da primeira questão de
cada caixa**, inclusive quando a caixa tinha uma questão só — e nesse caso não
há nada a separar. A linha existe para separar um item do item anterior.

Além disso, o espaço entre o fim do texto e a borda da caixa somava com o
espaço de fora da caixa (margem + padding + `margin-bottom` do último item),
produzindo um vão morto grande no pé de cada caixa e um vão diferente do
espaçamento usado entre os itens dentro da caixa.

Resultado esperado: uma linha aparece **apenas entre dois itens** da mesma
caixa, nunca no topo e nunca quando há um item só; e o vão depois da caixa é
o mesmo espaçamento configurado no painel, sem soma de paddings e margens.

## Escopo

### Incluído

- [x] Separador de dispositivo (`.pdf-inicio-artigo`) restrito a
      `:not(:first-child)`.
- [x] O primeiro item de cada caixa (`.`estilo-lei`, `.pdf-flow`) é marcado pelo
      JS com `pdf-sem-separador` e nunca recebe linha, mesmo quando vem depois
      da linha de incidência/bancas.
- [x] Linha entre questões consecutivas do mesmo bloco `QUESTAO`
      (`.bloco-linha + .bloco-linha`), que é o caso em que a separação faz
      sentido.
- [x] A linha passa a ficar acima da incidência (banca) em vez de entre a
      banca e o texto do artigo, porque a banca faz parte do item.
- [x] Neutralização de linha no topo de qualquer caixa, inclusive quando a
      regra vem do CSS do baralho colado no painel.
- [x] Fim do espaçamento duplicado: último item da caixa sem `margin-bottom`,
      padding vertical das caixas reduzido, margens externas menores.

### Não incluído

- Redesenhar as caixas de bloco (bordas e cores do CSS do baralho).
- Mudar a entrelinha, a hifenização ou os recuos.
- Separar questões que estão em caixas diferentes (a borda da caixa já as
  separa).

## Critérios de aceite

- [x] Nenhuma linha horizontal aparece acima do primeiro item de uma caixa.
- [x] Uma caixa com um único item não mostra nenhuma linha de separação.
- [x] Duas questões consecutivas dentro do mesmo bloco `QUESTAO` continuam
      separadas por uma linha.
- [x] O vão entre o fim do texto e a borda inferior da caixa não soma padding
      com `margin-bottom` do último item, nem dentro dos blocos
      (`.bloco-corpo > :last-child`).
- [x] `make gate` passa.

## Plano técnico

Tudo em `Formatador_Lei_Anki_Colab.py`.

**CSS do separador** (`css_separadores`, injetado depois do CSS do baralho e
depois do `_PDF_CSS`, para valer sobre os dois):

- `.estilo-lei > span.pdf-inicio-artigo:not(:first-child)` desenha a linha.
- `.pdf-sem-separador`, `.pdf-flow > :first-child`, `.estilo-lei > :first-child`
  e `details.comentario > .bloco-corpo > :first-child` zeram `border-top` e
  `margin-top` com `!important`.
- `details.comentario[data-bloco="questao"] .bloco-linha + .bloco-linha` desenha
  a linha apenas entre duas questões.

**JS** — sai o laço que marcava `pdf-primeiro-artigo` no primeiro artigo de cada
`.note-container` (era por seção, não por caixa, e por isso a linha aparecia em
caixas que começavam com uma questão). Entra um laço por caixa que marca o
primeiro item de conteúdo com `pdf-sem-separador`, ignorando as linhas de
incidência.

**Espaçamento** (`_PDF_CSS`):

- `.estilo-lei`, `.pdf-flow` e `.layout-split .estilo-lei` passam de
  `padding: 10px 12px` para `padding: 5px 12px 2px`.
- `.estilo-lei > :last-child { margin-bottom: 0 }` — o último item não empurra
  mais a borda da caixa.
- `.note-container` de 6px para 3px e `.card-wrapper` de 3px para 2px, para a
  margem externa não somar com o padding da caixa.
- `details.comentario` de `margin: 2px 0 3px` para `margin: 2px 0`, com
  `details.comentario:last-child { margin-bottom: 0 }`.

## Validação

### Automatizada

- [x] `make test` — resultado: 40 testes aprovados (8 novos)
- [x] `make audit` — resultado: complexidade dentro do baseline, 0 ciclos
- [x] `make gate` — resultado: exit code 0

### Manual

- [x] Lógica do JS de marcação conferida executando o HTML gerado num DOM
      real (`jsdom`): o primeiro item de cada caixa recebe `pdf-sem-separador`
      e os artigos seguintes recebem a linha; no layout sequencial, a segunda
      caixa do cartão também perde a linha do topo (era o bug).
- [ ] Renderização/impressão não medida: o sandbox não tem Chromium nem
      Pango, então não foi possível medir caracteres por página desta rodada.
- [ ] Imprimir um material com uma questão única por caixa e outro com duas
      questões no mesmo bloco e conferir a ausência/posição das linhas —
      resultado: pendente (depende da impressão do usuário)

## Resultado da entrega

A linha de separação deixou de ser um decoração fixa do topo da caixa: passa a
ser desenhada somente entre itens. Caixas com um item só ficam sem linha, e
cada questão dentro de um mesmo bloco `QUESTAO` continua separada da anterior.

O espaçamento do pé das caixas deixou de somar três parcelas (margem do último
item + padding da caixa + margem externa); agora o vão depois da caixa é o
mesmo `--pdf-espaco` configurado no painel.
