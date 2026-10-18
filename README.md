# Residencial Aurora — assistente virtual

Assistente virtual do Residencial Aurora, desenvolvido com [Google ADK](https://google.github.io/adk-docs/) 2.9.1 e exposto por uma API em FastAPI. Os moradores podem reservar áreas comuns, cancelar reservas, autorizar visitantes e esclarecer dúvidas sobre o regulamento interno pelo chat; a síndica determinou que nenhuma mensagem, por mais convincente que pareça, consiga contornar as regras do condomínio — por isso as cinco garantias abaixo estão implementadas em código, não em prompt.

## Arquitetura utilizada

Um agente central (`assistente_aurora`, em `app/agents/root_agent.py`) interage com o morador e distribui as tarefas entre três especialistas. O agente central não aciona diretamente uma tool de dados — apenas seleciona o especialista adequado e encaminha a solicitação em linguagem natural.

| Agente | Arquivo | Aciona quando | Tools |
|---|---|---|---|
| `assistente_aurora` (principal) | `app/agents/root_agent.py` | sempre — é quem fala com o morador | nenhuma tool própria |
| `especialista_reservas` | `app/agents/reservas_agent.py` | reservar, listar ou cancelar reserva de área comum | `listar_minhas_reservas`, `listar_areas_comuns`, `criar_reserva`, `cancelar_reserva` |
| `especialista_visitantes` | `app/agents/visitantes_agent.py` | listar ou autorizar visitante | `listar_meus_visitantes`, `autorizar_visitante` |
| `especialista_regulamento` | `app/agents/regulamento_agent.py` | qualquer dúvida sobre as regras do condomínio | `consultar_regulamento` |

Cada especialista opera em `mode="single_turn"` (ver o final de cada arquivo acima, `LlmAgent(..., mode="single_turn")`), anexado ao principal via `sub_agents=[...]` em `app/agents/root_agent.py:77`. Esse é o mecanismo oficial do ADK para disponibilizar um agente como tool de outro (a própria classe `AgentTool` recomenda essa forma em vez de uso direto — ver `google/adk/tools/agent_tool.py`): o framework registra o especialista automaticamente como uma tool do principal e o executa **dentro da mesma sessão e do mesmo branch de eventos**, em vez de abrir uma sessão isolada. Essa decisão não é meramente estilística — ela permite que a Garantia 1 funcione (veja abaixo). São considerados especialistas porque possuem responsabilidades, tools e critérios próprios para decidir quando atuar, independentemente da forma como são acionados.

Reservas e visitantes nunca são consultados ou registrados com base no que o modelo "lembra": todas as operações de leitura e escrita passam pelas tools em `app/agents/tools/`, que por sua vez chamam `app/storage/reservas.py` e `app/storage/visitantes.py` (SQLite via `aiosqlite`, arquivo `runtime/condominio.db`). O registro da conversa (eventos, estado da sessão) fica num banco SQLite separado (`runtime/sessoes.db`), gerido pelo `SqliteSessionService` do próprio ADK.

## Garantias

### Garantia 1 — cobrança ou liberação de acesso somente após confirmação

- `app/agents/tools/reservas_tools.py:84` — `criar_reserva_tool = FunctionTool(criar_reserva, require_confirmation=_area_tem_taxa)`: a reserva exige confirmação apenas quando a área possui taxa (regra de negócio 2), decidido por uma função Python que lê `dados/areas.json`, não pelo modelo.

- `app/agents/tools/visitantes_tools.py:45` — `autorizar_visitante_tool = FunctionTool(autorizar_visitante, require_confirmation=True)`: a autorização de visitante permite a entrada (regra de negócio 3) e por isso **sempre** exige confirmação.

- Esse `require_confirmation` é um recurso nativo do ADK (`google/adk/tools/function_tool.py`): quando a tool ainda não foi confirmada, ela nunca chega a executar o corpo da função — o ADK intercepta a chamada, marca a ação como pendente e devolve um evento `adk_request_confirmation` em vez do resultado. Assim, "nada é gravado antes da resposta" não depende do que o modelo decide: o código Python da tool literalmente não roda até a aprovação chegar.

- A aprovação só é considerada válida quando chega pela rota do sistema: `app/service.py:71` (`responder_confirmacao`) estrutura a resposta como um `FunctionResponse` estruturado (`ToolConfirmation`) e a envia ao Runner — nenhum texto do morador na conversa (como "já estou confirmando aqui") passa por esse caminho, então o especialista trata qualquer frase do tipo apenas como texto, sem efeito algum (ver a instrução de `especialista_visitantes` em `app/agents/visitantes_agent.py`, que pede explicitamente para nunca tratar uma frase do morador como confirmação).

- `app/service.py:78-79` — antes de reenviar a resposta ao Runner, o código calcula o conjunto de confirmações *ainda pendentes* na sessão (`app/adk_events.py:19`, `confirmacoes_pendentes`, que soma todos os `adk_request_confirmation` emitidos e subtrai os que já têm resposta de um evento do usuário) e só aceita o `id` recebido se ele estiver nesse conjunto. Qualquer outro `id` — inexistente ou já respondido — cai fora do conjunto e a rota devolve `409` sem chamar o Runner, então nada executa (`app/main.py`, rota `POST /sessoes/{session_id}/confirmacoes`).

- Retomar de forma correta a tool que solicitou a confirmação (e não travar o especialista, como o enunciado avisa que pode acontecer) depende de `resumability_config=ResumabilityConfig(is_resumable=True)` em `app/agents/root_agent.py:87`: com isso, `Runner.run_async` roteia a resposta de confirmação para o mesmo agente que fez a chamada original (`google/adk/agents/_agent_router.py:find_agent_to_run`), não para o principal. Essa configuração (especialistas `single_turn`, sessão SQLite via `google.adk.sessions.sqlite_session_service.SqliteSessionService` — `app/adk_runtime.py:23` — e resumability ligada) foi verificada neste projeto com um modelo roteirizado (sem depender da API do Gemini) simulando a sequência completa: pedido → confirmação pendente → aprovação → gravação, inclusive com uma sessão recarregada de um `SqliteSessionService` novo apontando para o mesmo arquivo, simulando reinício.

### Garantia 2 — cada sessão está vinculada a um apartamento

- `app/storage/sessoes.py` — `POST /sessoes` registra o apartamento uma única vez, numa tabela própria (`sessoes`) independentemente do modelo, e também no `state` da sessão do ADK (`app/service.py:31`, `state={"apartamento": apartamento}`).

- `app/agents/tools/reservas_tools.py:18` e `app/agents/tools/visitantes_tools.py:11` — a função `_apartamento(tool_context)` lê `tool_context.state.get("apartamento")` (estado da sessão, gerido pelo ADK, imutável pela conversa) e é executada por **toda** tool antes de acessar os dados. Nenhuma tool deste projeto declara um parâmetro `apartamento`: não há uma forma de o modelo selecionar o apartamento cujos dados serão lidos ou alterados, portanto, a garantia não depende de o modelo "se comportar" — o parâmetro simplesmente não existe na assinatura que o modelo vê (o schema de function-calling é gerado a partir da assinatura Python real).

- `app/storage/reservas.py` — `cancelar()` retorna exatamente a mesma resposta (`{"sucesso": False, "motivo": "nao_encontrada"}`) tanto para uma reserva inexistente quanto para uma reserva de outro apartamento, assim, nem mesmo o especialista consegue descobrir se uma reserva de terceiros existe.

- `app/storage/reservas.py` — `criar()` confere a disponibilidade da combinação área+data para **todos** os apartamentos (não só o da sessão) via um índice único no banco, porém, a conversa recebe apenas `sucesso`/`data_ocupada` (nunca o dono da reserva concorrente) — implementa literalmente "o que chega à conversa é só se a data está livre ou ocupada, nunca de quem é a reserva".

### Garantia 3 — os dados são preservados após reinicializações

- `app/adk_runtime.py` — o Runner usa `SqliteSessionService(db_path=SESSOES_DB_URL)` (`runtime/sessoes.db`), não o serviço em memória: todos os eventos da conversa (mensagens, chamadas de tool, confirmações) são persistidos em disco antes da resposta HTTP voltar.

- `app/storage/db.py` e `app/storage/reservas.py`/`visitantes.py` — as reservas e os visitantes ficam armazenados em `runtime/condominio.db`, outro arquivo SQLite, gravado de forma síncrona a cada tool que cria, cancela ou autoriza.

- Como ambos os bancos são arquivos em disco (não estado em memória do processo Python), ao reiniciar a API, as mesmas conexões são abertas novamente: a mesma sessão continua com os mesmos eventos, e reservas/visitantes gravados antes do reinício continuam nas rotas de verificação. Esse comportamento foi verificado neste projeto reabrindo um `SqliteSessionService` novo, num processo separado, apontando para o mesmo arquivo `.db` de um teste anterior, e conferindo que os eventos batiam.

### Garantia 4 — o regulamento é consultado sob demanda

- O regulamento **não aparece em nenhuma instrução**: nem em `app/agents/root_agent.py` (`INSTRUCAO_PRINCIPAL`), nem em `app/agents/regulamento_agent.py` (`INSTRUCAO`). O texto do regulamento é introduzido no processo exclusivamente pela tool `consultar_regulamento` (`app/agents/tools/regulamento_tools.py`).

- `app/regulamento/retrieval.py` — o regulamento é dividido por capítulo (`_dividir_em_capitulos`) e indexado com um TF‑IDF simples, sem dependências externas nem chamadas de API (`IndiceRegulamento`). Cada pergunta recupera apenas o(s) capítulo(s) mais relevantes (`consultar`, no máximo 2, e só o segundo se estiver claramente perto do primeiro em pontuação); a tool retorna somente esse conteúdo. Como cada capítulo do regulamento já trata de um único assunto (o título resume: "Piscina", "Garagem e veículos" etc.), o capítulo constitui a unidade natural de "um trecho, um assunto" — nenhum evento carrega trechos de capítulos sobre outros assuntos porque nenhum outro capítulo é devolvido.

- O teste com a pergunta do fluxo do avaliador ("Até que horas a piscina funciona aos domingos?"): a busca devolve só o Capítulo IV (Piscina), que contém o Art. 22 com os dois períodos de funcionamento (`8h às 22h` de segunda a sábado, `9h às 20h` aos domingos e feriados — `dados/regulamento.md`, artigo 22).

### Garantia 5 — uma única reserva para cada área e data

- `app/storage/db.py:38` — `CREATE UNIQUE INDEX ... ON reservas(area, data) WHERE status = 'ativa'`: um índice único parcial do SQLite, responsável por rejeitar no próprio `INSERT` uma segunda reserva ativa para a mesma área e data — não se trata de uma checagem prévia no código, mas de uma restrição aplicada atomicamente pelo banco no momento da gravação.

- `app/storage/reservas.py:40` — `criar()` tenta o `INSERT` direto (sem checar disponibilidade antes) e trata `aiosqlite.IntegrityError` como uma rejeição esperada (`{"sucesso": False, "motivo": "data_ocupada"}`), nunca como erro de servidor. Quando duas aprovações concorrentes chegam ao mesmo tempo para a mesma área/data, o SQLite serializa as duas escritas (modo WAL, `PRAGMA busy_timeout` em `app/storage/db.py`); uma delas grava e a outra recebe a violação da unicidade — assim, não podem existir duas reservas ativas para a mesma área/data, em nenhum instante.

- A mesma função também evita efeitos duplicados em caso de reexecução: cada chamada de `criar_reserva`/`autorizar_visitante` é identificada pelo `function_call_id` da tool (`tool_context.function_call_id`), gravado numa tabela `idempotencia` junto do resultado. Esse mecanismo contempla o cenário descrito na documentação do ADK de retomada "no mínimo uma vez": se o processo reiniciar entre a aprovação e a gravação e o ADK reexecutar a tool, a segunda execução encontra o resultado já registrado e o devolve sem inserir de novo, em vez de arriscar duas reservas para a mesma aprovação.

- Validado diretamente na camada de storage com duas chamadas concorrentes (`asyncio.gather`) para a mesma área/data e `function_call_id` diferentes: exatamente uma teve sucesso, a outra recebeu `data_ocupada`, sem exceção não tratada.

## Como rodar

Requisitos necessários: Python 3.12+, [uv](https://docs.astral.sh/uv/) e uma chave do [Google AI Studio](https://aistudio.google.com/apikey).

```bash
cp .env.example .env
# edite .env e preencha GOOGLE_API_KEY
uv sync
```

Variáveis de `.env`:

| Variável | Obrigatória | Descrição |
|---|---|---|
| `GOOGLE_API_KEY` | sim | Chave do Google AI Studio usada pelos agentes Gemini. |
| `GOOGLE_GENAI_USE_VERTEXAI` | não (default `FALSE`) | Mantém o ADK na API do AI Studio, não no Vertex AI. |
| `GOOGLE_MODEL` | não (default `gemini-flash-lite-latest`) | Modelo Gemini usado pelos quatro agentes. Preferimos um alias `-latest` a uma versão fixa (ex.: `gemini-2.5-flash`, desativada para chaves novas durante o desenvolvimento deste projeto) e a variante `lite` porque cada mensagem do morador pode disparar várias chamadas ao modelo (principal → especialista → retomada após confirmação), e o tier gratuito do flash "cheio" mais recente testado aqui tinha cota de só 20 requisições/dia. Se a sua chave tiver outros limites, troque para o modelo mais adequado (veja `client.models.list()` ou https://aistudio.google.com/). |

Para restaurar os dados iniciais (reservas e visitantes voltam ao estado de `dados/*.json`; não apaga sessões nem o histórico de conversa):

```bash
uv run python scripts/restaurar_dados.py
```

Para iniciar a API em `http://localhost:8000`:

```bash
uv run uvicorn app.main:app --port 8000
```

As informações do condomínio (`runtime/condominio.db`) e o histórico de sessões (`runtime/sessoes.db`) ficam em `runtime/`, fora do controle de versão (`.gitignore`), e sobrevivem a reinícios da API (Garantia 3).
