# Changelog - Video Builder Pro

## [v7.9.1] - 2026-11-04 - Motor local: resposta em streaming e diagnostico correto de lentidao

Relato do usuario no 1o uso do Ollama: "Erro: Ollama nao esta rodando em
http://localhost:11434 (timed out)".

### Diagnostico
| Fato | Conclusao |
|---|---|
| A falha foi "timed out", nao "connection refused" | Com o Ollama desligado a conexao e recusada na hora. Tempo esgotado = servidor no ar, mas sem responder a tempo. A mensagem "nao esta rodando" estava **errada** (v7.9 tratava todo erro de rede igual). |
| v7.9 pedia a resposta inteira de uma vez (`stream: false`) com limite de 600 s | Um 7b na CPU (sem placa de video) gera poucas palavras por segundo; um roteiro de ate 2500 tokens pode passar de 10 min e estourar o limite sem mostrar nada. |

### Decisoes (e por que)
| Decisao | Motivo | Teste |
|---|---|---|
| `chat()` em **streaming** (`stream: true`, NDJSON) | O limite de tempo passa a valer por **pausa** (300 s sem nenhuma palavra, inclui carregar o modelo), nao pela resposta inteira: textos longos na CPU nao estouram mais. | L13, L14, CI `ollama-real` |
| Texto **surgindo na tela** na aba IA (no maximo ~3 atualizacoes/s) | O usuario ve que esta funcionando em vez de esperar minutos sem retorno. | L15 |
| Callback de progresso **por thread** (`definir_progresso`) | O Diretor IA roda em outra thread e nao pode escrever na caixa da aba IA. Removido ao terminar (try/finally). | L15 |
| Erros separados: tempo esgotado -> "esta rodando, mas ficou N s sem responder" + sugestao de modelo menor; recusada -> "nao esta rodando" + instrucoes | Cada mensagem leva a acao certa. | L14, L05 |
| Conexao cai no meio da resposta -> usa o texto ja recebido (registrado no log) | Nao jogar fora minutos de geracao por uma queda no fim. | - |
| Servidor de teste agora responde em streaming como o real (e em threads) | Os testes seguem o protocolo real. | L02-L15 |
| `VERSAO = "7.9.1"` | Pre-release `teste-deb-7.9.1`. | CI |

### Garantia de "sem regressao"
| Suite | Antes | Depois |
|---|---|---|
| todas as anteriores | 127/127 | 127/127 (L02 ajustado: `stream` agora e `true`) |
| novos L13-L15 | - | 3/3 |

## [v7.9] - 2026-11-04 - Motor de IA local e gratuito (Ollama), ao lado do Claude

