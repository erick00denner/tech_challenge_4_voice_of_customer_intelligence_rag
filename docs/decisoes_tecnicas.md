# Decisões Técnicas — Voice of Customer Intelligence com RAG

## 1. Objetivo

Este documento registra as decisões técnicas adotadas no desenvolvimento do Tech Challenge — Fase 4, cujo objetivo é construir uma aplicação de Voice of Customer Intelligence baseada em Retrieval-Augmented Generation (RAG).

A aplicação permitirá consultar avaliações de consumidores do dataset Olist, recuperando evidências relevantes para fundamentar respostas geradas por um modelo de linguagem.

As decisões são documentadas considerando quatro aspectos:

- **Decisão:** abordagem adotada.
- **Justificativa:** motivo técnico da escolha.
- **Alternativa descartada:** abordagem considerada, mas não utilizada.
- **Evidência:** resultado ou observação que sustenta a decisão.

---

## 2. Fonte e seleção dos dados

### 2.1. Dataset

**Fonte:** Brazilian E-Commerce Public Dataset by Olist.

**Arquivo:** `olist_order_reviews_dataset.csv`.

**Origem:** https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce

**Decisão:** utilizar inicialmente os dados de avaliações dos consumidores, obtidos por meio da biblioteca `kagglehub`.

**Justificativa:** o arquivo contém comentários, títulos, notas e identificadores suficientes para construir uma base de conhecimento textual com rastreabilidade.

**Alternativa descartada:** integrar todas as tabelas do dataset Olist desde a primeira versão.

**Evidência:** a análise exploratória identificou 99.224 registros de avaliações, dos quais uma parcela possui conteúdo textual aproveitável.

A integração com outras tabelas poderá ser considerada futuramente, caso os testes demonstrem necessidade.

### 2.2. Seleção dos registros

**Decisão:** selecionar avaliações que possuam título ou comentário não vazio após a normalização de espaços.

**Justificativa:** documentos sem conteúdo textual não oferecem informações úteis para a recuperação semântica.

**Alternativa descartada:** indexar todas as avaliações, incluindo registros que possuem somente nota.

**Evidência:**

- 99.224 registros originais.
- 40.977 comentários não nulos.
- 40.950 comentários não vazios após remoção de espaços.
- 27 comentários compostos apenas por espaços.
- 1.737 registros adicionais com título, mas sem comentário.
- 42.687 registros inicialmente elegíveis.

Após o tratamento de títulos sem letras, a quantidade de registros elegíveis passou para 42.588.

---

## 3. Preparação e qualidade dos dados

### 3.1. Normalização textual

**Decisão:** remover espaços excedentes e substituir quebras de linha por espaços, preservando letras maiúsculas, minúsculas, acentos e o conteúdo original.

**Justificativa:** padronizar a estrutura textual sem alterar desnecessariamente as informações utilizadas para gerar embeddings.

**Alternativa descartada:** aplicar remoção de acentos, pontuação, stopwords e outras transformações agressivas diretamente ao texto indexado.

**Evidência:** a inspeção qualitativa identificou comentários com abreviações, erros ortográficos, pontuação irregular e quebras de linha.

Essas características fazem parte da linguagem utilizada pelos consumidores e serão preservadas sempre que possível.

### 3.2. Construção dos documentos

**Decisão:** combinar título e comentário em um único documento, quando ambos possuírem conteúdo válido.

As seguintes regras são aplicadas:

1. Títulos sem letras são descartados.
2. Quando título e comentário são iguais, o texto é utilizado uma única vez.
3. Quando o título aparece integralmente no início do comentário, respeitando os separadores previstos na implementação, utiliza-se apenas o comentário. A comparação ignora a pontuação final do título.
4. Nos demais casos, título e comentário são concatenados.

**Justificativa:** aproveitar o conteúdo informativo dos títulos sem introduzir repetições desnecessárias.

**Alternativa descartada:** concatenar todos os títulos e comentários indiscriminadamente.

**Evidência:** a análise exploratória identificou 575 registros em que o título é igual ao comentário ou aparece no início dele, aplicando a mesma regra do pipeline. A regra anterior, sem tratamento da pontuação final do título, detectava 561.

Também foram encontrados títulos numéricos ou sem significado linguístico, como "3".

### 3.3. Consolidação de avaliações duplicadas

**Decisão:** consolidar registros com o mesmo `review_id`, mantendo um documento por avaliação e preservando os pedidos associados no campo `order_ids`.

**Justificativa:** impedir que a mesma avaliação ocupe múltiplas posições na recuperação e seja contabilizada como evidência independente.

**Alternativa descartada:** indexar cada linha original como um documento independente.

**Evidência:**

- 789 identificadores `review_id` aparecem em múltiplos registros.
- Foram identificadas 814 ocorrências adicionais desses identificadores na base original.
- A análise não encontrou divergências de nota, título, comentário, data de criação ou data de resposta entre os registros de um mesmo identificador.
- Os registros repetidos podem estar associados a pedidos diferentes.

Na seleção textual inicial, 42.687 linhas correspondiam a 42.370 avaliações únicas.

Após o ajuste de títulos sem letras, o pipeline identificou 42.588 linhas elegíveis e 42.272 avaliações únicas antes do filtro final.

### 3.4. Exclusão de documentos sem letras

**Decisão:** excluir documentos finais que não contenham nenhuma letra Unicode.

**Justificativa:** reduzir ruídos como documentos formados exclusivamente por números, símbolos ou pontuação, que possuem baixa utilidade para a recuperação semântica.

**Alternativa descartada:** preservar indiscriminadamente todos os documentos não vazios.

**Evidência:** após a consolidação, foram excluídos 134 documentos sem letras.

A base final contém 42.138 documentos.

### 3.5. Preservação de documentos curtos

**Decisão:** preservar documentos curtos que contenham letras, independentemente do número de caracteres.

