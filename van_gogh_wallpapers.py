import csv
import io
import json
import os
import re
import sys
import time
import zipfile
import hashlib
from pathlib import Path
from urllib.parse import unquote
from collections import defaultdict

import requests
from PIL import (
    Image,
    ImageDraw,
    ImageEnhance,
    ImageFilter,
    ImageFont,
    ImageOps,
)
from tqdm import tqdm

# Garante que emojis nos prints não quebrem o console do Windows
# (cp1252 não suporta vários caracteres Unicode usados abaixo).
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


# ============================================================
# CONFIGURAÇÃO
# ============================================================

API_URL = "https://commons.wikimedia.org/w/api.php"

# As 50 pinturas mais famosas de Vincent van Gogh.
# Cada item é (nome de exibição p/ legenda, termo de busca
# no Commons — pode levar museu/ano para desambiguar).
FAMOUS_PAINTINGS = [
    ("The Starry Night", "The Starry Night"),
    ("Sunflowers", "Sunflowers National Gallery London"),
    ("The Potato Eaters", "The Potato Eaters"),
    ("Café Terrace at Night", "Café Terrace at Night"),
    ("The Bedroom (Van Gogh Museum)", "The Bedroom Van Gogh Museum"),
    ("Irises", "Irises Getty"),
    ("Self-Portrait with Bandaged Ear", "Self-Portrait with Bandaged Ear"),
    ("Wheatfield with Crows", "Wheatfield with Crows"),
    ("The Night Café", "The Night Café"),
    ("Almond Blossoms", "Almond Blossoms"),
    ("Starry Night Over the Rhône", "Starry Night Over the Rhône"),
    ("Self-Portrait (Musée d'Orsay)", "Self-Portrait 1889 Musée d'Orsay"),
    ("The Church at Auvers", "The Church at Auvers"),
    ("Portrait of Dr. Gachet", "Portrait of Dr. Gachet"),
    ("Vase with Fifteen Sunflowers", "Vase with Fifteen Sunflowers Neue Pinakothek"),
    ("Wheat Field with Cypresses (National Gallery)", "Wheat Field with Cypresses"),
    ("The Yellow House", "The Yellow House"),
    ("The Red Vineyard", "The Red Vineyard"),
    ("Portrait of Joseph Roulin", "Portrait of Joseph Roulin"),
    ("La Mousmé", "La Mousmé"),
    ("The Sower", "The Sower 1888"),
    ("Road with Cypress and Star", "Road with Cypress and Star"),
    ("Wheat Field with a Reaper", "Wheat Field with a Reaper"),
    ("Self-Portrait as a Painter", "Self-Portrait as a Painter"),
    ("Prisoners' Round", "Prisoners' Round"),
    ("Green Wheat Field with Cypress", "Green Wheat Field with Cypress"),
    ("The Olive Trees", "The Olive Trees"),
    ("Portrait of Père Tanguy", "Portrait of Père Tanguy"),
    ("Two Cut Sunflowers", "Two Cut Sunflowers"),
    ("Cypresses", "Cypresses Metropolitan Museum"),
    ("The Bedroom (Art Institute of Chicago)", "The Bedroom Art Institute of Chicago"),
    ("The Bedroom (Musée d'Orsay)", "The Bedroom Musée d'Orsay"),
    ("Vincent's Chair with His Pipe", "Vincent's Chair with His Pipe"),
    ("Paul Gauguin's Armchair", "Paul Gauguin's Armchair"),
    ("Wheatfield under Thunderclouds", "Wheatfield under Thunderclouds"),
    ("Portrait of Eugène Boch", "Portrait of Eugène Boch"),
    ("La Berceuse", "La Berceuse Augustine Roulin"),
    ("Portrait of Camille Roulin", "Portrait of Camille Roulin"),
    ("Portrait of Armand Roulin", "Portrait of Armand Roulin"),
    ("The Zouave", "The Zouave"),
    ("Vase with Twelve Sunflowers", "Vase with Twelve Sunflowers Neue Pinakothek Munich"),
    ("Fritillaries in a Copper Vase", "Fritillaries in a Copper Vase"),
    ("The Good Samaritan", "The Good Samaritan after Delacroix"),
    ("At Eternity's Gate", "At Eternity's Gate Sorrowing Old Man"),
    ("Landscape with Snow", "Landscape with Snow"),
    ("First Steps", "First Steps after Millet"),
    ("The Poplars at Saint-Rémy", "The Poplars at Saint-Rémy"),
    ("Tree Roots", "Tree Roots"),
    ("Daubigny's Garden", "Daubigny's Garden"),
    ("The Arlésienne", "The Arlésienne Portrait of Madame Ginoux"),
]

