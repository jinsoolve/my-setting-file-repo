#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CLion Live Templates XML -> VS Code cpp.json 변환기 (+ 설정 파일/최신 버전 탐색/번호 선택 지원)
- 최근 설정 파일을 우선 적용, 없으면 JetBrains 디렉터리에서 최신 CLion 버전 자동 선택
- confirm에서 'latest' 옵션 지원
- 'no'를 고르면 JetBrains의 CLion 버전 목록을 번호로 고를 수 있음(수동입력 m, 재검색 r, 취소 Enter)
"""

import json
import re
import html
import sys
import pathlib
import xml.etree.ElementTree as ET
from typing import Tuple, Dict, List, Optional

# ---------- 상수 설정 ----------

# 실행 중인 스크립트 파일이 위치한 디렉터리 기준 (설정 파일 저장용)
try:
    SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
except NameError:
    SCRIPT_DIR = pathlib.Path.cwd()

SETTINGS_PATH = SCRIPT_DIR / ".settings-converter-xml-to-json.json"

# JetBrains 기본 설치 디렉터리
JETBRAINS_DIR = pathlib.Path("~/Library/Application Support/JetBrains").expanduser()

# CLion 기본 템플릿 파일명
CLION_TEMPLATE_FILE = "templates/C_C__.xml"

# VS Code cpp.json 출력 경로
VSCODE_SNIPPET_PATH = pathlib.Path(
    "~/Library/Application Support/Code/User/snippets/cpp.json"
).expanduser()


# ---------- 경로 헬퍼 ----------
def make_input_path(version: str) -> pathlib.Path:
    """버전 문자열(YYYY.X)로 CLion 템플릿 XML의 전체 경로 생성"""
    return (JETBRAINS_DIR / f"CLion{version}" / CLION_TEMPLATE_FILE).expanduser()


def resolve_initial_version() -> str:
    """
    1) 설정 파일에 저장된 버전이 있으면 그걸 사용
    2) 없으면 JetBrains 폴더를 스캔해 latest 사용 (저장도 함께)
    3) latest가 없으면 사용자에게 수동 입력을 받아 사용 (저장도 함께)
    """
    settings = load_settings()
    if "clion_version" in settings:
        return settings["clion_version"]

    # 최신 스캔
    latest = pick_latest_version(find_clion_versions(JETBRAINS_DIR))
    if latest:
        settings["clion_version"] = latest
        save_settings(settings)
        print(f"[INFO] 최근 설정이 없어 최신 버전({latest})을 자동 선택했습니다.")
        return latest

    # JetBrains 폴더에서 찾지 못하면 수동 입력
    print("[WARN] JetBrains 디렉터리에서 CLion 버전을 찾지 못했습니다.")
    while True:
        manual = input(
            "CLion 버전을 수동 입력하세요 (예: 2026.2, 취소=Enter): "
        ).strip()
        if not manual:
            print("작업 취소됨.")
            sys.exit(0)
        if re.fullmatch(r"\d{4}\.\d+", manual):
            settings["clion_version"] = manual
            save_settings(settings)
            return manual
        print("⚠️ 형식 오류: YYYY.X 형태로 입력해주세요 (예: 2026.2)")


# ---------- 변환 로직 ----------


def convert_placeholders(text: str, enable_variable_conversion: bool = True) -> str:
    s = text.replace("$END$", "$0").replace("$SELECTION$", "$TM_SELECTED_TEXT")
    if not enable_variable_conversion:
        return s
    order: Dict[str, int] = {}

    def repl(m):
        var = m.group(1)
        if var in ("END", "SELECTION"):
            return m.group(0)
        if var not in order:
            order[var] = len(order) + 1
        return f"${{{order[var]}:{var}}}"

    return re.sub(r"\$(\w+)\$", repl, s)


def to_body_lines(value: str) -> List[str]:
    unescaped = html.unescape(value)
    normalized = unescaped.replace("\r\n", "\n").replace("\r", "\n")
    return normalized.split("\n")


def template_to_snippet(
    t: ET.Element, variable_conversion: bool = True
) -> Tuple[str, Dict]:
    name = t.attrib.get("name", "").strip()
    value = t.attrib.get("value", "")
    desc = t.attrib.get("description", "")
    if not name:
        raise ValueError("<template> missing name attribute")
    value = convert_placeholders(value, enable_variable_conversion=variable_conversion)
    body = to_body_lines(value)
    return name, {"prefix": name, "description": desc or name, "body": body}


def parse_templates(
    xml_path: pathlib.Path, variable_conversion: bool = True
) -> Dict[str, Dict]:
    tree = ET.parse(xml_path)
    root = tree.getroot()
    snippets: Dict[str, Dict] = {}
    for t in root.findall(".//template"):
        key, snip = template_to_snippet(t, variable_conversion)
        snippets[key] = snip
    return snippets


# ---------- 설정 파일 / 버전 탐색 ----------


def load_settings() -> Dict:
    if SETTINGS_PATH.exists():
        try:
            return json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_settings(d: Dict) -> None:
    try:
        SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        SETTINGS_PATH.write_text(
            json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception as e:
        print(f"[WARN] 설정 저장 실패: {e}", file=sys.stderr)


def find_clion_versions(
    base: pathlib.Path = JETBRAINS_DIR,
) -> List[Tuple[str, pathlib.Path]]:
    """
    base에서 'CLionYYYY.X' 폴더 탐색 → [('YYYY.X', path), ...]
    """
    results: List[Tuple[str, pathlib.Path]] = []
    if not base.exists():
        return results
    pat = re.compile(r"^CLion(\d{4})\.(\d+)$")
    for child in base.iterdir():
        if child.is_dir():
            m = pat.match(child.name)
            if m:
                ver = f"{m.group(1)}.{m.group(2)}"
                results.append((ver, child))
    return results


def sort_versions_desc(
    versions: List[Tuple[str, pathlib.Path]],
) -> List[Tuple[str, pathlib.Path]]:
    def keyf(vs: Tuple[str, pathlib.Path]):
        y, _, minor = vs[0].partition(".")
        return (int(y), int(minor) if minor.isdigit() else 0)

    return sorted(versions, key=keyf, reverse=True)


def pick_latest_version(versions: List[Tuple[str, pathlib.Path]]) -> Optional[str]:
    if not versions:
        return None
    return sort_versions_desc(versions)[0][0]


def extract_clion_version_from_path(p: pathlib.Path) -> Tuple[str, re.Match]:
    m = re.search(r"(CLion)(\d{4}\.\d+)", str(p))
    if not m:
        raise ValueError("경로에서 'CLionYYYY.X' 패턴을 찾지 못했습니다.")
    return m.group(2), m


def replace_clion_version_in_path(
    p: pathlib.Path, new_version: str, match_obj: re.Match
) -> pathlib.Path:
    prefix = match_obj.group(1)  # 'CLion'
    old = prefix + match_obj.group(2)
    new = prefix + new_version
    return pathlib.Path(str(p).replace(old, new, 1))


# ---------- 번호 선택 유틸 ----------


def choose_version_interactively(
    base_input_path: pathlib.Path, m: re.Match
) -> Optional[pathlib.Path]:
    """
    JetBrains에서 버전을 스캔해 번호로 고르게 한다.
    - 숫자: 해당 버전 선택
    - m: 수동으로 YYYY.X 입력
    - r: 재검색
    - Enter: 취소(프로그램 종료)
    선택되면 새 경로(Path) 반환. 선택/입력 취소 시 None.
    """
    while True:
        found = sort_versions_desc(find_clion_versions(JETBRAINS_DIR))
        if not found:
            print("[WARN] JetBrains 디렉터리에서 CLion 버전을 찾지 못했습니다.")
            # 수동 입력만 허용
            manual = input("수동 입력(YYYY.X) 또는 Enter로 취소: ").strip()
            if not manual:
                return None
            if re.fullmatch(r"\d{4}\.\d+", manual):
                return replace_clion_version_in_path(base_input_path, manual, m)
            print("⚠️ 형식 오류: YYYY.X 형태로 입력해주세요.")
            continue

        print("\n[선택 가능한 CLion 버전 목록] (최신 순)")
        for idx, (ver, _path) in enumerate(found, start=1):
            print(f"  {idx}. {ver}")
        print("  m. 수동 입력(YYYY.X)")
        print("  r. 재검색")
        print("  Enter. 취소")

        sel = input("번호를 선택하세요: ").strip().lower()
        if not sel:
            return None
        if sel == "r":
            continue
        if sel == "m":
            manual = input("버전 입력(예: 2026.2): ").strip()
            if re.fullmatch(r"\d{4}\.\d+", manual):
                return replace_clion_version_in_path(base_input_path, manual, m)
            print("⚠️ 형식 오류: YYYY.X 형태로 입력해주세요.")
            continue
        if sel.isdigit():
            num = int(sel)
            if 1 <= num <= len(found):
                ver = found[num - 1][0]
                return replace_clion_version_in_path(base_input_path, ver, m)
            print("⚠️ 범위를 벗어났습니다.")
            continue
        print("⚠️ 잘못된 입력입니다.")


# ---------- confirm (y / n / latest) + 설정 반영 ----------


def confirm_version_and_maybe_adjust_path(
    input_path: pathlib.Path,
    allow_latest: bool = True,
    update_settings_on_change: bool = True,
) -> pathlib.Path:
    version, m = extract_clion_version_from_path(input_path)
    prompt_opts = "y/n" + ("/latest" if allow_latest else "")
    print(f"[INFO] 감지된 CLion 버전: {version}")
    resp = input(f"이 버전으로 진행할까요? ({prompt_opts}) [y]: ").strip().lower()

    # 그대로 진행
    if resp in ("", "y", "yes"):
        return input_path

    # 최신 자동 선택
    if allow_latest and resp == "latest":
        latest = pick_latest_version(find_clion_versions(JETBRAINS_DIR))
        if latest:
            new_path = replace_clion_version_in_path(input_path, latest, m)
            print(f"[INFO] 최신 버전 감지: {latest}")
            print(f"경로를 다음으로 변경합니다:\n{new_path}")
            confirm = input("진행할까요? (y/n) [y]: ").strip().lower()
            if confirm in ("", "y", "yes"):
                if update_settings_on_change:
                    s = load_settings()
                    s["clion_version"] = latest
                    save_settings(s)
                return new_path
        else:
            print(
                "[WARN] JetBrains 디렉터리에서 CLion 버전을 찾지 못했습니다. 번호 선택/수동 입력으로 전환합니다."
            )

    # 번호 선택 또는 수동 입력
    new_path = choose_version_interactively(input_path, m)
    if new_path is None:
        print("작업 취소됨.")
        sys.exit(0)

    print(f"경로를 다음으로 변경합니다:\n{new_path}")
    confirm = input("진행할까요? (y/n) [y]: ").strip().lower()
    if confirm in ("", "y", "yes"):
        if update_settings_on_change:
            try:
                new_ver, _ = extract_clion_version_from_path(new_path)
                s = load_settings()
                s["clion_version"] = new_ver
                save_settings(s)
            except Exception:
                pass
        return new_path

    print("작업 취소됨.")
    sys.exit(0)


# ---------- 메인 ----------


def main():
    # 1) 초기 버전 결정 (설정 → 최신 → 수동)
    initial_version = resolve_initial_version()

    # 2) 버전으로 input_path 구성
    input_path = make_input_path(initial_version)

    # 3) 출력 경로는 상수 사용
    output_path = VSCODE_SNIPPET_PATH

    # 4) confirm (y/n/latest + 번호 선택) — 변경 시 설정 저장까지 내부에서 처리됨
    input_path = confirm_version_and_maybe_adjust_path(
        input_path,
        allow_latest=True,
        update_settings_on_change=True,
    )

    # 존재 확인
    if not input_path.exists():
        try:
            from tkinter import messagebox
            import tkinter as tk

            root = tk.Tk()
            root.withdraw()
            messagebox.showerror(
                "입력 파일 없음", f"입력 파일을 찾을 수 없습니다:\n{input_path}"
            )
            root.destroy()
        except Exception:
            print(
                f"[ERROR] 입력 파일을 찾을 수 없습니다: {input_path}", file=sys.stderr
            )
        sys.exit(1)

    # 변환 실행
    try:
        snippets = parse_templates(input_path, variable_conversion=True)
    except Exception as e:
        print(f"[ERROR] 변환 실패: {e}", file=sys.stderr)
        sys.exit(2)

    # 저장
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(snippets, f, ensure_ascii=False, indent=2)
        print(f"[OK] 스니펫 JSON을 저장했습니다: {output_path}")
    except Exception as e:
        print(f"[ERROR] 출력 쓰기 실패: {e}", file=sys.stderr)
        sys.exit(3)


if __name__ == "__main__":
    main()
