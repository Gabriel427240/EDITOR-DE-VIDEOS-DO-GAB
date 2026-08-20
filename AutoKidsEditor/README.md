# Editor de videos do gab

Aplicativo desktop local em Python para preparar a edicao automatica de videos para YouTube. Nesta etapa, o projeto oferece uma base modular com interface CustomTkinter, banco SQLite local, gerenciamento de projetos e importacao organizada de midias.

A edicao de videos, a analise por inteligencia artificial e a renderizacao serao adicionadas futuramente. Nenhum modelo de IA, Whisper, Ollama, PyTorch, CUDA, FFmpeg ou processamento pesado faz parte desta etapa.

## Criar ambiente virtual

No terminal, a partir da pasta do projeto:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

## Instalar dependencias

```powershell
pip install -r requirements.txt
```

## Executar

```powershell
python main.py
```

## FFmpeg

A analise tecnica das midias utiliza o executavel `ffprobe` por meio de `subprocess`. FFmpeg e FFprobe nao sao instalados pelo pip e nao sao baixados automaticamente pelo projeto.

Instale o FFmpeg separadamente e garanta que o executavel `ffprobe` esteja disponivel no PATH do sistema. Sem FFprobe, a importacao continua funcionando, mas os metadados ficam marcados como indisponiveis.

Ao criar um projeto pela interface, ele recebe um registro no SQLite, uma pasta propria em `data/projects/` e as subpastas `videos`, `images`, `audio`, `music`, `temp` e `output`.

Na tela do projeto, e possivel importar videos, imagens, uma narracao principal e uma musica opcional. Os arquivos sao copiados para a pasta do projeto; os arquivos originais permanecem no local de origem.

Tambem e possivel gerar uma timeline planejada com base na duracao da narracao e na ordem de importacao das imagens e videos. Essa timeline e apenas um plano de segmentos no SQLite; ela ainda nao gera MP4, cortes, efeitos, legendas ou renderizacao.

## Primeiro render

1. Importe uma narracao principal.
2. Importe videos e/ou imagens.
3. Clique em `Gerar Timeline`.
4. Clique em `Gerar Preview`.

O preview e renderizado com FFmpeg usando CPU, `libx264`, preset `veryfast`, resolucao 1920x1080 e a narracao como audio principal. O preset `Kids Story V1` aplica movimento Ken Burns suave nas imagens, fades visuais discretos, transicoes crossfade com fallback seguro e musica opcional em volume baixo. Esta versao nao escolhe cenas com IA e a selecao de midias ainda e mecanica, sem entender a historia.

## Modo CPU atual

- Transcricao: `faster-whisper`, modelo `base`, `device=cpu`, `compute_type=int8`
- Analise textual: Ollama local com `llama3.2:1b`
- Analise visual: nao instalada; aguardando um computador com GPU
- Matching: `basic_text` usando descricoes semanticas quando existirem e nome/metadados como fallback

Os modelos nao sao carregados ao iniciar o aplicativo. Transcricao e analise textual rodam somente quando solicitadas, em thread separada, e a transcricao e armazenada em cache no SQLite.

Em um computador com GPU, esta arquitetura podera receber analise visual, aceleracao e `SMART_VISION`. CUDA, PyTorch pesado, CLIP grande, NVENC e modelos visuais continuam fora desta instalacao.

Pipeline atual:

```text
midias -> timeline -> padronizacao visual -> movimento de imagens
-> transicoes -> narracao -> musica opcional -> MP4
```

## Arquitetura narrativa futura

O projeto agora possui a camada `Narrative Scenes`, preparada para representar trechos logicos da historia:

```text
Narração -> transcrição -> cenas narrativas -> descrição visual
-> correspondência com mídias -> timeline -> render
```

Nesta etapa, a transcrição e o matching inteligente ainda não estão ativos. O botão `Criar Cenas de Teste` gera cenas manuais de desenvolvimento com blocos de aproximadamente 10 segundos. `NarrativeAnalyzer` e `SceneMatcher` já possuem APIs futuras, mas informam claramente que seus backends ainda não estão configurados.