OUTPUT_DIR = Path("Van_Gogh_Collection")

ORIGINALS_DIR = OUTPUT_DIR / "Originals"

WALLPAPER_DIR = OUTPUT_DIR / "Wallpapers_FullHD"

METADATA_DIR = OUTPUT_DIR / "Metadata"

REPORT_DIR = OUTPUT_DIR / "Reports"

CACHE_DIR = OUTPUT_DIR / ".cache"

CSV_FILE = REPORT_DIR / "catalog.csv"

ZIP_FILE = Path("Van_Gogh_Wallpapers_FullHD.zip")


# ============================================================
# RESOLUÇÃO
# ============================================================

RES_FULLHD = (1920, 1080)

# Largura da miniatura pedida à API do Wikimedia.
# Full HD só precisa de ~1920px de fonte; pedimos um
# pouco mais para ter folga de qualidade sem baixar o
# arquivo original gigante (às vezes 100+ MP).
THUMB_WIDTH = 2560


# ============================================================
# REGRAS
# ============================================================

# Mínimo para considerar uma imagem (evita upscaling)
MIN_SOURCE_WIDTH = 1920
MIN_SOURCE_HEIGHT = 1080

# Diferença máxima de proporção para considerar
# que podemos preencher 16:9 com crop pequeno.
ASPECT_TOLERANCE = 0.10

# Qualidade JPEG
JPEG_QUALITY = 96

# Delay entre chamadas
REQUEST_DELAY = 0.5

# Criar ZIP
CREATE_ZIPS = True

# Ignorar imagens que provavelmente não são a obra
EXCLUDE_KEYWORDS = [
    "detail",
    "crop",
    "cropped",
    "frame",
    "framed",
    "museum display",
    "exhibition",
    "installation",
    "room",
    "poster",
    "book",
    "catalog",
    "stamp",
    "signature detail",
    "close-up",
    "sketch",
    "drawing",
    "study",
    "letter",
    "recto",
    "verso",
]


# ============================================================
# HTTP
# ============================================================

session = requests.Session()

session.headers.update({
    "User-Agent":
        "VanGoghWallpaperCollector/2.0 "
        "(personal wallpaper project; "
        "repam35142@crybio.com; "
        "Wikimedia Commons API)"
})


# ============================================================
# DIRETÓRIOS
# ============================================================

for directory in [
    OUTPUT_DIR,
    ORIGINALS_DIR,
    WALLPAPER_DIR,
    METADATA_DIR,
    REPORT_DIR,
    CACHE_DIR,
]:
    directory.mkdir(
        parents=True,
        exist_ok=True
    )


# ============================================================
# STRING UTILITIES
# ============================================================

def clean_html(text):

    if not text:
        return ""

    text = re.sub(
        r"<[^>]+>",
        "",
        str(text)
    )

    return unescape_text(text).strip()


def unescape_text(text):

    replacements = {
        "&nbsp;": " ",
        "&amp;": "&",
        "&quot;": '"',
        "&#39;": "'",
        "&lt;": "<",
        "&gt;": ">",
    }

    for a, b in replacements.items():

        text = text.replace(a, b)

    return text


def safe_filename(name):

    name = unquote(name)

    if name.startswith("File:"):
        name = name[5:]

    name = re.sub(
        r'[<>:"/\\|?*]',
        "_",
        name
    )

    name = re.sub(
        r"\s+",
        " ",
        name
    ).strip()

    return name


def slugify(text):

    text = text.lower()

    text = re.sub(
        r"[^a-z0-9]+",
        "_",
        text
    )

    text = re.sub(
        r"_+",
        "_",
        text
    )

    return text.strip("_")


