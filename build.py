#!/usr/bin/env python3
"""
Build do gasparettobjj-site.

Gera, a partir da fonte unica src/index.template.html:
  - index.html        (ES, idioma canonico)
  - pt/index.html
  - en/index.html
  - sitemap.xml
e otimiza as imagens de assets/img/{gallery,logos} para assets/img/opt
em AVIF + WebP + fallback no formato original.

Uso:
    python build.py            # tudo
    python build.py --images   # so as imagens
    python build.py --pages    # so o HTML/sitemap
    python build.py --force    # sobrescreve dist/ mesmo com edicao manual

Tudo o que se publica fica em dist/. Os originais de foto ficam fora dela.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageOps

ROOT = Path(__file__).parent
IMG_SRC = ROOT / "assets" / "img"
IMG_OUT = IMG_SRC / "opt"

# Dominio canonico. TROCAR AQUI quando o dominio final for definido --
# este e o unico lugar que alimenta canonical, hreflang, og:url,
# sitemap.xml e o JSON-LD.
SITE_URL = "https://www.gasparettojiujitsu.com"

LANGS = ("es", "pt", "en")
CANONICAL_LANG = "es"  # fica na raiz do site

# Qualidade escalonada por tamanho de exibicao, calibrada por PSNR contra o
# original: miniaturas de 380px toleram compressao agressiva, mas as versoes
# grandes (lightbox, telas 2x) caiam para ~32 dB em q=50 -- visivel em
# fotos de equipe cheias de detalhe. Acima de 1000px de largura sobe.
Q_AVIF_THUMB, Q_WEBP_THUMB = 50, 82
Q_AVIF_LARGE, Q_WEBP_LARGE = 62, 86
Q_JPEG = 82

# o hero e o LCP e o rosto do site: qualidade alta nas duas larguras
Q_OVERRIDE = {"logos/mau_world_cup_2025.jpg": (60, 86)}


def _quality(rel: str, width: int) -> tuple[int, int]:
    """(qualidade AVIF, qualidade WebP) para esta imagem nesta largura."""
    if rel in Q_OVERRIDE:
        return Q_OVERRIDE[rel]
    if width >= 1000:
        return Q_AVIF_LARGE, Q_WEBP_LARGE
    return Q_AVIF_THUMB, Q_WEBP_THUMB

# largura(s) de saida por imagem, derivadas do tamanho real de exibicao:
#   galeria  -> card de ~380px (760 = 2x) e lightbox (1600)
#   hero     -> coluna de ~513px (560) e telas 2x (1120)
#   logos    -> 2x da altura/largura renderizada
GALLERY_WIDTHS = [380, 760, 1600]
SPEC: dict[str, list[int]] = {
    "gallery/equipe_murcia_central.jpg": GALLERY_WIDTHS,
    "gallery/campeonatos_recientes.jpg": GALLERY_WIDTHS,
    "gallery/brasil_epoca.jpg": GALLERY_WIDTHS,
    "gallery/faixas_pretas_brasil.jpg": GALLERY_WIDTHS,
    "gallery/certificado_ajp.jpg": GALLERY_WIDTHS,
    "gallery/primeros_auxilios.jpg": GALLERY_WIDTHS,
    # hero: 560 (desktop 1x), 760 (celular 2x), 1120 (desktop 2x)
    "logos/mau_world_cup_2025.jpg": [560, 760, 1120],
    "logos/logo_circular.png": [384],
    "logos/logo_horizontal.png": [356],
    "logos/logoCT_Murcia.png": [136],
    # carrossel de mestres: originais ja sao pequenos, so converter
    "logos/kano.jpg": [0],
    "logos/maeda.jpg": [0],
    "logos/tanabe.jpg": [0],
    "logos/helio_carlos_221x148.jfif": [0],
}

# arquivos sem nenhuma referencia no HTML -- vao para _unused em vez de
# serem apagados (sao ativos de marca)
UNUSED = ["logos/logo_aspas.png", "logos/logo_monograma.png"]


def _fallback_ext(src: Path) -> str:
    """Formato do fallback: PNG so quando ha transparencia a preservar."""
    return ".png" if src.suffix.lower() == ".png" else ".jpg"


def optimize_images() -> None:
    IMG_OUT.mkdir(parents=True, exist_ok=True)
    total_before = total_after = 0

    for rel, widths in SPEC.items():
        src = IMG_SRC / rel
        if not src.exists():
            print(f"  ! ausente: {rel}")
            continue

        before = src.stat().st_size
        total_before += before

        # exif_transpose antes de redimensionar: o EXIF nao e copiado para a
        # saida, sem isso uma foto girada pela camera sairia deitada
        with Image.open(src) as im:
            im = ImageOps.exif_transpose(im)
            has_alpha = im.mode in ("RGBA", "LA", "P") and "transparency" in im.info
            has_alpha = has_alpha or im.mode in ("RGBA", "LA")
            im = im.convert("RGBA" if has_alpha else "RGB")
            ow, oh = im.size

            stem = Path(rel).stem
            fb_ext = _fallback_ext(src)

            for w in widths:
                # w == 0 significa "tamanho nativo"; nunca fazer upscale
                target = ow if w == 0 else min(w, ow)
                suffix = "" if w == 0 else f"-{target}"
                resized = (
                    im
                    if target == ow
                    else im.resize(
                        (target, round(oh * target / ow)), Image.LANCZOS
                    )
                )

                out_avif = IMG_OUT / f"{stem}{suffix}.avif"
                out_webp = IMG_OUT / f"{stem}{suffix}.webp"
                out_fb = IMG_OUT / f"{stem}{suffix}{fb_ext}"

                q_avif, q_webp = _quality(rel, target)
                resized.save(out_avif, format="AVIF", quality=q_avif)
                resized.save(out_webp, format="WEBP", quality=q_webp, method=6)
                if fb_ext == ".png":
                    resized.save(out_fb, format="PNG", optimize=True)
                else:
                    resized.convert("RGB").save(
                        out_fb,
                        format="JPEG",
                        quality=Q_JPEG,
                        optimize=True,
                        progressive=True,
                    )

                # o navegador baixa apenas UMA das tres versoes; o custo real
                # e o do AVIF (ou WebP em Safari antigo)
                total_after += out_avif.stat().st_size
                print(
                    f"  {rel:44} -> {resized.size[0]}x{resized.size[1]}  "
                    f"avif {out_avif.stat().st_size // 1024:>4} KB | "
                    f"webp {out_webp.stat().st_size // 1024:>4} KB | "
                    f"{fb_ext[1:]} {out_fb.stat().st_size // 1024:>4} KB"
                )

    unused_dir = IMG_SRC / "_unused"
    unused_dir.mkdir(parents=True, exist_ok=True)
    for rel in UNUSED:
        src = IMG_SRC / rel
        if src.exists():
            src.replace(unused_dir / src.name)
            print(f"  movido para _unused/: {rel}")

    # assets/sitemap.svg e o logo em PNG base64 (97 KB), nao um sitemap,
    # e nao e referenciado em lugar nenhum
    stray = ROOT / "assets" / "sitemap.svg"
    if stray.exists():
        stray.replace(unused_dir / "logo_849px.svg")
        print("  movido para _unused/logo_849px.svg: assets/sitemap.svg")

    print(
        f"\n  originais: {total_before / 1024:.0f} KB"
        f"  ->  servido (AVIF): {total_after / 1024:.0f} KB"
        f"  ({100 - total_after / total_before * 100:.0f}% menor)"
    )


def check_stale_images() -> list[str]:
    """Originais editados depois da ultima geracao.

    O site nunca serve assets/img/{gallery,logos} -- serve assets/img/opt.
    Trocar uma foto original sem rodar --images nao muda nada na pagina, e o
    sintoma (a foto antiga continua aparecendo) nao sugere a causa.
    """
    stale = []
    for rel, widths in SPEC.items():
        src = IMG_SRC / rel
        if not src.exists():
            continue
        stem = Path(rel).stem
        saidas = list(IMG_OUT.glob(f"{stem}-*.avif")) + list(
            IMG_OUT.glob(f"{stem}.avif")
        )
        if not saidas:
            stale.append(rel)
        elif src.stat().st_mtime > max(o.stat().st_mtime for o in saidas):
            stale.append(rel)
    return stale


def main() -> int:
    args = set(sys.argv[1:])
    flags = {"--force"}
    acoes = args - flags
    do_images = not acoes or "--images" in acoes
    do_pages = not acoes or "--pages" in acoes

    if not do_images:
        stale = check_stale_images()
        if stale:
            print("  ! ATENCAO: originais mais novos que as versoes servidas:")
            for rel in stale:
                print(f"      {rel}")
            print("    rode: python build.py --images\n")

    if do_images:
        print("== imagens ==")
        optimize_images()

    if do_pages:
        print("\n== paginas ==")
        from build_pages import build_pages

        build_pages(SITE_URL, force="--force" in args)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
