# 0004 — Verbete (síntese da orientação firmada) na jurisprudência

**Status:** Concluída
**Responsável:** agente
**Criada em:** 2026-10-26

## Objetivo

Quando o material trouxer jurisprudência, a IA deve acrescentar ao final do
bloco `JURISPRUDENCIA` um **verbete**: uma síntese da orientação jurídica
firmada pelo tribunal, isto é, a tese que o tribunal consolidou após
decisões repetidas no mesmo sentido.

Valor: o verbete é o que o estudante precisa saber ("qual é a regra que o
tribunal firmou"), e não a ementa do caso concreto. Hoje o bloco só entrega
a ementa transcrita do material.

## Escopo

### Incluído

- [x] Regra do verbete no `PROMPT_IA.md`: o que é, quando emitir, quando não
      emitir, e como transcrever.
- [x] Exemplo de output atualizado com o verbete.
- [x] `GUIA.md` ajustado na linha da tabela do bloco `JURISPRUDENCIA`.
- [x] Verbete renderizado em **itálico** no Anki e no PDF.
- [x] Verbete não é engolido pela linha `Incidência em provas:`.
- [x] Verbete sem asteriscos no modo "texto puro".

### Não incluído

- Novo tipo de bloco `VERBETE` no formatador do Colab e qualquer mudança em
  `Formatador_Lei_Anki_Colab.py`.
- Estilo visual próprio para o verbete.

## Critérios de aceite

- [x] O prompt define o verbete como síntese da orientação firmada pelo
      tribunal após decisões repetidas no mesmo sentido.
- [x] O prompt manda a IA **não inventar** o verbete: só emiti-lo quando o
      material permitir extrair a tese consolidada; caso contrário, omitir.
- [x] O prompt proíbe rótulo (`VERBETE:`, `TESE FIRMA:`) — o verbete é a
      última linha do corpo do bloco `JURISPRUDENCIA`, em prosa.
- [x] A ordem dentro do bloco fica definida: identificação, ementa, verbete,
      incidence.
- [x] O exemplo de output do prompt mostra o verbete.
- [x] `make gate` passa.

Nota: a ordem foi ajustada durante a implementação para **identificação,
ementa, verbete, incidence**. O verbete vem antes da incidence porque a
linha de incidence, no material, absorve as linhas seguintes; o verbete é
a última linha do bloco e precisa sobreviver a essa coleta.

## Plano técnico

Contrato de texto entre a IA externa e o formatador. O bloco
`JURISPRUDENCIA` já renderiza cada linha do corpo como prosa
(`_render_jurisprudencia`, `Formatador_Lei_Anki_Colab.py:1428`), então a
última linha vira automaticamente uma linha normal do bloco, sem qualquer
alteração no código do Colab.

Decisões:

- Verbete como **última linha** do corpo do bloco `JURISPRUDENCIA`, e não
  como tipo de bloco novo: evita contrato novo e novo estilo visual.
- A linha `Incidência em provas:` fica **depois** do verbete: a coleta de
  incidence do material (`_extrair_incidencia`) engolia a linha seguinte,
  e o verbete, sendo a última linha do bloco, era o mais prejudicado.
- O verbete é marcado pela IA com asteriscos (`*...*`) e o formatador o
  transforma em `<i>`. O asterisco é o único mecanismo de marcação que o
  prompt já autorizava (`**negrito**` e `*itálico*`).
- O verbete é uma **síntese do material**, não texto novo: a IA reescreve
  em uma frase a tese que o material já sustenta, sem criar fundamento,
  número de processo ou orientação que não esteja lá.

## Validação

### Automatizada

- [x] `make gate` — resultado: `GATE OK — auditorias e testes passaram`
      (45 testes)

### Manual

- [x] Prompt lido com o material de exemplo: a regra do verbete é
      inequívoca e o exemplo mostra a linha — resultado: ok

## Resultado da entrega

Critérios de aceite: todos atendidos.

O que mudou:

- `PROMPT_IA.md`: nova seção `VERBETE (a orientação firmada pelo tribunal)`,
  com definição, posição (última linha do corpo do bloco `JURISPRUDENCIA`),
  proibição de rótulo, limites de invenção, quando emitir e quando omitir.
  O princípio de transcrição passou a registrar a exceção (verbete), e a
  lista de rótulos proibidos ganhou `VERBETE:`. O exemplo de output final
  mostra o verbete depois da ementa e da incidence.
- `GUIA.md`: tabela do bloco `JURISPRUDENCIA` passa a citar o verbete.
- `Formatador_Lei_Anki_Colab.py`:
  - novo `_RE_VERBETE` e novo helper `_bloco_linha_html`, que renderiza a
    linha do verbete como `<i>` (Anki e PDF);
  - `_extrair_incidencia` ganhou o parâmetro `permitir_verbete`, ligado
    apenas ao bloco `JURISPRUDENCIA`: sem ele, a linha `Incidência em
    provas:` engolia o verbete;
  - `_mesclar_no_texto` (modo texto puro) tira os asteriscos do verbete;
  - correção de um bug pré-existente no working tree: em
  `formatar_para_anki` (tipo `INC`), o `font-size:%s%%` era aplicado por
  `%` sobre uma string que já continha os marcadores de banca com `%` no
  estilo inline, causando `TypeError: not enough arguments for format
  string`. O `font-size` passou a ser interpolado direto na f-string. Sem
  isso os três testes de incidencia quebravam e o gate não passava.
- `tests/test_regressoes.py`: três testes novos (itálico no HTML, verbete
  antes da incidence, verbete limpo no texto puro).

Validações: `make gate` (auditorias de complexidade e de dependências +
suite de 45 testes) passou.

Limitações conhecidas: o verbete depende inteiramente do material enviado
para a IA. Se o material trouxer um único julgado sem sinal de
reincidência, súmula ou tema, o prompt manda omitir o verbete, e o bloco
fica sem a linha. Não há, por enquanto, estilo visual próprio para o
verbete: ele sai como prosa normal da última linha do bloco.