Branch `feat/instalador` (PR #3). Pedido do usuario: sem saldo na API da Anthropic,
usar uma IA que nao dependa de creditos. Opcao escolhida: **IA local via Ollama**.
(Usar a assinatura do claude.ai como motor nao e permitido pelos termos da Anthropic
desde fev/2026, por isso nao foi feito.)

### Decisoes (e por que)
| Decisao | Motivo | Teste |
|---|---|---|
| Novo `modules/motor_local.py` falando com o servidor do Ollama pela API HTTP documentada (`POST /api/chat`, `GET /api/tags`) | Gratis, sem limite e offline depois de baixar o modelo. Nenhum codigo do Ollama (MIT) e copiado; os modelos (Qwen 2.5 Apache-2.0 nas versoes 0.5b/1.5b/7b/14b, Llama 3.2 licenca comunitaria Meta) sao baixados pelo proprio usuario com `ollama pull` e nao vao no instalador. | L01-L05 |
| `urllib` da biblioteca padrao, **ignorando proxy do sistema** | Sem dependencia nova no pacote; um `http_proxy` configurado no Debian desviaria a conexao para `localhost`. | L02 |
| `ClaudeEngine` mantem o nome e passa a **despachar** para o motor ativo (`motor_ia` = `claude` ou `ollama`) | Aba IA, Diretor IA, retakes e Revisor ja chamam `self.claude.mensagem(...)`: nenhum deles precisou mudar a chamada, so a checagem `tem_chave()` -> `pronto()`. | L06-L08 |
| **Claude continua o padrao**; motor invalido na config volta para Claude | Sem regressao para quem ja usa a API: nada muda ate o usuario escolher Ollama. | L06 |
| Modelos separados (`claude_model` e `ollama_model`) | Trocar de motor nao apaga a escolha do outro. | L07 |
| Blocos da Anthropic convertidos (texto + imagens base64 -> `images`); imagens so vao para modelos com visao (llava, qwen2.5vl, gemma3...) | O Revisor envia quadros do video; um modelo so-texto ignoraria ou recusaria. Com modelo sem visao a revisao fica tecnica (registrado no log). | L03 |
| Erro do motor local durante a edicao -> plano heuristico | Modelos pequenos as vezes devolvem JSON invalido; o Diretor ja caia na heuristica e documenta isso no relatorio (comportamento da v7.8 preservado). | L11 |
| Aba IA: quadro **"Motor de IA"** (Claude / Ollama, modelo local, "Atualizar lista", "Testar motor") com instrucoes de instalacao e **modelo sugerido pela RAM** | O usuario instala e configura sem sair do app. Limites de RAM ~1 GB abaixo do nominal (o Linux reporta 8 GB como ~7,6). | L09, L10, L05 |
| Diretor IA mostra o motor ativo e se atualiza na troca (`app.ao_mudar_motor`) | Evita a duvida "qual IA esta editando?". | L11 |
| Erros da API do Claude **traduzidos** (sem credito, chave recusada, 429, sobrecarga, modelo inexistente) com o detalhe tecnico no final | O erro em ingles "credit balance is too low" foi o que o usuario viu; agora diz o que fazer e sugere o motor local. | L12 |
| CI: job `ollama-real` instala o Ollama oficial, baixa `qwen2.5:0.5b` e gera titulos pelo motor do app (sobe `ollama serve` na mao: o runner nao tem systemd; a 1a execucao falhou exatamente por isso, e a instrucao do app ganhou a dica `ollama serve`) | Os testes L usam um servidor que imita o Ollama; este job prova a integracao com o servidor real. | CI |
| Instrucao de instalacao usa `su - -c` (com hifen) | No 1o teste do usuario, `su -c` nao trouxe `/usr/sbin` para o PATH (Debian) e o instalador do Ollama falhou em `useradd: not found`, sem criar o usuario nem o servico. | L05 |
| `motor_local` nos `hiddenimports` do PyInstaller; `VERSAO = "7.9"` | O modulo entra no .deb/.exe; pre-release de teste `teste-deb-7.9`. | CI |

### Garantia de "sem regressao"
| Suite | Antes | Depois |
|---|---|---|
| regressao + defeitos + diretor + instalador + correcoes 7.8.1 | 115/115 | 115/115 |
| `tests/test_motor_local.py` (novos, L01-L12) | - | 12/12 |
| Tk real (xvfb): aba IA com Ollama selecionado (captura conferida) | - | ok |

## [v7.8.1] - 2026-11-04 - Correcoes do 1o teste do .deb no Debian (importacao de midia e chave da API)

Branch `feat/instalador` (PR #3). Relato do usuario apos instalar `video-builder-pro_7.8_amd64.deb`:
"a importacao da midia, dos videos para edicao nao esta funcionando; o salvamento da chave
api da ia (Claude) nao esta ficando salva, quando mudo a aba ela some".

### Diagnostico (causa raiz, reproduzida antes de corrigir)
| Sintoma | Causa | Como foi confirmado |
|---|---|---|
| Nenhum video entra na timeline | O app empacotado (PyInstaller) define `LD_LIBRARY_PATH=/opt/aggilli/video-builder-pro/_internal`. Os subprocessos herdavam isso, e o `ffprobe`/`ffmpeg` **do sistema** carregavam a `libstdc++` antiga do pacote (Ubuntu 22.04). No Debian do usuario o ffmpeg exige `GLIBCXX_3.4.32`, entao o `ffprobe` morria e todo arquivo era "invalido", sem mensagem na tela. | `LD_LIBRARY_PATH=_internal /usr/bin/ffprobe -version` -> `GLIBCXX_3.4.32 not found`; o `--verificar` do pacote mostrava `"ffmpeg_versao": "?"` e mesmo assim `ok: true`. |
| Dialogo nao mostra `VIDEO.MP4` | O filtro do Tk no Linux diferencia maiusculas (`*.mp4` nao casa `.MP4`, padrao de cameras/celulares). | Teste C04b. |
| "A chave some ao mudar de aba" | (1) Colar a chave e trocar de aba **sem clicar em Salvar** perdia a chave; (2) depois de salva, o campo ficava vazio por seguranca (decisao D44 da v7.7) e parecia que a chave tinha sumido, sem indicacao de que estava salva. | Harness com Tk real (xvfb): a chave salva persistia; a colada e nao salva se perdia. |

### Decisoes (e por que)
| Decisao | Motivo | Teste |
|---|---|---|
| `isolar_subprocessos()` (em `ffmpeg_utils`), chamado no inicio do `rodar_v78.main()`: no app empacotado e fora do Windows, todo `subprocess.Popen` recebe `env` sem o `LD_LIBRARY_PATH` do pacote (restaura `LD_LIBRARY_PATH_ORIG` se existir) | Corrige na origem para TODOS os programas externos (ffmpeg, ffprobe, yt-dlp, xdg-open...), sem precisar mexer em cada chamada. O proprio app continua usando as libs dele. Em codigo-fonte e no Windows nao muda nada. Idempotente. | C01, C02 |
| Filtros de arquivo com maiusculas e minusculas + "Todos os arquivos" (`tipos_video()`/`tipos_midia()` unicos para base, v76 e Diretor IA) | Arquivos `.MP4`/`.MOV` de camera apareciam ocultos. Uma fonte so evita divergencia entre abas. | C03, C04b |
| Importacao mostra **quais** arquivos falharam e por que | Antes a falha so ia para o log; o usuario via "nada acontece". | C04 |
| `--verificar` reprova se ffmpeg/ffprobe nao rodam e faz uma **importacao real** de um video gerado | O verificar antigo dava `ok: true` com o ffprobe quebrado; foi por isso que o CI nao pegou o defeito. | C09 |
| CI instala o `.deb` em containers **Debian 12 e Debian 13** limpos e roda o `--verificar` | O teste anterior rodava no mesmo Ubuntu do build (mesma libstdc++), onde o defeito nao aparece. | CI |
| Campo da chave mostra uma **mascara** (`************************`, que NAO e a chave) + rotulo verde "Chave salva (termina em ...XXXX) - onde" | Mantem a decisao de seguranca da v7.7 (a chave nao volta para o widget) e mostra claramente que esta salva. | C05, D44 (atualizado) |
| **Salvamento automatico** ao sair do campo ou trocar de aba, quando o texto comeca com `sk-ant-` | Era exatamente o relato: colar, mudar de aba, perder. Texto sem `sk-ant-` nao e salvo sozinho (pergunta ao clicar Salvar). | C10, Tk real |
| Botao **Testar chave** (GET `/v1/models`, em segundo plano) e Enter salva | Confirma que a chave funciona sem gastar tokens; erros 401/403 e falta de rede viram mensagens claras. | C06, C08 |
| `onde_esta_chave` tolera erro do cofre (keyring) | Cofre bloqueado derrubava a montagem da aba IA; agora cai no arquivo (chmod 600). | C07 |
| `--verificar` informa o isolamento ja feito pelo `main()` | No 1o CI no Debian o relatorio dizia `subprocessos_isolados: false` (2a chamada e no-op), embora o ffprobe do sistema rodasse. Diagnostico tem que ser fiel. | C11 |
| `VERSAO = "7.8.1"` | A pre-release de teste vira `teste-deb-7.8.1`, separada da 7.8 com defeito. | I07 |

### Garantia de "sem regressao"
| Suite | Antes | Depois |
|---|---|---|
| regressao + defeitos + diretor + instalador | 103/103 | 103/103 (D44 ajustado a mascara: a chave continua fora do campo) |
| `tests/test_correcoes_781.py` (novos, C01-C11) | - | 12/12 |
| Verificacao com Tk real (xvfb): colar chave -> trocar todas as abas -> chave salva e mascarada; importar `CLIP.MP4` com `LD_LIBRARY_PATH` do pacote simulado | - | ok |

## [v7.8 - instalador] - 2026-11-03 - Instaladores Windows (.exe) e Linux (.deb) com o logo da Aggilli

Branch `feat/instalador`, empilhada sobre `feat/v7.8-diretor-ia` (PR #2).

### Garantia de "sem regressao"
| Suite | Antes | Depois |
|---|---|---|
| regressao + defeitos + diretor | 93/93 | 93/93 |
| `tests/test_instalador.py` (novos, I01-I10) | - | 10/10 |
| **Total** | 93 | **103/103** |
O CI (`.github/workflows/video-builder-pro.yml`) passa a rodar a suite inteira em todo PR.

### Decisoes (e por que)
| Decisao | Motivo |
|---|---|
| Build no **GitHub Actions** (windows-latest + ubuntu-22.04) | O `.exe` do Windows precisa ser gerado no Windows; o runner faz isso de graca e de forma reproduzivel. Ubuntu 22.04 (glibc 2.35) para o binario rodar tambem no Debian 12. |
| PyInstaller **onedir** (pasta) em vez de onefile | O onefile de 151 MB da v7.6 se descompactava a cada abertura (lento). Num instalador, a pasta abre rapido e atualiza melhor. |
| **Inno Setup 6** no Windows | Assistente moderno em portugues, imagens do logo, atalhos, desinstalador; instala por usuario SEM pedir administrador. |
| `.deb` com `Depends: ffmpeg` no Linux | O apt mantem o FFmpeg atualizado; no Windows (sem gerenciador padrao) o FFmpeg vai embutido (build BtbN GPL, licenca incluida em `bin/`). |
| **faster-whisper embutido** | Sem PyTorch (~250 MB): o Diretor IA transcreve palavra a palavra logo apos instalar, sem `pip install`. Os modelos baixam na 1a transcricao. |
| Builds de teste com monograma neutro "VB" | O logo oficial nao estava no repositorio e nao deve ser inventado. O PR valida todo o pipeline; a release oficial (tag `v*`) FALHA sem `assets/logo_aggilli.png`. |
| `pasta_app()` em vez de `Path(__file__).parent.parent` | No app empacotado esse caminho aponta para fora do pacote (estilos, LUTs e bin sumiriam). |
| Estilos e LUTs do usuario em `~/.video_builder_pro/` | Com o app em Program Files (somente leitura), o usuario ainda pode criar/editar estilos e LUTs. |
| `--verificar [arquivo.json]` no launcher | O CI testa o executavel gerado E o app depois de instalado (instalacao silenciosa no Windows; `apt install` do .deb no Linux). O .exe sem console grava o resultado em arquivo. |

### Adicionado
| Arquivo | O que faz | Teste |
|---|---|---|
| `assets/README.md` | Onde colocar o logo oficial (`logo_aggilli.png`/`.svg`) | - |
| `instalador/gerar_icones.py` | Logo -> `icone.ico` (16-256 px), PNG 256/512, imagens do assistente (1x e 2x DPI); `--sem-logo` para teste | I06 |
| `instalador/versao.py` | Versao unica (VERSAO do app) + metadados do .exe ("Aggilli Intelligence") | I07 |
| `instalador/video_builder_pro.spec` | PyInstaller (Windows/Linux), FFmpeg e pacotes opcionais | CI |
| `instalador/instalador_windows.iss` | Inno Setup: pt-BR, logo, atalhos, desinstalador, por usuario | CI |
| `instalador/build_deb.sh` | Pacote .deb: /opt/aggilli, comando `video-builder-pro`, menu, icone | I08 + CI |
| `.github/workflows/video-builder-pro.yml` | testes -> exe + deb -> testes de instalacao -> Release (em tags) | - |

### Alterado
- `modules/ffmpeg_utils.py`: `pasta_app()`, `preparar_ffmpeg_embutido()` (I01, I02).
- `modules/diretor_ia.py`: estilos do app + do usuario (I03). `luts_manager.py`: LUTs do usuario (I04).
  `upscaler.py`, `definitive_downloader.py`: caminhos via `pasta_app()`.
- `rodar_v78.py`: FFmpeg embutido no PATH, icone da janela, `--verificar` (I05).

### Logotipo (03/11/2026)
- `assets/logo_aggilli.png`: logo enviado pelo usuario, **sem a linha "OBRAS INTELLIGENCE"** (removida a pedido).
- `assets/simbolo_aggilli.png` e `assets/texto_aggilli.png`: simbolo e nome separados automaticamente.
  Motivo: o logo e horizontal (~3,4:1); num icone de 16-48 px o nome vira borrao, o simbolo continua legivel.
- `gerar_icones.py`: icones e cabecalho usam o simbolo; a imagem lateral empilha simbolo + nome (testes I09, I10).

### Corrigido: repositorio nao clonava no Windows
- O arquivo `projetos/video-builder-pro/projetos/video-builder-pro/Nota Esta versão é mantida como fallback
  estável. Para novos recursos, use v7.2.` terminava em ponto, nome invalido no Windows: o `git clone`/checkout
  falhava (detectado pelo job Windows do CI). Renomeado com `git mv` (historico preservado), conteudo intacto,
  para `contexto_2026-10-23_empacotamento.md` (o conteudo e a nota de contexto do empacotamento de 23/10).

### Pre-release de teste (.deb)
- Todo PR publica o `.deb` como **pre-release** `teste-deb-<versao>` marcada "nao oficial" (a tag e criada
  pelo proprio CI). Uma tag `teste-*` enviada manualmente faz o mesmo sem o job Windows. Motivo: os artefatos do Actions ficam num armazenamento que exige login/zip; a release da
  um link direto para baixar e testar. O Windows nao roda nessas tags (o .exe sera gerado depois).

### Como publicar a versao oficial
1. Adicionar `projetos/video-builder-pro/assets/logo_aggilli.png` (commit).
2. `git tag v7.8.0 && git push origin v7.8.0` -> o Actions gera e publica `VideoBuilderPro-Setup-7.8.exe`
   e `video-builder-pro_7.8_amd64.deb` em Releases.

### Limitacoes
- O executavel do Windows nao e assinado digitalmente: o SmartScreen mostra "Editor desconhecido" ate
  que se use um certificado de assinatura de codigo (pago).
- Modulos pesados (WhisperX, Demucs, GFPGAN) continuam fora do instalador (PyTorch tem varios GB).

## [v7.8] - 2026-11-03 - Sprint A: Diretor IA (edicao autonoma)

Branch `feat/v7.8-diretor-ia`, empilhada sobre `fix/v7.7-correcoes-auditoria` (PR #1).
Objetivo: sair da "edicao por IA rudimentar" (so remover silencio por volume) para um fluxo de
editor profissional: transcricao por palavra -> corte de fala -> diretor -> render -> revisor.

### Garantia de "sem regressao"

| Suite | Antes (v7.7, `775b23e`) | Depois (v7.8) |
|---|---|---|
| `tests/test_regressao.py` (15) | 15/15 | 15/15 |
| `tests/test_defeitos.py` (53) | 53/53 | 53/53 |
| `tests/test_diretor.py` (25, novos, IDs S01-S23) | - | 25/25 |
| **Total** | 68/68 | **93/93** |

As 20 abas da v7.7 nao mudaram: o Diretor e um **patch separado** (`v78_diretor.py`, 21a aba).
`rodar_v77.py` continua abrindo a versao de 20 abas; `rodar_v78.py` abre as 21.

### Decisoes (e por que)

| Decisao | Motivo |
|---|---|
| Diretor escolhe **unidades** (frases ja limpas), nao tempos livres | Um LLM que devolve timestamps erra por decimos de segundo e corta palavras. Escolhendo so unidades pre-validadas, **nenhum corte cai no meio de palavra** por construcao (teste S05). |
| Laco Diretor -> Render -> Revisor com nova tentativa | Padrao do `poseljacob/agentic-video-editor` (MIT). O Revisor junta nota tecnica (objetiva) e nota visual do Claude (subjetiva): 40% / 60%. |
| Estilos em JSON (`estilos/`) e nao YAML | Sem dependencia nova (PyYAML). Conceito de estilo reutilizavel do FireRed-OpenStoryline (Apache-2.0). |
| Varios backends de transcricao com cache | WhisperX e o mais preciso para corte, mas pesado; o app usa o melhor que estiver instalado. Cache porque transcrever e a etapa mais lenta e o Diretor replaneja. |
| Funciona sem chave da API | Sem Claude: plano heuristico (densidade de fala) e revisao so tecnica. Nada quebra. |
| Codigo proprio, nenhum trecho copiado | OpenMontage (AGPL-3.0) e RobustVideoMatting (GPL-3.0) foram estudados mas nao usados: copiar obrigaria o app a mudar de licenca. Os projetos MIT/Apache serviram de referencia de arquitetura. |
| `ClaudeEngine.mensagem()` novo; `gerar()` intocado no comportamento | A visao precisa de blocos de imagem. `gerar()` agora delega a `mensagem()` com o MESMO corpo de requisicao (teste S19). |
| `enquadramento` com padrao "ajustar" | Reels a partir de video 16:9 precisa recortar (preencher) ou desfocar; o padrao mantem as barras pretas da v7.7 (teste S20). Projetos .vbp.json antigos abrem como antes (S21). |

### Adicionado

| Arquivo | O que faz | Testes |
|---|---|---|
| `modules/transcricao.py` | Transcricao com tempo de cada palavra. Backends: whisperx > stable_whisper > faster_whisper > whisper. Interpola palavras sem tempo (numeros no WhisperX), cache em `~/.video_builder_pro/cache/transcricoes`. | S01-S03 |
| `modules/corte_fala.py` | Corte bruto de fala: vicios ("eh", "hum", "ahn", "eee" alongado), repeticoes ("eu eu", "eu acho eu acho" -> mantem a ultima), falsas partidas ("pro-"), pausas longas (encurta), bordas, retakes (Claude, opcional). Palavras ambiguas ("e", "a", "ha", "um", "uhum") so saem quando alongadas/isoladas. Modo seguro se os vicios passarem de 35% da fala. | S04-S10 |
| `modules/diretor_ia.py` | Indexador (unidades por frase ou por cena, folha de contato 1280 px), Diretor (Claude + heuristica, valida ids, ajusta duracao), Revisor (QC, duracao, ritmo, silencio residual + visao), orquestrador com versoes `_v1`, `_v2`... e relatorio. | S11-S18 |
| `estilos/*.json` | `youtube_educativo`, `reels_dinamico` (9:16, 45 s, gancho 3 s), `depoimento` (fade, soft light), `podcast_cortes` (trecho continuo, fundo desfocado). Edite ou crie novos: aparecem na aba automaticamente. | S12 |
| `v78_diretor.py` | Aba "Diretor IA": material, estilo, briefing, Analisar, Editar automaticamente, Enviar para a Timeline (ajuste fino manual), Abrir relatorio. | S22-S23 |
| `rodar_v78.py` | Launcher com as 21 abas. | - |
| Relatorio `<saida>.diretor.md` / `.json` | Para cada execucao: palavras removidas (tempo, motivo, texto), retakes, unidades escolhidas e por que, notas e problemas de cada versao. | S17 |

### Alterado (aditivo, sem mudar comportamento existente)
- `video_builder_pro_v7_suite.py`: `ClaudeEngine.mensagem()` (multimodal); `ProjectTimeline.enquadramento` +
  combo "Enquadramento" na aba Projeto + render (`preencher`/`desfocar`); serializacao do projeto; `VERSAO = "7.8"`.

### Corrigido durante o desenvolvimento (pego pelos testes antes do commit)
- Corte de palavra no inicio/fim com pausa curta deixava 0,05 s da palavra removida (S05).
- Id nao numerico na resposta de retakes descartava todos os retakes validos (S10).
- Limite de seguranca contava silencio e retakes e entrava em modo seguro sem necessidade (S07, S10).

### Limitacoes conhecidas
- **Testado com Whisper e Claude simulados** (sem modelos nem chave no ambiente de teste). Validar com
  gravacoes reais e a sua chave antes de uso em producao; ajustar `estilos/*.json` ao seu gosto.
- O Diretor ve ate 4 arquivos por vez (folhas de contato) para controlar custo de tokens.
- Retakes e revisao visual consomem a API do Claude (2 a 4 chamadas por versao).
- Dicionario de vicios focado em portugues (+ alguns do ingles).

## [v7.7] - 2026-11-03 - Correcao de todos os defeitos da auditoria v7.6

Origem: auditoria tecnica de 03/11/2026 sobre o commit `85c9ea4` (v7.6).
Escopo: `modules/*.py`, `v76_patch.py`, `video_builder_pro_v7_suite.py`.
Branch: `fix/v7.7-correcoes-auditoria`.

### Como foi garantido "sem regressao"

1. **Antes de alterar qualquer linha**, criei `tests/test_regressao.py`: 15 testes do
   comportamento que JA funcionava na v7.6. Rodaram verdes no codigo original.
2. Para cada defeito, um teste em `tests/test_defeitos.py` (IDs **D01-D49** abaixo).
3. Resultado, com a mesma suite nos dois codigos:

| Codigo | Regressao (15) | Defeitos (53 casos) | Total |
|---|---|---|---|
| v7.6 original (`85c9ea4`) | 15 passam | **53 falham** | 15/68 |
| v7.7 (esta versao) | 15 passam | 53 passam | **68/68** |

Midia de teste 100% sintetica (FFmpeg `lavfi`), incluindo caminhos com espaco,
`:` , virgula, colchetes e apostrofo. Rodar: `cd projetos/video-builder-pro && python -m pytest tests`.
A UI e testada com um stub de Tkinter (`tests/fake_tk.py`), sem display.

### Decisoes de arquitetura (e por que)

| Decisao | Motivo |
|---|---|
| Novo `modules/ffmpeg_utils.py` | Havia 3 copias de `_obter_duracao`, 2 parsers de `silencedetect`, 2 MD5, e ~40 `subprocess.run` sem checar returncode. Agora um so lugar, com `FFmpegErro` contendo o fim do stderr. |
| Novo `modules/ui_thread.py` (`UIDispatcher`) | Tkinter nao e thread-safe; ~30 threads tocavam em widgets. Regra unica: threads usam `ui.chamar()`; a UI drena a fila a cada 50 ms. |
| Remover moviepy, pydub e ffmpeg-python | moviepy 2.x removeu `moviepy.editor`/`subclip`/`speedx`; pydub depende de `audioop`, removido no Python 3.13. Tudo foi refeito em FFmpeg puro: menos dependencias, mesmo resultado. |
| Implementar os 8 modulos ausentes | O patch importava `upscaler`, `stems_separator`, `face_restore`, `auto_*_ai`, que nao existiam no repositorio: 3 abas e 5 botoes nunca funcionaram. |
| Manter nomes publicos | `aplicar_patch`, `V73Patch`, `_obter_duracao`, `queimar_legendas_no_video` etc. continuam existindo: o `rodar_v76.py` local segue funcionando. |
| Base + patch mantidos (sem consolidar) | A consolidacao e uma mudanca estrutural separada (ROADMAP v7.8). Misturar com correcoes dificultaria revisar e reverter. |

### Corrigido - modules/

| ID | Arquivo | Defeito | Causa | Correcao |
|---|---|---|---|---|
| D01 | auto_editor.py | "Detectar Cenas" quebrava (`'float' object has no attribute 'get'`) | Modulo devolve `List[float]`; a UI tratava como dicts | Novo `detectar_cenas()` -> `[{inicio, fim, duracao}]`; `detectar_cortes_cena()` mantido |
| - | auto_editor.py | Remover silencios cortava no keyframe (trechos imprecisos/congelados) | `-ss` depois de `-i` com `-c copy` | Corte unico `trim/atrim + concat` com reencode (preciso ao frame) |
| - | auto_editor.py | Falhas de FFmpeg silenciosas; video sem audio quebrava | returncode ignorado | `executar()` com erro claro; sem audio = copia |
| - | auto_editor.py | `aplicar_edicao_automatica` usava filtro inexistente `abremoveloud` | - | Reusa o corte por trechos |
| D02 | vertical_converter.py | Conversao vertical quebrava (`'str' object has no attribute 'value'`) | UI passava `"smart"`; blur caia em `resolucao_saida` | Aceita `CropMode` ou `str`; opcionais so por palavra-chave |
| D03 | vertical_converter.py | Blur de fundo invisivel | Frente recortada 9:16 e escalada para tela cheia cobria o fundo | Video inteiro centralizado sobre fundo desfocado |
| D04 | vertical_converter.py | Video sem audio falhava | `-c:a aac` sem stream | Audio mapeado so se existir |
| - | vertical_converter.py | Face tracking escolhia a face errada; exigia GPU | `bbox[2]*bbox[3]` nao e area; `ctx_id=0` fixo | Area real; CPU quando nao ha CUDA |
| D05 | subtitles_ai.py | "Queimar legendas" quebrava; caminhos `C:\...` ou com apostrofo quebravam o filtro | Metodo `queimar_legendas` nao existia; caminho sem escape | Alias criado; `escapar_caminho_filtro()` (2 niveis de escape do FFmpeg) |
| D06 | subtitles_ai.py | SRT gerado se perdia | Gravado no temp (apagado no `__del__`) com nome fixo | Parametro `saida`; padrao ao lado do video |
| D07 | luts_manager.py | Intensidade < 1 INVERTIA o look (contraste 1,15 x 0,5 = 0,575) | Multiplicava o parametro pelo slider | Interpola do neutro: `n + (v - n) * i`; colorbalance, vignette e unsharp tambem |
| D08 | luts_manager.py | `.cube` com intensidade parcial ou caminho com `:`/apostrofo falhava | `blend` sem formato comum; caminho sem escape | `filter_complex` com `format=gbrp`; escape; rotulos unicos por clipe |
| D09-D10 | transitions_gl.py | 42 das 46 transicoes falhavam (`No such filter: 'st(1'`) | Expressao solta, fora de `xfade=transition=custom` | 25 mascaras reais + 17 mapeadas para a nativa mais proxima, marcadas "(aprox.)" |
| D11 | transitions_gl.py | Easing invertido | No xfade, `P` vai de 1 a 0 (verificado em teste) | Curvas usam `1-P` |
| D09 | transitions_gl.py | Clipes de formatos diferentes abortavam; audio descartado | Sem normalizacao; sem `-map` de audio | Normalizacao no grafo; `acrossfade`; silencio sintetico para clipe mudo |
| D12 | transitions_gl.py | 3 ou mais clipes com offset errado | Offset usava so a duracao do clipe i | Duracao acumulada; validacao de transicao maior que o clipe |
| D13 | gpu_encoder.py | NVIDIA "detectada" sem placa (reproduzido) | `ffmpeg -encoders` lista o que foi compilado, nao o hardware | Encode real de 1 quadro antes de marcar disponivel; parse do nome corrigido |
| D14 | gpu_encoder.py | Qualidade invertida ("Rapido" 28 Mbps > "Qualidade" 18 Mbps); filtros quebravam com CUDA | CRF usado como bitrate; `-hwaccel_output_format cuda` | `-cq`/`-global_quality`/`-qp`; quadros na RAM; AMF com `-quality` |
| D15 | definitive_downloader.py | Aba Download morta no Windows, com mensagem falsa "pip install yt-dlp" | `Path("/home").iterdir()` no `__init__` | Perfis de navegador por sistema (Windows/macOS/Linux/Flatpak/Snap) |
| D16 | definitive_downloader.py | **Seguranca:** como root, usava os cookies do primeiro usuario de `/home/*` | Varredura de todos os homes | So o home do usuario real (`SUDO_USER` via `pwd`) |
| D17 | definitive_downloader.py | **Seguranca:** `cookies.txt` em 644 (legivel por todos) | - | Ajusta para 600 com aviso; local preferido `~/.video_builder_pro/cookies.txt`; `cookies.txt` tem prioridade sobre o navegador |
| - | definitive_downloader.py | Retornava o arquivo intermediario (`.f137.mp4`); progresso invisivel | Hook `finished` e anterior ao merge | `requested_downloads[].filepath`; logger do yt-dlp na UI; nova tentativa sem cookies do navegador |
| D18 | upscaler.py (novo) | Aba Upscale nunca funcionou | Arquivo inexistente | Real-ESRGAN ncnn-vulkan (IA) com fallback classico (FFmpeg lanczos) |
| D19-D20 | upscaler.py | - | - | Testado: modo classico real + pipeline IA com binario simulado |
| D21 | stems_separator.py (novo) | Aba Stems nunca funcionou | Arquivo inexistente | Demucs CLI (2 ou 4 stems) |
| D22 | face_restore.py (novo) | Aba Face Restore nunca funcionou | Arquivo inexistente | GFPGAN quadro a quadro via pipe FFmpeg; detecta e explica o erro `basicsr`/`torchvision` |
| D23 | auto_suite.py (novo) | 5 botoes da Auto-Edit Suite falhavam | `auto_*_ai` inexistentes | Edicao automatica (com transicoes), cor automatica (signalstats), mixagem (EBU R128), legendas, 4 formatos de plataforma |

### Corrigido - video_builder_pro_v7_suite.py (base)

| ID | Defeito | Correcao |
|---|---|---|
| D24 | Render de clipes heterogeneos dessincronizado (video 7,24 s x audio 3,04 s) | Cada clipe normalizado (scale/pad/fps/aresample) + filtro `concat` |
| D25 | In/out ignorados (fim=10 fixo); velocidade ignorada | `-ss/-t` por clipe; `setpts` + cadeia `atempo` |
| D26 | Proxies gerados e descartados em DRAFT/FAST (tempo dobrado) | Removido do render; proxies so para preview |
| D27 | Padrao de audio ignorado; `loudnorm` deixava 0,1 s de cauda | Loudnorm em 2 passadas para o padrao escolhido + `atrim` na duracao original |
| D28 | Aba Cor (LUT/sliders), aba Audio (EQ/ducking) e transicoes nao chegavam ao render | Look/LUT, `eq`, EQ de 3 bandas, trilha com `sidechaincompress` e xfade no grafo |
| D29 | `speed_ramp` devolvia `setpts=0.5*PTS` fixo | `setpts` por trechos (velocidade constante por segmento) |
| D30 | QC aprovava video SEM audio | Sem audio ou audio mudo = reprovado |
| D31 | True peak, dropped e black frames eram constantes | Medidos: `loudnorm` (TP/LRA), `blackdetect`, `freezedetect`, contagem de pacotes, bitrate por segundo |
| D32 | Alvo fixo em -23: videos para YouTube (-14) sempre reprovados | Alvo e true peak seguem o padrao do projeto (+/- 1 LU) |
| D33 | `gerar_relatorio_pdf` era `pass` | PDF gerado sem dependencias (ou .txt) |
| D34 | Luminosidade fixa em 45 IRE; match de cameras fixo | `signalstats` real; match por Y/U/V/saturacao medios |
| D35 | Sincronia multicam = 0,0 fixo; duracao 10 s fixa | Correlacao cruzada do envelope de audio (resolucao de 10 ms) |
| D36 | Ripple mexia no material de origem; slide era no-op | Ripple sobre a posicao na timeline (clipe ou intervalo); slide ajusta os vizinhos |
| D37 | EDL sem in/out; `pathurl` invalida | in/out/start/end, taxa da sequencia, URI `file:///` |
| D38 | Fila nunca renderizava | `processar_fila` renderiza cada projeto + botao na UI |
| D39 | **Seguranca:** chave em base64 num arquivo 644 | Cofre do sistema (`keyring`) quando disponivel; senao arquivo 600 em diretorio 700, com gravacao atomica |
| D40 | Sem logging em arquivo | `~/.video_builder_pro/logs/video_builder.log` rotativo (5 x 1 MB) |
| D41 | Threads escreviam nos widgets | `UIDispatcher` |
| D42 | Abrir/Salvar projeto eram placeholders | JSON `.vbp.json` com clipes, in/out, velocidade, look, audio, trilha e transicao |
| D43 | Escolhas da UI nao chegavam ao render | `_montar_timeline()` le todas as abas |
| D44 | Chave salva carregada de volta no campo da tela | Campo vazio + rotulo "salva em: cofre/arquivo 600" |
| - | Timeline: canvas vazio e 4 botoes placeholder | Lista de clipes, In/Out, velocidade, speed ramp, subir/descer, ripple, multicam, preview (ffplay) |

### Corrigido - v76_patch.py

| ID | Defeito | Correcao |
|---|---|---|
| D45 | Detectar Cenas quebrava | Usa `detectar_cenas()` |
| D46 | Vertical e Queimar legendas quebravam | Chamadas corretas |
| D47 | WhisperX sempre "cuda" (quebrava em CPU) | CUDA via `torch.cuda.is_available()`; `compute_type` int8 na CPU; palavras sem alinhamento puladas; `{}` escapados no ASS |
| D48 | Preview, Speed, Trim, Analise e Normalizacao dependiam de moviepy/pydub (quebrados no 3.13); a normalizacao descartava o video | FFmpeg puro; EBU R128 (LUFS) com video copiado |
| D49 | `mixagem_automatica` usava `self.auto_audio_padrao` inexistente e nao tinha botao; Transicoes GL so listavam nomes | Botoes e combos ligados; transicao aplicavel entre 2 clipes ou no projeto |
| - | Slider duplicado no dialogo de Speed Ramp | Dialogo simples |

### Adicionado
- `rodar_v77.py`: launcher com checagem de FFmpeg e erro de inicializacao em janela e no log.
- `requirements.txt` (principal) e `requirements-ia.txt` (opcionais pesados).
- `tests/`: 68 testes automatizados.

### Removido
- Dependencias moviepy, pydub e ffmpeg-python.
- `*.log` versionados (`git rm --cached`): o `.gitignore` ja os excluia, e um deles expunha um caminho com nome de usuario do Windows.

### Limitacoes conhecidas (nao sao regressoes)
- **Transicoes de distorcao** (Cube, Page Curl, Swirl 3D...): o `xfade` do FFmpeg so escolhe pixel de A ou B, nao desloca imagem. Por isso usam a transicao nativa mais proxima e aparecem como "(aprox.)".
- **Speed ramp** fica sem audio no trecho com rampa, porque o `atempo` nao varia no tempo. A velocidade constante mantem o audio.
- **Campos por clipe** `transicao_entrada/saida` e `movimento` existem no modelo, mas ainda nao tem UI. A transicao e unica para o projeto.
- **Testados com binarios/modulos simulados**, nao com os modelos reais (ausentes no ambiente de teste): Real-ESRGAN, Demucs, GFPGAN, Whisper, faster-whisper, WhisperX, yt-dlp com rede. Validar com videos reais antes do uso em producao.
- **Binario PyInstaller nao reconstruido.** Para rebuild:
  `pyinstaller --onefile --windowed --paths modules --hidden-import upscaler --hidden-import stems_separator --hidden-import face_restore --hidden-import definitive_downloader rodar_v77.py`
  (os 4 modulos sao carregados dinamicamente pelo patch e precisam do `--hidden-import`; FFmpeg nao vai dentro do binario).

## [v7.5] - 2026-10-23 (FINAL)

### Adicionado
- **19 abas funcionais** (8 originais + 11 novas)
- **Video Downloader** (yt-dlp): YouTube, TikTok, Instagram, etc
- **Face Restore** (GFPGAN): Restauração de rostos em videos
- **WhisperX**: Legendas karaokê com word-level timestamps
- **Upscale AI** (Real-ESRGAN): SD → HD → 4K
- **Audio Stems** (Demucs): Separação vocals/instrumental
- **Legendas Turbo** (faster-whisper): 4x mais rápido

### Integrações AI
- Claude AI (roteiros, títulos, descrições)
- Whisper AI (legendas automáticas)
- faster-whisper (legendas 4x mais rápidas)
- WhisperX (karaokê word-level)
- Demucs (separação de áudio)
- Real-ESRGAN (upscale de video)
- GFPGAN (restauração facial)

### Técnico
- Sistema modular com patch architecture
- GPU encoding (NVENC/AMF/QuickSync)
- 70+ transições GL com easing
- 15+ LUTs profissionais
- Auto-edição (detectar cenas, remover silêncios)
- Conversor vertical 9:16 (TikTok/Reels)
- QC automático (loudness, true peak, checksums)

### Corrigido
- Métodos bool sendo chamados como funções (patch v7.5)
- Download de vídeos: formato simples funciona sem Node.js

---

## [v7.4] - 2026-10-23

### Adicionado
- **16 abas funcionais**
- Upscale AI (Real-ESRGAN)
- Audio Stems (Demucs)
- Legendas Turbo (faster-whisper)

---

## [v7.3] - 2026-10-23

### Adicionado
- **13 abas funcionais**
- 70+ transições GL com easing
- 15+ LUTs embutidas
- Auto-edição (detectar cenas, remover silêncios)
- Legendas AI (Whisper)
- Conversor vertical 9:16
- GPU encoding

---

## [v7.2] - 2026-10-23

### Adicionado
- Salvar/Abrir projeto (.vbp JSON)
- Escolher pasta de renderização
- Transições entre clips
- Color grading por clip

---

## [v7.1] - 2026-10-22

### Adicionado
- Claude AI integrada
- Roteiros, títulos, descrições
- Capítulos e hashtags

---

## [v7.0] - 2026-10-22

### Inicial
- 8 abas: Projeto, Mídia, Timeline, Cor, Áudio, IA, Render, QC
- Renderização básica com FFmpeg
- Menu completo

---

## [v6.0] - Legado

- Versão anterior sem integração AI
