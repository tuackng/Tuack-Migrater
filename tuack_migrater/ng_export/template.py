import re
import os
import json
from . import info

SECTION_MAP = {
    'description': '题目描述',
    'background': '题目背景',
    'input format': '输入格式',
    'output format': '输出格式',
    'sample': '样例',
    'sample input': '样例输入',
    'sample output': '样例输出',
    'sample explanation': '样例解释',
    'data range': '数据范围',
    'constraints': '数据范围',
    'pre': '预测试数据',
    'hint': '提示',
    'note': '提示',
    'title': '',
}

SECTION_RE = re.compile(r"""
    \{\{\s*s\(['\"]([^'\"]+)['\"](?:,\s*(\d+))?\)\s*\}\}
""", re.VERBOSE)

def replace_section(m):
    name = m.group(1)
    num = m.group(2)
    if name in SECTION_MAP:
        label = SECTION_MAP[name]
        if label:
            if num:
                return f'## {label} {num}'
            return f'## {label}'
    return m.group(0)

FILE_CALL_RE = re.compile(r"""
    \{\{\s*(?:file_name|down_file)\s*\(\s*['"]?(\d+)\.(in|ans)['"]?\s*\)\s*\}\}
""", re.VERBOSE)

def replace_file_call(m):
    return "<!-- " + m.group(0) + " -->"

TBL_RE = re.compile(r"""
    \{\{\s*tbl\s*\(\s*['"]([^'"]+)['"]\s*(?:,\s*[^)]*)?\)\s*\}\}
""", re.VERBOSE)

def replace_tbl(m):
    table_name = m.group(1)
    return "{{" + f' statement.table("tables/{table_name}.lua") ' + "}}"

IMG_RE = re.compile(r"""
    \{\{\s*img\s*\(\s*['"]([^'"]+)['"]\s*(.*?)\s*\)\s*\}\}
""", re.VERBOSE)

def replace_img(m):
    src = m.group(1)
    args_str = m.group(2).strip()
    base = f"![{src}](img/{src})"

    if not args_str:
        return base

    size_m = re.search(r"""size\s*=\s*['"]?([\d.]+)['"]?""", args_str)
    width_m = re.search(r"""width\s*=\s*['"]?([\d.]+)(\w*)['"]?""", args_str)
    height_m = re.search(r"""height\s*=\s*['"]?([\d.]+)(\w*)['"]?""", args_str)

    if size_m:
        try:
            pct = float(size_m.group(1)) * 100
            if pct == int(pct):
                return base + "{" + f"width={int(pct)}%" + "}"
            return base + "{" + f"width={pct}%" + "}"
        except ValueError:
            return base
    elif width_m:
        val, unit = width_m.group(1), width_m.group(2) or ''
        if unit in ('pt', 'mm', 'cm', 'in', 'em', '%'):
            return base + "{" + f"width={val}{unit}" + "}"
    elif height_m:
        val, unit = height_m.group(1), height_m.group(2) or ''
        if unit in ('pt', 'mm', 'cm', 'in', 'em', '%'):
            return base + "{" + f"height={val}{unit}" + "}"

    return m.group(0)

GETTEXT_RE = re.compile(r"""
    \{\{\s*_\s*\(\s*['"]([^'"]+)['"]\s*\)\s*\}\}
""", re.VERBOSE)

def replace_gettext(m):
    return m.group(1)

VARIABLE_MAP = [
    (re.compile(r"\bprob\b"), "problem"),
]

def convert_variable_name(text):
    for pat, repl in VARIABLE_MAP:
        text = pat.sub(repl, text)
    return text

# tuack fields → tuack-ng fields
_FIELD_MAP = {
    'time limit': 'time limit',
    'memory limit': 'memory limit',
    'type': 'type',
    'name': 'name',
    'title': 'title',
    'args': 'args',
    'data': 'data',
    'samples': 'samples',
}

def convert_field_access(text):
    ng_access = re.compile(r"""\bproblem\s*\[\s*['"]([^'"]+)['"]\s*\]""")
    unknown_fields = []
    def replace_acc(m):
        field = m.group(1)
        if field in _FIELD_MAP:
            return f'problem["{_FIELD_MAP[field]}"]'
        unknown_fields.append(field)
        return f'<!-- problem["{field}"] -->'
    result = ng_access.sub(replace_acc, text)
    return result, unknown_fields

def convert_tr(text):
    tr_re = re.compile(r"""\.tr\s*\(\s*['"]([^'"]+)['"]\s*\)""")
    tr_field_other = None
    def replace_tr(m):
        nonlocal tr_field_other
        field = m.group(1)
        if field in _FIELD_MAP:
            mapped = _FIELD_MAP[field]
            return f'["{mapped}"]'
        tr_field_other = field
        return '<!-- .tr(...) -->'
    result = tr_re.sub(replace_tr, text)
    return result, tr_field_other

SELF_TITLE_RE = re.compile(r"""
    \{\{\s*self\.title\(\)\s*\}\}
""", re.VERBOSE)

