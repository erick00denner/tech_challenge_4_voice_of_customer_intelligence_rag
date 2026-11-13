# Voice of Customer Intelligence com RAG

**Tech Challenge — Fase 4 | FIAP Pós-Tech**

Aplicação de *Retrieval-Augmented Generation* (RAG) para explorar avaliações históricas de consumidores do dataset público **Brazilian E-Commerce Public Dataset by Olist**, produzindo respostas sintéticas acompanhadas das avaliações que as fundamentam.

## Funcionalidades

- **Consulta ao vivo:** pergunta em linguagem natural, recuperação semântica no ChromaDB e geração de resposta fundamentada pelo Gemini.
- **Evidências auditáveis:** exibição do texto original e `review_id` de cada avaliação citada.
- **Abstenção:** perguntas vagas, fora do escopo ou sem evidências suficientes podem ser recusadas explicitamente.
- **Modo demonstração:** reprodução de resultados salvos do Notebook 03, sem chamada à API e sem carregar o modelo de embeddings.
- **Tratamento de erros:** falhas externas são apresentadas separadamente de abstenções por insuficiência de evidência.

> O sistema resume **avaliações recuperadas**, não calcula frequências representativas de todos os consumidores, nem responde a políticas comerciais atuais da Olist.

## Tecnologias

Python 3.12, Streamlit, ChromaDB, Sentence Transformers (`paraphrase-multilingual-MiniLM-L12-v2`), Google GenAI/Gemini, Pandas, Kagglehub, Jupyter e pytest. A implementação utiliza módulos Python próprios; **LangChain não é uma dependência do pipeline entregue**.

## Pré-requisitos

- Python **3.12** e acesso à internet para instalação de bibliotecas, download do dataset e download inicial do modelo de embeddings.
- Chave de API do Gemini para o modo de consulta ao vivo; o modo demonstração não exige chave.
- Espaço em disco para o dataset, o modelo de embeddings e o índice vetorial local.

## Instalação

Na raiz do repositório:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pip check
```

No **Windows (CMD)**, use os comandos abaixo na raiz do projeto:

```cmd
py -3.12 -m venv .venv
.venv\Scripts\activate.bat
python -m pip install -r requirements.txt
python -m pip check
```

O projeto foi validado em uma instalação nova no Windows com **Python 3.12.10**. Ambientes virtuais não devem ser copiados entre máquinas ou movidos entre diretórios: recrie `.venv` no local definitivo do projeto.

O `requirements.txt` fixa as versões **diretas** utilizadas no ambiente de referência. `requirements-lock.txt` registra também dependências transitivas do ambiente Linux/Python 3.12, inclusive pacotes específicos de CUDA; não deve ser tratado como lock universal para todas as plataformas.

## Configuração da API

```bash
cp .env.example .env
```

Edite `.env`:

```dotenv
GEMINI_API_KEY=sua_chave_aqui
GEMINI_MODEL=gemini-3.8-flash
```

**Nunca versione `.env` ou a chave de API.** O nome do modelo deve corresponder a um modelo efetivamente disponível para o projeto Google utilizado. O ambiente de avaliação usou `gemini-3.8-flash`.

## Preparação dos dados e construção do índice

O dataset é obtido da [fonte pública Olist no Kaggle](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce). Execute, na ordem:

```bash
python -m src.download_data
python -m src.prepare_data
python -m src.build_index_data
```

Para reconstruir deliberadamente uma coleção já existente:

```bash
python -m src.build_index_data --reset
```

O pipeline parte de **99.224 registros originais** e produz **42.138 documentos textuais distintos** após preparação e consolidação. O índice persistente é armazenado em `data/chroma/` e não precisa ser versionado; pode ser reconstruído a partir dos dados originais. O download e a indexação podem exigir tempo e memória conforme a máquina.

## Executar a interface

```bash
python -m streamlit run app.py --server.fileWatcherType none
```

Abra o endereço local exibido pelo Streamlit (normalmente `http://localhost:8501`). A opção `--server.fileWatcherType none` evita avisos de monitoramento `inotify` observados no ambiente Linux; após mudanças de código, reinicie manualmente o servidor.

### Consulta ao vivo

Selecione **Consulta ao vivo**, digite uma pergunta sobre experiências de compra e clique em **Consultar avaliações**. Exemplo:

> Quais problemas os consumidores relatam sobre atrasos na entrega?

Esse modo exige `.env` configurado, índice ChromaDB disponível e acesso à API Gemini. O fluxo utiliza `src/rag.py` e o parâmetro de referência `top_k=20`.

### Demonstração sem API

Selecione **Demonstração com resultados salvos** e escolha uma pergunta do Notebook 03. Esse modo exige o arquivo versionado `evaluation/generation_runs.jsonl`, mas **não faz uma nova inferência**. Casos ilustrativos:

