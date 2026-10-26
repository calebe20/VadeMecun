# Regras de trabalho neste repositorio

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
- Ao mexer no CSS do PDF, meca o resultado renderizando um PDF de verdade e comparando caracteres por pagina. A intuicao erra.

## Entrega ao usuario

- O entregavel final e o conteudo de `Formatador_Lei_Anki_Colab.py`, copiado para a celula do Colab. Naopiece passos manuais de "salvar este arquivo".
- Sempre rode `make gate` antes de relatar sucesso.
