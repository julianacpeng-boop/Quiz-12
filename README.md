# Juh Quiz — Verdadeiro ou Falso

Gera um vídeo vertical para cada afirmação cadastrada: a narração lê a pergunta, aparece uma contagem visual de 3 segundos e, em seguida, a voz informa se é verdadeira ou falsa e explica a resposta.

## O padrão do vídeo

- Vídeo vertical: **1080 × 1920 px** (9:16).
- Narração: voz `pt-BR-AntonioNeural`, velocidade `+10%`. A conexão usa o endpoint Edge Services validado no Quiz-10, tenta novamente em caso de falha temporária e recorre à voz local em português se o serviço continuar indisponível.
- Contagem antes da resposta: 3 segundos, com os números 3, 2 e 1 e bipes curtos.
- Cada TXT para publicação começa com CAPA_SEGUNDOS=2 e inclui uma legenda curta e até 4 hashtags relacionadas ao tema.
- As seis caricaturas incluídas são quadradas, em **970 × 970 px**, e aparecem na área entre as posições `(55, 500)` e `(1025, 1470)` do vídeo. Imagens opcionais também cabem nessa área sem cortes ou distorções.
- A resposta e a explicação aparecem nessa área depois da contagem.
- Cada item de `PERGUNTAS` gera um vídeo com apenas uma afirmação.
- O MP4 e o TXT são enviados para `saida/Juh-Quiz-12/verdadeiro-ou-falso/execucao-ID/` no Drive.

## Colocar no repositório Quiz-12

Envie estes arquivos para a raiz do repositório, mantendo a pasta `.github/workflows/`:

```text
gerar_vf.py
dados_vf.py
requirements-vf.txt
FONTES.md
imagens_perguntas/
.github/workflows/gerar-vf.yml
```

O modo Verdadeiro ou Falso fica em arquivos próprios, sem substituir outros geradores do repositório.

## Perguntas e caricaturas incluídas

O arquivo `dados_vf.py` já vem com seis vídeos prontos: lobisomem, bruxa, vampiro, fantasma, zumbi e dragão. Cada pergunta tem uma explicação narrada e uma caricatura em `imagens_perguntas/`. As fontes históricas usadas estão em `FONTES.md`.

## Cadastrar perguntas

Edite `dados_vf.py`. Para cada vídeo, preencha `pergunta`, `verdadeiro`, `explicacao`, `legenda` e até 4 `hashtags`. `imagem` pode ser `None` ou o caminho de uma imagem dentro de `imagens_perguntas/`. O TXT de publicação é montado automaticamente com CAPA_SEGUNDOS=2, legenda e hashtags.

```python
{
    "pergunta": "Dragões aparecem em mitologias antigas de diferentes culturas?",
    "verdadeiro": True,
    "explicacao": "Seres parecidos com dragões aparecem em tradições antigas de várias regiões.",
    "imagem": "imagens_perguntas/dragao.png",
    "legenda": "Dragões aparecem em histórias antigas de várias culturas. Você sabia?",
    "hashtags": ["#Dragões", "#Mitologia", "#Curiosidades", "#JuhQuiz"],
}
```

Use `True` para verdadeiro e `False` para falso. As seis caricaturas incluídas estão no tamanho exato de **970 × 970 px**. Para adicionar outra, prefira esse tamanho; imagens de outras proporções também serão ajustadas para caber na área sem serem cortadas.

## Gerar pelo GitHub

1. Abra a aba **Actions** do repositório.
2. Escolha **Gerar Juh Quiz — Verdadeiro ou Falso**.
3. Toque em **Run workflow**.
4. O fluxo salva os MP4 e TXT no Google Drive e também disponibiliza o artefato `juh-quiz-verdadeiro-ou-falso` para baixar.

## Secret do Google Drive

No Quiz-12, abra **Settings → Secrets and variables → Actions**. Cadastre o secret com o nome exato `RCLONE_DRIVE_TOKEN` e cole no valor o JSON completo do token rclone que você já usa no Quiz-10. O workflow salva os arquivos em `saida/Juh-Quiz-12/verdadeiro-ou-falso/execucao-ID/` no Drive.

O gerador também pode ser executado localmente com `python gerar_vf.py` após instalar `requirements-vf.txt` e o FFmpeg.