# Termos que não identificam a obra em si, apenas a
# digitalização/fonte (variam entre providers do mesmo quadro).
TITLE_NOISE_TERMS = [
    "google art project",
    "web gallery of art",
    "wga",
    "high resolution",
    "high res",
    "hi res",
    "hires",
    "restored",
    "retouched",
    "edit",
    "edited",
]


def normalize_title_key(title):

    text = title.lower()

    text = re.sub(r"file:", "", text)

    for term in TITLE_NOISE_TERMS:
        text = text.replace(term, " ")

    text = re.sub(r"\b\d{3,5}\b", "", text)

    text = re.sub(r"[^a-z0-9]+", " ", text)

    return text.strip()


# ============================================================
# API
# ============================================================

def api_request(params):

    max_attempts = 8

    for attempt in range(max_attempts):

        try:

            response = session.get(
                API_URL,
                params=params,
                timeout=90
            )

            if response.status_code == 429:

                retry_after = response.headers.get(
                    "Retry-After"
                )

                wait = (
                    float(retry_after)
                    if retry_after
                    else min(60, 5 * (attempt + 1))
                )

                print(
                    f"\n429 Too Many Requests "
                    f"(tentativa {attempt + 1}/{max_attempts}), "
                    f"aguardando {wait:.0f}s..."
                )

                time.sleep(wait)

                continue

            response.raise_for_status()

            data = response.json()

            time.sleep(REQUEST_DELAY)

            return data

        except Exception as e:

            print(
                f"\nAPI error "
                f"(tentativa {attempt + 1}/{max_attempts}): "
                f"{e}"
            )

            time.sleep(
                min(60, 2 ** attempt)
            )

    raise RuntimeError(
        "Falha definitiva na API."
    )


# ============================================================
# BUSCA DAS OBRAS MAIS FAMOSAS
# ============================================================

def search_files(query, limit=5):

    params = {
        "action": "query",
        "list": "search",
        "srsearch": f"{query} Vincent van Gogh",
        "srnamespace": "6",
        "srlimit": str(limit),
        "format": "json",
    }

    data = api_request(params)

    return [
        result["title"]
        for result in data
        .get("query", {})
        .get("search", [])
    ]


def discover_famous_files():

    files = {}

    print(
        "\n=========================================="
    )
    print(
        f" BUSCANDO AS {len(FAMOUS_PAINTINGS)} "
        "OBRAS MAIS FAMOSAS"
    )
    print(
        "==========================================\n"
    )

    for display_name, query in FAMOUS_PAINTINGS:

        print(
            f"[{display_name}]"
        )

        try:

            titles = search_files(query)

        except Exception as e:

            print(
                f"  ERRO: {e}"
            )

            continue

        for title in titles:

            files[title] = {
                "title": title,
                "category": display_name
            }

    print()
    print(
        f"Arquivos candidatos encontrados: "
        f"{len(files)}"
    )

    return list(files.values())


# ============================================================
# METADADOS DAS IMAGENS
# ============================================================

def chunks(items, size):

    for i in range(
        0,
        len(items),
        size
    ):

        yield items[i:i + size]


def get_image_metadata(file_titles):

    results = []

    for chunk in chunks(
        file_titles,
        50
    ):

        params = {
            "action": "query",
            "titles": "|".join(chunk),
            "prop": "imageinfo",
            "iiprop":
                "url|size|mime|sha1|extmetadata",
            "iiurlwidth": str(THUMB_WIDTH),
            "iilimit": "1",
            "format": "json",
        }

        data = api_request(params)

        pages = (
            data
            .get("query", {})
            .get("pages", {})
        )

        for page in pages.values():

            if "missing" in page:
                continue

            info_list = page.get(
                "imageinfo"
            )

            if not info_list:
                continue

            info = info_list[0]

            width = info.get(
                "width",
                0
            )

            height = info.get(
                "height",
                0
            )

            mime = info.get(
                "mime",
                ""
            )

            if not mime.startswith(
                "image/"
            ):
                continue

            if (
                width < MIN_SOURCE_WIDTH
                or
                height < MIN_SOURCE_HEIGHT
            ):
                continue

            extmetadata = info.get(
                "extmetadata",
                {}
            )

            def meta(key):

                value = extmetadata.get(
                    key,
                    {}
                )

                return clean_html(
                    value.get(
                        "value",
                        ""
                    )
                )

            results.append({

                "title":
                    page["title"],

                "url":
                    info.get("url"),

                "download_url":
                    info.get(
                        "thumburl"
                    ) or info.get("url"),

                "width":
                    width,

                "height":
                    height,

                "mime":
                    mime,

                "sha1":
                    info.get(
                        "sha1",
                        ""
                    ),

                "artist":
                    meta("Artist"),

                "description":
                    meta("ImageDescription"),

                "date":
                    meta("DateTimeOriginal"),

                "credit":
                    meta("Credit"),

                "license":
                    meta("LicenseShortName"),

                "categories":
                    meta("Categories"),

            })

    return results


