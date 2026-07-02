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
@click.option("--validate", is_flag=True, help="번역 완료 후 자동 검증 실행")
@click.option("--review", is_flag=True, help="개발 관점 LLM 리뷰 + 용어집 갱신 (끝에 유지/되돌리기 확인)")
def translate(url, output, no_translate, no_images, lang, validate, review):
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

    # 원문 저장 — 이미지 다운로드·번역 전 블록 상태로 저장
    original_md = blocks_to_markdown(title, blocks, url)
    (output_dir / "original.md").write_text(original_md, encoding="utf-8")

    if not no_images:
        click.echo("[3/4] 이미지 다운로드 중...")
        blocks = download_images(blocks, output_dir / "images")
    else:
        click.echo("[3/4] 이미지 스킵")

    if not no_translate:
        auth_key = os.getenv("DEEPL_AUTH_KEY")
        if not auth_key:
            raise click.ClickException("DEEPL_AUTH_KEY가 .env에 설정되지 않았습니다.")
        from glossary import load_glossary

        glossary = load_glossary()
        click.echo(f"[4/4] 번역 중 (→ {lang})...")
        blocks = translate_blocks(blocks, auth_key, lang, glossary=glossary)
    else:
        click.echo("[4/4] 번역 스킵")

    result = blocks_to_markdown(title, blocks, url)
    output_file = output_dir / "index.md"
    output_file.write_text(result, encoding="utf-8")

    click.echo(f"\n완료: {output_file}")

    if validate:
        click.echo("\n[검증] 번역 품질 검증 중...")
        from validators.reporter import run_validator

        report = run_validator(output_file, output_dir / "original.md")
        summary = report["summary"]
        issues = summary.get("total_issues", summary["llm_confirmed_issues"])
        untranslated = summary.get("untranslated", 0)
        click.echo(
            f"      총 단락: {summary['total_paragraphs']} | nltk 플래그: {summary['nltk_flagged']} | "
            f"미번역: {untranslated} | 확인된 이슈: {summary['llm_confirmed_issues']}"
        )
        if issues > 0:
            click.echo(f"[warn] {issues}개 단락에 문제가 있습니다 — 리포트: {report['report_path']}")
        else:
            click.echo("      검증 완료 — 이슈 없음")

    if review and not no_translate:
        _run_review(output_file)


def _run_review(output_file):
    """개발 관점 리뷰 → 자동 적용 → 끝 게이트(콘텐츠/용어집 각각 유지/되돌리기)."""
    import shutil

    from glossary import load_glossary, merge_glossary_changes
    from reviewer import apply_content_edits, review_translation

    original_file = output_file.parent / "original.md"
    glossary = load_glossary()

    click.echo("\n[리뷰] 개발 관점 검토 중...")
    result = review_translation(output_file, original_file, glossary)
    edits = result["edits"]
    g_changes = result["glossary"]
    has_g_changes = bool(
        g_changes.get("add") or g_changes.get("narrow") or g_changes.get("remove")
    )

    if not edits and not has_g_changes:
        click.echo("      리뷰 완료 — 변경 사항 없음")
        return

    # 콘텐츠(index.md)는 이 글 전용 파일이라 락 불필요 — 되돌리기용 백업만.
    content_bak = output_file.with_suffix(".md.bak")
    shutil.copy2(output_file, content_bak)

    n_content = apply_content_edits(output_file, edits)

    # 용어집은 공유 자산 → 락 걸고 델타만 병합(동시 리뷰 안전). g_inverse로 되돌린다.
    g_summary, g_inverse = [], {"add": {}, "narrow": {}, "remove": []}
    if has_g_changes:
        g_summary, g_inverse = merge_glossary_changes(g_changes)

    # 변경 요약
    click.echo("\n변경 요약 " + "─" * 30)
    click.echo(f"[콘텐츠] {output_file.name}: {n_content}개 단락 수정")
    for e in edits[:10]:
        click.echo(f"  · {e['reason']} — {e['new'][:50]}")
    click.echo(f"[용어집] glossary.json: {len(g_summary)}건")
    for s in g_summary:
        click.echo(f"  {s}")
    click.echo("─" * 40)

    # 끝 게이트 — 콘텐츠 / 용어집 각각 유지 여부
    try:
        if n_content and not click.confirm("\n콘텐츠 변경을 유지할까요?", default=True):
            shutil.copy2(content_bak, output_file)
            click.echo("      콘텐츠 변경을 되돌렸습니다.")
        if g_summary and not click.confirm("용어집 변경을 유지할까요?", default=True):
            # 락 걸고 이번 변경분만 정확히 되돌림(다른 리뷰가 그 사이 추가한 건 보존)
            merge_glossary_changes(g_inverse)
            click.echo("      용어집 변경을 되돌렸습니다.")
    finally:
        content_bak.unlink(missing_ok=True)


if __name__ == "__main__":
    cli()
