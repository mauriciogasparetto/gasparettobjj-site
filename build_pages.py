#!/usr/bin/env python3
"""
Gerador de paginas do gasparettobjj-site. Chamado por build.py.

A partir de src/index.template.html produz uma pagina por idioma, cada uma
contendo apenas o seu proprio texto -- e nao os tres ao mesmo tempo, que era
o que diluia o SEO. Tambem gera sitemap.xml, robots.txt e site.webmanifest.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
import shutil
from datetime import date
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).parent
TEMPLATE = ROOT / "src" / "index.template.html"
# tudo que o build produz vai para dist/: e a pasta que se publica, e
# manter os originais de foto (8 MB) fora dela evita subir peso morto
DIST = ROOT / "dist"
MANIFEST = ROOT / ".build-manifest.json"

# elementos sem tag de fechamento: nao abrem nivel de aninhamento
VOID = {
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link",
    "meta", "param", "source", "track", "wbr",
}

BANNER = """<!--
  =========================================================================
   ARQUIVO GERADO AUTOMATICAMENTE -- NAO EDITE ESTE ARQUIVO.

   Qualquer alteracao feita aqui sera APAGADA no proximo build.
   Edite o conteudo em:  src/index.template.html
   Depois rode:          python build.py --pages
  =========================================================================