**Justificativa:** expressões como "Bom", "Ok" e "Péssimo" podem representar opiniões legítimas dos consumidores.

**Alternativa descartada:** excluir automaticamente todos os documentos com menos de 10 caracteres.

**Evidência:**

- 3.536 documentos finais possuem menos de 10 caracteres.
- Esses documentos representam aproximadamente 8,4% da base preparada.
- A inspeção qualitativa identificou tanto avaliações informativas quanto expressões genéricas.

O comprimento `n_chars` será preservado como metadado.

Na consulta `não recebi o produto`, os oito primeiros resultados tinham menos de 30 caracteres, o que sugere que textos curtos podem dominar o topo do ranking. O efeito foi medido na avaliação da recuperação (seção 10.1). O pós-filtro de 30 caracteres não apresentou ganho consistente; decidiu-se preservar os textos curtos.

---

## 4. Redundância textual

### 4.1. Preservação de avaliações distintas

**Decisão:** manter avaliações com `review_id` diferentes, mesmo quando apresentam textos iguais.

**Justificativa:** comentários idênticos podem representar experiências legítimas de consumidores distintos.

**Alternativa descartada:** remover permanentemente todas as avaliações com conteúdo textual repetido.

**Evidência:** a base final contém 7.347 ocorrências adicionais de chaves textuais normalizadas repetidas, aproximadamente 17,4% dos documentos.

Esse número representa ocorrências adicionais, não a quantidade de grupos de textos distintos.

### 4.2. Chave auxiliar de deduplicação

**Decisão:** criar o campo `dedup_key`, utilizado exclusivamente para identificar textos equivalentes durante a recuperação.

A chave é construída com:

- Conversão para minúsculas.
- Remoção de acentos.
- Remoção de pontuação.
- Normalização de espaços.

**Justificativa:** reduzir a redundância no contexto enviado ao modelo de linguagem, sem modificar o texto utilizado na geração dos embeddings.

**Alternativa descartada:** utilizar o texto normalizado como documento principal ou eliminar definitivamente os documentos repetidos.

**Evidência:** a análise identificou concentração de avaliações genéricas, como "Ótimo", "Muito bom" e "Recomendo".

#### Chaves normalizadas mais frequentes

| Chave | Ocorrências |
|---|---:|
| otimo | 601 |
| muito bom | 590 |
| bom | 454 |
| recomendo | 440 |
| excelente | 283 |
| super recomendo | 158 |
| ok | 151 |
| otimo produto | 143 |
| otima | 130 |
| boa | 126 |
| tudo ok | 116 |
| nao recebi o produto | 114 |
| tudo certo | 85 |
| gostei | 77 |
| entrega rapida | 73 |
| bom produto | 73 |
| gostei muito | 57 |
| adorei | 56 |
| chegou antes do prazo | 56 |
| ainda nao recebi o produto | 51 |

A deduplicação na recuperação foi implementada e é descrita na seção 9.

---

## 5. Estrutura da base preparada

### 5.1. Arquivo gerado

**Caminho:** `data/processed/olist_reviews_clean.csv`

**Quantidade final:** 42.138 documentos.

**Decisão:** utilizar CSV como formato intermediário para a base preparada.

**Justificativa:** formato simples, portátil, inspecionável e suficiente para o volume atual de documentos.

**Alternativa descartada:** introduzir banco de dados relacional ou infraestrutura adicional nesta etapa.

**Evidência:** o pipeline executou localmente e produziu um arquivo com 42.138 registros e sete colunas.

### 5.2. Campos

| Campo | Finalidade |
|---|---|
| `review_id` | Identificador da avaliação |
| `order_ids` | Pedidos associados, armazenados como texto |
| `review_score` | Nota atribuída pelo consumidor |
| `review_creation_date` | Data de envio da pesquisa de satisfação |
| `n_chars` | Comprimento do documento em caracteres |
| `dedup_key` | Chave auxiliar de comparação textual |
| `document` | Texto utilizado na geração dos embeddings |

### 5.3. Distribuição do comprimento

| Estatística | Caracteres |
|---|---:|
| Quantidade de documentos | 42.138 |
| Média | 69,08 |
| Mediana | 54 |
| Percentil 90 | 162 |
| Percentil 95 | 193 |
| Percentil 99 | 209 |
| Máximo | 228 |
| Documentos com menos de 10 caracteres | 3.536 |

### 5.4. Estratégia de fragmentação

**Decisão:** não aplicar chunking.

Cada avaliação será representada por um único documento.

**Justificativa:** os textos são curtos, e a fragmentação poderia prejudicar a interpretação e a rastreabilidade das avaliações.

**Alternativa descartada:** dividir os documentos em fragmentos menores.

**Evidência:** o comprimento máximo da base preparada é de 228 caracteres, com mediana de 54 caracteres.

---

## 6. Validação e testes

### 6.1. Integridade da base

**Decisão:** validar a unicidade dos identificadores e a presença de conteúdo textual nos documentos finais.

**Justificativa:** impedir a indexação de registros duplicados por identificador ou sem conteúdo linguístico.

**Alternativa descartada:** confiar exclusivamente nas verificações manuais realizadas durante a EDA.

**Evidência:**

- 42.138 documentos gerados.
- Nenhum `review_id` duplicado na base final.
- Documentos sem letras removidos.
- Contagens de seleção, consolidação e exclusão verificadas.

### 6.2. Testes unitários

**Decisão:** utilizar `pytest` para testar as funções de preparação textual, recuperação e geração RAG.

**Justificativa:** garantir que alterações futuras não comprometam regras já validadas.

**Alternativa descartada:** depender apenas da execução manual do pipeline.

**Evidência:** a suíte de preparação e recuperação registrou **41 testes aprovados** (20 de preparação e 21 de recuperação). Posteriormente, foram implementados testes para a geração RAG em `tests/test_rag.py`, abrangendo validação de estrutura, citações, abstenções e tratamento de erros. Uma execução anterior da suíte completa registrou **77 testes aprovados**; recomenda-se executar novamente `python -m pytest -q` após as últimas alterações de versionamento do prompt.

