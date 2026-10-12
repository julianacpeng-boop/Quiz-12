# Juh Quiz — Verdadeiro ou Falso

Gera um vídeo vertical para cada afirmação cadastrada: a narração lê a pergunta, aparece uma contagem visual de 3 segundos e, em seguida, a voz informa se é verdadeira ou falsa e explica a resposta.

## O padrão do vídeo

- Vídeo vertical: **1080 × 1920 px** (9:16).
- Narração: voz `pt-BR-AntonioNeural`, velocidade `+10%`.
- Contagem: 3 segundos, com os números 3, 2 e 1 e bipes curtos.
- Imagem opcional: sempre encaixada sem corte ou distorção na área **970 × 970 px**, entre as posições `(55, 500)` e `(1025, 1470)` do vídeo.
- A resposta e a explicação aparecem nessa área depois da contagem.
- Cada item de `PERGUNTAS` gera um vídeo com apenas uma afirmação.

## Colocar no repositório Quiz-10

Envie estes arquivos para a raiz do repositório, mantendo a pasta `.github/workflows/`:

```text
gerar_vf.py
dados_vf.py
requirements-vf.txt
imagens_perguntas/
.github/workflows/gerar-vf.yml
```

Não substitua o gerador ou os dados do Quiz-10. O modo Verdadeiro ou Falso fica separado.

## Cadastrar perguntas

Edite `dados_vf.py`. Para cada vídeo, preencha `pergunta`, `verdadeiro` e `explicacao`. `imagem` pode ser `None` ou o caminho de uma imagem dentro de `imagens_perguntas/`.

```python
{
    "pergunta": "A água ferve sempre a 100 °C, em qualquer lugar?",
    "verdadeiro": False,
    "explicacao": "Em lugares altos, a pressão atmosférica é menor. Por isso, a água ferve abaixo de 100 °C.",
    "imagem": "imagens_perguntas/agua_ferve.png",
}
```

Use `True` para verdadeiro e `False` para falso. A imagem de exemplo já está no tamanho exato de **970 × 970 px**. Você pode substituí-la por outra mantendo esse tamanho; imagens de outras proporções também serão ajustadas para caber na área sem serem cortadas.

## Gerar pelo GitHub

1. Abra a aba **Actions** do repositório.
2. Escolha **Gerar Juh Quiz — Verdadeiro ou Falso**.
3. Toque em **Run workflow**.
4. Ao terminar, baixe o artefato `juh-quiz-verdadeiro-ou-falso` para obter os MP4 e TXT.

O gerador também pode ser executado localmente com `python gerar_vf.py` após instalar `requirements-vf.txt` e o FFmpeg.
