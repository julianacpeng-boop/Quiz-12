"""Gera vídeos Juh Quiz: uma afirmação V/F, pausa de 3 s e explicação."""

from __future__ import annotations

import asyncio
import argparse
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
import unicodedata
import wave
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from PIL import Image, ImageDraw, ImageFont, ImageOps

from dados_vf import PERGUNTAS


ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "saida_vf"
VOICE = "pt-BR-AntonioNeural"
RATE = "+10%"
VIDEO_W, VIDEO_H = 1080, 1920
IMAGE_BOX = (55, 500, 1025, 1470)  # left, top, right, bottom: 970 x 970 px
ANSWER_IMAGE_BOX = (55, 235, 1025, 1205)  # same 970 x 970 px on the answer screen
IMAGE_INSET = 50  # caricature appears 870 x 870 px inside the fixed 970 x 970 px frame
FPS = 30
DRIVE_BASE = "DESTINO:saida/Juh-Quiz-12/verdadeiro-ou-falso"
BG_TOP = (37, 22, 63)
BG_BOTTOM = (74, 31, 93)
BRAND = "#ffd84d"
TITLE = "#fff8e8"
MUTED = "#e2d2f3"
CARD = "#35204f"
LINE = "#a77bd5"
TRUE = "#35b873"
FALSE = "#ff6272"


def run(command: list[str]) -> None:
    subprocess.run(command, check=True, stdout=subprocess.DEVNULL)