# ============================================================
# FILTROS
# ============================================================

def should_exclude(item):

    # A busca por texto pode trazer obras de outros
    # artistas (falso positivo por relevância). O campo
    # Artist do Commons é o sinal mais confiável de autoria.
    artist = item.get("artist", "").lower()

    if artist and "van gogh" not in artist:

        return True

    text = (
        item["title"]
        + " "
        + item.get(
            "description",
            ""
        )
        + " "
        + item.get(
            "categories",
            ""
        )
    ).lower()

    if not artist and "van gogh" not in text:

        return True

    for keyword in EXCLUDE_KEYWORDS:

        if keyword in text:

            return True

    return False


def score_image(item):

    """
    Quanto maior, melhor.

    Priorizamos:
    - resolução
    - proporção
    - arquivos sem indicação de crop
    """

    width = item["width"]
    height = item["height"]

    pixels = width * height

    aspect = width / height

    target = 16 / 9

    aspect_difference = abs(
        aspect - target
    )

    score = pixels / 1_000_000

    # Pequeno bônus para proporções
    # próximas de 16:9
    score += max(
        0,
        10 - aspect_difference * 30
    )

    return score


# ============================================================
# DEDUPLICAÇÃO
# ============================================================

def deduplicate(items):

    print(
        "\n🔎 Eliminando duplicatas..."
    )

    # Primeiro SHA1
    by_sha1 = {}

    for item in items:

        sha1 = item.get(
            "sha1"
        )

        if not sha1:
            continue

        existing = by_sha1.get(
            sha1
        )

        if (
            existing is None
            or
            score_image(item)
            >
            score_image(existing)
        ):

            by_sha1[sha1] = item

    unique_sha1 = list(
        by_sha1.values()
    )

    # Segundo agrupamento: cada item carrega em "category"
    # o nome da obra famosa que originou a busca — usamos
    # isso como chave primária, então cada uma das obras
    # pedidas rende no máximo 1 imagem no resultado final.
    # Sem essa chave (ex: item de uma busca antiga), caímos
    # para o número de catálogo (Faille/JH) ou o título
    # normalizado, que identificam a mesma obra mesmo com
    # títulos diferentes (ex: "- Google Art Project").
    groups = defaultdict(list)

    for item in unique_sha1:

        category = item.get("category")

        if category:

            key = ("category", category)

        else:

            identification = identify_work(item)

            if identification["faille"]:

                key = ("faille", identification["faille"])

            elif identification["jh"]:

                key = ("jh", identification["jh"])

            else:

                key = ("title", normalize_title_key(item["title"]))

        groups[key].append(
            item
        )

    selected = []

    for group in groups.values():

        group = [
            item
            for item in group
            if not should_exclude(item)
        ]

        if not group:
            continue

        best = max(
            group,
            key=score_image
        )

        selected.append(best)

    print(
        f"Antes: {len(items)}"
    )

    print(
        f"Após SHA1: {len(unique_sha1)}"
    )

    print(
        f"Obras selecionadas: "
        f"{len(selected)}"
    )

    return selected


# ============================================================
# IDENTIFICAÇÃO
# ============================================================

def extract_faille(text):

    patterns = [
        r"\bF[- ]?(\d{1,4})\b",
        r"\bF(\d{1,4})\b",
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            text,
            re.IGNORECASE
        )

        if match:

            return (
                "F"
                + match.group(1)
            )

    return ""


