import os
import re
from . import info
from .models import (
    ContestConfigFile, ContestDayConfigFile, ProblemConfigFile,
    ProblemType, DmkConfig, ScorePolicy,
    SampleItem, SingleDataItem, BundleDataItem,
    TestCase, CheckerConfig, CheckerConfigPair,
    GeneratorConfig, GeneratorConfigPair,
    InteractiveConfig, DataItem,
)


def extract_title(title_dict, lang):
    if not title_dict:
        return ""
    if isinstance(title_dict, str):
        return title_dict
    if lang and lang in title_dict:
        return title_dict[lang]
    for val in title_dict.values():
        if isinstance(val, str):
            return val
    return ""

def parse_time_to_array(time_str):
    if not time_str:
        return None
    m = re.match(r'(\d{4})-(\d{2})-(\d{2})\s+(\d{2}):(\d{2}):(\d{2})', str(time_str))
    if m:
        return [int(m.group(i)) for i in range(1, 7)]
    return None


def migrate_contest(v2_conf, lang, titles):
    return ContestConfigFile(
        name=v2_conf.get('name', ''),
        subdir=list(v2_conf.get('subdir', [])),
        title=titles.get('title', extract_title(v2_conf.get('title', {}), lang)),
        short_title=titles.get('short_title', extract_title(v2_conf.get('short title', {}), lang)),
    )


def migrate_day(v2_conf, lang, day_compile, titles):
    st = parse_time_to_array(v2_conf.get('start time'))
    et = parse_time_to_array(v2_conf.get('end time'))
    return ContestDayConfigFile(
        name=v2_conf.get('name', ''),
        subdir=list(v2_conf.get('subdir', [])),
        title=titles.get('title', extract_title(v2_conf.get('title', {}), lang)),
        compile=day_compile or {},
        start_time=st,
        end_time=et,
    )


def migrate_problem(v2_prob, prob_path, lang, interactive_info):
    pt_map = {'program': ProblemType.program,
              'output': ProblemType.output,
              'interactive': ProblemType.interactive}
    prob_type = pt_map.get(v2_prob.get('type', 'program'), ProblemType.program)

    samples, down_files = migrate_samples(v2_prob, prob_path)
    data, subtasks = migrate_data(v2_prob, prob_path)
    tests = migrate_users(v2_prob, prob_path)
    checker = detect_checker(prob_path)
    generator = detect_generator(prob_path)

    interactive = None
    if prob_type == ProblemType.interactive and interactive_info:
        interactive = InteractiveConfig(**interactive_info)

    config = ProblemConfigFile(
        type=prob_type,
        name=v2_prob.get('name', ''),
        title=extract_title(v2_prob.get('title', {}), lang),
        time_limit=v2_prob.get('time limit', 1.0),
        memory_limit=v2_prob.get('memory limit', '512 MiB'),
        args=dict(v2_prob.get('args', {})),
        samples=samples,
        data=data,
        subtasks={str(k): v for k, v in subtasks.items()},
        tests=tests,
        checker=checker,
        generator=generator,
        interactive=interactive,
    )

    return config, samples, down_files