Comando de execução:

```bash
python -m pytest -q
```

---

## 7. Limitações conhecidas

### 7.1. Representatividade

A base textual apresenta maior proporção de avaliações negativas que o conjunto completo.

As notas 1 e 2 representam aproximadamente:

- 14,7% de todas as avaliações.
- 26,6% das avaliações com comentários textuais.

Portanto, os documentos indexados não representam proporcionalmente a distribuição de satisfação de todos os consumidores.

### 7.2. Nota não equivale a sentimento

A nota atribuída é um indicador aproximado de satisfação, mas não constitui um rótulo confiável do conteúdo semântico.

Uma nota baixa não garante que o texto descreva uma reclamação, assim como uma nota alta não impede a presença de críticas. Na consulta `não recebi o produto`, por exemplo, um dos resultados (`Não entregaram Não recebi o produto`) tem nota 3.

### 7.3. Possível truncamento

A inspeção de comentários próximos de 200 caracteres identificou frases e palavras aparentemente interrompidas.

Isso sugere possível truncamento na origem, mas não comprova a regra aplicada.

Os textos serão preservados sem reconstrução artificial.

### 7.4. Semântica das datas

O campo `review_creation_date` representa a data de envio da pesquisa de satisfação, não a data da compra.

Os registros analisados abrangem outubro de 2016 a agosto de 2018.

A análise do período de compra exigiria integração com informações adicionais dos pedidos.

### 7.5. Anonimização

O dataset contém nomes fictícios utilizados para anonimizar determinadas entidades, incluindo referências a casas de Game of Thrones.

Esses nomes não devem ser interpretados como identificações reais de lojas ou parceiros.

### 7.6. Frequência de reclamações

A recuperação por similaridade semântica não permite, isoladamente, determinar quais problemas são mais frequentes em toda a base.

Na versão inicial, respostas de síntese deverão restringir suas conclusões às avaliações efetivamente recuperadas.

---

## 8. Embeddings e indexação vetorial — implementados

### 8.1. Modelo de embeddings

**Decisão:** utilizar `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`, executado localmente por meio da biblioteca Sentence Transformers.

**Justificativa:** suporte multilíngue, incluindo português, geração local de vetores sem custo de API e dimensão de 384, adequada à primeira implementação do projeto.

**Alternativa descartada:** iniciar com embeddings de uma API externa, que acrescentaria dependência de serviço e custos potenciais antes de validar a recuperação.

**Evidência:** modelo carregado com sucesso em CPU; embeddings gerados para os 42.138 documentos. A consulta exploratória `produto não chegou` retornou documentos semanticamente compatíveis. Isso confirma o funcionamento inicial, mas não estabelece superioridade do modelo nem qualidade geral de recuperação.

**Configuração:** embeddings normalizados (`normalize_embeddings=True`), lotes de 128 documentos e dimensão vetorial de 384.

**Verificação pendente:** confirmar, por meio do tokenizador do modelo, se o documento mais longo da base (228 caracteres) ultrapassa o limite de 128 tokens. Caso ocorra truncamento, será necessário avaliar seu impacto sobre a representação semântica dos documentos afetados. Essa verificação é complementar à avaliação de recuperação já realizada e não invalida, por si só, os resultados observados.

### 8.2. Banco vetorial e persistência

**Decisão:** utilizar ChromaDB com armazenamento local persistente em `data/chroma/`, coleção `olist_reviews` e métrica de distância cosseno.

**Justificativa:** implementação direta em Python, persistência entre execuções e armazenamento de documentos e metadados para rastreabilidade.

**Alternativa descartada:** utilizar infraestrutura vetorial remota ou serviço gerenciado nesta fase, que acrescentaria complexidade operacional sem necessidade demonstrada.

**Evidência:** indexação concluída e validação de `collection.count()` com 42.138 documentos; métrica `cosine` confirmada na configuração da coleção.

O índice preserva os documentos e os metadados `order_ids`, `review_score`, `review_creation_date`, `n_chars` e `dedup_key`; o identificador da coleção para cada documento é `review_id`.

### 8.3. Construção e validação do índice

**Decisão:** executar a indexação por lotes, com `upsert`, opção explícita `--reset` para reconstrução e validação de contagem, métrica e consulta exploratória ao final.

**Justificativa:** limitar o uso de memória, permitir repetição da carga por identificador e detectar problemas básicos antes da etapa de recuperação.

**Alternativa descartada:** carregar todos os embeddings de uma vez ou reconstruir automaticamente a coleção em toda execução.

**Evidência da execução em Linux/CPU:**

