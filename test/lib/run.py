import argparse
import importlib
from pathlib import Path

import yaml

from test.lib.evol import GeneratorConfig, GeneratorConfigType, Task, TestCaseConfig, TestCaseDataGenerator
from test.lib.utils import RunFilter


def run [C: GeneratorConfig] (
    tcg: TestCaseDataGenerator[C],
    init_seed: int,
    config_file: Path,
    output_dir: Path,
    run_tags: RunFilter,
    max_workers: int | None = None
) -> None:
    seed = init_seed

    print(f'[i] Config file: {config_file}')

    with open(config_file) as f:
        config = TestCaseConfig(**yaml.load(f, Loader=yaml.SafeLoader))
        if config.seed is not None:
            seed = config.seed

    print(f'[i] Default seed: {seed:#X}')
    print(f'[i] Output directory: {output_dir}')
    print()

    S = len(config.subcases)
    pad = len(str(S))

    tasks: list[Task[C]] = []
    for i, (tag, subcase) in enumerate(config.subcases.items(), start=1):
        if not run_tags.should_run(tag):
            print(f'[{i:>{pad}}/{S}] Skipping: {tag}')
            continue

        if 'seed' not in subcase or subcase['seed'] is None:
            subcase['seed'] = seed

        subconfig = tcg.build_subconfig(subcase)

        print(f'[{i:>{pad}}/{S}] Subcase: {tag} ({subconfig})')

        subtasks, subfiles = tcg.prepare(
            base_dir=Path(output_dir) / tag,
            config=subconfig,
            subcase=tag,
            tags=run_tags,
        )

        for task in subtasks:
            print(
                f'  + Task: {task.name()} '
                f'-> {task.path.relative_to(output_dir)}'
            )

        for group in tcg.groups:
            files = subfiles.get(group.name)
            if not files:
                print(f'  > Group "{group.name}": Skipped')
            else:
                print(f'  > Group "{group.name}":')
                for file in files:
                    print(f'    + Written: {file.relative_to(output_dir)}')
                for tblname in [
                    table.name for table in group.tables
                    if not run_tags.should_run(table.name)
                ]:
                    print(f'    - Skipped: Table "{tblname}"')

        tasks.extend(subtasks)

    T = len(tasks)
    pad = len(str(T))

    print_workers = max_workers if max_workers is not None else 'auto'

    print()
    print(f'[i] Total tasks: {T}')
    print(f'[i] Running tasks with max_workers={print_workers}...')
    print()

    for i, fut, task in tcg.run_tasks(
        tasks=tasks,
        max_workers=max_workers,
    ):
        try:
            fut.result()
            print(
                f'[{i+1:0>{pad}}/{T}] '
                f'Completed: {task.name()} '
                f'-> {task.path.relative_to(output_dir)}')
        except Exception as e:
            print(f'[{i+1:0>{pad}}/{T}] Failed: {task.name()}: {e!r}')
            raise

def main(
    tcg: TestCaseDataGenerator[GeneratorConfigType],
    default_conf_file: Path,
    default_outdir: Path
) -> None:
    argparser = argparse.ArgumentParser()
    argparser.add_argument('--config', '-i', type=Path, default=default_conf_file)
    argparser.add_argument('--output', '-o', type=Path, default=default_outdir)
    argparser.add_argument('--seed', '-s', type=int, default=0xFF)
    argparser.add_argument('--max-workers', type=int, default=None)

    argparser.add_argument('--include', '-I', nargs='*', default=[])
    argparser.add_argument('--exclude', '-x', nargs='*', default=[])

    args = argparser.parse_args()

    run(
        tcg,
        init_seed=args.seed,
        config_file=args.config,
        output_dir=args.output,
        run_tags=RunFilter(pick=args.include, skip=args.exclude),
        max_workers=args.max_workers
    )


def get_config(mod_name: str) -> tuple[TestCaseConfig, type]:
    with open(Path(__file__).parent.parent / mod_name / 'in.yml') as f:
        config = TestCaseConfig(**yaml.safe_load(f))

    mod = importlib.import_module(f'test.{mod_name}.{mod_name}')
    subconf_class = getattr(mod, 'Config')

    return config, subconf_class