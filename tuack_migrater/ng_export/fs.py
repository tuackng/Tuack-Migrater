import os
import shutil
from ..base import logger as log
from . import info

SKIP_DIRS = {'__pycache__', '.git', '.svn', 'venv', 'node_modules'}

def ensure_dir(path):
    os.makedirs(path, exist_ok=True)

def copy_file(src, dst):
    if os.path.isfile(src):
        ensure_dir(os.path.dirname(dst))
        shutil.copy2(src, dst)

def copy_dir(src, dst):
    if os.path.isdir(src):
        ensure_dir(os.path.dirname(dst))
        if os.path.exists(dst):
            shutil.rmtree(dst)
        shutil.copytree(src, dst)

def migrate_structure(prob_path, dst_path, config_samples, down_files, lang):
    ensure_dir(dst_path)
    prob_name = os.path.basename(prob_path)

    sample_dst = os.path.join(dst_path, 'sample')
    ensure_dir(sample_dst)

    for sample in config_samples:
        for key in ('input', 'output'):
            fname = sample.input if key == 'input' else sample.output
            if not fname:
                continue
            src = os.path.join(prob_path, 'down', fname)
            if os.path.isfile(src):
                copy_file(src, os.path.join(sample_dst, fname))

    mapping = [
        ('data', 'data'),
        ('resources', 'img'),
        ('pre', 'pre'),
    ]
    for src_sub, dst_sub in mapping:
        src_full = os.path.join(prob_path, src_sub)
        if os.path.isdir(src_full):
            dst_full = os.path.join(dst_path, dst_sub)
            copy_dir(src_full, dst_full)
            if src_sub == 'pre':
                info.add_warning(f"pre/ 已复制，pretest 支持将在 tuack-ng 后续版本加入")

    for f in down_files:
        rel = os.path.relpath(f, prob_path)
        dst_file = os.path.join(dst_path, 'down', os.path.basename(f))
        copy_file(f, dst_file)

    chk_dir_src = os.path.join(prob_path, 'data', 'chk')
    if os.path.isdir(chk_dir_src):
        copy_dir(chk_dir_src, os.path.join(dst_path, 'data', 'chk'))

    tables_src = os.path.join(prob_path, 'tables')
    if os.path.isdir(tables_src):
        copy_dir(tables_src, os.path.join(dst_path, 'tables'))
        info.add_item(info.STATUS_MANUAL,
                      f"tables/ 已复制，但需手动迁移为 Lua 脚本")

    gen_py = os.path.join(prob_path, 'gen.py')
    if os.path.isfile(gen_py):
        copy_file(gen_py, os.path.join(dst_path, 'gen.py'))

    for fname in os.listdir(prob_path):
        if fname in SKIP_DIRS:
            continue
        if fname in ('data', 'down', 'pre', 'sample', 'resources', 'tables', 'statement', 'statements', 'result', 'bin', 'tmp', 'conf.json', 'conf.yaml', 'gen.py', 'tuack.log', 'random_state'):
            continue
        src_full = os.path.join(prob_path, fname)
        if os.path.isfile(src_full) or os.path.isdir(src_full):
            dst_full = os.path.join(dst_path, fname)
            if os.path.isfile(src_full):
                copy_file(src_full, dst_full)
            else:
                copy_dir(src_full, dst_full)

def migrate_statement(prob_path, dst_path, lang):
    statement_dir = os.path.join(prob_path, 'statement')
    if not os.path.isdir(statement_dir):
        return None, None

    candidates = []
    if lang:
        candidates.append(f'{lang}.md')
    candidates.extend(f for f in sorted(os.listdir(statement_dir))
                      if f.endswith('.md') and f not in candidates)

    src_md = None
    for c in candidates:
        p = os.path.join(statement_dir, c)
        if os.path.isfile(p):
            src_md = p
            break

    if not src_md:
        return None, None

    orig_dst = os.path.join(dst_path, 'statement.orig.md')
    copy_file(src_md, orig_dst)

    return src_md, orig_dst

def migrate_day_structure(day_path, dst_path, lang):
    ensure_dir(dst_path)

    src = os.path.join(day_path, 'precautions', f'{lang or "zh-cn"}.md')
    if os.path.isfile(src):
        copy_file(src, os.path.join(dst_path, 'precaution.md'))

def migrate_contest_structure(contest_path, dst_path, lang=None):
    _ensure_precaution(contest_path, dst_path, lang)

def _ensure_precaution(contest_root, dst_root, lang=None):
    # 直接构造目标路径
    src = os.path.join(contest_root, 'precautions', f'{lang or "zh-cn"}.md')
    dst = os.path.join(dst_root, 'precaution.md')

    if os.path.isfile(src):
        copy_file(src, dst)
        log.info(f"precaution: {src} → precaution.md")
    else:
        with open(dst, 'w', encoding='utf-8') as f:
            f.write('')
        log.info("precaution: 未找到，已创建空 precaution.md")