def extract_jh(text):

    patterns = [
        r"\bJH[- ]?(\d{1,5})\b",
        r"\bJH(\d{1,5})\b",
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            text,
            re.IGNORECASE
        )

        if match:

            return (
                "JH"
                + match.group(1)
            )

    return ""


def extract_year(text):

    matches = re.findall(
        r"\b(18[7-9]\d|1900)\b",
        text
    )

    if matches:

        return matches[0]

    return ""


def identify_work(item):

    text = " ".join([
        item.get("title", ""),
        item.get("description", ""),
        item.get("date", ""),
        item.get("categories", ""),
    ])

    faille = extract_faille(text)

    jh = extract_jh(text)

    year = extract_year(text)

    return {
        "faille": faille,
        "jh": jh,
        "year": year,
    }


# ============================================================
# DOWNLOAD
# ============================================================

def download_file(item):

    title = safe_filename(
        item["title"]
    )

    filename = Path(title).stem

    destination = (
        ORIGINALS_DIR
        /
        f"{filename}.jpg"
    )

    if destination.exists():

        return destination

    print(
        f"\n⬇️ {filename}"
    )

    max_attempts = 3

    for attempt in range(max_attempts):

        try:

            response = session.get(
                item["download_url"],
                timeout=240,
                stream=True
            )

            response.raise_for_status()

            with open(
                destination,
                "wb"
            ) as f:

                for chunk in response.iter_content(
                    chunk_size=1024 * 1024
                ):

                    if chunk:

                        f.write(chunk)

            return destination

        except Exception as e:

            print(
                f"❌ Download falhou "
                f"(tentativa {attempt + 1}/{max_attempts}): "
                f"{e}"
            )

            if destination.exists():
                destination.unlink()

            if attempt + 1 < max_attempts:
                time.sleep(3)

    return None


# ============================================================
# PROCESSAMENTO DE WALLPAPER
# ============================================================

def resize_cover(image, size):

    return image.resize(
        size,
        Image.Resampling.LANCZOS
    )


def create_background(
    image,
    size
):

    background = ImageOps.fit(
        image,
        size,
        method=Image.Resampling.LANCZOS,
        centering=(0.5, 0.5)
    )

    # Blur
    background = background.filter(
        ImageFilter.GaussianBlur(
            radius=45
        )
    )

    # Leve redução de brilho
    background = ImageEnhance.Brightness(
        background
    ).enhance(0.55)

    return background.convert(
        "RGBA"
    )


def fit_without_crop(
    image,
    size
):

    target_width, target_height = size

    ratio = min(
        target_width / image.width,
        target_height / image.height
    )

    new_width = int(
        image.width * ratio
    )

    new_height = int(
        image.height * ratio
    )

    return image.resize(
        (
            new_width,
            new_height
        ),
        Image.Resampling.LANCZOS
    )


CAPTION_FONT_CANDIDATES = [
    "C:\\Windows\\Fonts\\segoeuisl.ttf",
    "C:\\Windows\\Fonts\\segoeui.ttf",
    "C:\\Windows\\Fonts\\arial.ttf",
]


def get_caption_font(size):

    for path in CAPTION_FONT_CANDIDATES:

        if Path(path).exists():

            try:

                return ImageFont.truetype(path, size)

            except Exception:

                continue

    return ImageFont.load_default()


