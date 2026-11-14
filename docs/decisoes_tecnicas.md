
# Decisões Técnicas — Voice of Customer Intelligence com RAG

## 1. Objetivo

Este documento registra as decisões técnicas adotadas no desenvolvimento do Tech Challenge — Fase 4, cujo objetivo é construir uma aplicação de Voice of Customer Intelligence baseada em Retrieval-Augmented Generation (RAG).

A aplicação permite consultar avaliações de consumidores do dataset Olist, recuperando evidências relevantes para fundamentar respostas geradas por um modelo de linguagem.

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

O comprimento `n_chars` é preservado como metadado. A suficiência das evidências é avaliada durante a geração e a validação da resposta; o comprimento, isoladamente, não determina relevância.

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
| excelente | 282 |
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

A estratégia de deduplicação foi implementada em `src/retrieve.py` e avaliada no Notebook 02. O campo `candidate_occurrences` se refere apenas aos candidatos examinados naquela consulta, não à frequência global do texto no corpus.

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
| Média | 69,09 |
| Mediana | 54 |
| Percentil 90 | 162 |
| Percentil 95 | 193 |
| Percentil 99 | 209 |
| Máximo | 228 |
| Documentos com menos de 10 caracteres | 3.536 |

### 5.4. Estratégia de fragmentação

**Decisão:** não aplicar chunking.

Cada avaliação é representada por um único documento.

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

**Decisão:** utilizar `pytest` para testar funções de preparação textual.

**Justificativa:** garantir que alterações futuras não comprometam regras já validadas.

**Alternativa descartada:** depender apenas da execução manual do pipeline.

**Evidência histórica:** a fase inicial de preparação registrou 20 testes aprovados para construção de documentos e chaves de deduplicação. **Estado atual:** a suíte pré-commit passou com 96/96 testes no Windows em 13/11/2026 (uma versão intermediária passou com 97/97). Os 20 testes referem-se a uma etapa anterior, não ao total atual.

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

Uma nota baixa não garante que o texto descreva uma reclamação, assim como uma nota alta não impede a presença de críticas.

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

Na versão atual, respostas de síntese restringem suas conclusões às avaliações efetivamente recuperadas. Perguntas exploratórias amplas são aceitas quando há evidências; não são produzidas frequências globais sem análise do corpus.

---

## 8. Embeddings e armazenamento vetorial — decisão implementada

**Decisão:** gerar embeddings localmente com `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` e armazenar os documentos em uma coleção persistente do ChromaDB (`olist_reviews`), com distância cosseno.

**Justificativa:** modelo multilíngue adequado ao português, sem custo por embedding na API, com persistência local e capacidade de reconstrução do índice.

**Alternativas não adotadas:** depender de serviço remoto de embeddings ou introduzir uma camada de orquestração adicional sem necessidade demonstrada. O pipeline foi implementado diretamente em Python, sem LangChain.

**Evidência:** `src/build_index_data.py`, `src/config.py`, `src/retrieve.py`, Notebook 02. A base preparada possui 42.138 documentos distintos.

### 8.1. Recuperação e controle de redundância

**Decisão:** recuperar candidatos por similaridade semântica, deduplicar por `dedup_key` normalizado e utilizar **`top_k=20`** como configuração de referência para a geração. A recuperação pode examinar mais candidatos antes de selecionar as avaliações finais.

**Justificativa:** equilibrar evidências disponíveis, redundância e tamanho do contexto. Não utilizar um limiar global de similaridade como único mecanismo de detecção de perguntas fora do escopo, pois a avaliação mostrou que esse sinal não separa adequadamente todos os casos.

**Evidência:** Notebook 02, com 9 consultas do domínio, 270 julgamentos humanos sobre candidatos e avaliação de relevância em escala 0–2. A Precision@10/20/30 estrita foi, respectivamente, **60,0%, 60,0% e 58,9%**; a tolerante, **93,3%, 91,7% e 90,0%**. As perguntas Q04–Q06 tiveram menor quantidade de evidências diretamente relevantes. Um filtro experimental de textos com menos de 30 caracteres não trouxe melhoria consistente e não foi adotado.

