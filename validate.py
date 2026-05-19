from pathlib import Path

import click
from dotenv import load_dotenv

load_dotenv()


@click.command()
@click.argument("target")
@click.argument("original", required=False)
@click.option("--threshold", default=1, show_default=True, help="문장 수 차이 허용 범위")
@click.option("--nltk-only", is_flag=True, help="LLM 호출 없이 nltk만 실행")
@click.option("--skip-short", default=100, show_default=True, help="이 글자 수 미만 단락 스킵")
@click.option("--report", "report_dir", default="./reports", show_default=True, help="리포트 저장 경로")
@click.option("--no-report", is_flag=True, help="리포트 파일 저장 안 함")
def validate(target, original, threshold, nltk_only, skip_short, report_dir, no_report):
    """번역 품질 검증.

    TARGET에 output/{slug}/ 디렉토리를 주면 index.md·original.md를 자동 참조.
    파일을 직접 지정할 경우 ORIGINAL도 함께 입력.
    """
    from validators.reporter import run_validator

    target_path = Path(target)

    if target_path.is_dir():
        translated_path = target_path / "index.md"
        original_path = target_path / "original.md"
    else:
        translated_path = target_path
        original_path = Path(original) if original else None

    if not translated_path.exists():
        raise click.ClickException(f"번역 파일을 찾을 수 없습니다: {translated_path}")
    if not original_path or not original_path.exists():
        raise click.ClickException(f"원문 파일을 찾을 수 없습니다: {original_path}")

    click.echo(f"검증 중: {translated_path}")

    report = run_validator(
        translated_path,
        original_path,
        threshold=threshold,
        nltk_only=nltk_only,
        skip_short=skip_short,
        report_dir=None if no_report else report_dir,
    )

    summary = report["summary"]
    click.echo(f"\n총 단락       : {summary['total_paragraphs']}")
    click.echo(f"nltk 플래그   : {summary['nltk_flagged']}")
    click.echo(f"확인된 이슈   : {summary['llm_confirmed_issues']}")

    if report["issues"]:
        click.echo("\n이슈 목록:")
        for issue in report["issues"]:
            desc = issue.get("issue_description") or "문제 감지됨"
            click.echo(f"  [단락 {issue['paragraph_index']}] {desc}")
            if issue.get("suggestion"):
                click.echo(f"    → 제안: {issue['suggestion']}")

    if not no_report and "report_path" in report:
        click.echo(f"\n리포트 저장: {report['report_path']}")


if __name__ == "__main__":
    validate()