def require_program(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise RuntimeError(f"Não encontrei {name}. Instale o FFmpeg e tente novamente.")
    return path


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"
        if bold
        else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()


def wrap_lines(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if current and draw.textlength(candidate, font=font) > width:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def draw_wrapped(
    draw: ImageDraw.ImageDraw,
    text: str,
    xy: tuple[int, int],
    font: ImageFont.ImageFont,
    fill: str,
    width: int,
    line_gap: int = 16,
    max_lines: int | None = None,
) -> int:
    x, y = xy
    lines = wrap_lines(draw, text, font, width)
    if max_lines and len(lines) > max_lines:
        raise ValueError(
            f"Texto longo demais para a tela ({len(lines)} linhas; máximo {max_lines}): {text}"
        )
    for line in lines:
        draw.text((x, y), line, font=font, fill=fill)
        y += font.size + line_gap
    return y


def rounded(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], radius: int, fill: str, outline=None, width=1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def draw_answer_buttons(draw: ImageDraw.ImageDraw) -> None:
    """Solid game-show buttons, with matched sizes and high contrast."""
    font = load_font(27, True)
    buttons = (
        ((55, 1495, 520, 1592), "VERDADEIRO", TRUE, "check"),
        ((560, 1495, 1025, 1592), "FALSO", FALSE, "cross"),
    )
    for box, label, accent, icon in buttons:
        x1, y1, x2, y2 = box
        rounded(draw, (x1, y1 + 8, x2, y2 + 8), 25, "#160d25")
        rounded(draw, box, 25, accent)
        center = (x1 + 55, (y1 + y2) // 2)
        draw.ellipse((center[0] - 21, center[1] - 21, center[0] + 21, center[1] + 21), fill="#fff8e8")
        icon_color = accent
        if icon == "check":
            draw.line((center[0] - 10, center[1], center[0] - 2, center[1] + 8,
                       center[0] + 12, center[1] - 10), fill=icon_color, width=5, joint="curve")
        else:
            draw.line((center[0] - 9, center[1] - 9, center[0] + 9, center[1] + 9),
                      fill=icon_color, width=5)
            draw.line((center[0] + 9, center[1] - 9, center[0] - 9, center[1] + 9),
                      fill=icon_color, width=5)
        bounds = draw.textbbox((0, 0), label, font=font)
        text_x = (x1 + x2 - (bounds[2] - bounds[0])) / 2 - bounds[0] + 15
        text_y = (y1 + y2 - (bounds[3] - bounds[1])) / 2 - bounds[1]
        draw.text((text_x, text_y), label, font=font, fill="#281740")


def fit_question_font(
    draw: ImageDraw.ImageDraw,
    text: str,
    width: int = 970,
) -> tuple[ImageFont.ImageFont, int]:
    """Shrink long prompts just enough to keep them clear above the image."""
    max_height = 142
    for size in (48, 44, 40, 36, 32, 28, 24):
        font = load_font(size, True)
        lines = wrap_lines(draw, text, font, width)
        height = len(lines) * size + max(0, len(lines) - 1) * 6
        if len(lines) <= 3 and height <= max_height:
            return font, 6
    raise ValueError("A pergunta continua longa demais para caber acima da imagem, mesmo reduzindo a fonte.")


def make_paper(seed_text: str) -> Image.Image:
    """Deep purple game-show background with a subtle vertical gradient."""
    strip = Image.new("RGB", (1, VIDEO_H))
    pixels = []
    for y in range(VIDEO_H):
        t = y / max(1, VIDEO_H - 1)
        pixels.append(tuple(round(BG_TOP[c] * (1 - t) + BG_BOTTOM[c] * t) for c in range(3)))
    strip.putdata(pixels)
    return strip.resize((VIDEO_W, VIDEO_H))


def paste_optional_image(
    canvas: Image.Image,
    image_path: Path | None,
    box: tuple[int, int, int, int] = IMAGE_BOX,
) -> None:
    left, top, right, bottom = box
    box_w, box_h = right - left, bottom - top
    draw = ImageDraw.Draw(canvas)
    rounded(draw, box, 34, CARD, LINE, 3)
    inner_w = max(1, box_w - IMAGE_INSET * 2)
    inner_h = max(1, box_h - IMAGE_INSET * 2)
    inner_box = (left + IMAGE_INSET, top + IMAGE_INSET, right - IMAGE_INSET, bottom - IMAGE_INSET)
    if image_path is None:
        rounded(draw, inner_box, 24, "#4a2b61", LINE, 2)
        draw.text((left + 85, top + 95), "IMAGEM OPCIONAL", font=load_font(30, True), fill=BRAND)
        draw.ellipse((left + 256, top + 256, left + 714, top + 714), fill="#74518d")
        draw.ellipse((left + 350, top + 350, left + 620, top + 620), fill=BRAND)
        draw.text((left + 370, top + 430), "V / F", font=load_font(82, True), fill="#281740")
        return

    if not image_path.exists():
        raise FileNotFoundError(f"Imagem não encontrada: {image_path.relative_to(ROOT)}")
    with Image.open(image_path) as source:
        source = ImageOps.exif_transpose(source).convert("RGBA")
        # Contain, never crop/stretch. The outer frame stays 970 px square;
        # the caricature is 870 px square with a visible 50 px margin.
        fitted = ImageOps.contain(source, (inner_w, inner_h), method=Image.Resampling.LANCZOS)
        px = left + (box_w - fitted.width) // 2
        py = top + (box_h - fitted.height) // 2
        canvas.paste(fitted, (px, py), fitted)


def render_question_frame(question: dict, image_path: Path | None, countdown: int | None = None) -> Image.Image:
    canvas = make_paper(question["pergunta"])
    draw = ImageDraw.Draw(canvas)
    rounded(draw, (55, 55, 365, 130), 24, BRAND)
    draw.text((82, 73), "JUH QUIZ", font=load_font(40, True), fill="#281740")
    draw.text((620, 84), "VERDADEIRO OU FALSO", font=load_font(23, True), fill=MUTED)
    draw.line((55, 180, 1025, 180), fill=LINE, width=3)
    draw.text((60, 200), "DESAFIO DE HOJE", font=load_font(26, True), fill=BRAND)
    draw.text((55, 238), "A afirmação é:", font=load_font(34, True), fill=TITLE)
    rounded(draw, (55, 278, 1025, 445), 24, CARD, LINE, 2)

    question_font, question_gap = fit_question_font(draw, question["pergunta"], width=916)
    draw_wrapped(draw, question["pergunta"], (82, 295), question_font, TITLE, 916,
                 line_gap=question_gap, max_lines=3)
    paste_optional_image(canvas, image_path, IMAGE_BOX)
    draw = ImageDraw.Draw(canvas)
    draw_answer_buttons(draw)
    draw.text((230, 1645), "VOCÊ TEM 3 SEGUNDOS PARA RESPONDER", font=load_font(25, True), fill=MUTED)

    if countdown is not None:
        # The countdown stays centered inside the fixed 970 x 970 image frame.
        draw.ellipse((415, 825, 665, 1075), fill=BRAND, outline="#fff8e8", width=7)
        label = str(countdown)
        font = load_font(150, True)
        bounds = draw.textbbox((0, 0), label, font=font)
        text_x = 540 - (bounds[2] - bounds[0]) / 2 - bounds[0]
        text_y = 950 - (bounds[3] - bounds[1]) / 2 - bounds[1]
        draw.text((text_x, text_y), label, font=font, fill="#281740")
    return canvas


def render_answer_frame(question: dict, image_path: Path | None, answer_text: str) -> Image.Image:
    canvas = make_paper(question["pergunta"])
    draw = ImageDraw.Draw(canvas)
    rounded(draw, (55, 55, 365, 130), 24, BRAND)
    draw.text((82, 73), "JUH QUIZ", font=load_font(40, True), fill="#281740")
    draw.text((620, 84), "VERDADEIRO OU FALSO", font=load_font(23, True), fill=MUTED)
    draw.line((55, 180, 1025, 180), fill=LINE, width=3)
    draw.text((60, 200), "RESPOSTA", font=load_font(28, True), fill=BRAND)

    paste_optional_image(canvas, image_path, ANSWER_IMAGE_BOX)
    draw = ImageDraw.Draw(canvas)
    left, top, right, bottom = ANSWER_IMAGE_BOX
    label = "VERDADEIRA" if question["verdadeiro"] else "FALSA"
    rounded(draw, (left + 183, top + 28, right - 183, top + 122), 28, TRUE if question["verdadeiro"] else FALSE)
    label_font = load_font(46, True)
    bounds = draw.textbbox((0, 0), label, font=label_font)
    tx = (VIDEO_W - (bounds[2] - bounds[0])) / 2 - bounds[0]
    ty = top + 53 - bounds[1]
    draw.text((tx, ty), label, font=label_font, fill="#ffffff")

    card = (55, 1245, 1025, 1775)
    rounded(draw, card, 28, CARD, LINE, 2)
    draw.text((90, 1285), "POR QUÊ?", font=load_font(32, True), fill=BRAND)
    explanation_font = load_font(29)
    draw_wrapped(draw, question["explicacao"], (90, 1345), explanation_font, TITLE,
                 900, line_gap=12, max_lines=8)
    draw.text((90, 1715), "JUH QUIZ  •  EXPLICAÇÃO", font=load_font(22, True), fill=MUTED)
    return canvas


def write_beep(path: Path, frequency: int = 950, seconds: float = 1.0) -> None:
    sample_rate = 48000
    total = int(sample_rate * seconds)
    beep_len = int(sample_rate * 0.12)
    with wave.open(str(path), "wb") as output:
        output.setnchannels(2)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        frames = bytearray()
        for i in range(total):
            if i < beep_len:
                fade = min(1.0, i / (sample_rate * 0.008), (beep_len - i) / (sample_rate * 0.025))
                value = int(7000 * fade * math.sin(2 * math.pi * frequency * i / sample_rate))
            else:
                value = 0
            frames.extend(value.to_bytes(2, "little", signed=True) * 2)
        output.writeframes(frames)


_EDGE_CONFIGURED = False


def configure_edge() -> None:
    """Use the Edge Services endpoint and current Edge browser headers."""
    global _EDGE_CONFIGURED
    import edge_tts.constants as constants
    import edge_tts.communicate as communicate
    import edge_tts.voices as voices

    version = os.getenv("QUIZ_EDGE_VERSION", "").strip()
    if version and not re.fullmatch(r"\d+\.\d+\.\d+\.\d+", version):
        raise ValueError("QUIZ_EDGE_VERSION precisa ser uma versão completa do Edge.")
    if not version:
        try:
            with urlopen("https://edgeupdates.microsoft.com/api/products?view=enterprise", timeout=15) as response:
                products = json.load(response)
            versions = [release["ProductVersion"]
                        for product in products if product.get("Product") == "Stable"
                        for release in product.get("Releases", [])
                        if release.get("Platform") == "Windows"
                        and release.get("Architecture") == "x64"
                        and re.fullmatch(r"\d+\.\d+\.\d+\.\d+", release.get("ProductVersion", ""))]
            version = max(versions, key=lambda item: tuple(map(int, item.split("."))))
        except (URLError, TimeoutError, OSError, ValueError, KeyError, TypeError):
            version = "155.0.4283.45"
            print("Catálogo Edge indisponível; usando a versão validada 155.0.4283.45.", flush=True)

    major = version.split(".")[0]
    constants.CHROMIUM_FULL_VERSION = version
    constants.CHROMIUM_MAJOR_VERSION = major
    constants.SEC_MS_GEC_VERSION = communicate.SEC_MS_GEC_VERSION = voices.SEC_MS_GEC_VERSION = "1-" + version
    base = "api.msedgeservices.com/tts/cognitiveservices"
    token = constants.TRUSTED_CLIENT_TOKEN
    constants.WSS_URL = communicate.WSS_URL = f"wss://{base}/websocket/v1?Ocp-Apim-Subscription-Key={token}"
    constants.VOICE_LIST = voices.VOICE_LIST = f"https://{base}/voices/list?Ocp-Apim-Subscription-Key={token}"
    user_agent = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        f"(KHTML, like Gecko) Chrome/{major}.0.0.0 Safari/537.36 Edg/{major}.0.0.0"
    )
    for headers in (constants.BASE_HEADERS, constants.WSS_HEADERS, constants.VOICE_HEADERS,
                    communicate.WSS_HEADERS, voices.VOICE_HEADERS):
        headers["User-Agent"] = user_agent
    communicate.WSS_HEADERS["Sec-WebSocket-Protocol"] = "synthesize"
    voices.VOICE_HEADERS["Authority"] = "api.msedgeservices.com"
    voices.VOICE_HEADERS["Sec-CH-UA"] = (
        f'" Not;A Brand";v="99", "Microsoft Edge";v="{major}", "Chromium";v="{major}"'
    )
    for module in (communicate, voices):
        context = getattr(module, "_SSL_CTX", None)
        if context is not None:
            context.load_default_certs()
    _EDGE_CONFIGURED = True
    print(f"Voz {VOICE}: conexão Edge Services, versão {version}, sem chave Azure.", flush=True)


async def synthesize(text: str, destination: Path) -> None:
    """Use Edge TTS with retries, then local Brazilian Portuguese speech as fallback."""
    try:
        import edge_tts
        from aiohttp import ClientError

        if not _EDGE_CONFIGURED:
            await asyncio.to_thread(configure_edge)

        temporary = destination.with_name(destination.name + ".parcial.mp3")
        waits = (5, 10, 20)
        for attempt in range(len(waits) + 1):
            try:
                temporary.unlink(missing_ok=True)
                communicator = edge_tts.Communicate(
                    text, VOICE, rate=RATE, connect_timeout=30, receive_timeout=90,
                )
                await communicator.save(str(temporary))
                if not temporary.exists() or temporary.stat().st_size == 0:
                    raise edge_tts.exceptions.NoAudioReceived("Áudio vazio.")
                if probe_duration(temporary) <= 0:
                    raise ValueError("Áudio da voz Antonio sem duração.")
                temporary.replace(destination)
                return
            except (ClientError, asyncio.TimeoutError, edge_tts.exceptions.NoAudioReceived) as error:
                temporary.unlink(missing_ok=True)
                if attempt == len(waits):
                    print(
                        f"Edge TTS falhou após {attempt + 1} tentativas ({error}). "
                        "Usando a voz local pt-br para concluir o vídeo.", flush=True
                    )
                    break
                wait = waits[attempt]
                print(f"Voz Antonio: tentativa {attempt + 1} falhou ({type(error).__name__}); nova tentativa em {wait}s.", flush=True)
                await asyncio.sleep(wait)
            except Exception:
                temporary.unlink(missing_ok=True)
                raise
    except ImportError as error:
        print(f"Edge TTS indisponível ({error}). Usando a voz local pt-br.")

    local_wav = destination.with_name(f"{destination.stem}_local.wav")
    run([
        "espeak-ng", "-v", "pt-br", "-s", "165",
        "-w", str(local_wav), text,
    ])
    run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(local_wav), "-codec:a", "libmp3lame", "-q:a", "3",
        str(destination),
    ])


