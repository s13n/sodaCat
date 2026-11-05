Analysis scripts from adding STM32G5 (see tasks/g5-family.md).  They read the
G5 SVDs from the supplement checkout `build/_deps/stm32g5_svd_supplement-src/SVD`
(configure the build first).  Run from the repo root with the project venv.

- `match.py <chip>`: best-matching existing ST model per peripheral (bit coverage)
- `gaps.py PERIPH=Model ...`: fields a model lacks for G544/G564
- `diediff.py`: per-peripheral differences between and within the two dies
- `tconf.py`: G5 timer fields vs TimerV2 (add/rename/widen/conflict)
- `inst_cover.py`: which timer instance covers which
- `params.py`, `params2.py`: SVD evidence for shared-block parameter values
- `g5cov.py`: coverage of every G5 chip instance by its model
