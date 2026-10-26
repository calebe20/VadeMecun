# 0003 — Separadores entre questões e espaçamento externo da caixa

**Status:** Concluída (validação manual pendente)
**Responsável:** Agente Arena
**Criada em:** 2026-10-26

## Objetivo

No PDF, a linha cinza que separa os dispositivos e as questões aparece no lugar errado: fica no topo da caixa que agrupa as questões, em cima da primeira questão, mesmo quando só há uma questão. A linha deve servir apenas para separar itens consecutivos. Além disso, a distância entre as caixas (espaço externo) está maior do que o necessário e deve diminuir, para caber mais texto por página impressa.

## Escopo

### Incluído

- [x] A linha entre dispositivos e questões só aparece entre dois itens consecutivos da mesma caixa.
- [x] A linha nunca aparece no topo da caixa, nem em cima da primeira questão.
- [x] Uma questão isolada, ou a primeira de uma sequência, não recebe linha.
- [x] Um artigo que abre a caixa, ou que vem logo após a sua incidência, não recebe linha.
- [x] A incidência do dispositivo fica junto do artigo: quando existir, a linha vai acima da incidência e não entre ela e o artigo.
- [x] Espaço externo entre a caixa e a caixa seguinte (margem do grupo de assunto) reduzido de 6px para 3px.

### Não incluído

- Espaçamento interno da caixa (padding de 10px/12px e margens das questões). O usuário pediu reduzir somente o espaço externo.
- Layout de duas colunas e de texto corrido como padrão. Continuam do jeito atual.
- Mudança no conteúdo gerado pela IA ou no formato do arquivo Anki.
- Renderização real do PDF no Chromium: o ambiente não tem navegador disponível para isso (ver Validação).

## Critérios de aceite

- [x] Uma caixa com uma única questão não exibe nenhuma linha separadora.
- [x] Em uma caixa com duas questões seguidas, a linha aparece só acima da segunda.
- [x] Em uma caixa com artigo, questão e outro artigo, a linha aparece acima do segundo artigo, entre a questão e o artigo.
- [x] O primeiro artigo de cada caixa não recebe linha, com ou sem incidência antes dele.
- [x] A margem inferior de cada `.note-container` é de 3px.
- [x] `make gate` passa.

## Plano técnico

Arquivo afetado: `Formatador_Lei_Anki_Colab.py`, somente strings de CSS e de JavaScript dentro de `gerar_html_pdf`. Nenhuma função Python muda de lógica, então a complexidade não sobe.

- **CSS da linha** (`css_separadores`): nova regra `.estilo-lei > details.pdf-separador-questao` com a mesma borda, margem e padding da linha dos artigos.
- **JS de marcação**: a lógica atual marca só o primeiro artigo de cada `.note-container`. Ela passa a:
  - marcar `pdf-primeiro-artigo` em qualquer artigo sem irmão anterior na caixa (ou cujo único irmão anterior é a incidência);
  - mover a linha da incidência para a própria incidência quando ela existir antes do artigo;
  - marcar `pdf-separador-questao` em uma questão cujo irmão anterior também é questão.
- **CSS externo** (`_PDF_CSS`): `.note-container { margin: 0 0 3px; }`.

Riscos: a regra depende de `details[data-bloco="questao"]` ser irmão direto de `.estilo-lei > span`. Isso vale para o HTML gerado pelo `mesclar_comentarios`, que insere os blocos como irmãos.

## Validação

### Automatizada

- [x] `make test` — resultado: 37 testes aprovados (5 novos da spec 0003 falharam antes da correção)
- [x] `make audit` — resultado: complexidade dentro do limite, 0 ciclos de dependência (`gerar_html_pdf` cresceu em linhas por causa das strings de CSS/JS, sem mudança de M)
- [x] `make gate` — resultado: exit code 0, "GATE OK"
- [x] JavaScript do PDF executado em jsdom (fora do repositório) com 4 cenários: uma questão; duas questões; artigo entre questões; incidência antes do artigo — resultado: classes atribuídas conforme os critérios

### Manual

- [ ] Gerar o PDF com uma caixa de uma questão e conferir que não há linha — resultado: pendente (não foi possível renderizar o PDF neste ambiente; o Chromium não pôde ser baixado)
- [ ] Gerar o PDF com duas questões seguidas e conferir a linha só entre elas — resultado: pendente
- [ ] Conferir a distância entre as caixas no PDF impresso em A4 — resultado: pendente

## Resultado da entrega

Entregue: a linha de separação passou a valer só entre itens consecutivos da mesma caixa; a questão isolada e a primeira questão da caixa deixaram de receber linha; a incidência passou a levar a linha junto de si, e não separar a incidência do artigo; a margem externa entre caixas caiu de 6px para 3px.

Limitações conhecidas:

- A renderização real do PDF (Chromium) não foi feita: o ambiente não consegue baixar o navegador. A lógica foi verificada executando o JavaScript em jsdom, e o CSS foi conferido no texto gerado. Medir a folga no PDF impresso segue pendente, como manda o `AGENTS.md`.
- Os testes de CSS e JS são verificações de contrato sobre o texto gerado; o comportamento visual foi checado só pelos cenários em jsdom.
- Não foi alterado o espaçamento interno da caixa (padding de 10px/12px), por escolha do usuário.

Trabalho futuro deliberadamente adiado: validar a impressão na L3150 (pendência já registrada na spec 0001).
