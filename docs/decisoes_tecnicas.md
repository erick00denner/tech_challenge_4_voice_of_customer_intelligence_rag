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

Na consulta `não recebi o produto`, os oito primeiros resultados tinham menos de 30 caracteres, o que sugere que textos curtos podem dominar o topo do ranking. O efeito será medido na avaliação da recuperação (seção 10.1).

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

**Decisão:** utilizar `pytest` para testar funções de preparação textual e de recuperação.

**Justificativa:** garantir que alterações futuras não comprometam regras já validadas.

**Alternativa descartada:** depender apenas da execução manual do pipeline.

**Evidência:** a execução de `python -m pytest -q` concluiu com **41 testes aprovados** (20 de preparação e 21 de recuperação). Os testes cobrem construção de documentos, chaves de deduplicação, detecção de letras, consolidação de `review_id`, deduplicação na recuperação, expansão adaptativa de candidatos, flags de retorno e tratamento de entradas inválidas.

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

**Pendente:** verificar se o documento mais longo da base (228 caracteres) cabe no limite de 128 tokens do modelo, tokenizando-o e registrando o resultado. Textos acima do limite seriam truncados pelo modelo na geração do embedding.

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

Esses resultados demonstram funcionamento técnico, mas **não comprovam ainda precisão, cobertura temática ou qualidade das respostas**.

---

## 10. Próximas decisões — Avaliação e geração

### 10.1. Avaliação da recuperação (notebook 02)

**Abordagem prevista:** construir `notebooks/02_retrieval_evaluation.ipynb` com 12 perguntas previamente definidas, incluindo nove consultas dentro do escopo e três fora do escopo.

Serão analisados:

- Relevância manual dos documentos e Precision@k.
- Cobertura temática qualitativa, incluindo temas relevantes ausentes.
- Comparação de `top_k` igual a 10, 20 e 30, mantendo fixos o modelo, o índice, as perguntas e os critérios de julgamento.
- Qualidade da resposta gerada em cada `top_k`, pois a Precision@k tende a cair com valores maiores mesmo quando o contexto melhora.
- Variante de seleção com mínimo de 30 caracteres, sem alterar o índice.
- Quantidade de candidatos examinados, redundância e recuperação incompleta.
- Tempo de recuperação (registrado, sem peso na decisão) e tamanho do contexto em tokens.

**Critério de relevância (a confirmar antes do julgamento):** uma avaliação é relevante quando seu texto menciona explicitamente o tema da pergunta. A relevância é julgada pelo conteúdo textual, nunca pela nota. Perguntas fora do escopo são avaliadas por acerto binário de recusa.

**Perguntas de teste:** as 12 perguntas devem ser registradas neste documento antes da avaliação, distribuídas entre reclamações, entrega, elogios, qualidade de produtos, insatisfação e fora do escopo (por exemplo, "Qual o melhor smartphone de 2025?").

**Cuidados metodológicos:** a comparação com filtro de comprimento precisa recuperar candidatos suficientes antes de selecionar os documentos. Perguntas fora do escopo exigem avaliação específica de abstenção após a implementação da geração.

### 10.2. Respostas fundamentadas e abstenção

**Abordagem prevista:** gerar respostas com identificação das avaliações usadas como evidência, restringindo conclusões ao contexto recuperado.

**Pendente:** definir o provedor e o modelo de linguagem, implementar a integração com a LLM, a construção do contexto, a calibração da suficiência das evidências e a recusa fundamentada quando a pergunta não puder ser respondida. Similaridade elevada e quantidade de resultados, isoladamente, não garantem evidência suficiente. O limiar mínimo de similaridade será calibrado com consultas reais, incluindo perguntas fora do escopo.

Para perguntas de padrões ou frequência, a versão inicial deverá empregar linguagem cautelosa, como "nas avaliações recuperadas", sem inferir frequências globais a partir do top-k ou de `candidate_occurrences`.

---

## 11. Reprodutibilidade

Ordem de execução:

1. `python -m src.download_data`
2. `python -m src.prepare_data`
3. `python -m src.build_index_data --reset`
4. `python -m src.retrieve "<pergunta>" --top-k 10`
5. `python -m pytest -q`

**Pendente:** fixar no `requirements.txt` as versões de `chromadb` e `sentence-transformers`, pois a configuração da métrica e as exceções do Chroma dependem da versão. Confirmar que `data/` e arquivos de credenciais estão no `.gitignore` e documentar no README o download do dataset (sem versionar os CSVs).

---

## 12. Estado atual do projeto

**Concluído:**

- Configuração do ambiente Python e Git e criação do repositório GitHub.
- Download automatizado do dataset e análise exploratória.
- Preparação, consolidação e validação da base com 42.138 documentos.
- Geração local de embeddings e indexação persistente no ChromaDB, com distância cosseno.
- Implementação do recuperador semântico com deduplicação, expansão adaptativa, rastreabilidade e sinalização de limites.
- 41 testes aprovados na suíte completa (21 deles de recuperação).
- Validação funcional com consultas reais ao índice.

**Pendente:**

- Definição das 12 perguntas e do critério de relevância.
- Calibração do limiar de similaridade com consultas reais (entrega, qualidade, elogios e fora do escopo).
- Etapa de transformação da pergunta além da normalização de espaços.
- Verificação do limite de 128 tokens do modelo.
- Escolha da LLM, geração das respostas e mecanismo de abstenção.
- Interface Streamlit, README e vídeo de até 7 minutos.

**Próxima etapa:** criar o notebook `02_retrieval_evaluation.ipynb`, definir os critérios de relevância e executar a avaliação comparativa antes da integração com a LLM.