def probe_duration(path: Path) -> float:
    output = subprocess.check_output(
        [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(path),
        ],
        text=True,
    ).strip()
    return float(output)


def convert_to_wav(source: Path, destination: Path) -> None:
    run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(source), "-ar", "48000", "-ac", "2",
        "-c:a", "pcm_s16le", str(destination),
    ])


def build_segment(frame_path: Path, audio_path: Path, output_path: Path, duration: float) -> None:
    run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-loop", "1", "-framerate", str(FPS), "-i", str(frame_path),
        "-i", str(audio_path), "-t", f"{duration:.3f}", "-map", "0:v:0", "-map", "1:a:0",
        "-vf", "format=yuv420p", "-r", str(FPS), "-c:v", "libx264", "-preset", "veryfast",
        "-crf", "20", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
        "-shortest", str(output_path),
    ])


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "_", normalized.lower()).strip("_")[:64] or "pergunta"


def resolve_image(value: str | None) -> Path | None:
    if not value:
        return None
    path = (ROOT / value).resolve()
    if ROOT not in path.parents:
        raise ValueError("O caminho da imagem precisa ficar dentro do repositório.")
    if path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
        raise ValueError(f"Formato de imagem não suportado: {path.suffix}")
    return path


def validate(question: dict, index: int) -> None:
    required = ("pergunta", "verdadeiro", "explicacao", "legenda", "hashtags")
    missing = [field for field in required if field not in question]
    if missing:
        raise ValueError(f"Pergunta {index}: faltam os campos {', '.join(missing)}.")
    if not isinstance(question["pergunta"], str) or not question["pergunta"].strip():
        raise ValueError(f"Pergunta {index}: o campo pergunta precisa ter texto.")
    if not isinstance(question["verdadeiro"], bool):
        raise ValueError(f"Pergunta {index}: verdadeiro precisa ser True ou False.")
    if not isinstance(question["explicacao"], str) or not question["explicacao"].strip():
        raise ValueError(f"Pergunta {index}: escreva uma explicação.")
    if not isinstance(question["legenda"], str) or not question["legenda"].strip():
        raise ValueError(f"Pergunta {index}: escreva a legenda para publicação.")
    tags = question["hashtags"]
    if not isinstance(tags, list) or not 1 <= len(tags) <= 4:
        raise ValueError(f"Pergunta {index}: informe de 1 a 4 hashtags relacionadas ao tema.")
    if any(not isinstance(tag, str) or not tag.startswith("#") or len(tag) < 2 for tag in tags):
        raise ValueError(f"Pergunta {index}: cada hashtag deve começar com #.")