SELF_INPUT_RE = re.compile(r"""
    \{\{\s*self\.input_file\(\)\s*\}\}
""", re.VERBOSE)

SELF_OUTPUT_RE = re.compile(r"""
    \{\{\s*self\.output_file\(\)\s*\}\}
""", re.VERBOSE)

SAMPLE_TEXT_RE = re.compile(r"""
    \{\{\s*s\('sample',\s*(\d+)\)\s*\}\}\s*\n\s*
    \{\{\s*self\.sample_text\(\)\s*\}\}
""", re.VERBOSE)

SAMPLE_FILE_RE = re.compile(r"""
    \{\{\s*s\('sample',\s*(\d+)\)\s*\}\}\s*\n\s*
    \{\{\s*self\.sample_file\(\)\s*\}\}
""", re.VERBOSE)

OTHER_SELF_RE = re.compile(r"""
    \{\{\s*self\.(\w+)\(\)\s*\}\}
""", re.VERBOSE)

def convert_statement(src_path, dst_path):
    info.add_item(info.STATUS_OK, f"题面：{os.path.basename(src_path)}")

    with open(src_path, 'r', encoding='utf-8') as f:
        content = f.read()

    original_content = content

    self_title_count = len(SELF_TITLE_RE.findall(content))
    content = SELF_TITLE_RE.sub('', content)

    sample_text_count = len(SAMPLE_TEXT_RE.findall(content))
    content = SAMPLE_TEXT_RE.sub(r'{{ sample.text(\1) }}', content)

    sample_file_count = len(SAMPLE_FILE_RE.findall(content))
    content = SAMPLE_FILE_RE.sub(r'## 样例 \1\n\n{{ sample.file(\1) }}', content)

    content = SELF_INPUT_RE.sub('{{ s.input_file() }}', content)
    content = SELF_OUTPUT_RE.sub('{{ s.output_file() }}', content)

    other_self_matches = OTHER_SELF_RE.findall(content)
    content = OTHER_SELF_RE.sub(lambda m: f'<!-- {{{{ self.{m.group(1)}() }}}} -->', content)

    section_count = len(SECTION_RE.findall(content))
    content = SECTION_RE.sub(replace_section, content)

    file_count = len(FILE_CALL_RE.findall(content))
    content = FILE_CALL_RE.sub(replace_file_call, content)

    tbl_count = len(TBL_RE.findall(content))
    content = TBL_RE.sub(replace_tbl, content)

    img_count = 0
    img_unrecognized = 0
    def img_handler(m):
        nonlocal img_count, img_unrecognized
        result = replace_img(m)
        if result == m.group(0):
            img_unrecognized += 1
        else:
            img_count += 1
        return result
    content = IMG_RE.sub(img_handler, content)

    gettext_count = len(GETTEXT_RE.findall(content))
    content = GETTEXT_RE.sub(replace_gettext, content)

    content = convert_variable_name(content)
    content, field_unknowns = convert_field_access(content)
    content, tr_field_other = convert_tr(content)

    has_control_flow = '{%' in content and '%}' in content
    has_render = 'render(' in content and ')' in content
    has_get = '.get(' in content

    if has_control_flow:
        info.add_warning("题面包含 {% %} 控制流，请自行检查正确性")

    if has_render:
        info.add_warning("{{ render(...) }} 已保留原样")

    if has_get:
        info.add_warning("{{ .get(...) }} 已保留原样，需手动改用 default 过滤器")

    if tbl_count > 0:
        info.add_warning(f"检测到 {tbl_count} 个 {{ tbl() }} 调用，已替换为 Lua 路径，但您需要手动迁移表格文件")

    if img_unrecognized > 0:
        info.add_warning(f"存在 {img_unrecognized} 个 {{ img(...) }} 参数无法识别")

    if tr_field_other:
        info.add_warning(f".tr('{tr_field_other}') 无法转换，已注释")
    if field_unknowns:
        info.add_warning(f"无法识别的字段访问：{', '.join(field_unknowns)}，已注释")
    if other_self_matches:
        info.add_warning(f"存在无法识别的 self 调用，已注释")

    with open(dst_path, 'w', encoding='utf-8') as f:
        f.write(content)

    parts = []
    if section_count:
        parts.append(f"{section_count} sections")
    if file_count:
        parts.append(f"{file_count} samples")
    if tbl_count:
        parts.append(f"{tbl_count} tables")
    if img_count:
        parts.append(f"{img_count} images")
    if gettext_count:
        parts.append(f"{gettext_count} translations")
    if self_title_count:
        parts.append(f"{self_title_count} self.title() removed")
    if sample_text_count:
        parts.append(f"{sample_text_count} sample.text()")
    if sample_file_count:
        parts.append(f"{sample_file_count} sample.file()")

    info.add_item(info.STATUS_OK,
                  f"-> statement.md ({os.path.basename(dst_path)})" +
                  (f" [{', '.join(parts)}]" if parts else ""))

    return content