-->
"""

LANG_META = {
    "es": {"locale": "es_ES", "path": "/", "name": "Español", "label": "ES"},
    "pt": {"locale": "pt_BR", "path": "/pt/", "name": "Português", "label": "PT"},
    "en": {"locale": "en_US", "path": "/en/", "name": "English", "label": "EN"},
}
ORDER = ("es", "pt", "en")
DEFAULT_LANG = "es"  # fica na raiz e responde por hreflang="x-default"

# saida de cada idioma
OUT_FILE = {"es": "index.html", "pt": "pt/index.html", "en": "en/index.html"}

# rotulos do seletor de idioma e strings usadas pelo JS
UI = {
    "es": {
        "lang_group": "Idioma",
        "sending": "Enviando…",
        "ok": "¡Mensaje enviado! Gracias por escribir.",
        "fallback": "No pudimos enviar el formulario. Abrimos WhatsApp con tu mensaje.",
    },
    "pt": {
        "lang_group": "Idioma",
        "sending": "Enviando…",
        "ok": "Mensagem enviada! Obrigado pelo contato.",
        "fallback": "Não foi possível enviar o formulário. Abrimos o WhatsApp com sua mensagem.",
    },
    "en": {
        "lang_group": "Language",
        "sending": "Sending…",
        "ok": "Message sent! Thanks for reaching out.",
        "fallback": "We couldn't send the form. We've opened WhatsApp with your message.",
    },
}

# dados de contato -- uma unica fonte para HTML e JSON-LD
PHONE = "+34635437530"
EMAIL = "gasparettojiujitsu@gmail.com"
INSTAGRAM = "https://www.instagram.com/mauricio_gasparetto"
YOUTUBE = "https://www.youtube.com/@gasparettojiujitsu"


# ---------------------------------------------------------------------------
# 1. [[es:...|pt:...|en:...]]  ->  texto do idioma
# ---------------------------------------------------------------------------
# o split so quebra num "|" seguido de "es:", "pt:" ou "en:", para que a
# barra possa aparecer livremente no meio do texto (ex.: no <title>)
_BLOCK = re.compile(r"\[\[(.+?)\]\]", re.DOTALL)
_SPLIT = re.compile(r"\|(?=(?:es|pt|en):)")


def resolve_inline(text: str, lang: str) -> str:
    def pick(match: re.Match[str]) -> str:
        options = {}
        for part in _SPLIT.split(match.group(1)):
            code, _, value = part.partition(":")
            options[code.strip()] = value.strip()
        missing = set(ORDER) - options.keys()
        if missing:
            raise ValueError(
                f"traducao faltando ({', '.join(sorted(missing))}) em: "
                f"{match.group(0)[:70]}"
            )
        return options[lang]

    return _BLOCK.sub(pick, text)


# ---------------------------------------------------------------------------
# 2. remover as subarvores data-lang dos outros idiomas
# ---------------------------------------------------------------------------
class LangFilter(HTMLParser):
    """Reemite o HTML descartando elementos data-lang de outros idiomas.

    Usa get_starttag_text() para devolver a tag exatamente como foi escrita,
    preservando atributos, entidades e formatacao.
    """

    def __init__(self, lang: str) -> None:
        super().__init__(convert_charrefs=False)
        self.lang = lang
        self.out: list[str] = []
        self.skip = 0  # profundidade dentro de um bloco descartado
        self.dropped = 0

    # -- tags ---------------------------------------------------------------
    def handle_starttag(self, tag: str, attrs) -> None:
        if self.skip:
            if tag not in VOID:
                self.skip += 1
            return
        value = dict(attrs).get("data-lang")
        if value is not None and value != self.lang:
            self.dropped += 1
            if tag not in VOID:
                self.skip = 1
            return
        self.out.append(self.get_starttag_text() or "")

    def handle_startendtag(self, tag: str, attrs) -> None:
        if self.skip:
            return
        value = dict(attrs).get("data-lang")
        if value is not None and value != self.lang:
            self.dropped += 1
            return
        self.out.append(self.get_starttag_text() or "")

    def handle_endtag(self, tag: str) -> None:
        if self.skip:
            self.skip -= 1
            return
        self.out.append(f"</{tag}>")

    # -- conteudo -----------------------------------------------------------
    def handle_data(self, data: str) -> None:
        if not self.skip:
            self.out.append(data)

    def handle_entityref(self, name: str) -> None:
        if not self.skip:
            self.out.append(f"&{name};")

    def handle_charref(self, name: str) -> None:
        if not self.skip:
            self.out.append(f"&#{name};")

    def handle_comment(self, data: str) -> None:
        # comentarios do template servem a quem edita a fonte, nao ao visitante
        pass

    def handle_decl(self, decl: str) -> None:
        self.out.append(f"<!{decl}>")

    def handle_pi(self, data: str) -> None:
        self.out.append(f"<?{data}>")

    def result(self) -> str:
        return "".join(self.out)


# ---------------------------------------------------------------------------
# 3. fragmentos por idioma
# ---------------------------------------------------------------------------
def lang_switch(lang: str, site_url: str) -> str:
    items = []
    for code in ORDER:
        meta = LANG_META[code]
        current = ' aria-current="page"' if code == lang else ""
        items.append(
            f'<a href="{meta["path"]}" lang="{code}" hreflang="{code}" '
            f'aria-label="{meta["name"]}"{current}>{meta["label"]}</a>'
        )
    group = html.escape(UI[lang]["lang_group"], quote=True)
    return (
        f'<div class="lang" role="group" aria-label="{group}">'
        + "".join(items)
        + "</div>"
    )


def head_alternates(site_url: str) -> str:
    links = [
        f'<link rel="alternate" hreflang="{code}" '
        f'href="{site_url}{LANG_META[code]["path"]}" />'
        for code in ORDER
    ]
    links.append(
        f'<link rel="alternate" hreflang="x-default" '
        f'href="{site_url}{LANG_META[DEFAULT_LANG]["path"]}" />'
    )
    return "\n    ".join(links)


def og_alt_locales(lang: str) -> str:
    return "\n    ".join(
        f'<meta property="og:locale:alternate" content="{LANG_META[c]["locale"]}" />'
        for c in ORDER
        if c != lang
    )


def json_ld(lang: str, site_url: str) -> str:
    """LocalBusiness + Person.

    PENDENTE (so o dono tem os dados exatos): "geo" com latitude/longitude e
    "openingHoursSpecification" com a agenda oficial. Nao foram inventados de
    proposito -- dado errado em JSON-LD prejudica mais que a ausencia dele.
    """
    business_id = f"{site_url}/#business"
    person_id = f"{site_url}/#mauricio"
    modalities = {
        "es": [
            "Defensa Personal Femenina",
            "Defensa Personal",
            "Jiu-Jitsu Gi",
            "Jiu-Jitsu No-Gi",
            "Jiu-Jitsu Kids",
            "Clases Particulares",
        ],
        "pt": [
            "Defesa Pessoal Feminina",
            "Defesa Pessoal",
            "Jiu-Jitsu Gi",
            "Jiu-Jitsu No-Gi",
            "Jiu-Jitsu Kids",
            "Aulas Particulares",
        ],
        "en": [
            "Women's Self-Defense",
            "Self-Defense",
            "Gi Jiu-Jitsu",
            "No-Gi Jiu-Jitsu",
            "Kids Jiu-Jitsu",
            "Private Lessons",
        ],
    }[lang]

    data = {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": ["LocalBusiness", "SportsActivityLocation"],
                "@id": business_id,
                "name": "Gasparetto BJJ",
                "alternateName": "Gasparetto Brazilian Jiu-Jitsu",
                "url": f"{site_url}{LANG_META[lang]['path']}",
                "image": f"{site_url}/assets/img/opt/logo_circular-288.png",
                "logo": f"{site_url}/assets/img/opt/logo_circular-288.png",
                "telephone": PHONE,
                "email": EMAIL,
                "priceRange": "€€",
                "currenciesAccepted": "EUR",
                # aulas dentro da LEVSPORT Altorreal, em Molina de Segura --
                # municipio distinto de Murcia capital, e e por ele que o
                # publico local busca
                "address": {
                    "@type": "PostalAddress",
                    "streetAddress": "C.C. Green Park, Av. del Golf, 117",
                    "addressLocality": "Molina de Segura",
                    "addressRegion": "Región de Murcia",
                    "postalCode": "30506",
                    "addressCountry": "ES",
                },
                "containedInPlace": {
                    "@type": "SportsActivityLocation",
                    "name": "LEVSPORT Altorreal",
                },
                "areaServed": [
                    {"@type": "City", "name": "Molina de Segura"},
                    {"@type": "City", "name": "Murcia"},
                ],
                "sameAs": [INSTAGRAM, YOUTUBE],
                "employee": {"@id": person_id},
                "hasOfferCatalog": {
                    "@type": "OfferCatalog",
                    "name": "Brazilian Jiu-Jitsu",
                    "itemListElement": [
                        {
                            "@type": "Offer",
                            "itemOffered": {"@type": "Service", "name": name},
                        }
                        for name in modalities
                    ],
                },
            },
            {
                "@type": "Person",
                "@id": person_id,
                "name": "Mauricio Gasparetto Fonseca",
                "jobTitle": {
                    "es": "Profesor de Brazilian Jiu-Jitsu",
                    "pt": "Professor de Brazilian Jiu-Jitsu",
                    "en": "Brazilian Jiu-Jitsu Coach",
                }[lang],
                "worksFor": {"@id": business_id},
                # linhagem: XCOACH e a equipe (fundada por Celsinho Venicius);
                # Guga Fraga e o mestre que graduou o Mauricio -- papeis
                # distintos, nao trocar
                "memberOf": {
                    "@type": "SportsOrganization",
                    "name": "XCOACH",
                    "founder": {"@type": "Person", "name": "Celsinho Venicius"},
                },
                "nationality": {"@type": "Country", "name": "Brasil"},
                "knowsLanguage": ["es", "pt", "en"],
                "sameAs": [INSTAGRAM, YOUTUBE],
                "hasCredential": {
                    "@type": "EducationalOccupationalCredential",
                    "credentialCategory": {
                        "es": "Cinturón negro de Brazilian Jiu-Jitsu (2020)",
                        "pt": "Faixa-preta de Brazilian Jiu-Jitsu (2020)",
                        "en": "Brazilian Jiu-Jitsu black belt (2020)",
                    }[lang],
                },
            },
        ],
    }
    body = json.dumps(data, ensure_ascii=False, indent=2)
    return f'<script type="application/ld+json">\n{body}\n</script>'


# ---------------------------------------------------------------------------
# 4. arquivos auxiliares
# ---------------------------------------------------------------------------
def write_sitemap(site_url: str) -> None:
    today = date.today().isoformat()
    urls = "\n".join(
        f"  <url>\n"
        f"    <loc>{site_url}{LANG_META[c]['path']}</loc>\n"
        f"    <lastmod>{today}</lastmod>\n"
        f"    <changefreq>monthly</changefreq>\n"
        f"    <priority>{'1.0' if c == DEFAULT_LANG else '0.8'}</priority>\n"
        f"  </url>"
        for c in ORDER
    )
    _emit("sitemap.xml",
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{urls}\n"
        "</urlset>\n"
    )


def write_robots(site_url: str) -> None:
    # tem de ficar na raiz: nenhum crawler procura em /assets/robots.txt
    _emit("robots.txt",
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /_backup_original/\n"
        "Disallow: /src/\n"
        "\n"
        f"Sitemap: {site_url}/sitemap.xml\n"
    )


def write_manifest() -> None:
    manifest = {
        "name": "Gasparetto BJJ",
        "short_name": "Gasparetto BJJ",
        "description": "Clases de Brazilian Jiu-Jitsu en Altorreal, Molina de Segura, con el profesor Mauricio Gasparetto (XCOACH).",
        "lang": "es",
        "id": "/",
        "start_url": "/",
        "scope": "/",
        "display": "standalone",
        "background_color": "#ffffff",
        "theme_color": "#e30613",
        "icons": [
            {
                "src": "/assets/img/logos/web-app-manifest-192x192.png",
                "sizes": "192x192",
                "type": "image/png",
                "purpose": "maskable",
            },
            {
                "src": "/assets/img/logos/web-app-manifest-512x512.png",
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "maskable",
            },
            {
                "src": "/assets/img/logos/web-app-manifest-512x512.png",
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "any",
            },
        ],
    }
    _emit("site.webmanifest", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")


# ---------------------------------------------------------------------------
# 4b. escrita protegida
# ---------------------------------------------------------------------------
_written: dict[str, str] = {}


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _emit(rel: str, text: str) -> Path:
    """Grava em dist/ e registra o hash para a checagem do proximo build."""
    out = DIST / rel
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    _written[rel] = _digest(text)
    return out


def check_hand_edits() -> list[str]:
    """Arquivos de dist/ alterados a mao desde o ultimo build.

    Sem isto, uma correcao feita direto no HTML gerado desapareceria no build
    seguinte sem nenhum aviso.
    """
    if not MANIFEST.exists():
        return []
    try:
        antigo = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    editados = []
    for rel, esperado in antigo.items():
        f = DIST / rel
        if f.exists() and _digest(f.read_text(encoding="utf-8")) != esperado:
            editados.append(rel)
    return editados


# o que a hospedagem precisa receber -- os originais de foto ficam de fora
COPY_DIRS = ["assets/fonts", "assets/img/opt"]
COPY_FILES = [
    "404.html",
    "assets/img/logos/favicon.ico",
    "assets/img/logos/favicon-96x96.png",
    "assets/img/logos/apple-touch-icon.png",
    "assets/img/logos/web-app-manifest-192x192.png",
    "assets/img/logos/web-app-manifest-512x512.png",
]


def copy_assets() -> int:
    total = 0
    for d in COPY_DIRS:
        origem = ROOT / d
        if not origem.exists():
            continue
        destino = DIST / d
        if destino.exists():
            shutil.rmtree(destino)
        shutil.copytree(origem, destino)
        total += sum(f.stat().st_size for f in destino.rglob("*") if f.is_file())
    for f in COPY_FILES:
        origem = ROOT / f
        if not origem.exists():
            continue
        destino = DIST / f
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(origem, destino)
        total += destino.stat().st_size
    return total


# ---------------------------------------------------------------------------
# 5. orquestracao
# ---------------------------------------------------------------------------
def build_pages(site_url: str, force: bool = False) -> None:
    site_url = site_url.rstrip("/")

    editados = check_hand_edits()
    if editados and not force:
        print("  ! PARADO: estes arquivos de dist/ foram editados a mao:")
        for rel in editados:
            print(f"      dist/{rel}")
        print("    Eles sao gerados -- a alteracao seria perdida agora.")
        print("    Leve a mudanca para src/index.template.html e rode de novo,")
        print("    ou use --force para descartar a edicao manual.")
        print()
        raise SystemExit(1)

    template = TEMPLATE.read_text(encoding="utf-8")

    for lang in ORDER:
        text = resolve_inline(template, lang)

        parser = LangFilter(lang)
        parser.feed(text)
        parser.close()
        text = parser.result()

        canonical = f"{site_url}{LANG_META[lang]['path']}"
        tokens = {
            "{{LANG}}": lang,
            "{{SITE_URL}}": site_url,
            "{{CANONICAL}}": canonical,
            "{{HEAD_ALTERNATES}}": head_alternates(site_url),
            "{{OG_LOCALE}}": LANG_META[lang]["locale"],
            "{{OG_ALT_LOCALES}}": og_alt_locales(lang),
            "{{LANG_SWITCH}}": lang_switch(lang, site_url),
            "{{YEAR}}": str(date.today().year),
            "{{JSONLD}}": json_ld(lang, site_url),
            "{{I18N_JSON}}": json.dumps(
                {k: UI[lang][k] for k in ("sending", "ok", "fallback")},
                ensure_ascii=False,
            ),
        }
        for token, value in tokens.items():
            text = text.replace(token, value)

        leftovers = re.findall(r"\{\{[A-Z_]+\}\}", text)
        if leftovers:
            raise ValueError(f"token nao substituido em {lang}: {set(leftovers)}")

        # o aviso vai depois do doctype para nao atrapalhar o parser
        text = text.replace("<!DOCTYPE html>", "<!DOCTYPE html>\n" + BANNER, 1)

        out = _emit(OUT_FILE[lang], text)
        print(
            f"  dist/{OUT_FILE[lang]:16} {out.stat().st_size / 1024:6.1f} KB  "
            f"({parser.dropped} blocos de outros idiomas removidos)"
        )

    write_sitemap(site_url)
    write_robots(site_url)
    write_manifest()
    print("  dist/: sitemap.xml, robots.txt e site.webmanifest")

    copiado = copy_assets()
    print(f"  dist/: fontes, imagens otimizadas e favicons ({copiado / 1024 / 1024:.1f} MB)")

    MANIFEST.write_text(json.dumps(_written, indent=2), encoding="utf-8")

    # arquivos das versoes anteriores, quando a saida ficava na raiz
    for antigo in ("index.html", "pt/index.html", "en/index.html",
                   "sitemap.xml", "robots.txt", "site.webmanifest",
                   "assets/robots.txt", "assets/site.webmanifest"):
        caminho = ROOT / antigo
        if caminho.exists():
            caminho.unlink()
            print(f"  removido da raiz (agora vive em dist/): {antigo}")
    for pasta in ("pt", "en"):
        d = ROOT / pasta
        if d.is_dir() and not any(d.iterdir()):
            d.rmdir()
