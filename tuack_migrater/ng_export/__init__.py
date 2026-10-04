import os
import sys
import json
import shutil

import questionary
from questionary import Choice

from . import config as ng_config
from . import fs as ng_fs
from . import template as ng_template
from . import info

from ..base import load_json, logger as log

try:
    from ..base import custom_conf
    custom_conf()
except Exception:
    pass

def note(msg):
    log.log("NOTE", msg)

KNOWN_LANGS = {'zh-cn', 'zh', 'en', 'ja', 'ko', 'ru', 'fr', 'de', 'es', 'pt', 'ar', 'vi', 'th'}


def _is_tty():
    return sys.stdin.isatty() and sys.stdout.isatty()


def _ask(question, default):
    if not _interactive and default is not None:
        return default
    result = question.ask()
    if result is None:
        print()
        sys.exit(0)
    return result


def _choose_lang(conf):
    langs = set()

    def collect_langs(obj):
        if hasattr(obj, 'sub'):
            for sub in obj.sub:
                collect_langs(sub)
        if hasattr(obj, 'statement'):
            stmt_dir = os.path.join(obj.path, 'statement')
            if os.path.isdir(stmt_dir):
                for f in os.listdir(stmt_dir):
                    if f.endswith('.md'):
                        lang = f[:-3]
                        if lang in KNOWN_LANGS:
                            langs.add(lang)

    collect_langs(conf)

    if not langs:
        langs.add('zh-cn')

    lang_list = sorted(langs)
    if len(lang_list) == 1:
        log.info(f"语言：{lang_list[0]}")
        return lang_list[0]

    if not _interactive:
        return "zh-cn"

    return _ask(
        questionary.select(
            "选择要迁移的语言",
            choices=[Choice(l, l) for l in lang_list],
            default="zh-cn",
        ),
        "zh-cn"
    ) or "zh-cn"


def _choose_compile(probs):
    compile_set = {}
    for prob in probs:
        comp = dict(prob.get('compile', {}))
        if comp:
            key = json.dumps(comp, sort_keys=True)
            if key not in compile_set:
                compile_set[key] = (comp, prob.get('name', '?'))

    if not compile_set:
        log.info("compile 配置：未检测到")
        return {}

    if len(compile_set) == 1:
        comp, pname = list(compile_set.values())[0]
        log.info(f"compile 配置：使用 {pname} 的配置 ({json.dumps(comp, ensure_ascii=False)})")
        return comp

    if not _interactive:
        comp, pname = list(compile_set.values())[0]
        log.info(f"compile 配置：使用 {pname} 的配置")
        return comp

    choices = []
    for key, (comp, pname) in compile_set.items():
        label = f"{pname}: {', '.join(f'{k}={v}' for k, v in comp.items())}"
        choices.append(Choice(label, comp))
    choices.append(Choice("自定义...", "__custom__"))
    choices.append(Choice("跳过 (留空)", None))

    result = _ask(
        questionary.select(
            "检测到多个不同的 compile 配置。Tuack-NG 不允许为同一比赛日设置不同 compile 配置。使用哪道题的配置？",
            choices=choices,
        ),
        None
    )
    if result == "__custom__":
        result = _ask(
            questionary.text("输入自定义 compile 配置 (JSON 对象，如 {\"cpp\": \"-O2\"})", default="{}"),
            None,
        )
        try:
            result = json.loads(result)
        except (json.JSONDecodeError, TypeError):
            log.warning("compile 配置解析失败，使用默认")
            return {}
    return result or {}


GRADER_PATTERNS = ['grader', 'interactor']
HEADER_PATTERNS = ['grader', 'interactor', 'stub', 'header']


def _find_interactive_files(prob_path, prob_name):
    grader_candidates = []
    header_candidates = []

    if not prob_path or not os.path.isdir(prob_path):
        return grader_candidates, header_candidates

    search_dirs = [prob_path]
    for fname in os.listdir(prob_path):
        fpath = os.path.join(prob_path, fname)
        if os.path.isdir(fpath) and not fname.startswith('.'):
            search_dirs.append(fpath)

    seen = set()
    for d in search_dirs:
        if not os.path.isdir(d):
            continue
        for f in sorted(os.listdir(d)):
            low = f.lower()
            name_no_ext = os.path.splitext(low)[0]
            ext = os.path.splitext(f)[1].lower()
            if ext not in ('.cpp', '.c', '.h', '.hpp', '.pas', '.java'):
                continue
            rel = os.path.relpath(os.path.join(d, f), prob_path)
            if rel in seen:
                continue
            seen.add(rel)
            if ext in ('.cpp', '.c'):
                if name_no_ext == prob_name.lower() or any(p in low for p in GRADER_PATTERNS):
                    grader_candidates.append(rel)
            if ext in ('.h', '.hpp'):
                if name_no_ext == prob_name.lower() or any(p in low for p in HEADER_PATTERNS):
                    header_candidates.append(rel)

    return grader_candidates, header_candidates

