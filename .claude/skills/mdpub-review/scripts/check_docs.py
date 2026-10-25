#!/usr/bin/env python3
"""
src/content/docs/ 配下の Markdown を機械的にチェックする。
モデルに判断させず、毎回同じ結果が出るべき項目だけを扱う。

使い方:
  python3 check_docs.py                 # base ブランチとの差分で追加/変更された docs を対象にする
  python3 check_docs.py --base origin/main
  python3 check_docs.py path/to/a.md ...

チェック内容:
  [error]   frontmatter がない、または title / description がない
  [error]   sidebar.badge.text が 新規 / 更新 / info 以外
  [error]   地の文にダッシュ（— U+2014、― U+2015）がある
  [error]   太字（**）が CommonMark の規則で閉じない、または開かない
  [warning] 地の文に中黒（・）がある（固有名詞の内部なら許容されるため warning）

error が 1 件でもあれば終了コード 1 を返す。
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import unicodedata
from pathlib import Path
from typing import List, Optional, Tuple

DOC_PATH = "src/content/docs/"
ALLOWED_BADGES = {"新規", "更新", "info"}
DASHES = {"—": "em ダッシュ（—）", "―": "horizontal bar（―）"}

Finding = Tuple[str, str, int, str]  # (level, path, line, message)


def changed_docs(base: str, repo_root: Path) -> List[str]:
    """base との差分（コミット済み＋作業ツリー＋未追跡）で追加/変更された docs 配下の md を返す。"""
    paths = set()
    cmds = [
        ["git", "diff", "--name-only", "--diff-filter=AM", f"{base}...HEAD", "--", DOC_PATH],
        ["git", "diff", "--name-only", "--diff-filter=AM", "HEAD", "--", DOC_PATH],
        ["git", "ls-files", "--others", "--exclude-standard", "--", DOC_PATH],
    ]
    for cmd in cmds:
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=repo_root)
        if result.returncode != 0:
            sys.exit(f"git コマンドが失敗しました: {' '.join(cmd)}\n{result.stderr}")
        paths.update(p.strip() for p in result.stdout.splitlines() if p.strip())
    return sorted(p for p in paths if p.endswith((".md", ".mdx")))


def split_frontmatter(lines: List[str]) -> Tuple[Optional[List[str]], int]:
    """frontmatter の行リストと、本文の開始行（0 始まり）を返す。"""
    if not lines or lines[0].strip() != "---":
        return None, 0
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return lines[1:i], i + 1
    return None, 0


def badge_text(fm: List[str]) -> Optional[str]:
    """sidebar.badge の text を返す（文字列形式の badge にも対応）。"""
    in_sidebar = in_badge = False
    for line in fm:
        stripped = line.strip()
        indent = len(line) - len(line.lstrip())
        if indent == 0:
            in_sidebar = stripped.startswith("sidebar:")
            in_badge = False
            continue
        if in_sidebar and stripped.startswith("badge:"):
            value = stripped[len("badge:"):].strip()
            if value:
                return value.strip("'\"")
            in_badge = True
            continue
        if in_badge and stripped.startswith("text:"):
            return stripped[len("text:"):].strip().strip("'\"")
    return None


def check_frontmatter(path: str, fm: Optional[List[str]]) -> List[Finding]:
    if fm is None:
        return [("error", path, 1, "frontmatter がありません")]
    findings: List[Finding] = []
    keys = {line.split(":", 1)[0] for line in fm if line and not line[0].isspace() and ":" in line}
    for key in ("title", "description"):
        if key not in keys:
            findings.append(("error", path, 1, f"frontmatter に {key} がありません"))
    text = badge_text(fm)
    if text is not None and text not in ALLOWED_BADGES:
        findings.append(("error", path, 1, f"badge「{text}」は {sorted(ALLOWED_BADGES)} のいずれでもありません"))
    return findings


def is_punct(ch: str) -> bool:
    """CommonMark の「Unicode 句読点」に相当する判定（P* と S*）。"""
    return unicodedata.category(ch)[0] in ("P", "S")


def is_space(ch: str) -> bool:
    return ch == "" or ch.isspace()


def mask_code_and_urls(line: str) -> str:
    """インラインコードの中身とリンク先 URL を x で塗る（長さと、両端の ` や ] は保つ）。

    両端を残すのは、** の flanking 判定が隣の文字（` など）に依存するため。
    """
    line = re.sub(r"(`+)([^`]*)(\1)", lambda m: m.group(1) + "x" * len(m.group(2)) + m.group(3), line)
    return re.sub(r"\]\(([^)]*)\)", lambda m: "](" + "x" * len(m.group(1)) + ")", line)


def is_japanese(ch: str) -> bool:
    """かな、漢字、全角記号などの日本語の文字か。"""
    return bool(ch) and (
        "\u3000" <= ch <= "\u30ff" or "\u3400" <= ch <= "\u9fff" or "\uff00" <= ch <= "\uffef"
    )


def dash_in_japanese(line: str, ch: str) -> bool:
    """ダッシュの前後（空白を除く）のどちらかが日本語の文字なら True。英語の書誌情報は対象外にする。"""
    for m in re.finditer(re.escape(ch) + "+", line):
        before = line[:m.start()].rstrip()[-1:]
        after = line[m.end():].lstrip()[:1]
        if is_japanese(before) or is_japanese(after):
            return True
    return False


def check_bold(path: str, lineno: int, line: str) -> List[Finding]:
    """** の区切りを CommonMark の left/right-flanking 規則で対応づけ、崩れるものを報告する。"""
    findings: List[Finding] = []
    opener: Optional[int] = None
    for m in re.finditer(r"(?<!\*)\*\*(?!\*)", line):
        start, end = m.start(), m.end()
        before = line[start - 1] if start > 0 else ""
        after = line[end] if end < len(line) else ""
        left = not is_space(after) and (not is_punct(after) or is_space(before) or is_punct(before))
        right = not is_space(before) and (not is_punct(before) or is_space(after) or is_punct(after))
        if opener is not None and right:
            opener = None
        elif opener is not None:
            # 閉じるはずの ** が right-flanking にならず、新しい開きとして扱われる典型
            context = line[opener:end + 4].strip()
            findings.append(("error", path, lineno, f"「{context}」の ** が閉じません（全角括弧などの直後に閉じ ** を置いていないか）"))
            opener = None
        elif left:
            opener = start
        else:
            context = line[max(0, start - 8):end + 8].strip()
            findings.append(("error", path, lineno, f"「{context}」の ** が太字として解釈されません"))
    if opener is not None:
        context = line[opener:opener + 20].strip()
        findings.append(("error", path, lineno, f"「{context}…」の ** が閉じません（全角括弧の直後に閉じ ** を置いていないか）"))
    return findings


def check_body(path: str, lines: List[str], body_start: int) -> List[Finding]:
    findings: List[Finding] = []
    in_code = False
    for i in range(body_start, len(lines)):
        raw = lines[i]
        lineno = i + 1
        if raw.lstrip().startswith(("```", "~~~")):
            in_code = not in_code
            continue
        if in_code:
            continue
        line = mask_code_and_urls(raw)
        for ch, name in DASHES.items():
            if dash_in_japanese(line, ch):
                findings.append(("error", path, lineno, f"{name} があります。括弧か句点で書き換えてください"))
        if "・" in line:
            findings.append(("warning", path, lineno, "中黒（・）があります。固有名詞の内部でなければ読点などに"))
        findings.extend(check_bold(path, lineno, line))
    return findings


def check_file(path: str, repo_root: Path) -> List[Finding]:
    text = (repo_root / path).read_text(encoding="utf-8")
    lines = text.split("\n")
    fm, body_start = split_frontmatter(lines)
    return check_frontmatter(path, fm) + check_body(path, lines, body_start)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("files", nargs="*", help="チェックするファイル（省略時は base との差分）")
    parser.add_argument("--base", default="origin/main", help="差分の基準（既定: origin/main）")
    args = parser.parse_args()

    repo_root = Path(
        subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True).stdout.strip() or "."
    )
    targets = args.files or changed_docs(args.base, repo_root)
    if not targets:
        print("チェック対象の docs はありません")
        return 0

    findings: List[Finding] = []
    for path in targets:
        findings.extend(check_file(path, repo_root))

    print("=== 機械チェック結果 ===")
    print("対象: " + ", ".join(targets))
    for level, path, lineno, message in findings:
        print(f"  [{level}] {path}:{lineno} {message}")
    errors = sum(1 for f in findings if f[0] == "error")
    warnings = len(findings) - errors
    print(f"\nerror: {errors} 件 / warning: {warnings} 件")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