- **Q01:** resposta fundamentada com citações.
- **Q12:** abstenção por pergunta fora do escopo.
- **Q19:** abstenção por pergunta vaga.

Os resultados são históricos, foram gerados com uma versão anterior do prompt e podem diferir das consultas ao vivo. A interface exibe esse aviso explicitamente.

## Testes

```bash
python -m pytest -q
```

**Histórico de validação:** **89/89 testes aprovados** na validação original no Linux (7,31 segundos) e no Windows com Python 3.12.10 (32,94 segundos). Após a revisão pré-commit do prompt e dos testes, **96/96 testes aprovados no Windows** (18,68 segundos, execução informada em 13/11/2026). A versão intermediária havia registrado 97/97 testes (17,69 segundos); a diferença decorre da revisão dos testes, não de uma nova avaliação completa do Gemini. A suíte atualizada não foi reexecutada no Linux. A instalação das dependências, a preparação dos dados e a reconstrução do índice também foram verificadas no Windows. Esses resultados demonstram a execução nos ambientes testados, não compatibilidade universal com qualquer plataforma. Alguns testes da interface requerem `evaluation/generation_runs.jsonl` disponível.

## Avaliação e rastreabilidade

| Artefato | Finalidade |
|---|---|
| `notebooks/01_exploratory_analysis.ipynb` | Exploração e qualidade dos dados |
| `notebooks/02_retrieval_evaluation.ipynb` | Avaliação manual da recuperação semântica |
| `notebooks/03_generation_evaluation.ipynb` | Avaliação de geração, abstenção e auditoria de evidências |
| `evaluation/retrieval_labels.csv` | Julgamentos humanos de relevância |
| `evaluation/retrieval_candidates.csv` | Candidatos recuperados para avaliação |
| `evaluation/generation_runs.jsonl` | Respostas, evidências e execuções registradas |
| `evaluation/generation_labels.csv` | Notas e observações da avaliação humana |
| `docs/decisoes_tecnicas.md` | Decisões, métricas e limitações |

**Resultados históricos de geração, anteriores aos ajustes de prompt (19 perguntas):** 9 respostas avaliadas, médias 2,00/2 em fidelidade, qualidade das citações e qualidade da resposta; 10/10 decisões de abstenção consideradas adequadas. Precisão estrita das citações: **97/98 (99,0%)**; cobertura das evidências diretas presentes no top-20: **97/108 (89,8%)**. Esses números descrevem o conjunto avaliado, não desempenho garantido em produção.

## Arquitetura e fluxo RAG

```text
Pergunta do usuário (Streamlit)
          |
          v
Normalização de espaços (`src/retrieve.py`)
          |
          v
Embedding da pergunta (Sentence Transformers, local)
          |
          v
Busca vetorial no ChromaDB + deduplicação por `dedup_key`
          |
          v
Até 20 avaliações selecionadas (`top_k=20`)
          |
          v
Contexto textual + instruções de segurança (`src/rag.py`)
          |
          v
Gemini -> JSON estruturado -> validação de IDs e estado
          |
          v
Resposta, evidências citadas ou abstenção (Streamlit)
```

**Ingestão (executada antes das consultas):** download do dataset Olist -> seleção e limpeza -> consolidação por `review_id` -> embeddings locais -> índice persistente ChromaDB. O modelo Gemini **não** consulta diretamente o CSV completo: recebe apenas o contexto recuperado. A aplicação não calcula ranking estatístico de reclamações no corpus.

## Exemplos de perguntas e respostas observadas

Os textos abaixo são **transcrições literais de consultas ao vivo realizadas em 13/11/2026**, registradas nas capturas de validação. Não são respostas recalculadas ao abrir o README. Os resultados dependem das avaliações recuperadas e do prompt utilizado na ocasião.

**Pergunta:** Quais são as reclamações relacionadas à entrega que aparecem com maior frequência entre os clientes?

**Resposta observada (11 avaliações citadas):**

> As avaliações recuperadas não permitem medir a frequência estatística das ocorrências no corpus completo, mas apontam os principais temas de insatisfação. Os clientes relatam atrasos excessivos, prazos prolongados e pedidos não entregues mesmo após o pagamento. Também são mencionadas entregas divididas ou parciais sem aviso prévio, além de comunicação deficiente e informações confusas sobre o status do envio.

**Pergunta:** Qual é a capital da Austrália?

**Resposta observada (`fora_do_escopo`, sem citações):**

> A pergunta não tem relação com a experiência de compra descrita nas avaliações de consumidores, tratando-se de um tema de conhecimentos gerais que está fora do escopo desta análise.