def _select_or_custom(prob_name, label, candidates, allow_skip=False):
    choices = []
    if candidates:
        choices = [Choice(c, c) for c in candidates]
    if allow_skip:
        choices.append(Choice("不指定", "__skip__"))
    choices.append(Choice("自定义...", "__custom__"))
    if not candidates and not allow_skip:
        return _ask(
            questionary.path(f"[{prob_name}] {label} 路径", default=""),
            "",
        )
    default = candidates[0] if candidates else None
    choice = _ask(
        questionary.select(f"[{prob_name}] {label}", choices=choices),
        default,
    )
    if choice == "__custom__":
        return _ask(
            questionary.path(f"[{prob_name}] {label} 路径 (自定义)", default=""),
            "",
        )
    if choice == "__skip__":
        return None
    return choice


def _handle_interactive(prob):
    if prob.get('type') != 'interactive':
        return None

    prob_name = prob.get('name', '?')
    prob_path = getattr(prob, 'path', None) or os.path.join(os.getcwd(), prob_name)
    log.info(f"处理交互题：{prob_name}")

    grader_defaults, header_defaults = _find_interactive_files(prob_path, prob_name)

    if not _interactive:
        if grader_defaults and header_defaults:
            log.info(f"交互题 {prob_name}: 使用自动检测的 grader/header")
            return {"grader": grader_defaults[0], "header": header_defaults[0]}
        info.add_warning(f"交互题 grader/header 未配置，interactive 字段留空")
        return None

    note(f"[题目 {prob_name}] 请配置交互信息")

    grader = _select_or_custom(prob_name, "grader", grader_defaults)
    if not grader:
        info.add_warning(f"交互题 grader/header 未配置，interactive 字段留空")
        return None

    header = _select_or_custom(prob_name, "header", header_defaults)

    result = {"grader": grader, "header": header or ''}
    grader_sample = _select_or_custom(prob_name, "样例 grader", grader_defaults, allow_skip=True)
    grader_dmk = _select_or_custom(prob_name, "dmk grader", grader_defaults, allow_skip=True)
    if grader_sample:
        result["sample_grader"] = grader_sample
    if grader_dmk:
        result["dmk_grader"] = grader_dmk
    note(f"交互题 {prob_name}: grader={grader}, header={header}")
    return result


def _migrate_single_problem(v2_prob, prob_rel_path, src_root, dst_root, lang):
    prob_name = v2_prob.get('name', 'unknown')
    info.push(prob_name)
    log.info(f"迁移题目：{prob_name}")
    dst_prob_root = os.path.join(dst_root, prob_rel_path) if prob_rel_path else dst_root
    ng_fs.ensure_dir(dst_prob_root)

    interactive_info = _handle_interactive(v2_prob)

    ng_config_result = ng_config.migrate_problem(v2_prob, os.path.join(src_root, prob_rel_path), lang, interactive_info)
    prob_config, config_samples, down_files = ng_config_result

    ng_fs.migrate_structure(
        os.path.join(src_root, prob_rel_path),
        dst_prob_root,
        config_samples,
        down_files,
        lang,
    )

    stmt_src, stmt_orig = ng_fs.migrate_statement(
        os.path.join(src_root, prob_rel_path),
        dst_prob_root,
        lang,
    )
    if stmt_src:
        stmt_dst = os.path.join(dst_prob_root, 'statement.md')
        ng_template.convert_statement(stmt_src, stmt_dst)

    conf_path = os.path.join(dst_prob_root, 'conf.json')
    with open(conf_path, 'w', encoding='utf-8') as f:
        json.dump(prob_config.model_dump(exclude_none=True, by_alias=True), f, indent=2, ensure_ascii=False)

    info.add_item(info.STATUS_OK, f"conf.json v2→v7")
    info.pop()
    return prob_config


def _migrate_day(v2_day, day_rel_path, src_root, dst_root, lang, compile_config, contest_titles):
    day_name = v2_day.get('name', 'unknown')
    info.push(day_name)
    log.info(f"迁移比赛日：{day_name}")
    dst_day_root = os.path.join(dst_root, day_rel_path)
    ng_fs.ensure_dir(dst_day_root)

    day_title = ng_config.extract_title(v2_day.get('title', {}), lang)

    day_config = ng_config.migrate_day(v2_day, lang, compile_config, {'title': day_title})
    conf_path = os.path.join(dst_day_root, 'conf.json')
    with open(conf_path, 'w', encoding='utf-8') as f:
        json.dump(day_config.model_dump(exclude_none=True, by_alias=True), f, indent=2, ensure_ascii=False)

    ng_fs.migrate_day_structure(
        os.path.join(src_root, day_rel_path),
        dst_day_root,
        lang,
    )

    info.add_item(info.STATUS_OK, f"conf.json v2→v7")

    prob_dirs = v2_day.get('subdir', [])
    probs = list(v2_day.sub) if hasattr(v2_day, 'sub') and v2_day.sub else []
    for prob_dir, prob in zip(prob_dirs, probs):
        _migrate_single_problem(prob, prob_dir, os.path.join(src_root, day_rel_path), dst_day_root, lang)

    info.pop()
    return day_config


