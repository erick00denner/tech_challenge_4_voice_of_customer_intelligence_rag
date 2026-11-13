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

No Windows, adapte a ativação do ambiente virtual. O `requirements.txt` fixa as versões **diretas** utilizadas no ambiente de referência. `requirements-lock.txt` registra também dependências transitivas do ambiente Linux/Python 3.12, inclusive pacotes específicos de CUDA; não deve ser tratado como lock universal para todas as plataformas.

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

Os resultados são históricos e devem ser identificados como tal na apresentação.

## Testes

```bash
python -m pytest -q
```

**Última validação informada:** 89 testes aprovados em 7,31 segundos, com `pip check` sem conflitos, no ambiente de desenvolvimento do projeto. Esse resultado não equivale a uma instalação limpa validada em outro computador. Alguns testes da interface requerem `evaluation/generation_runs.jsonl` disponível.

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

**Resultados de geração (19 perguntas):** 9 respostas avaliadas, médias 2,00/2 em fidelidade, qualidade das citações e qualidade da resposta; 10/10 decisões de abstenção consideradas adequadas. Precisão estrita das citações: **97/98 (99,0%)**; cobertura das evidências diretas presentes no top-20: **97/108 (89,8%)**. Esses números descrevem o conjunto avaliado, não desempenho garantido em produção.

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

## Limitações conhecidas

- A qualidade da síntese depende das avaliações recuperadas; fidelidade às citações não implica cobertura completa da base.
- Perguntas atuais, institucionais ou muito vagas podem resultar em abstenção.
- A API Gemini está sujeita a cotas e erros externos. No plano gratuito observado, o painel indicou **5 RPM** e **20 RPD**; esses valores são específicos daquele projeto e podem mudar.
- O cliente realiza **até duas tentativas por consulta**, com espera de **5 segundos** entre tentativas para falhas transitórias tratadas. Isso limita o consumo de cota, mas não garante disponibilidade.
- O modo demonstração é reprodutível a partir de resultados salvos, não substitui uma execução ao vivo.
- O projeto é um MVP acadêmico, sem autenticação, persistência de conversas ou garantia de disponibilidade de serviço.

## Fonte dos dados

Olist — [Brazilian E-Commerce Public Dataset](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce).
