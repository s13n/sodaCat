# ST Device Descriptions

ST Microelectronics provides device descriptions as SVD files, but their quality
varies quite a bit. It is not uncommon to find bugs in the description of shared
peripherals fixed only in some SVD files, but not others. Hence part of the
effort consists of hunting down the files with the least problems.

ST publishes SVD archives per family at
https://www.st.com/en/microcontrollers/stm32-32-bit-arm-cortex-mcus.html
under the "CAD Resources" tab. Each family has its own ZIP archive containing
the SVD files for every chip in that family. The download automation in this
directory fetches these archives directly from st.com.

Like with all SVD based descriptions, you end up with many files containing the
same description, because the same peripherals are used in a variety of
different chips. From time to time peripherals gain additional features, while
otherwise being backwards compatible with previous versions. The task therefore
is to find the most capable and complete version, of which all others are
subsets, and create a parameterized description that allows features to be
selectively turned on or off.

On the other hand, there are also cases when the same name is used for rather
different peripherals. You can't unify that into a common description, and need
to change the naming in order to make clear which alternative you're dealing
with.

## Directory contents

- **`STM32.yaml`** — Consolidated configuration for all registered STM32
  families. Contains subfamily-to-chip mappings, block definitions with SVD
  source selection and transforms, interrupt mappings, parameters, and SVD
  archive version tracking. This is the single source of truth for the
  extraction pipeline and is updated automatically when new SVD archives are
  downloaded.

- **`*.zip`** — SVD zip archives downloaded from st.com, one per family
  (e.g. `stm32h7-svd.zip`). Each contains the individual `.svd` files for
  every chip in that family.

- **`CMakeLists.txt`** — Registers each family and creates the CMake targets
  described below.

- **`SVD_ERRATA.md`** — Known SVD bugs verified against reference manuals,
  with the transforms that work around them.

## CMake targets

Build targets are created by `cmake/stm32-extraction.cmake` and registered
in `CMakeLists.txt`. All targets are invoked from the build directory:

```
cmake --build <build_dir> --target <target>
```

The registered families and their target IDs are listed in `CMakeLists.txt`.
To see them at configure time, look for the `stm32_print_families()` output.

### Extraction (built by default)

| Target | Description |
|---|---|
| `stm32<id>-models` | Extract YAML models from one family's SVD archive |
| `rebuild-stm32<id>-models` | Force re-extraction (deletes stamp, then rebuilds) |

Extraction runs `extractors/generate_stm32_models.py`, which reads the family
config from `STM32.yaml`, opens the corresponding zip archive, and writes
YAML models to `models/ST/`. Stamp files in the build directory prevent
redundant re-extraction; rebuilds only happen when the zip or config changes.

### Transform audit (not built by default)

| Target | Description |
|---|---|
| `audit-stm32<id>-models` | Check one family's transforms for no-ops |
| `audit-stm32-models` | Audit all families |

After an SVD update, some transforms that fix SVD bugs may become unnecessary
because ST fixed the bug upstream. The audit targets detect these no-ops so
the corresponding transforms can be cleaned up. See `SVD_ERRATA.md`.

### SVD updates (not built by default)

| Target | Description |
|---|---|
| `check-stm32-svds` | Query st.com for version changes (read-only, no downloads) |
| `update-stm32-svds` | Download updated archives and update `STM32.yaml` |

These targets run `tools/st_maintenance.py svd`, which fetches ST's SVD
metadata API, compares remote versions against the `svd.version` fields in
`STM32.yaml`, and optionally downloads changed archives. On download, the
`svd.version` and `svd.date` fields are updated in-place.

Typical workflow after an SVD update:

1. `cmake --build . --target update-stm32-svds` — download new archives
2. `cmake --build .` — re-extract models (stamps are invalidated)
3. `cmake --build . --target audit-stm32-models` — check for obsolete transforms
4. Review changes in `git diff -- models/` and clean up no-op transforms

For the full step-by-step procedure including transform cleanup and
verification, see `tasks/stm32-svd-update.md`.
