# GUIA DE USO

Um arquivo só, com o layout original intacto.

| Arquivo | Função |
|---|---|
| `Formatador_Lei_Anki_Colab.py` | O formatador completo, com a interface visual original. Aceita os blocos do prompt no campo "Mesclar Comentários da IA". |
| `PROMPT_IA.md` | O prompt que a IA externa recebe, em texto puro. Copie o arquivo inteiro e cole na IA. É ele que faz a extração do material. |

Não existe módulo separado para instalar: o formatador já sabe ler o
output do prompt.

## INSTALAÇÃO NO COLAB

Substitua o conteúdo da sua primeira célula pelo conteúdo de
`Formatador_Lei_Anki_Colab.py`. Nada mais. O layout, os botões, os
sliders e o PDF continuam iguais.

Se preferir manter o arquivo no Drive:

```python
from google.colab import drive
drive.mount('/content/drive')
exec(open('/content/drive/MyDrive/Formatador_Lei_Anki_Colab.py').read())
```

## FLUXO

1. Cole o texto legal e clique em **Formatar**.
2. Copie o texto formatado e envie para a IA externa junto com o
   material (matrículas, questões, jurisprudência, doutrina).
3. A IA devolve os blocos no formato do `PROMPT_IA.md`, dentro de **um
   único bloco de código**.
4. Cole o retorno no campo **"Mesclar Comentários da IA"**.
5. Clique em **Formatar, Mesclar e Copiar**.
6. Exporte para o Anki ou para o PDF.

## O QUE MUDOU NO CÓDIGO

Apenas o parser do campo "Mesclar Comentários da IA". Antes ele entendia
só `Art. 15|texto`; agora entende também os blocos tipados:

```
TIPO|ALVO|SUBTITULO|RELEVANCIA
corpo...
```

- `TIPO`: `COMENTARIO`, `TABELA`, `ESQUEMA`, `QUESTAO`, `JURISPRUDENCIA`,
  `DOUTRINA`, `NOTA`.
- `ALVO`: `Art. 2º`, `Art. 2º, § 1º`, `Art. 2º-A, alínea c`,
  `Art. 3º, parágrafo único`.
- `RELEVANCIA`: inteiro 0–100, que mede o quanto o dispositivo é cobrado.

O formato antigo continua funcionando: `Art. 15|texto` vira um
`COMENTARIO`.

Além disso:

- O output da IA agora vem dentro de **um único bloco de código** (```).
  O formatador remove a cerca automaticamente, então dá para copiar tudo
  sem risco.
- O **`SUBTITULO` não é mais exibido**. O bloco mostra apenas o tipo
  (`Questão`, `Comentário`, `Tabela`...), sem título inventado.
- O **corpo do bloco `QUESTAO` é só o enunciado**, transcrito do material,
  com a marca da banca inline (`(DPERO-2023-CESPE) ...`). A única linha
  extra admitida é `RESPOSTA:`. `ENUNCIADO:`, `FUNDAMENTO:` e `BANCA:`
  não são exibidos (o formato antigo com esses campos ainda funciona).
- O **`FUNDAMENTO` da questão não é exibido** (a âncora já indica o
  dispositivo). Se a resposta gabaritada depender do fundamento, ele vai
  dentro do próprio `RESPOSTA`.
- As **bancas** (linha `BANCA:` ou `FONTES:`) saem num rodapé
  discreto e compacto: `Fontes: MPMS-2022 AOCP · MPSP-2023 VUNESP`.
- A **linha de INCIDÊNCIA** do material (`Incidência em provas:`) é
  transcrita **como está no material** e aparece **logo após o texto**
  do bloco, junto com a lista de bancas, numa **única linha** em fonte
  pequena, itálico e cinza claro.

## COMO A IA ORGANIZA O MATERIAL

O prompt manda a IA **organizar**, não redigir. Ela separa o material
em blocos, ancora cada bloco no dispositivo e **transcreve literalmente**.

| Bloco | Corpo do bloco |
|---|---|
| `QUESTAO` | o enunciado transcrito, com a banca inline e o gabarito no fim |
| `COMENTARIO` | todos os `#Dica`, `#Atenção`, `#DOD` do material, na ordem |
| `JURISPRUDENCIA` | identificação numa linha (`STF · RE 695911 · ...`) + ementa em prosa + verbete final em itálico (tese firmada pelo tribunal) |
| `DOUTRINA` | referência numa linha (`AUTOR · OBRA · EDITORA · ANO · p. N`) + tese em prosa |

Regras que o prompt impõe:

- **Nenhum rótulo acrescentado.** Nada de `ENUNCIADO:`, `RESPOSTA:`,
  `FUNDAMENTO:`, `BANCA:`, `TRIBUNAL:`, `EMENTA:`. Se a informação
  precisa ser transcrita, vai como está no material.
- **Nenhum título, nenhum subtítulo.** O `SUBTITULO` do cabeçalho vai
  sempre vazio.
- **Questões são selecionadas**, não todas copiadas: no máximo 3 a 5 por
  dispositivo, as que testam o conteúdo do artigo ou têm didática.
- **Comentários, jurisprudência e doutrina entram todos**, sem resumo.

## BLOCO `MARCAS` (as bancas no texto legal)

As bancas que o material atribui a um dispositivo **não são um bloco de
análise**. Elas entram **no fim do texto legal**, entre parênteses:

```
Art. 3º Somente será admitido o parcelamento do solo para fins urbanos em zonas urbanas, de expansão urbana ou de urbanização específica, assim definidas pelo plano diretor ou aprovadas por lei municipal. (PGESP-2002) (MPSP-2005/2008/2013) (MPGO-2013) (PGM-Goiânia/GO-2015) (DPERO-2023)
```

Para isso, a IA emite um bloco `MARCAS` com a lista de bancas do
material:

```
MARCAS|Art. 3º||80
PGESP-2002; MPSP-2005/2008/2013; MPGO-2013; PGM-Goiânia/GO-2015; DPERO-2023
```

O corpo do bloco `MARCAS` é **só a lista de bancas**, sem
`Incidência em provas:` e sem frases. Cada banco vira um marcador entre
parênteses, em fonte menor e mais clara que o texto legal.

Nenhuma outra parte do código foi tocada. Os regex originais estão todos
lá (verificado por comparação automática), e a interface visual é a mesma.

## COMO CADA TIPO APARECE

| Tipo | No PDF |
|---|---|
| `QUESTAO` | enunciado, resposta e fundamento, em caixa azul |
| `TABELA` | vira `<table>` de verdade, com bordas |
| `ESQUEMA` | monoespaçado, dentro de caixa própria |
| `JURISPRUDENCIA` | tribunal, processo, relator, data, leading, ementa e verbete |
| `DOUTRINA` | autor, obra, editora, ano, página e tese |
| `COMENTARIO` | texto corrido, com **negrito** e *itálico* |
| `NOTA` | texto curto |

Dentro do mesmo dispositivo a ordem é:

**QUESTÃO → COMENTÁRIO → TABELA → ESQUEMA → JURISPRUDÊNCIA → DOUTRINA → NOTA**

e, dentro do mesmo tipo, pela relevância (maior primeiro).

## REGRAS DE ANCORAGEM

A âncora é deduzida do **texto visível** de cada trecho do HTML, não do
markup. Funciona com qualquer versão do formatador: basta que `Art.`,
`§`, o inciso e a alínea apareçam no texto.

Níveis reconhecidos:

```
Art. 2º
Art. 2º-A
Art. 2º, § 1º
Art. 2º, § 1º, inciso II
Art. 2º, inciso XXV, alínea a
Art. 3º, parágrafo único
```

Se o dispositivo do bloco não existir no texto, o bloco é mantido e
inserido ao final do artigo correspondente (nunca se perde).

## SEGURANÇA

O texto devolvido pela IA passa por um sanitizador que:

- remove `script`, `style`, `iframe`, `object`, `embed`, `link`;
- mantém apenas uma lista branca de tags (`table`, `b`, `i`, `ul`, `li`,
  `code`, `pre`, `sup`, `sub`, etc.);
- descarta todos os atributos, exceto `colspan` e `rowspan` em tabelas;
- escapa todo o texto.

## IMPRESSÃO (L3150 / A4 / MONO)

O PDF já sai compacto para impressora laser:

| Ajuste | Valor |
|---|---|
| Margem da página | 6mm (7mm embaixo, para o rodapé) |
| Fonte | 9px (mínimo 8, máximo 20) |
| Entrelinha | 1.0 |
| Espaçamento entre dispositivos | 2px |
| Recuo de parágrafo | 2px |
| Recuo de inciso/alínea | 8px |
| Padding das caixas de bloco | 2px |

Resultado medido: **52% mais caracteres por página** que antes (12.057
contra 7.935 numa página A4 de teste) e **193mm de largura útil** contra
185mm.

### Hifenização

A justificacao em coluna estreita abre buracos enormes entre as
palavras. Como o Chromium não aplica hifenização automática, ela é
feita por software com `pyphen`, antes de gerar o HTML:

- instalar: o próprio formatador instala o `pyphen` na primeira
  execução (só funciona se a célula tiver permissão de `pip`);
- se não conseguir instalar, o PDF sai sem hifenização, mas continua
  sendo gerado;
- cada palavra recebe no máximo um ponto de divis��o a cada três
  posições possíveis, e cada pedaço tem ao menos 3 caracteres.

### Se quiser ainda mais compacto

Os controles do painel (espaçamento, recuos, entrelinha, fonte) continuam
funcionando. Mova-os para o mínimo. Para o PDF em duas colunas em vez
de três, troque o layout para "Frente e verso em sequência" ou "Texto
corrido".