def draw_caption(image, text):

    if not text:

        return image

    width, height = image.size

    overlay = Image.new(
        "RGBA",
        (width, height),
        (0, 0, 0, 0)
    )

    draw = ImageDraw.Draw(overlay)

    font = get_caption_font(
        max(18, height // 32)
    )

    margin = height // 45

    bbox = draw.textbbox(
        (0, 0),
        text,
        font=font
    )

    text_width = bbox[2] - bbox[0]

    text_height = bbox[3] - bbox[1]

    bar_height = text_height + margin * 3

    draw.rectangle(
        [(0, height - bar_height), (width, height)],
        fill=(0, 0, 0, 140)
    )

    # Alinhado à direita.
    x = (
        width
        - margin * 2
        - text_width
        - bbox[0]
    )

    y = (
        height
        - bar_height
        + margin
        - bbox[1]
    )

    draw.text(
        (x + 2, y + 2),
        text,
        font=font,
        fill=(0, 0, 0, 200)
    )

    draw.text(
        (x, y),
        text,
        font=font,
        fill=(255, 255, 255, 240)
    )

    return Image.alpha_composite(
        image.convert("RGBA"),
        overlay
    ).convert("RGB")


def create_wallpaper(
    source_path,
    destination_path,
    size,
    caption=None
):

    with Image.open(
        source_path
    ) as source:

        image = source.convert(
            "RGB"
        )

        target_ratio = (
            size[0] / size[1]
        )

        image_ratio = (
            image.width
            /
            image.height
        )

        # ====================================================
        # CASO MUITO PRÓXIMO DE 16:9
        # ====================================================

        if abs(
            image_ratio
            -
            target_ratio
        ) <= ASPECT_TOLERANCE:

            result = ImageOps.fit(
                image,
                size,
                method=Image.Resampling.LANCZOS,
                centering=(0.5, 0.5)
            )

        else:

            # =================================================
            # FUNDO
            # =================================================

            background = create_background(
                image,
                size
            )

            # =================================================
            # OBRA ORIGINAL INTACTA
            # =================================================

            foreground = fit_without_crop(
                image,
                size
            )

            x = (
                size[0]
                -
                foreground.width
            ) // 2

            y = (
                size[1]
                -
                foreground.height
            ) // 2

            background.alpha_composite(
                foreground.convert(
                    "RGBA"
                ),
                (x, y)
            )

            result = background.convert(
                "RGB"
            )

        if caption:

            result = draw_caption(
                result,
                caption
            )

        result.save(
            destination_path,
            "JPEG",
            quality=JPEG_QUALITY,
            subsampling=0,
            optimize=True
        )


# ============================================================
# METADADOS
# ============================================================

def save_metadata(
    item,
    identification,
    original_path,
    wallpaper
):

    data = {
        "title":
            item["title"],

        "artist":
            item.get(
                "artist",
                ""
            ),

        "date":
            item.get(
                "date",
                ""
            ),

        "faille":
            identification["faille"],

        "j_h":
            identification["jh"],

        "year":
            identification["year"],

        "source_url":
            item["url"],

        "sha1":
            item.get(
                "sha1",
                ""
            ),

        "source_width":
            item["width"],

        "source_height":
            item["height"],

        "license":
            item.get(
                "license",
                ""
            ),

        "credit":
            item.get(
                "credit",
                ""
            ),

        "original_file":
            str(original_path),

        "wallpaper":
            str(wallpaper)
            if wallpaper
            else "",
    }

    filename = safe_filename(
        item["title"]
    )

    filename = Path(
        filename
    ).stem

    output = (
        METADATA_DIR
        /
        f"{filename}.json"
    )

    with open(
        output,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            data,
            f,
            indent=2,
            ensure_ascii=False
        )


# ============================================================
# CSV
# ============================================================

def write_csv(records):

    fields = [
        "title",
        "artist",
        "year",
        "faille",
        "j_h",
        "source_width",
        "source_height",
        "license",
        "source_url",
        "original_file",
        "wallpaper",
    ]

    with open(
        CSV_FILE,
        "w",
        newline="",
        encoding="utf-8-sig"
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=fields
        )

        writer.writeheader()

        for record in records:

            writer.writerow({
                field:
                    record.get(
                        field,
                        ""
                    )
                for field in fields
            })


# ============================================================
# ZIP
# ============================================================

def make_zip(
    source_dir,
    zip_path
):

    files = list(
        source_dir.rglob(
            "*.jpg"
        )
    )

    if not files:

        print(
            f"Nenhum arquivo para "
            f"compactar em {source_dir}"
        )

        return

    print(
        f"\n📦 Criando {zip_path}"
    )

    with zipfile.ZipFile(
        zip_path,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=6
    ) as archive:

        for file in tqdm(
            files,
            desc="Compactando"
        ):

            archive.write(
                file,
                file.relative_to(
                    source_dir
                )
            )

    size_gb = (
        zip_path.stat().st_size
        /
        (1024 ** 3)
    )

    print(
        f"✓ ZIP: {zip_path}"
    )

    print(
        f"✓ Tamanho: "
        f"{size_gb:.2f} GB"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    # ========================================================
    # 1. DESCOBERTA
    # ========================================================

    discovered = (
        discover_famous_files()
    )

    titles = [
        item["title"]
        for item in discovered
    ]

    # ========================================================
    # 2. METADADOS
    # ========================================================

    print(
        "\n🔗 Obtendo metadados..."
    )

    metadata = get_image_metadata(
        titles
    )

    category_by_title = {
        item["title"]: item["category"]
        for item in discovered
    }

    for item in metadata:

        item["category"] = category_by_title.get(
            item["title"],
            ""
        )

    print(
        f"Metadados obtidos: "
        f"{len(metadata)}"
    )

    # ========================================================
    # 3. FILTRO
    # ========================================================

    metadata = [
        item
        for item in metadata
        if not should_exclude(item)
    ]

    # ========================================================
    # 4. DEDUPLICAÇÃO
    # ========================================================

    selected = deduplicate(
        metadata
    )

    # ========================================================
    # 5. PROCESSAMENTO
    # ========================================================

    records = []

    print(
        "\n=========================================="
    )

    print(
        " DOWNLOAD + PROCESSAMENTO"
    )

    print(
        "==========================================\n"
    )

    for index, item in enumerate(
        selected,
        start=1
    ):

        title = safe_filename(
            item["title"]
        )

        filename = Path(
            title
        ).stem

        print(
            f"\n[{index}/{len(selected)}]"
        )

        print(
            f"🎨 {filename}"
        )

        print(
            f"📐 "
            f"{item['width']}x"
            f"{item['height']}"
        )

        # ----------------------------------------------------
        # Identificação
        # ----------------------------------------------------

        identification = identify_work(
            item
        )

        # ----------------------------------------------------
        # Download
        # ----------------------------------------------------

        original = download_file(
            item
        )

        if not original:
            continue

        # ----------------------------------------------------
        # Full HD
        # ----------------------------------------------------

        painting_name = (
            item.get("category")
            or filename
        )

        caption = (
            f"{painting_name} - {identification['year']}"
            if identification["year"]
            else painting_name
        )

        wallpaper = (
            WALLPAPER_DIR
            /
            f"{filename}_1920x1080.jpg"
        )

        if not wallpaper.exists():

            print(
                "🖥️ Gerando Full HD..."
            )

            try:

                create_wallpaper(
                    original,
                    wallpaper,
                    RES_FULLHD,
                    caption=caption
                )

            except Exception as e:

                print(
                    f"❌ Erro Full HD: {e}"
                )

                wallpaper = None

        else:

            print(
                "✓ Full HD já existe"
            )

        # ----------------------------------------------------
        # Metadados
        # ----------------------------------------------------

        save_metadata(
            item,
            identification,
            original,
            wallpaper
        )

        # ----------------------------------------------------
        # Registro
        # ----------------------------------------------------

        records.append({

            "title":
                item["title"],

            "artist":
                item.get(
                    "artist",
                    ""
                ),

            "year":
                identification["year"],

            "faille":
                identification["faille"],

            "j_h":
                identification["jh"],

            "source_width":
                item["width"],

            "source_height":
                item["height"],

            "license":
                item.get(
                    "license",
                    ""
                ),

            "source_url":
                item["url"],

            "original_file":
                str(original),

            "wallpaper":
                str(wallpaper)
                if wallpaper
                else "",
        })

        # Salva CSV incrementalmente
        write_csv(records)

    # ========================================================
    # ZIP
    # ========================================================

    if CREATE_ZIPS:

        make_zip(
            WALLPAPER_DIR,
            ZIP_FILE
        )

    # ========================================================
    # FINAL
    # ========================================================

    print(
        "\n=========================================="
    )

    print(
        "              CONCLUÍDO"
    )

    print(
        "=========================================="
    )

    print(
        f"\nColeção:"
        f"\n  {OUTPUT_DIR}"
    )

    print(
        f"\nWallpapers Full HD:"
        f"\n  {WALLPAPER_DIR}"
    )

    print(
        f"\nCatálogo:"
        f"\n  {CSV_FILE}"
    )

    print(
        "\n✓ Todas as informações de origem "
        "foram preservadas no catálogo."
    )


if __name__ == "__main__":

    main()