| Indicador | Resultado |
|---|---|
| Script | `src/build_index_data.py` |
| Modelo | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` |
| Dimensão dos embeddings | 384 |
| Tamanho do lote | 128 |
| Lotes processados | 330 |
| Documentos indexados | 42.138 |
| Métrica de distância | Cosseno |
| Dispositivo | CPU |
| Tempo total registrado | 1.905,4 segundos (aprox. 31 min e 45 s) |
| Consulta de validação | `produto não chegou` |
| Similaridades exibidas | 0,994; 0,990; 0,990 |

A similaridade exibida foi calculada como `1 - distância cosseno`. Valores maiores indicam maior proximidade entre os vetores.

Os três primeiros resultados exibiram o mesmo texto (`o produto não chegou`), com notas iguais a 1. **Isso não equivale a três evidências textuais independentes** e confirma a necessidade de deduplicação na recuperação.

A consulta é uma verificação funcional, não uma avaliação formal da qualidade do recuperador.

**Limitações operacionais:** `--reset` exclui a coleção antes de reconstruí-la; falhas durante a execução podem deixar uma coleção incompleta. O uso de `upsert` não remove automaticamente documentos que tenham desaparecido do CSV. O diretório `data/chroma/` permanece fora do versionamento Git.

---

## 9. Recuperação semântica — implementada

### 9.1. Estratégia de recuperação

**Decisão:** implementar a recuperação em `src/retrieve.py`, com normalização de espaços da pergunta, geração local do embedding, busca por similaridade cosseno e seleção de avaliações textualmente distintas por `dedup_key`.

**Justificativa:** recuperar evidências relevantes e evitar que comentários equivalentes ocupem várias posições do contexto.

**Alternativa descartada:** utilizar diretamente os primeiros `top_k` resultados do ChromaDB, sem deduplicação.

**Evidência:** na consulta `não recebi o produto`, o recuperador retornou 10 textos distintos após examinar 200 candidatos. Os resultados foram ordenados por similaridade (de 1,000 a 0,930) e exibiram `review_id`, `order_ids`, nota e texto.

**Limitação — transformação da pergunta:** a etapa atual de processamento da consulta limita-se à normalização de espaços. O enunciado pede que a transformação da pergunta seja demonstrada. **Pendente:** definir e implementar uma etapa adicional, como a extração de filtros a partir da pergunta (por exemplo, "clientes insatisfeitos" associado a `review_score ≤ 2`, usando o metadado do índice) ou a reescrita da consulta.

### 9.2. Expansão adaptativa e limites

**Decisão:** buscar inicialmente `top_k × 5` candidatos e dobrar a quantidade quando a deduplicação produzir menos resultados que `top_k`, respeitando o teto operacional de 200 candidatos e o tamanho da coleção.

**Justificativa:** consultas com comentários muito repetidos podem produzir poucos textos distintos mesmo quando há outras avaliações relevantes no índice.

**Alternativa descartada:** fixar a busca em `top_k × 5` candidatos, independentemente da diversidade recuperada.

**Evidência:** para `não recebi o produto`, `top_k=10` retornou 10 avaliações distintas entre 200 candidatos; `top_k=250` retornou 57 avaliações distintas, também entre 200 candidatos, indicando recuperação incompleta. Comandos utilizados:

```bash
python -m src.retrieve "não recebi o produto" --top-k 10
python -m src.retrieve "não recebi o produto" --top-k 250
```

O retorno distingue:

- `candidates_examined`: quantidade de candidatos examinados na última busca.
- `candidate_limit_reached`: indica que a busca atingiu o limite efetivo de candidatos (o menor entre o teto de 200 e o tamanho da coleção), mesmo quando `top_k` foi atendido.
- `retrieval_incomplete`: indica que foram retornados menos documentos distintos que o `top_k` solicitado.

**Regra de interpretação:** `retrieval_incomplete` é o sinal principal de quantidade insuficiente de resultados distintos. Isso não equivale, por si só, à insuficiência semântica das evidências, que ainda será avaliada.

### 9.3. Ocorrências entre candidatos e rastreabilidade

**Decisão:** retornar `candidate_occurrences` para cada chave textual selecionada e preservar `order_ids` na saída.

**Justificativa:** permitir inspecionar redundância no conjunto recuperado e identificar os pedidos vinculados à avaliação.

**Alternativa descartada:** descartar duplicatas sem registrar sua ocorrência entre os candidatos examinados.

**Evidência:** na consulta `não recebi o produto`, a chave do primeiro resultado apareceu 107 vezes entre os 200 candidatos examinados. Como o teto de 200 foi atingido, **107 é um valor mínimo**: podem existir mais cópias fora do conjunto examinado.

**Limitação:** `candidate_occurrences` **não representa frequência na base inteira**. A contagem depende dos candidatos recuperados e pode subestimar as ocorrências existentes fora desse conjunto. Não deve fundamentar afirmações como "a reclamação mais frequente da base". Além disso, o resultado exibe apenas um `review_id` por texto, embora o mesmo texto possa vir de várias avaliações; os demais identificadores não são retornados.

### 9.4. Validação do recuperador

**Decisão:** validar as regras de recuperação por testes unitários e executar consultas reais contra o índice persistente.

**Justificativa:** verificar a deduplicação, a ordenação, os limites, as flags de retorno e o tratamento de entradas inválidas antes de integrar a LLM.

**Alternativa descartada:** confiar apenas na inspeção visual das consultas de exemplo.

**Evidência:** `python -m pytest tests/test_retrieve.py -q` concluiu com **21 testes aprovados** e `python -m pytest -q` concluiu com **41 testes aprovados**. As consultas reais com `top_k=10` e `top_k=250` confirmaram o comportamento esperado das flags.

Esses resultados demonstram funcionamento técnico. A precisão da recuperação foi posteriormente medida no Notebook 02 (seção 10.1), e a qualidade das respostas geradas foi posteriormente avaliada no Notebook 03 (seção 10.3).

---

## 10. Avaliação da recuperação semântica e decisões para geração

### 10.1. Avaliação da recuperação — Notebook 02

**Decisão:** avaliar quantitativamente a relevância dos documentos recuperados e investigar qualitativamente o comportamento do recuperador diante de perguntas fora do escopo e perguntas vagas, antes da implementação da geração de respostas com LLM.

**Justificativa:** o funcionamento técnico da busca vetorial não garante que os documentos recuperados sustentem o sentido específico da pergunta. A avaliação permite identificar limitações e fundamentar decisões sobre a seleção do contexto enviado ao futuro modelo de linguagem.

**Alternativa descartada:** considerar a inspeção visual de consultas isoladas e os valores de similaridade como evidência suficiente da qualidade da recuperação.

**Evidência:** experimento executado no Notebook 02, com 19 perguntas e classificação manual de 270 pares pergunta–avaliação.

#### 10.1.1. Escopo e metodologia

Foram executadas 19 perguntas, distribuídas em três grupos:

- **9 perguntas de domínio (Q01–Q09):** consultas relacionadas às experiências dos consumidores, como entrega, defeitos, atendimento, reembolso e qualidade dos produtos.
- **7 perguntas fora do escopo (Q10–Q16):** solicitações que não podem ser respondidas com as avaliações históricas disponíveis.
- **3 perguntas vagas (Q17–Q19):** consultas com contexto insuficiente ou intenção pouco específica.

A avaliação quantitativa foi realizada exclusivamente nas nove perguntas de domínio, considerando os 30 primeiros resultados de cada pergunta, totalizando **270 pares pergunta–avaliação**.

As perguntas fora do escopo e as perguntas vagas foram analisadas qualitativamente, sem cálculo de Precision@k.

#### 10.1.2. Critérios de relevância e rotulagem

**Decisão:** utilizar classificação manual de relevância, considerando o conteúdo textual da avaliação e sua capacidade de sustentar o sentido da pergunta.

Os 270 pares foram classificados exclusivamente por **um anotador humano**, segundo a escala:

| Rótulo | Classificação | Critério |
|---|---|---|
| 2 | Evidência direta | A avaliação sustenta o sentido específico da pergunta. |
| 1 | Relevância temática | A avaliação aborda o tema, mas não sustenta diretamente a afirmação investigada. |
| 0 | Irrelevante | A avaliação não apresenta relação suficiente com a pergunta. |

A classificação não utiliza a nota (`review_score`) como substituta da análise textual.

Um experimento preliminar de pré-rotulagem com LLM foi descartado. **Nenhum rótulo gerado por LLM foi utilizado no conjunto final de avaliação ou no cálculo das métricas apresentadas nesta seção.**

Como a classificação final foi realizada por um único anotador humano, não foi medida concordância interavaliadores para esse conjunto. Essa característica constitui uma limitação metodológica do experimento.

#### 10.1.3. Métricas utilizadas

Foram calculadas duas variantes de Precision@k:

- **Precision estrita:** considera relevantes apenas avaliações com rótulo 2.
- **Precision tolerante:** considera relevantes avaliações com rótulos 1 ou 2.

As métricas foram calculadas para `k=10`, `k=20` e `k=30`, utilizando exclusivamente perguntas com rótulos completos nas posições avaliadas.

A precisão estrita mede a proporção de avaliações que sustentam diretamente a pergunta. A precisão tolerante mede a proporção de avaliações que apresentam, no mínimo, relação temática.

#### 10.1.4. Resultados da recuperação original

**Evidência — média das nove perguntas de domínio:**

| k | Precision estrita | Precision tolerante | Evidências diretas por pergunta |
|---|---:|---:|---:|
| 10 | 60,0% | 93,3% | 6,0 |
| 20 | 60,0% | 91,7% | 12,0 |
| 30 | 58,9% | 90,0% | 17,7 |

A precisão estrita permaneceu próxima de 60% nos três valores de k. A precisão tolerante diminuiu de 93,3% para 90,0% entre k=10 e k=30.

Aumentar k de 10 para 30 elevou a média de evidências diretas de 6,0 para 17,7 por pergunta, mantendo precisão estrita semelhante. Entretanto, também aumentou a quantidade absoluta de avaliações relacionadas apenas ao tema ou irrelevantes, exigindo maior capacidade de seleção de evidências na etapa de geração.

**Principal limitação identificada:** o recuperador frequentemente identifica corretamente o tema, mas não distingue com a mesma precisão o sentido específico da pergunta.

Essa diferença foi especialmente evidente em:

| Pergunta | Precision@30 estrita | Precision@30 tolerante |
|---|---:|---:|
| Q04 — Produtos com defeito | 26,7% | 96,7% |
| Q05 — Produto diferente do anunciado | 16,7% | 80,0% |
| Q06 — Dificuldades no atendimento | 10,0% | 60,0% |

Em Q04, por exemplo, avaliações sobre qualidade ruim nem sempre descrevem defeitos explícitos. Em Q05, a proximidade temática não garante que o produto recebido seja diferente do anunciado.

Q06 apresentou o desempenho mais fraco: a precisão tolerante caiu de 80,0% em k=10 para 60,0% em k=30, com a inclusão de textos curtos e genéricos no ranking.

Esses resultados demonstram que a similaridade semântica, isoladamente, não assegura evidência direta para a geração de respostas.

#### 10.1.5. Experimento com filtro mínimo de 30 caracteres

**Decisão experimental:** comparar a recuperação original com uma variante que seleciona apenas avaliações com pelo menos 30 caracteres, a partir dos 40 resultados recuperados.

**Justificativa:** investigar se a remoção de avaliações muito curtas melhora a relevância do contexto, sem alterar o índice vetorial.

A comparação foi realizada de forma pareada, utilizando apenas perguntas com rotulagem completa nas duas variantes para cada valor de k.

| k | Perguntas comparadas | Precision estrita (original → filtro) | Precision tolerante (original → filtro) |
|---|---:|---|---|
| 10 | 9 | 60,0% → 58,9% | 93,3% → 91,1% |
| 20 | 7 | 61,4% → 60,7% | 94,3% → 93,6% |

Para k=20, Q02 e Q06 foram excluídas da comparação pareada porque a variante filtrada exigiria três rótulos de avaliações posicionadas além do rank 30, que não foram atribuídos.

Essas duas perguntas estavam entre as que apresentaram maior quantidade de textos curtos nos 40 candidatos. Entretanto, ambas participaram da comparação em k=10.

**Resultado:** o filtro não apresentou melhoria nas configurações avaliadas e pode excluir avaliações curtas que constituem evidências diretas.

**Decisão final:** manter a recuperação original, sem aplicar o filtro mínimo de 30 caracteres.

#### 10.1.6. Perguntas fora do escopo e vagas

As sete perguntas fora do escopo e as três perguntas vagas foram utilizadas para investigar limitações qualitativas da recuperação.

A similaridade máxima observada nas perguntas fora do escopo variou aproximadamente de 0,52 a 0,74, sobrepondo-se aos valores das perguntas de domínio, aproximadamente de 0,67 a 0,86.

A pergunta Q16 apresentou similaridade máxima de 0,738, superior à observada em Q06 (0,666) e Q07 (0,685), embora estivesse fora do escopo das informações disponíveis.

As avaliações recuperadas podiam conter termos relacionados à pergunta, como "prazo", "garantia" ou "anunciado", sem fornecer evidências suficientes para respondê-la.

**Conclusão:** um limiar de similaridade isolado não permite distinguir, de forma confiável, perguntas respondíveis de perguntas sem evidência suficiente.

Nas perguntas vagas, Q17 e Q19 retornaram apenas quatro e duas avaliações distintas após a deduplicação, mesmo com o exame de 200 candidatos. Esse comportamento evidencia uma limitação da recuperação diante de consultas vagas e conjuntos altamente redundantes.

#### 10.1.7. Limitações da avaliação

A interpretação dos resultados considera as seguintes limitações:

- **Precisão, não recall:** não foi medida a quantidade de evidências relevantes existentes fora dos primeiros resultados.
- **Conjunto limitado de perguntas:** as médias representam nove perguntas de domínio e não garantem desempenho equivalente para todas as consultas possíveis.
- **Anotador único:** os rótulos finais foram atribuídos por um único avaliador humano, sem medição de concordância interavaliadores.
- **Critérios semânticos:** perguntas como Q04 e Q07 dependem de distinções específicas, como defeito explícito versus qualidade ruim e pedido de reembolso versus reclamação sobre o processo.
- **Ausência de testes de significância:** as médias e diferenças observadas são descritivas.
- **Redundância:** `candidate_occurrences` representa ocorrências entre os candidatos examinados, não a frequência dos textos na base completa.
- **Avaliação restrita à recuperação:** os resultados desta subseção não demonstram, por si só, a qualidade das respostas produzidas pelo LLM; essa dimensão é avaliada separadamente no Notebook 03.

### 10.2. Geração fundamentada com LLM — implementada

**Decisão:** implementar a geração em `src/rag.py`, utilizando o modelo `gemini-3.8-flash` pela API Google Gen AI e o recuperador semântico existente como única fonte de evidências para as respostas sobre consumidores.

**Justificativa:** a avaliação de recuperação demonstrou que documentos semanticamente relacionados nem sempre sustentam diretamente a pergunta. A geração deve selecionar evidências pertinentes, apresentar citações verificáveis e abster-se quando não houver suporte adequado.

**Estratégia implementada:**

1. Recuperar inicialmente **20 avaliações textualmente distintas** por pergunta (`top_k=20`).
2. Construir o contexto com os textos das avaliações e seus `review_id`.
3. Orientar o modelo a distinguir evidências diretas de semelhança apenas temática, sem extrapolar os relatos recuperados para toda a base.
4. Solicitar uma resposta sintética, normalmente em 2 a 4 frases, **sem inserir identificadores de avaliações no corpo de `answer`**; as fontes são apresentadas separadamente em `cited_review_ids`.
5. Validar a estrutura da saída e os identificadores citados, impedindo referências a avaliações não recuperadas.
6. Registrar `status` (`respondida`, `abstencao` ou `erro`), indicação de evidência insuficiente, motivo de abstenção e sinalizador `limited_evidence` quando aplicável. Menos de duas citações não implica abstenção automática.
7. Tratar falhas transitórias da API com tentativas adicionais para erros 429, 500 e 503, preservando erros técnicos como distintos de abstenções semânticas.

**Decisão sobre suficiência:** não utilizar um limiar isolado de similaridade para determinar se a pergunta pode ser respondida. A suficiência depende da adequação semântica das evidências, das instruções de geração e das validações estruturais.

**Alternativas não adotadas:** adicionar reranking, reescrita de consultas ou filtros rígidos de comprimento antes de verificar o comportamento da geração com a recuperação original. Também não foi adotada a obrigatoriedade de duas citações como condição para responder.

**Evidência:** implementação de `src/rag.py`, testes em `tests/test_rag.py` e avaliação empírica no Notebook 03, descrita a seguir.

### 10.3. Avaliação da geração — Notebook 03

#### 10.3.1. Escopo e metodologia

**Decisão:** avaliar manualmente as respostas e abstenções do RAG com as mesmas **19 perguntas** do experimento de recuperação: nove perguntas de domínio (Q01–Q09), sete fora do escopo (Q10–Q16) e três ambíguas (Q17–Q19).

**Justificativa:** verificar não apenas se o recuperador encontra documentos pertinentes, mas se a resposta final utiliza corretamente as fontes e se o sistema reconhece perguntas que não deve responder.

As nove respostas de domínio foram avaliadas por três critérios, cada um na escala de **0 a 2**: `faithfulness` (fidelidade às evidências), `citation_quality` (qualidade das citações) e `answer_quality` (qualidade da resposta). Para as dez perguntas que resultaram em abstenção, avaliou-se `abstention_correct` em escala binária (0 ou 1). A avaliação foi humana, com justificativas registradas individualmente.

**Artefatos:** `notebooks/03_generation_evaluation.ipynb`, `evaluation/generation_runs.jsonl` e `evaluation/generation_labels.csv`.

#### 10.3.2. Configuração e resultados

**Configuração avaliada:** `gemini-3.8-flash` (camada gratuita), `top_k=20`, `temperature=0`, prompt identificado por `a128a1fe07c1`. O conjunto contém 19 perguntas, com uma execução válida final por pergunta; tentativas anteriores com erros de API foram preservadas no histórico.

| Indicador | Resultado |
|---|---:|
| Perguntas com execução válida | 19/19 |
| Perguntas de domínio respondidas | 9/9 |
| Perguntas fora do escopo com abstenção | 7/7 |
| Perguntas vagas com abstenção | 3/3 |
| Fidelidade média (`faithfulness`) | 2,00/2 (9 respostas) |
| Qualidade média das citações (`citation_quality`) | 2,00/2 (9 respostas) |
| Qualidade média das respostas (`answer_quality`) | 2,00/2 (9 respostas) |
| Abstenções consideradas adequadas | 10/10 |
| Erros técnicos nas execuções finais válidas | 0 |

**Decisão:** complementar as notas humanas com uma comparação automática entre os `review_id` citados e os rótulos humanos de relevância (0, 1 ou 2) atribuídos no Notebook 02. Todos os 20 documentos recuperados para cada uma das nove perguntas de domínio estavam rotulados.

- **Precisão estrita das citações:** proporção de citações com rótulo 2 entre todas as citações emitidas.
- **Cobertura das evidências diretas recuperadas:** proporção de documentos de rótulo 2, presentes no top-20, que foram citados na resposta.

| Pergunta | Citações | Precisão estrita | Cobertura das evidências diretas no top-20 |
|---|---:|---:|---:|
| Q01 | 16 | 16/16 | 16/16 |
| Q02 | 19 | 18/19 | 18/19 |
| Q03 | 18 | 18/18 | 18/18 |
| Q04 | 2 | 2/2 | **2/5** |
| Q05 | 2 | 2/2 | 2/2 |
| Q06 | 3 | 3/3 | 3/3 |
| Q07 | 7 | 7/7 | **7/12** |
| Q08 | 16 | 16/16 | 16/18 |
| Q09 | 15 | 15/15 | 15/15 |
| **Total** | **98** | **97/98 (99,0%)** | **97/108 (89,8%)** |

Das 98 citações, 97 receberam rótulo 2 e uma recebeu rótulo 1 (Q02); nenhuma recebeu rótulo 0. A cobertura de 89,8% refere-se **somente às evidências diretas identificadas entre os 20 documentos recuperados por pergunta**, e não ao conjunto completo de avaliações Olist. A nota humana `citation_quality` avalia pertinência e sustentação da resposta; a cobertura é uma métrica separada e não integra essa nota.

A latência registrada variou de **25 a 1.854 segundos por pergunta** na camada gratuita da API. Houve tentativas com erros 429 e 503 antes da conclusão das 19 execuções válidas; essas falhas foram registradas como `erro`, nunca como abstenção.

#### 10.3.3. Interpretação e limitações

- **Seleção semântica das citações:** nas Q04–Q06, em que a recuperação apresentou baixa precisão estrita, as citações escolhidas pelo LLM receberam rótulo 2. Em Q05, o modelo citou duas avaliações diretas e não citou relatos que indicavam conformidade com o anúncio. Isso apoia o uso da seleção semântica pelo LLM, sem comprovar que `top_k=20` seja superior a outras configurações.
- **Cobertura desigual:** em Q04 foram citadas apenas 2 das 5 evidências diretas recuperadas; em Q07, 7 das 12. Portanto, uma resposta fiel às fontes citadas ainda pode omitir relatos pertinentes. Em Q08 a cobertura foi 16/18.
- **Q02 — fronteira semântica:** uma das 19 citações recebeu rótulo 1, pois mencionar um atraso não equivale necessariamente a reclamar dele. Essa distinção também explica parte das diferenças entre documentos recuperados e citados.
- **Q07 — formulação ambígua:** a expressão “recusa no recebimento de produtos danificados” admite interpretação diferente da avaliação sobre a empresa não aceitar devolução. Apesar da nota humana máxima, a formulação merece cautela.
- **Abstenções:** as dez decisões foram consideradas adequadas ao prompt atual, inclusive a recusa de Q16 apesar da similaridade relativamente alta. Em Q14, o motivo `evidencia_insuficiente` foi menos apropriado que `fora_do_escopo`; acerto da decisão não significa acerto da classificação do motivo.
- **Perguntas amplas:** Q18 (“Problemas com a compra”) recebeu abstenção por vagueza, coerente com as instruções atuais; um assistente exploratório poderia optar por apresentar um panorama inicial.
- **Consultas curtas:** Q17 e Q19 retornaram respectivamente quatro e duas avaliações distintas, com `retrieval_incomplete=True`, após a deduplicação de textos muito genéricos.
- **Limitações metodológicas:** uma execução válida por pergunta, nove perguntas de domínio com formatos semelhantes e avaliação manual por uma única pessoa. Notas no teto não demonstram generalização; `temperature=0` não assegura determinismo absoluto. Não houve comparação entre modelos nem medição de recall sobre toda a base.
- **Operação:** erros 429/503 e latência elevada na API gratuita podem comprometer a experiência de uso, embora as tentativas finais tenham sido concluídas.

**Decisão final:** manter `top_k=20` e o prompt `a128a1fe07c1` como linha de base para a interface inicial. Manter a decisão de suficiência baseada em análise semântica e validações explícitas, sem limiar isolado de similaridade. Registrar Q04 e Q07 como casos prioritários de cobertura insuficiente **dentro do top-20**.

**Experimento futuro condicionado à necessidade:** comparar `top_k=20` e `top_k=30`, preservando modelo, perguntas e critérios, para investigar se a cobertura melhora em Q04 e Q07. Os rótulos do Notebook 02 cobrem até a posição 30, mas a avaliação de novas respostas exigirá inspeção apropriada. Essa comparação ainda não foi realizada.

### 10.4. Auditoria das evidências

**Decisão:** preservar o histórico das execuções e oferecer no Notebook 03 uma seção específica para inspeção das fontes de cada resposta, sem realizar novas chamadas à API ou consultas ao ChromaDB.

**Justificativa:** permitir que terceiros verifiquem a correspondência entre pergunta, resposta, avaliações citadas e julgamento humano, distinguindo a auditoria do experimento original de uma nova execução potencialmente variável.

**Procedimento:** selecionar `AUDIT_QUESTION_ID` (Q01–Q19) na seção de auditoria do Notebook 03. A visualização utiliza os registros persistidos para exibir pergunta, resposta ou abstenção, `cited_review_ids`, textos das avaliações recuperadas e notas/justificativas de `generation_labels.csv`.

**Rastreabilidade:** `generation_runs.jsonl` preserva também tentativas com erros técnicos, que não devem ser confundidas com abstenções válidas. Para auditoria e métricas, deve-se selecionar a execução válida correspondente a cada pergunta e configuração experimental. O arquivo de rótulos humanos deve ser mantido sem sobrescrita.

**Controle de versão do prompt:** a configuração avaliada utiliza o identificador `a128a1fe07c1`. O experimento passou a registrar `prompt_sha256`, calculado a partir das instruções de sistema, template da pergunta e esquema de resposta. Algumas execuções legadas não possuem esse campo; seu reaproveitamento pressupõe a confirmação de que o prompt efetivo não foi alterado. O hash não substitui a preservação do código e dos resultados originais.

**Limite da auditoria:** conferir as evidências citadas permite avaliar a fundamentação das respostas registradas, mas não comprova que o recuperador encontrou todas as avaliações relevantes existentes no dataset.

---

## 11. Reprodutibilidade

### 11.1. Ordem de execução

1. `python -m src.download_data`
2. `python -m src.prepare_data`
3. `python -m src.build_index_data --reset`
4. `python -m src.retrieve "<pergunta>" --top-k 10`
5. Executar `notebooks/02_retrieval_evaluation.ipynb` com o índice persistente e os arquivos originais de avaliação.
6. Configurar a credencial do Gemini no `.env` local, sem versioná-la.
7. Executar `notebooks/03_generation_evaluation.ipynb`, preferencialmente com `RUN_BATCH = False` para consultar os resultados já registrados sem novas chamadas à API. A execução de um novo lote deve ser deliberada e preservar os resultados anteriores.
8. Utilizar a seção **Auditoria das evidências** do Notebook 03 para conferir as fontes e os julgamentos humanos.
9. `python -m pytest -q`

### 11.2. Rastreabilidade das avaliações

**Recuperação:**

- `evaluation/retrieval_candidates.csv`: resultados recuperados, incluindo identificadores, posição no ranking, similaridade e metadados.
- `evaluation/retrieval_labels.csv`: rótulos humanos de relevância associados aos pares `question_id` e `review_id`.

**Geração:**

- `evaluation/generation_runs.jsonl`: histórico das execuções, com perguntas, respostas, citações, documentos recuperados, status e eventuais erros técnicos.
- `evaluation/generation_labels.csv`: avaliação humana das respostas e abstenções, com notas, justificativas e identificação da configuração experimental.

A reprodução das métricas deve preservar os arquivos originais e selecionar apenas registros compatíveis com a configuração avaliada. Novas execuções da recuperação ou geração podem produzir diferenças de ranking, conteúdo ou resposta; os rótulos antigos não devem ser associados automaticamente a resultados novos.

**Auditoria versus reprodução:** a auditoria verifica as respostas e fontes efetivamente registradas, sem depender da API do Gemini ou do índice vetorial. A reprodução completa exige reconstruir o ambiente e pode produzir resultados diferentes; portanto, não substitui a auditoria do histórico original.

### 11.3. Pendências de reprodutibilidade

- Fixar ou documentar versões das dependências críticas, especialmente `chromadb`, `sentence-transformers` e `google-genai`.
- Confirmar que os arquivos de avaliação necessários à auditoria estão versionados e acessíveis ao avaliador, respeitando o `.gitignore`.
- Confirmar que `data/`, credenciais e demais arquivos locais não destinados ao repositório estão no `.gitignore`.
- Documentar no README a obtenção do dataset e a configuração local da API, sem publicar credenciais ou versionar os dados originais.
- Executar novamente a suíte completa de testes após as últimas alterações no controle de versão do prompt.

---

## 12. Estado atual do projeto

**Concluído:**

- Configuração do ambiente Python e Git e criação do repositório GitHub.
- Download automatizado do dataset, análise exploratória e preparação de 42.138 documentos.
- Geração local de embeddings e indexação persistente no ChromaDB.
- Recuperação semântica com deduplicação, expansão adaptativa e rastreabilidade.
- Notebook 02: avaliação da recuperação com 19 perguntas e 270 pares classificados manualmente nas nove perguntas de domínio; comparação do filtro de 30 caracteres concluída.
- Integração com `gemini-3.8-flash` em `src/rag.py`, incluindo geração fundamentada, citações, abstenções e tratamento de falhas transitórias.
- Testes automatizados de geração adicionados; a suíte completa registrou 77 testes aprovados antes das últimas alterações de versionamento do prompt.
- Notebook 03: 19 execuções válidas, avaliação humana de nove respostas e dez abstenções, precisão estrita das citações de 97/98 (99,0%) e cobertura das evidências diretas do top-20 de 97/108 (89,8%), com limitações documentadas.
- Seção de auditoria das evidências disponibilizada no Notebook 03.
- Linha de base de geração definida: `gemini-3.8-flash`, `top_k=20`, `temperature=0`, prompt `a128a1fe07c1`.

**Pendente:**

- Interface Streamlit.
- Consolidação das instruções de instalação, execução e auditoria no README.
- Verificação complementar do limite de 128 tokens do modelo de embeddings.
- Etapa de transformação da pergunta além da normalização de espaços, conforme requisito identificado na seção 9.1.
- Conferência final de versionamento dos arquivos de avaliação e das dependências.
- Nova execução da suíte de testes e preparação do vídeo de demonstração de até 7 minutos.
- Se houver necessidade demonstrada, comparar `top_k=20` e `top_k=30` para investigar cobertura em Q04 e Q07; não tratar essa comparação como já executada.

**Próxima etapa:** implementar a interface Streamlit utilizando o pipeline RAG avaliado, sem alterar o prompt ou as regras de geração sem necessidade demonstrada.
