import os
from pathlib import Path
from urllib.parse import urlparse

import click
from dotenv import load_dotenv

load_dotenv()


@click.group()
def cli():
    pass


@cli.command()
@click.argument("url")
@click.option("--output", "-o", default="./output", help="저장 디렉토리")
@click.option("--no-translate", is_flag=True, help="번역 스킵, 원문 MD만 저장")
@click.option("--no-images", is_flag=True, help="이미지 다운로드 스킵")
@click.option("--lang", default="KO", help="번역 대상 언어 (DeepL 형식)")
def translate(url, output, no_translate, no_images, lang):
    from converter import blocks_to_markdown
    from crawler import fetch_article_html
    from downloader import download_images
    from parser import parse_article
    from translator import translate_blocks

    slug = urlparse(url).path.split("/")[-1]
    output_dir = Path(output) / slug
    output_dir.mkdir(parents=True, exist_ok=True)

    click.echo(f"[1/4] 크롤링 중: {url}")
    html = fetch_article_html(url)

    click.echo("[2/4] 파싱 중...")
    article = parse_article(html)
    title = article["title"]
    blocks = article["blocks"]
    click.echo(f"      제목: {title}")
    click.echo(f"      블록 수: {len(blocks)}")

    if not no_images:
        click.echo("[3/4] 이미지 다운로드 중...")
        blocks = download_images(blocks, output_dir / "images")
    else:
        click.echo("[3/4] 이미지 스킵")

    if not no_translate:
        auth_key = os.getenv("DEEPL_AUTH_KEY")
        if not auth_key:
            raise click.ClickException("DEEPL_AUTH_KEY가 .env에 설정되지 않았습니다.")
        click.echo(f"[4/4] 번역 중 (→ {lang})...")
        blocks = translate_blocks(blocks, auth_key, lang)
    else:
        click.echo("[4/4] 번역 스킵")

    result = blocks_to_markdown(title, blocks, url)
    output_file = output_dir / "index.md"
    output_file.write_text(result, encoding="utf-8")

    click.echo(f"\n완료: {output_file}")


if __name__ == "__main__":
    cli()