**Pergunta:** E quanto a isso?

**Resposta observada (`pergunta_vaga`, sem citações):**

> A pergunta é vaga e não apresenta um assunto ou referência identificável para análise nas avaliações. Por favor, forneça mais detalhes ou especifique o tema sobre a experiência de compra que deseja consultar.

**Pergunta:** Quais compradores receberam um reembolso em criptomoedas após uma entrega feita por submarino?

**Resposta observada (`evidencia_insuficiente`, sem citações):**

> Não foram encontradas evidências nas avaliações que relatem compradores recebendo reembolso em criptomoedas ou entregas realizadas por submarino. Os relatos disponíveis tratam de outros problemas comuns de entrega e reembolsos convencionais.

**Outras validações documentadas:** pergunta exploratória geral (11 avaliações citadas); atraso na entrega (7); dificuldades de contato com vendedores (8); produtos diferentes dos anunciados (5); e três cenários de abstenção anteriores à revisão pré-commit. As **sete consultas anteriores e as quatro consultas pré-commit** constituem verificações manuais direcionadas, não uma taxa de acerto estatisticamente representativa. O prompt atual não contém os exemplos literais de abstenção utilizados na primeira rodada; os resultados históricos do Notebook 03 permanecem separados.

## Estrutura do repositório

```text
app.py                      # Interface Streamlit
src/                        # Download, preparação, indexação, recuperação e RAG
scripts/                    # Verificações auxiliares
notebooks/                  # EDA e avaliações experimentais
evaluation/                 # Candidatos, resultados e julgamentos humanos
tests/                      # Testes automatizados
docs/decisoes_tecnicas.md   # Registro das decisões técnicas
requirements.txt            # Dependências diretas fixadas
requirements-lock.txt       # Snapshot completo do ambiente de referência
.env.example                # Modelo de configuração sem credenciais
data/                       # Dados e índice locais, não versionados
```

## Validação de ponta a ponta no Windows

A validação foi realizada em uma máquina Windows com Python 3.12.10, partindo de uma instalação nova de dependências. Foram confirmados:

1. Instalação e execução dos **89 testes automatizados da versão original**; posteriormente, **96 testes da versão pré-commit** passaram no Windows (uma versão intermediária registrou 97).
2. Download dos dados Olist e preparação de **42.138 documentos**, em concordância com o ambiente Linux.
3. Reconstrução do índice ChromaDB com **42.138 documentos**, embeddings `paraphrase-multilingual-MiniLM-L12-v2` e distância cosseno.
4. Recuperação independente pelo comando `python -m src.retrieve "produto não chegou" --top-k 5`, com cinco avaliações retornadas.
5. Funcionamento do Streamlit tanto em **Consulta ao vivo** (Gemini + ChromaDB) quanto em **Demonstração com resultados salvos**.

**Incidente observado:** o primeiro índice construído no Windows funcionou no teste interno de indexação, mas apresentou `Error loading hnsw index` quando aberto por um novo processo Python. Mover o projeto para fora do OneDrive e recriar o ambiente virtual não resolveu o erro naquele índice. Após preservar o índice anterior como backup e reconstruir `data/chroma` no diretório local, a recuperação independente e a consulta ao vivo funcionaram. **A causa-raiz não foi determinada**; não é possível atribuí-la comprovadamente ao OneDrive.

Se esse erro ocorrer, primeiro encerre os processos que utilizam o ChromaDB e teste a recuperação diretamente. Preserve o índice problemático antes de reconstruir o índice a partir de `data/processed/olist_reviews_clean.csv` com `python -m src.build_index_data`. Não é necessário repetir download e preparação se o CSV processado estiver íntegro.

## Limitações conhecidas

- A qualidade da síntese depende das avaliações recuperadas; fidelidade às citações não implica cobertura completa da base.
- Perguntas atuais, institucionais ou muito vagas podem resultar em abstenção.
- A API Gemini está sujeita a cotas e erros externos. No plano gratuito observado, o painel indicou **5 RPM** e **20 RPD**; esses valores são específicos daquele projeto e podem mudar.
- O cliente realiza **até duas tentativas por consulta**, com espera de **5 segundos** entre tentativas para falhas transitórias tratadas. Isso limita o consumo de cota, mas não garante disponibilidade.
- O modo demonstração é reprodutível a partir de resultados salvos, não substitui uma execução ao vivo.
- A persistência HNSW apresentou um incidente de leitura no Windows, resolvido após reconstrução do índice; a causa não foi confirmada.
- O projeto é um MVP acadêmico, sem autenticação, persistência de conversas ou garantia de disponibilidade de serviço.

## Fonte dos dados

Olist — [Brazilian E-Commerce Public Dataset](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce).
