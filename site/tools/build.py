"""Builds the website's generated parts (run after changing icons or fonts; the page itself is plain HTML).

  python3 site/tools/build.py --icons DIR --fonts DIR

- fonts.css: Nunito 400/700/800/900 (woff2 from @fontsource/nunito) inlined as data URIs. Public sites on Pages
  run in a CSP sandbox (opaque origin), where fonts from the same host count as cross-origin.
- *.html: every <use href="#i-NAME"> gets its Material Design Icon as a <symbol> in the sprite between the
  "sprite" markers, so the page needs no other request for icons.

Icons: the server image has them: docker run --rm paperkiosk tar -C /icons -c . | tar -x -C /tmp/icons
"""
import argparse
import base64
import re
from pathlib import Path

SITE = Path(__file__).resolve().parent.parent
START, END = "<!-- sprite:start -->", "<!-- sprite:end -->"


def fonts(font_dir):
    css = ["/* Nunito (SIL OFL 1.1, https://github.com/googlefonts/nunito), from @fontsource/nunito 5.3.0. "
           "Made by tools/build.py. */"]
    for w in (400, 700, 800, 900):
        data = base64.b64encode((Path(font_dir) / f"nunito-latin-{w}-normal.woff2").read_bytes()).decode()
        css.append(f'@font-face{{font-family:"Nunito";font-style:normal;font-weight:{w};font-display:swap;'
                   f'src:url(data:font/woff2;base64,{data}) format("woff2")}}')
    (SITE / "fonts.css").write_text("\n".join(css) + "\n")


def sprite(icon_dir):
    for page_file in sorted(SITE.glob("*.html")):
        sprite_page(icon_dir, page_file)


def sprite_page(icon_dir, page_file):
    page = page_file.read_text()
    names = sorted(set(re.findall(r'href="#i-([a-z0-9-]+)"', page)))
    symbols = []
    for n in names:
        svg = (Path(icon_dir) / f"{n}.svg").read_text()
        path = re.search(r'<path d="([^"]+)"', svg).group(1)
        symbols.append(f'<symbol id="i-{n}" viewBox="0 0 24 24"><path d="{path}"/></symbol>')
    block = (f'{START}\n<svg xmlns="http://www.w3.org/2000/svg" style="display:none">'
             + "".join(symbols) + f"</svg>\n{END}")
    page = re.sub(re.escape(START) + ".*?" + re.escape(END), lambda _: block, page, flags=re.S)
    page_file.write_text(page)
    print(f"{page_file.name}: {len(names)} icons")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--icons", required=True)
    ap.add_argument("--fonts", required=True)
    a = ap.parse_args()
    fonts(a.fonts)
    sprite(a.icons)