**Limitação:** relevância dos documentos selecionados não garante recuperação exaustiva das avaliações existentes. A comparação de `top_k=20` com `top_k=30` na geração permanece uma possibilidade futura, não uma melhoria comprovada.

---

## 9. Geração fundamentada, citações e abstenção

**Decisão:** utilizar Gemini (`gemini-3.8-flash` no ambiente avaliado), com contexto formado pelas avaliações recuperadas, resposta estruturada e validação dos identificadores citados.

**Justificativa:** produzir sínteses curtas sustentadas por comentários verificáveis e distinguir ausência de evidência de falhas operacionais.

**Implementação:** `src/rag.py` separa `status` em `respondida`, `abstencao` e `erro`. As citações são apresentadas em campo separado da síntese, conforme instrução do prompt; portanto, a ausência de IDs dentro do texto da resposta não constitui falha. O indicador `limited_evidence` sinaliza quantidade reduzida de citações, sem implicar abstenção automática.

**Abstenções:** contemplam perguntas fora do escopo, perguntas vagas e evidência insuficiente. Erros técnicos não são classificados como abstenções legítimas.

**Controle experimental:** a avaliação histórica de 19 perguntas utilizou `top_k=20` e registra o prefixo SHA-256 **`a128a1fe07c1`** como identificador do prompt histórico. As 19 execuções válidas não gravaram `prompt_sha256` (anteriores ao registro do hash). Em 13/11/2026, o hash foi recalculado a partir da versão de `src/rag.py` anterior à revisão do prompt (instrução, schema e template) e resultou em `a128a1fe07c1`, igual ao registrado; o Notebook 03 trata registros sem hash como pertencentes a esse prompt histórico (`HISTORICAL_PROMPT_SHA256`). O hash do prompt atual é **`d26713c2be2d`**. Em 13/11/2026, as instruções foram alteradas para aceitar perguntas exploratórias amplas e distinguir melhor `pergunta_vaga` de `evidencia_insuficiente`; **o hash histórico não identifica o prompt atual**. A avaliação histórica não foi sobrescrita nem deve ser apresentada como avaliação integral da nova versão. O parâmetro `top_k=20` foi preservado.

---

## 10. Avaliação de geração e auditoria

**Conjunto histórico de avaliação (anterior aos ajustes de prompt):** 19 perguntas — 9 pertinentes ao domínio, 7 fora do escopo e 3 ambíguas. Os resultados e julgamentos humanos estão em `evaluation/generation_runs.jsonl` e `evaluation/generation_labels.csv`, respectivamente.

| Métrica | Resultado |
|---|---:|
| Execuções válidas | 19/19 |
| Respostas fundamentadas avaliadas | 9 |
| Fidelidade média às evidências | 2,00/2 |
| Qualidade média das citações | 2,00/2 |
| Qualidade média das respostas | 2,00/2 |
| Decisões de abstenção consideradas adequadas | 10/10 |
| Precisão estrita das citações selecionadas | 97/98 (99,0%) |
| Cobertura das evidências diretas recuperadas no top-20 | 97/108 (89,8%) |

**Interpretação:** precisão das citações mede a proporção de citações selecionadas julgadas diretamente pertinentes; cobertura mede a proporção das evidências diretas **presentes no top-20 recuperado** que foram citadas. Nenhuma das duas métricas representa cobertura de toda a base Olist.

**Limitações observadas:** cobertura menor em Q04 (**2/5**) e Q07 (**7/12**); em Q14, a decisão de abstenção foi adequada, mas o motivo `evidencia_insuficiente` foi menos preciso que `fora_do_escopo`; Q18 foi considerada vaga conforme o **prompt histórico**, embora a versão atual aceite perguntas exploratórias amplas quando há evidências. O tamanho reduzido e a seleção intencional do conjunto de teste limitam a generalização dos resultados.

