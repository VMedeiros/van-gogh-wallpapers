# Van Gogh Wallpapers

Baixa as pinturas mais famosas de Vincent van Gogh do Wikimedia Commons,
gera wallpapers em Full HD (1920x1080) com o nome da obra e o ano
sobrepostos na imagem, e troca o papel de parede da área de trabalho
automaticamente em um intervalo configurável.

Downloads the most famous Vincent van Gogh paintings from Wikimedia
Commons, generates Full HD (1920x1080) wallpapers with the painting's
name and year overlaid on the image, and rotates the desktop wallpaper
automatically at a configurable interval.

**[🇧🇷 Português](#português) | [🇬🇧 English](#english)**

---

## Português

Duas partes:

- `van_gogh_wallpapers.py` — busca, baixa e processa as imagens.
- `van_gogh_wallpaper_rotator.py` — troca o papel de parede do Windows
  a cada X minutos, sem repetir uma imagem antes de passar por todas.

### Requisitos

- Windows (o rotator usa a API do Windows para trocar o papel de parede)
- Python 3.10+

```
pip install -r requirements.txt
```

### 1. Baixar e gerar os wallpapers

```
python van_gogh_wallpapers.py
```

O que o script faz:

1. Busca no Wikimedia Commons as ~50 pinturas mais famosas do Van Gogh
   (lista editável em `FAMOUS_PAINTINGS`, no topo do arquivo).
2. Baixa uma miniatura de cada uma (resolução suficiente para Full HD,
   bem mais leve que o arquivo original do museu).
3. Remove duplicatas (por hash do arquivo e pelo nome da obra) e filtra
   resultados de outros artistas que a busca por texto possa trazer.
4. Gera uma versão 1920x1080 de cada pintura — sem cortar a obra; se a
   proporção não bate com 16:9, usa a própria pintura borrada como
   fundo — com o nome da obra e o ano no canto inferior direito.
5. Salva tudo em `Van_Gogh_Collection/`:
   - `Originals/` — imagens originais baixadas
   - `Wallpapers_FullHD/` — wallpapers prontos (1920x1080)
   - `Reports/catalog.csv` — catálogo com fonte, licença e créditos de
     cada imagem
6. Compacta os wallpapers em `Van_Gogh_Wallpapers_FullHD.zip`.

Rodar de novo é seguro: imagens já baixadas/processadas são
reaproveitadas (não baixa nem gera de novo).

#### Ajustar a lista de pinturas

Edite a lista `FAMOUS_PAINTINGS` no início do arquivo. Cada item é uma
tupla `(nome de exibição, termo de busca)` — o nome de exibição é o que
aparece na legenda da imagem; o termo de busca pode incluir museu/ano
para desambiguar obras com nomes parecidos (ex: Van Gogh pintou "The
Bedroom" três vezes, em três museus diferentes).

### 2. Trocar o papel de parede automaticamente

```
python van_gogh_wallpaper_rotator.py [intervalo_em_minutos]
```

Exemplo, trocando a cada 20 minutos:

```
python van_gogh_wallpaper_rotator.py 20
```

Sem argumento, o padrão é 30 minutos. `Ctrl+C` para parar.

O rotator também fixa o estilo do papel de parede do Windows como
"Preencher" (mantém a proporção da imagem, sem esticar), e evita repetir
uma pintura antes de passar por todas as outras.

#### Iniciar automaticamente com o Windows

```
python van_gogh_wallpaper_rotator.py --install-startup [intervalo_em_minutos]
```

Isso cria um atalho na pasta Startup do Windows que roda o rotator em
segundo plano (sem janela de console) a cada login. Para desativar:

```
python van_gogh_wallpaper_rotator.py --uninstall-startup
```

Rodando sem console (via login automático), a saída vai para
`Van_Gogh_Collection/.cache/rotator.log` em vez do terminal.

### Notas

- O script respeita o Wikimedia Commons: sem downloads em paralelo, com
  espaçamento entre requisições e backoff em caso de erro 429 (muitas
  requisições). Ajuste `REQUEST_DELAY` em `van_gogh_wallpapers.py` se
  quiser.
- Todas as imagens são de domínio público / licença livre do Wikimedia
  Commons; a fonte e a licença de cada uma ficam registradas em
  `Reports/catalog.csv`.

---

## English

Two parts:

- `van_gogh_wallpapers.py` — searches for, downloads, and processes the
  images.
- `van_gogh_wallpaper_rotator.py` — rotates the Windows desktop
  wallpaper every X minutes, without repeating an image before cycling
  through all of them.

### Requirements

- Windows (the rotator uses the Windows API to change the wallpaper)
- Python 3.10+

```
pip install -r requirements.txt
```

### 1. Download and generate the wallpapers

```
python van_gogh_wallpapers.py
```

What the script does:

1. Searches Wikimedia Commons for Van Gogh's ~50 most famous paintings
   (editable list in `FAMOUS_PAINTINGS`, at the top of the file).
2. Downloads a thumbnail of each one (resolution high enough for Full
   HD, much lighter than the museum's original file).
3. Removes duplicates (by file hash and by painting name) and filters
   out results from other artists that the text search might return.
4. Generates a 1920x1080 version of each painting — never cropping the
   artwork itself; if the aspect ratio doesn't match 16:9, it uses a
   blurred copy of the painting as the background — with the painting's
   name and year in the bottom-right corner.
5. Saves everything to `Van_Gogh_Collection/`:
   - `Originals/` — downloaded original images
   - `Wallpapers_FullHD/` — ready-to-use wallpapers (1920x1080)
   - `Reports/catalog.csv` — catalog with source, license, and credit
     for each image
6. Zips the wallpapers into `Van_Gogh_Wallpapers_FullHD.zip`.

Safe to re-run: already downloaded/processed images are reused (not
downloaded or generated again).

#### Adjusting the painting list

Edit the `FAMOUS_PAINTINGS` list at the top of the file. Each item is a
`(display name, search query)` tuple — the display name is what shows
up in the image caption; the search query can include the museum/year
to disambiguate paintings with similar names (e.g. Van Gogh painted
"The Bedroom" three times, in three different museums).

### 2. Automatically rotate the wallpaper

```
python van_gogh_wallpaper_rotator.py [interval_in_minutes]
```

Example, changing every 20 minutes:

```
python van_gogh_wallpaper_rotator.py 20
```

Defaults to 30 minutes if no argument is given. `Ctrl+C` to stop.

The rotator also locks the Windows wallpaper style to "Fill" (keeps the
image's aspect ratio, no stretching), and avoids repeating a painting
before cycling through all the others.

#### Start automatically with Windows

```
python van_gogh_wallpaper_rotator.py --install-startup [interval_in_minutes]
```

This creates a shortcut in the Windows Startup folder that runs the
rotator in the background (no console window) on every login. To
disable it:

```
python van_gogh_wallpaper_rotator.py --uninstall-startup
```

When running without a console (via automatic login), output goes to
`Van_Gogh_Collection/.cache/rotator.log` instead of the terminal.

### Notes

- The script is respectful of Wikimedia Commons: no parallel downloads,
  spacing between requests, and backoff on 429 errors (too many
  requests). Adjust `REQUEST_DELAY` in `van_gogh_wallpapers.py` if
  needed.
- All images are public domain / freely licensed on Wikimedia Commons;
  the source and license for each one are recorded in
  `Reports/catalog.csv`.