_interactive = True


def migrate(src_root, dst_root, force=False):
    global _interactive
    _interactive = _is_tty() and not force

    info.clear()
    info.clear()

    if os.path.exists(dst_root):
        if force:
            shutil.rmtree(dst_root)
        elif _interactive:
            confirm = _ask(
                questionary.confirm(f"目标目录 '{dst_root}' 已存在，覆盖？", default=False),
                None
            )
            if not confirm:
                print("已取消")
                return False
            shutil.rmtree(dst_root)
        else:
            print(f"错误：目标目录 '{dst_root}' 已存在，使用 --force 覆盖")
            return False

    conf = load_json(src_root)
    if not conf:
        log.error("无法加载配置文件")
        return False

    contest_name = conf.get('name', '')
    log.info(f"加载项目：{contest_name} ({conf.folder})")
    log.info(f"开始迁移：{contest_name} ({conf.folder}) → {dst_root}")

    lang = _choose_lang(conf)

    contest_titles = {}
    if conf.folder != 'problem':
        title_src = []
        for k in ('title', 'short title', 'subtitle'):
            v = ng_config.extract_title(conf.get(k, {}), lang)
            if v:
                title_src.append(v)
        title_src = list(dict.fromkeys(title_src))

        def _pick_title(prompt, default):
            if not _interactive or len(title_src) <= 1:
                return default
            choices = [Choice(v, v) for v in title_src]
            choices.append(Choice("自定义...", "__custom__"))
            c = _ask(questionary.select(prompt, choices=choices), default)
            if c == "__custom__":
                c = _ask(questionary.text(prompt, default=default), default) or default
            return c

        contest_titles['title'] = _pick_title(
            f"[{contest_name}] 选择比赛标题用于 NG 的 title",
            title_src[0] if title_src else '',
        )
        contest_titles['short_title'] = _pick_title(
            f"[{contest_name}] 选择比赛标题用于 NG 的 short title",
            title_src[1] if len(title_src) > 1 else (title_src[0] if title_src else ''),
        )

    if conf.folder == 'contest':
        info.push(contest_name)
        ng_fs.ensure_dir(dst_root)
        log.info(f"迁移 contest 配置：{contest_name}")
        contest_config = ng_config.migrate_contest(conf, lang, contest_titles)
        conf_path = os.path.join(dst_root, 'conf.json')
        with open(conf_path, 'w', encoding='utf-8') as f:
            json.dump(contest_config.model_dump(exclude_none=True, by_alias=True), f, indent=2, ensure_ascii=False)
        info.add_item(info.STATUS_OK, f"conf.json v2→v7")

        ng_fs.migrate_contest_structure(src_root, dst_root, lang=lang)

        day_dirs = conf.get('subdir', [])
        days = list(conf.sub) if hasattr(conf, 'sub') else []

        all_probs = []
        for day in days:
            all_probs.extend(day.sub if hasattr(day, 'sub') and day.sub else [])

        compile_config = _choose_compile(all_probs)
        if compile_config:
            log.info(f"compile 配置：{json.dumps(compile_config, ensure_ascii=False)}")
        else:
            log.info("compile 配置：留空")

        for day_dir, day in zip(day_dirs, days):
            _migrate_day(day, day_dir, src_root, dst_root, lang, compile_config, contest_titles)

        info.pop()

    elif conf.folder == 'day':
        ng_fs.ensure_dir(dst_root)
        probs = list(conf.sub) if hasattr(conf, 'sub') and conf.sub else []
        compile_config = _choose_compile(probs)
        info.push(conf.get('name', '?'))
        _migrate_day(conf, '', src_root, dst_root, lang, compile_config, contest_titles)
        info.pop()

    elif conf.folder == 'problem':
        _migrate_single_problem(conf, '', src_root, dst_root, lang)

    else:
        log.error(f"不支持的文件夹类型：{conf.folder}")
        return False

    info.print_summary()
    return True


def main():
    if len(sys.argv) < 2:
        print("用法：python -m tuack_migrater <目标目录> [--force]")
        sys.exit(1)

    dst_root = os.path.abspath(sys.argv[1])
    force = '--force' in sys.argv or '-f' in sys.argv
    src_root = os.getcwd()

    success = migrate(src_root, dst_root, force)
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