**Auditoria:** o Notebook 03 permite conferir respostas, identificadores e textos citados, bem como notas humanas, a partir dos registros persistidos, sem novas chamadas ao Gemini. Os resultados históricos não devem ser confundidos com nova inferência.

---

## 11. Interface Streamlit e operação

**Decisão:** disponibilizar um MVP de página única em `app.py`, reutilizando `src/rag.py` sem duplicar a lógica de geração ou recuperação.

**Consulta ao vivo:** carrega coleção ChromaDB e modelo de embeddings com cache; exibe síntese, evidências expandidas, abstenções e erros técnicos em estados separados.

**Modo demonstração:** lê `evaluation/generation_runs.jsonl` e reproduz execuções válidas do Notebook 03 sem acessar Gemini ou carregar os embeddings. A interface informa explicitamente que esses resultados foram gerados com um prompt anterior e podem diferir das consultas ao vivo. É útil para apresentação auditável quando a API está indisponível, mas não substitui a integração ao vivo.

**Tratamento de falhas:** o cliente Gemini usa timeout configurado de 90 segundos por chamada e até **duas tentativas**, com intervalo de **5 segundos** para erros transitórios tratados. Os códigos explicitamente classificados como repetíveis incluem 429, 500 e 503. Outros erros, incluindo 504, podem ser apresentados como falha técnica, sem presumir sucesso ou evidência insuficiente. O limite de tentativas foi reduzido de quatro para duas para preservar a cota gratuita.

**Evidência operacional:** houve consulta ao vivo concluída e demonstrada com citações; outras tentativas apresentaram 503/504. O painel do Google AI Studio mostrou limites de **5 RPM** e **20 RPD** no projeto gratuito observado, com **26 requisições registradas para um limite de 20 por dia**, isto é, o limite foi excedido. O critério exato de contagem (por exemplo, se inclui tentativas rejeitadas) não foi verificado, e as falhas não são atribuídas exclusivamente à cota. A disponibilidade futura do provedor não é garantida.

**Alternativas não adotadas:** autenticação, armazenamento de conversas, implantação em nuvem e novos recursos de interface, por não serem necessários ao escopo do MVP acadêmico.

---

## 12. Testes e reprodutibilidade

**Decisão:** validar a execução do MVP em Linux e em uma instalação nova no Windows, mantendo Python 3.12 e dependências diretas fixadas em `requirements.txt`.

**Testes automatizados:** **89/89 aprovados** na versão anterior no Linux (7,31 segundos) e no Windows com Python **3.12.10** (32,94 segundos). A versão intermediária dos ajustes registrou **97/97 aprovados no Windows** (17,69 segundos). Após a revisão pré-commit do prompt e da suíte, **96/96 aprovados no Windows** em 13/11/2026 (18,68 segundos). A contagem menor decorre da revisão dos testes e não representa, por si só, perda de funcionalidade. O ambiente Windows foi preparado a partir da instalação do Python, criação de `.venv` e instalação das dependências. A execução bem-sucedida demonstra portabilidade nos dois ambientes testados, sem comprovar compatibilidade com qualquer sistema ou configuração.

**Pipeline de dados no Windows:** os scripts `src/download_data.py`, `src/prepare_data.py` e `src/build_index_data.py` foram executados nessa ordem. A preparação produziu **42.138 documentos**, o mesmo total observado no Linux. O ChromaDB foi reconstruído com o modelo `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`, distância cosseno e 42.138 documentos. A recuperação foi verificada em um **processo Python separado** com `python -m src.retrieve "produto não chegou" --top-k 5`, retornando cinco avaliações relevantes.

**Interface e integração:** no Windows, foram validados os dois modos Streamlit: **Demonstração com resultados salvos** e **Consulta ao vivo**, esta última envolvendo recuperação vetorial e geração via Gemini. Portanto, a validação integrada que anteriormente estava pendente foi concluída.

**Dependências:** `requirements.txt` fixa as dependências diretas testadas; `requirements-lock.txt` registra o snapshot do ambiente Linux/Python 3.12, incluindo pacotes CUDA/NVIDIA específicos desse ambiente. O lock não é universal entre plataformas. A instalação Windows e a suíte de testes foram executadas com sucesso usando `requirements.txt`.

