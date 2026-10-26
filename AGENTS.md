# Regras de trabalho neste repositorio

## Eficiencia: rapido e objetivo

Este repositorio e pequeno e o codigo e direta. O trabalho padrao e: **faca a
mudanca, rode `make gate`, reporte**. O resto e desnecessario.

### Faca

- Antes de comecar, transforme o pedido do usuario em um checklist curto, com
  um item por requisito concreto. Use a ferramenta de lista de tarefas para
  registrar. Isso garante que nada do que foi pedido fique para tras.
- No fim, revise o checklist: cada item precisa estar feito, com teste ou
  validacao que o comprove. Se algum item nao pode ser feito, diga qual e por
  que, em vez de silenciar.
- Leia so o trecho do codigo que a mudanca toca. Use `grep` para localizar, nao
  leia o arquivo inteiro.
- Antes de perguntar algo ao usuario, pergunte a si mesmo se o repositorio ja
  responde. Se responder, vae em frente.
- Uma pergunta so, e so quando a resposta errada custar caro (apagar dado,
  mudar contrato, quebrar producao). Casos triviais: escolha o padrao
  razoavel, faca e diga o que escolheu.
- Mudanca visual pequena (CSS, cor, espaco, borda): edite e valide. Nao
  preciso de spec nova, de script de medicao, nem de PDF renderizado para
  confirmar. O `make gate` basta.
- Se a spec da entrega anterior ja cobre a mudanca, use essa spec em vez de
  criar outra.

### Nao faca

- Nao invente itens no checklist que o usuario nao pediu. O checklist reflete o
  pedido, nao o escopo ideal da IA.
- Nao instale pacote, nao baixe navegador, nao crie script auxiliar, nao
  renderize PDF, nao monte grafico ou planilha para "conferir" uma mudanca
  simples. Isso custa minutos e nao agrega.
- Nao leia imagens, PDF ou capture tela para descrever o resultado. Descreva
  pelo codigo e pelo texto.
- Nao invente requisito, nao "melhore" codigo adjacente, nao renomeie, nao
  reformate, nao reorganize arquivo. A entrega e o que foi pedido, nada mais.
- Nao escreva documentacao a mais do que a solicitada. Nao gere README, guia
  ou resumo que o usuario nao pediu.
- Nao reexecute validacao que ja passou. `make gate` uma vez, no fim.
- Nao espere confirmacao para o que ja foi pedido. Pedido feito e trabalho a
  fazer.

### Resumo da entrega

Sai com o resultado, o que mudou em uma frase e o `make gate` passando. Sem
relatorio de processo, sem lista do que nao foi feito, sem pergunta final.
O checklist fica registrado na lista de tarefas da sessao, com tudo marcado
como concluido.

## Desenvolvimento guiado por especificacao

- Para qualquer funcionalidade nova, alteracao de comportamento, mudanca de dados, integracao externa ou refatoracao de impacto, localize uma especificacao aplicavel em `specs/` ou crie uma nova a partir de `specs/TEMPLATE.md` antes de implementar.
- A especificacao e o contrato da entrega: nao implemente requisitos que nao estejam nela. Se o pedido do usuario divergir da spec ou trouxer ambiguidade material, peça esclarecimento ou atualize a spec antes de codar.
- Mudancas pequenas, isoladas e sem alteracao de comportamento (por exemplo, correcao de typo, formatacao ou ajuste mecanico) podem dispensar uma spec; declare essa excecao no resumo final.
- Antes de editar codigo, confirme na spec: objetivo, escopo, criterios de aceite, plano tecnico e validacao. Mantenha esses itens atualizados quando o trabalho revelar uma decisao relevante.
- Ao concluir, marque na spec os criterios de aceite atendidos, registre os comandos de validacao executados e seus resultados, e reporte requisitos pendentes ou nao validados.
- Use nomes sequenciais e descritivos: `specs/0001-nome-da-entrega.md`. Nao reutilize nem sobrescreva a spec de outra entrega.

## Gate antes de entregar

- **Nenhuma entrega sem `make gate` passando.** O gate roda as auditorias e a suite de testes.
- `make test` — suite de regressao. Deve passar inteiro.
- `make audit` — complexidade ciclomatica e ciclos de dependencia. Deve passar inteiro.
- Se uma correcao de comportamento foi feita, ela precisa de um teste que falharia sem a correcao. Sem o teste, a correcao nao esta protegida contra regressao.
- Ao introduzir uma regressao proposital para conferir o gate, reverta antes de entregar.

## Complexidade

- `scripts/complexity_audit.py` estima `M = predicados + 1` por funcao.
- O gate bloqueia quando uma funcao **piora** em relacao ao `BASELINE` registrado no proprio script. O baseline existe porque o arquivo e um notebook monolitico: a regra e nao piorar, nao reescrever tudo de uma vez.
- Ao refatorar uma funcao para ficar menor, reduza o numero no `BASELINE`. O baseline deve tender a zero.
- Novas funcoes tem limite padrao de `M <= 15`.

## Dependencias

- `scripts/dependency_audit.py` monta o grafo de chamadas entre as funcoes do modulo e detecta ciclos.
- Funcoes que se chamam mutuamente nao sao permitidas.
- `gerar_html_pdf`, `formatar_para_anki` e `mesclar_comentarios` sao as maiores do arquivo. Ao mexer nelas, prefira extrair helpers em vez de aumentar o corpo.

## Ambiente

- O codigo roda no Google Colab, mas os testes rodam localmente.
- `make setup` cria o `.venv` e instala o `pytest`.
- `tests/conftest.py` carrega `Formatador_Lei_Anki_Colab.py` com stubs de `IPython.display`. Se o topo do arquivo mudar e o stub deixar de bater, o `conftest` falha com mensagem clara — atualize o stub em vez de remover o teste.

## Impressao

- O PDF mira A4 para impressora laser (L3150). Margem de 6mm, fonte 9px, entrelinha 1.0.
- A hifenizacao e feita por software com `pyphen`, porque o Chromium nao aplica `hyphens: auto`. O `pyphen` nao vem no Colab: o formatador tenta instalar na primeira execucao e, se falhar, o PDF sai sem hifenizacao mas continua sendo gerado.
- So meca com PDF renderizado quando a mudanca mexer na densidade da pagina
  (margem, fonte, entrelinha, padding da coluna). Mudanca de cor, borda ou
  separador se confirma lendo o CSS.

## Entrega ao usuario

- O entregavel final e o conteudo de `Formatador_Lei_Anki_Colab.py`, copiado para a celula do Colab. Naopiece passos manuais de "salvar este arquivo".
- Sempre rode `make gate` antes de relatar sucesso.