def format_caption(question: dict) -> str:
    tags = " ".join(question["hashtags"])
    return f"CAPA_SEGUNDOS=2\n\n{question['legenda'].strip()}\n{tags}\n"


def make_one_video(index: int, question: dict, send_drive: bool = False, batch: str = "manual") -> tuple[Path, Path]:
    validate(question, index)
    image_path = resolve_image(question.get("imagem"))
    answer_label = "verdadeira" if question["verdadeiro"] else "falsa"
    answer_text = f"A resposta é {answer_label}. {question['explicacao']}"
    base_name = f"{index:02d}_{slugify(question['pergunta'])}"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="juh_vf_") as temp_dir:
        temp = Path(temp_dir)
        question_audio_mp3 = temp / "pergunta.mp3"
        answer_audio_mp3 = temp / "resposta.mp3"
        asyncio.run(synthesize(question["pergunta"], question_audio_mp3))
        asyncio.run(synthesize(answer_text, answer_audio_mp3))
        question_audio = temp / "pergunta.wav"
        answer_audio = temp / "resposta.wav"
        convert_to_wav(question_audio_mp3, question_audio)
        convert_to_wav(answer_audio_mp3, answer_audio)

        frames: list[Path] = []
        audios: list[Path] = []
        durations: list[float] = []
        question_frame = temp / "pergunta.png"
        render_question_frame(question, image_path).save(question_frame)
        frames.append(question_frame)
        audios.append(question_audio)
        durations.append(probe_duration(question_audio))

        for count in (3, 2, 1):
            frame_path = temp / f"contagem_{count}.png"
            render_question_frame(question, image_path, countdown=count).save(frame_path)
            beep_path = temp / f"bip_{count}.wav"
            write_beep(beep_path)
            frames.append(frame_path)
            audios.append(beep_path)
            durations.append(1.0)

        answer_frame = temp / "resposta.png"
        render_answer_frame(question, image_path, answer_text).save(answer_frame)
        frames.append(answer_frame)
        audios.append(answer_audio)
        durations.append(probe_duration(answer_audio))

        segments: list[Path] = []
        for part, (frame, audio, duration) in enumerate(zip(frames, audios, durations, strict=True), start=1):
            segment = temp / f"segmento_{part:02d}.mp4"
            build_segment(frame, audio, segment, duration)
            segments.append(segment)

        concat_file = temp / "segmentos.txt"
        concat_file.write_text("".join(f"file '{segment.as_posix()}'\n" for segment in segments), encoding="utf-8")
        video_path = OUTPUT_DIR / f"{base_name}.mp4"
        run([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0",
            "-i", str(concat_file), "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-pix_fmt", "yuv420p", "-r", str(FPS), "-c:a", "aac", "-b:a", "192k",
            "-ar", "48000", "-ac", "2", "-movflags", "+faststart", str(video_path),
        ])

    caption_path = OUTPUT_DIR / f"{base_name}.txt"
    result_word = "Verdadeiro" if question["verdadeiro"] else "Falso"
    caption_path.write_text(format_caption(question), encoding="utf-8")
    if send_drive:
        run([
            "rclone", "copyto", str(video_path),
            f"{DRIVE_BASE}/execucao-{batch}/{video_path.name}",
        ])
        run([
            "rclone", "copyto", str(caption_path),
            f"{DRIVE_BASE}/execucao-{batch}/{caption_path.name}",
        ])
    return video_path, caption_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Gera vídeos Juh Quiz de Verdadeiro ou Falso.")
    parser.add_argument("--enviar-drive", action="store_true", help="envia MP4 e TXT para o Drive do Quiz-12")
    parser.add_argument("--lote", default=None, help="identificador da pasta de execução no Drive")
    args = parser.parse_args()

    require_program("ffmpeg")
    require_program("ffprobe")
    if args.enviar_drive:
        require_program("rclone")
    if not PERGUNTAS:
        raise ValueError("Adicione pelo menos uma pergunta em dados_vf.py.")
    batch = args.lote or "manual"
    for index, question in enumerate(PERGUNTAS, start=1):
        video, caption = make_one_video(index, question, args.enviar_drive, batch)
        print(f"Criado: {video.name} e {caption.name}")
        if args.enviar_drive:
            print(f"Enviado ao Drive: {DRIVE_BASE}/execucao-{batch}/")


if __name__ == "__main__":
    main()