**Artefatos versionados:** notebooks 01–03, `evaluation/retrieval_candidates.csv`, `evaluation/retrieval_labels.csv`, `evaluation/generation_runs.jsonl`, `evaluation/generation_labels.csv` e este documento. Os dados brutos e o índice ChromaDB permanecem locais e reconstruíveis.

---

## 12.1. Validação direcionada da versão atual — 13/11/2026

**Objetivo:** verificar as mudanças do prompt sem substituir os experimentos históricos ou alterar o índice, os embeddings e a recuperação.

| Consulta ao vivo | Resultado observado | Avaliação manual |
|---|---|---|
| Principais problemas relatados pelos clientes | Síntese qualitativa com 11 avaliações citadas e ressalva sobre frequência | Adequado |
| Previsão do tempo para amanhã em São Paulo | Abstenção por `fora_do_escopo` | Adequado |
| “Foi bom?” | Abstenção por `pergunta_vaga` | Adequado |
| Reembolso em bitcoin após entrega por drone | Abstenção por `evidencia_insuficiente`, sem citações inventadas | Adequado após ajuste de prompt |
| Problemas de atraso na entrega | Síntese sustentada por 7 avaliações citadas | Adequado |
| Dificuldades de contato com vendedores | Síntese sustentada por 8 avaliações citadas | Adequado |
| Produtos diferentes dos anunciados | Síntese sustentada por 5 avaliações citadas | Adequado |

**Escopo e limitação:** os sete casos foram revisados manualmente a partir das saídas da interface, sem nova rotulagem independente ou cálculo de métricas populacionais. A validação de IDs no código não substitui a avaliação semântica das citações. A ausência de evidência no conjunto recuperado não prova ausência do fato em toda a base. O teste de bitcoin/drone foi inicialmente classificado como `pergunta_vaga`; após revisão das instruções, a nova consulta retornou `evidencia_insuficiente`.


### 12.2. Verificação pré-commit da versão revisada — 13/11/2026

Após remover exemplos literais do prompt para reduzir o risco de validação circular, foram executadas **três perguntas inéditas** de abstenção no modo ao vivo:

| Pergunta | Classificação observada | Resultado |
|---|---|---|
| Qual é a capital da Austrália? | `fora_do_escopo` | Abstenção sem resposta de conhecimento geral |
| E quanto a isso? | `pergunta_vaga` | Pedido de especificação do tema |
| Quais compradores receberam um reembolso em criptomoedas após uma entrega feita por submarino? | `evidencia_insuficiente` | Abstenção sem casos ou citações inventadas |

Uma quarta consulta perguntou **quais reclamações relacionadas à entrega aparecem com maior frequência**. O Gemini apresentou síntese qualitativa sustentada por **11 avaliações citadas** e declarou explicitamente que as avaliações recuperadas não permitem medir a frequência estatística no corpus completo. A resposta não constitui ranking populacional.

O aviso do modo demonstração foi atualizado e verificado em captura de tela: os resultados são históricos, provenientes do Notebook 03, e podem diferir do prompt atual. A suíte automatizada passou com **96/96 testes no Windows (18,68 segundos)** após essas alterações. Os testes com mocks verificam contratos e regras locais, **não** comprovam generalização do LLM. As quatro consultas adicionais são verificações pontuais, não nova avaliação sistemática das 19 perguntas históricas.
---

## 13. Estado final do MVP e próximos passos opcionais

**Concluído:** preparação, indexação, recuperação semântica, geração fundamentada, avaliações manuais, auditoria das evidências, interface Streamlit, demonstração offline e suíte automatizada.

**Decisão de encerramento:** preservar a versão pré-commit validada em 96 testes automatizados no Windows, sete consultas direcionadas anteriores e quatro consultas adicionais pré-commit, concluir a documentação e preparar a entrega do Tech Challenge. Os resultados do Notebook 03 permanecem identificados como históricos, sem alegação de reavaliação completa do novo prompt.