def migrate_samples(v2_prob, prob_path):
    conf_samples = v2_prob.get('samples', [])
    down_dir = os.path.join(prob_path, 'down')
    sample_dir = os.path.join(prob_path, 'sample')

    declared_ids = set()
    for s in conf_samples:
        for c in s.get('cases', []):
            try:
                declared_ids.add(int(c))
            except (ValueError, TypeError):
                declared_ids.add(str(c))

    if not declared_ids and os.path.isdir(down_dir):
        for f in sorted(os.listdir(down_dir)):
            m = re.match(r'(\d+)\.in$', f)
            if m:
                declared_ids.add(int(m.group(1)))

    config_samples: list[SampleItem] = []
    declared_sample_files: set[str] = set()

    for sid in sorted(declared_ids, key=lambda x: (isinstance(x, str), x)):
        input_candidates = [
            os.path.join(down_dir, f'{sid}.in'),
            os.path.join(sample_dir, f'{sid}.in'),
        ]
        output_candidates = [
            os.path.join(down_dir, f'{sid}.ans'),
            os.path.join(sample_dir, f'{sid}.ans'),
        ]

        found_in = None
        for p in input_candidates:
            if os.path.isfile(p):
                found_in = os.path.basename(p)
                declared_sample_files.add(p)
                break

        found_out = None
        for p in output_candidates:
            if os.path.isfile(p):
                found_out = os.path.basename(p)
                declared_sample_files.add(p)
                break

        config_samples.append(SampleItem(
            id=sid if isinstance(sid, int) else int(sid) if str(sid).isdigit() else sid,
            input=found_in or f'{sid}.in',
            output=found_out or f'{sid}.ans',
        ))

    all_down_files = set()
    if os.path.isdir(down_dir):
        for f in os.listdir(down_dir):
            fp = os.path.join(down_dir, f)
            if os.path.isfile(fp):
                all_down_files.add(fp)

    remaining_down = list(all_down_files - declared_sample_files)
    return config_samples, remaining_down


def migrate_data(v2_prob, prob_path):
    v2_data = v2_prob.get('data', [])
    if not v2_data:
        return [], {"0": ScorePolicy.sum}

    packed = v2_prob.get('packed', False)
    items: list[DataItem] = []
    subtasks: dict[int, ScorePolicy] = {}

    total_data_score = sum(d.get('score', 0) for d in v2_data if 'score' in d)
    unscored = [d for d in v2_data if 'score' not in d]

    if unscored:
        per_group = (100.0 - total_data_score) / len(unscored) if total_data_score < 100 else 0
        for d in unscored:
            d['score'] = per_group

    for i, datum in enumerate(v2_data):
        cases = datum.get('cases', [])
        score = float(datum.get('score', 0))
        subtask_id = i

        if packed and score > 0:
            id_list = [int(c) if str(c).isdigit() else c for c in cases]
            items.append(BundleDataItem(
                id=id_list,
                score=int(score) if score == int(score) else int(score),
                subtask=subtask_id,
            ))
            subtasks[subtask_id] = ScorePolicy.min
        else:
            case_count = len(cases)
            per_case = score / case_count if case_count > 0 else 0
            for c in cases:
                cid = int(c) if str(c).isdigit() else c
                items.append(SingleDataItem(
                    id=cid,
                    score=int(per_case) if per_case == int(per_case) else int(per_case),
                    subtask=subtask_id,
                ))
            subtasks[subtask_id] = ScorePolicy.sum

    return items, subtasks


def migrate_users(v2_prob, prob_path):
    v2_users = v2_prob.get('users', {})
    tests: dict[str, TestCase] = {}
    for user_name, algos in v2_users.items():
        if not isinstance(algos, dict):
            continue
        for algo_name, algo_info in algos.items():
            test_name = f'{user_name}-{algo_name}'
            if not isinstance(algo_info, dict):
                path = os.path.join(prob_path, str(algo_info)) if algo_info else ''
                tests[test_name] = TestCase(path=path)
            else:
                path = algo_info.get('path', os.path.join(user_name, algo_name))
                if not os.path.isabs(path):
                    path = os.path.join(prob_path, path)
                expected = algo_info.get('expected', '')
                if isinstance(expected, (list, dict)):
                    expected = str(expected)
                tests[test_name] = TestCase(path=path, expected=expected)
    return tests


def detect_checker(prob_path):
    chk_cpp = os.path.join(prob_path, 'data', 'chk', 'chk.cpp')
    if os.path.isfile(chk_cpp):
        return CheckerConfigPair(
            data=CheckerConfig(source="data/chk/chk.cpp"),
        )
    return None


def detect_generator(prob_path):
    gen_py = os.path.join(prob_path, 'gen.py')
    if os.path.isfile(gen_py):
        info.add_warning(f"gen.py 已保留，但 tuack-ng 不支持 Python 生成器，需手动重写为 C++")
    return None
