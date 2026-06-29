from datetime import date


def blocks_to_markdown(title: str, blocks: list, url: str) -> str:
    today = date.today().strftime("%Y-%m-%d")
    lines = [
        f"# {title}",
        "",
        f"> 원문: [{title}]({url})  ",
        f"> 번역일: {today}",
        "",
        "---",
        "",
    ]

    for block in blocks:
        btype = block["type"]
        text = block.get("translated", block.get("text", ""))

        if btype == "subtitle":
            lines += [f"**{text}**", ""]

        elif btype == "heading":
            prefix = "#" * block["level"]
            lines += [f"{prefix} {text}", ""]

        elif btype == "paragraph":
            lines += [text, ""]

        elif btype == "code":
            lang = block.get("lang", "")
            lines += [f"```{lang}", block["text"].rstrip(), "```", ""]

        elif btype == "blockquote":
            for line in text.splitlines():
                lines.append(f"> {line}")
            lines.append("")

        elif btype == "list":
            items = block.get("translated_items", block.get("items", []))
            for item in items:
                lines.append(f"- {item}")
            lines.append("")

        elif btype == "image":
            src = block.get("local_path", block["src"])
            alt = block.get("alt", "")
            lines += [f"![{alt}]({src})", ""]

    return "\n".join(lines)
