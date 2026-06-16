#!/usr/bin/env python3
"""
src/content/docs/ 配下のMarkdownファイルのfrontmatter sidebar.badge を、
git diff結果に基づいて更新する。

ルール:
  - sidebar.badge.text: info → スキップ（保護）
  - 追加(A) → sidebar.badge: {text: 新規, variant: tip}
  - 変更(M) → sidebar.badge: {text: 更新, variant: note}
  - diff対象外 → sidebar.badge を削除
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Tuple

DOC_PATH = "src/content/docs/"


def get_diff_files(repo_root: Path) -> Tuple[set, set]:
    """git diff HEAD で追加(A)/変更(M)されたdocs配下のファイルパスを返す。"""
    added, modified = set(), set()

    for cmd in [
        ["git", "diff", "HEAD", "--name-status", "--diff-filter=AM", "--", DOC_PATH],
        ["git", "diff", "--cached", "--name-status", "--diff-filter=AM", "--", DOC_PATH],
    ]:
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=repo_root)
        for line in result.stdout.splitlines():
            parts = line.split("\t", 1)
            if len(parts) == 2:
                status, path = parts
                if status.startswith("A"):
                    added.add(path)
                elif status.startswith("M"):
                    modified.add(path)

    # 未追跡ファイル（git addされていない新規ファイル）も追加扱いにする
    result_untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard", "--", DOC_PATH],
        capture_output=True, text=True, cwd=repo_root
    )
    for path in result_untracked.stdout.splitlines():
        if path.strip():
            added.add(path.strip())

    return added, modified


def split_frontmatter(content: str) -> Tuple[Optional[List[str]], str]:
    """
    frontmatterをパースして行リストとbodyを返す。
    Returns: (fm_lines, body) or (None, content)
    fm_lines は --- を含まない行のリスト（末尾改行なし）。
    """
    if not content.startswith("---"):
        return None, content
    end = content.find("\n---", 3)
    if end == -1:
        return None, content
    fm_text = content[3:end]
    body = content[end + 4:]
    fm_lines = fm_text.split("\n")
    # 先頭の空行を除く
    if fm_lines and fm_lines[0] == "":
        fm_lines = fm_lines[1:]
    return fm_lines, body


def get_indent(line: str) -> int:
    return len(line) - len(line.lstrip())


def get_badge_text_from_lines(fm_lines: List[str]) -> Optional[str]:
    """
    sidebar.badge.text の値を取得する。
    sidebar: → badge: → text: の順にネストを辿る。
    """
    in_sidebar = False
    in_badge = False
    sidebar_indent = -1
    badge_indent = -1

    for line in fm_lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        indent = get_indent(line)
        key = stripped.split(":", 1)[0].strip()

        if not in_sidebar:
            if key == "sidebar" and indent == 0:
                in_sidebar = True
                sidebar_indent = indent
            continue

        # sidebar ブロックを抜けた
        if indent <= sidebar_indent and key != "sidebar":
            break

        if not in_badge:
            if key == "badge" and indent > sidebar_indent:
                in_badge = True
                badge_indent = indent
            continue

        # badge ブロックを抜けた
        if indent <= badge_indent:
            break

        if key == "text":
            val = stripped.split(":", 1)[1].strip()
            # コメントを除去
            val = val.split("#")[0].strip()
            return val

    return None


def rebuild_frontmatter(fm_lines: List[str], new_badge: Optional[str], new_variant: Optional[str]) -> List[str]:
    """
    frontmatterの行リストを受け取り、sidebar.badge を差し替えた新しい行リストを返す。

    - new_badge が None の場合は badge ブロックを削除する
    - new_badge が文字列の場合は badge ブロックを新しい内容で置き換える（なければ追加）
    """
    result: List[str] = []
    i = 0

    in_sidebar = False
    sidebar_indent = -1

    while i < len(fm_lines):
        line = fm_lines[i]
        stripped = line.strip()

        if not stripped or stripped.startswith("#"):
            result.append(line)
            i += 1
            continue

        indent = get_indent(line)
        key = stripped.split(":", 1)[0].strip()

        # sidebar ブロックに入る
        if key == "sidebar" and indent == 0 and not in_sidebar:
            in_sidebar = True
            sidebar_indent = 0
            result.append(line)
            i += 1

            # sidebar の子要素を処理
            while i < len(fm_lines):
                child_line = fm_lines[i]
                child_stripped = child_line.strip()

                if not child_stripped or child_stripped.startswith("#"):
                    # コメント行はスキップ（badge に属するコメントも削除）
                    i += 1
                    continue

                child_indent = get_indent(child_line)
                if child_indent <= sidebar_indent:
                    # sidebar ブロック終了
                    break

                child_key = child_stripped.split(":", 1)[0].strip()

                if child_key == "badge":
                    # badge ブロックを丸ごとスキップ
                    badge_block_indent = child_indent
                    i += 1
                    while i < len(fm_lines):
                        next_line = fm_lines[i]
                        next_stripped = next_line.strip()
                        if not next_stripped or next_stripped.startswith("#"):
                            i += 1
                            continue
                        next_indent = get_indent(next_line)
                        if next_indent <= badge_block_indent:
                            break
                        i += 1
                else:
                    result.append(child_line)
                    i += 1

            # badge を挿入（削除でない場合）
            if new_badge is not None:
                result.append(f"  badge:")
                result.append(f"    text: {new_badge}")
                result.append(f"    variant: {new_variant}")
            else:
                # badge のみで sidebar の内容が空になった場合は sidebar: 行自体も削除
                # result の末尾に "sidebar:" が残っていれば取り除く
                if result and result[-1].rstrip() == "sidebar:":
                    result.pop()

            in_sidebar = False
            continue

        result.append(line)
        i += 1

    # sidebar ブロック自体がなかった場合に badge を追加
    if new_badge is not None and not in_sidebar and sidebar_indent == -1:
        result.append("sidebar:")
        result.append(f"  badge:")
        result.append(f"    text: {new_badge}")
        result.append(f"    variant: {new_variant}")

    return result


def process_file(
    filepath: Path,
    repo_root: Path,
    added: set,
    modified: set,
) -> Optional[str]:
    """
    ファイルのbadgeを更新する。
    Returns: "新規" / "更新" / "クリア" / "スキップ(info)" / None（変更なし）
    """
    rel_path = str(filepath.relative_to(repo_root))
    content = filepath.read_text(encoding="utf-8")

    fm_lines, body = split_frontmatter(content)
    if fm_lines is None:
        return None

    # info バッジは保護
    current_text = get_badge_text_from_lines(fm_lines)
    if current_text and current_text.lower() == "info":
        return "スキップ(info)"

    # 付与するバッジを決定
    if rel_path in added:
        new_text, new_variant, action = "新規", "tip", "新規"
    elif rel_path in modified:
        new_text, new_variant, action = "更新", "note", "更新"
    else:
        new_text, new_variant, action = None, None, "クリア"

    # 変更不要なら何もしない
    if action == "クリア" and current_text is None:
        return None
    if action != "クリア" and current_text == new_text:
        return None

    new_fm_lines = rebuild_frontmatter(fm_lines, new_text, new_variant)
    new_content = "---\n" + "\n".join(new_fm_lines) + "\n---" + body
    filepath.write_text(new_content, encoding="utf-8")

    return action


def main():
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print("エラー: gitリポジトリが見つかりません", file=sys.stderr)
        sys.exit(1)

    repo_root = Path(result.stdout.strip())
    doc_dir = repo_root / DOC_PATH

    if not doc_dir.exists():
        print(f"エラー: {doc_dir} が存在しません", file=sys.stderr)
        sys.exit(1)

    added, modified = get_diff_files(repo_root)

    counts = {"新規": 0, "更新": 0, "クリア": 0, "スキップ(info)": 0}
    results = []

    for md_file in sorted(doc_dir.rglob("*.md")):
        action = process_file(md_file, repo_root, added, modified)
        if action:
            rel = md_file.relative_to(repo_root)
            results.append((rel, action))
            if action in counts:
                counts[action] += 1

    print("=== バッジ更新結果 ===")
    for rel, action in results:
        print(f"  [{action}] {rel}")
    print()
    print(
        f"新規: {counts['新規']} 件 / 更新: {counts['更新']} 件 / "
        f"クリア: {counts['クリア']} 件 / info保護スキップ: {counts['スキップ(info)']} 件"
    )
    if not results:
        print("変更対象なし（全ファイルのバッジは既に最新）")


if __name__ == "__main__":
    main()
