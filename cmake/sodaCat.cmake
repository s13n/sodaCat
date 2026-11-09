# sodaCat.cmake - Integration module for sodaCat resources

# When this file is loaded from a sodaCat checkout (rather than a downloaded
# copy of just this file), that checkout's generators/ and models/ are used
# directly instead of downloading them.  A client project can thus test local
# sodaCat changes by putting <checkout>/cmake on CMAKE_MODULE_PATH.
get_filename_component(_sodacat_root "${CMAKE_CURRENT_LIST_DIR}/.." ABSOLUTE)
if(EXISTS "${_sodacat_root}/generators" AND EXISTS "${_sodacat_root}/models")
    set_property(GLOBAL PROPERTY SODACAT_CHECKOUT "${_sodacat_root}")
    set(SODACAT_LOCAL_DIR "${_sodacat_root}/models" CACHE STRING "sodaCat local model dir")
    message(STATUS "Using sodaCat checkout ${_sodacat_root}")
else()
    set_property(GLOBAL PROPERTY SODACAT_CHECKOUT "")
    set(SODACAT_LOCAL_DIR "${CMAKE_BINARY_DIR}/models" CACHE STRING "sodaCat local download dir")
    if(SODACAT_URL_BASE)
        message(VERBOSE "Using sodaCat repository in ${SODACAT_URL_BASE}")
    else()
        message(WARNING "Variable SODACAT_URL_BASE not defined. Can't download models.")
    endif()
endif()

find_package(Python3 REQUIRED COMPONENTS Interpreter)

# Fetch a generator language directory (e.g. "cxx") from the sodaCat repository.
# Uses the GitHub Contents API to list files, then downloads each one.
# Sets SODACAT_GENERATOR_<LANGUAGE> to the local path.
# No-op if the directory already exists locally under CMAKE_SOURCE_DIR.
function(sodacat_fetch_generator language)
    string(TOUPPER "${language}" lang_upper)

    # If generators exist locally (the sodaCat checkout this file was loaded
    # from, or the project itself being sodaCat), use them directly
    get_property(_checkout GLOBAL PROPERTY SODACAT_CHECKOUT)
    foreach(local_dir IN ITEMS "${_checkout}/generators/${language}"
                               "${CMAKE_SOURCE_DIR}/generators/${language}")
        if(EXISTS "${local_dir}/generate_header.py")
            set(SODACAT_GENERATOR_${lang_upper} "${local_dir}" CACHE INTERNAL "" FORCE)
            _sodacat_collect_generator_scripts("${lang_upper}" "${local_dir}")
            return()
        endif()
    endforeach()

    if(NOT SODACAT_URL_BASE)
        message(FATAL_ERROR "Generator '${language}' not found locally and SODACAT_URL_BASE not set")
    endif()

    set(generator_dir "${CMAKE_BINARY_DIR}/_generators/${language}")
    if(EXISTS "${generator_dir}/generate_header.py")
        set(SODACAT_GENERATOR_${lang_upper} "${generator_dir}" CACHE INTERNAL "" FORCE)
        _sodacat_collect_generator_scripts("${lang_upper}" "${generator_dir}")
        return()
    endif()

    # List files via GitHub Contents API and download each one
    # SODACAT_URL_BASE is https://raw.githubusercontent.com/<owner>/<repo>/<ref>
    string(REGEX MATCH "raw\\.githubusercontent\\.com/([^/]+)/([^/]+)/([^/]+)" _match "${SODACAT_URL_BASE}")
    set(owner "${CMAKE_MATCH_1}")
    set(repo "${CMAKE_MATCH_2}")
    set(ref "${CMAKE_MATCH_3}")

    message(STATUS "Fetching generator '${language}' from ${owner}/${repo}@${ref}")
    execute_process(
        COMMAND ${Python3_EXECUTABLE} -c
            "import json,urllib.request; data=json.loads(urllib.request.urlopen('https://api.github.com/repos/${owner}/${repo}/contents/generators/${language}?ref=${ref}').read()); print(';'.join(f['name'] for f in data if f['type']=='file'))"
        OUTPUT_VARIABLE file_list
        OUTPUT_STRIP_TRAILING_WHITESPACE
        RESULT_VARIABLE result
    )
    if(NOT result EQUAL 0 OR NOT file_list)
        message(FATAL_ERROR "Failed to list generator files for '${language}' from GitHub API")
    endif()

    file(MAKE_DIRECTORY "${generator_dir}")
    foreach(file IN LISTS file_list)
        string(CONCAT url "${SODACAT_URL_BASE}" "/generators/${language}/${file}")
        file(DOWNLOAD "${url}" "${generator_dir}/${file}" STATUS status)
        list(GET status 0 status_code)
        if(NOT status_code EQUAL 0)
            list(GET status 1 status_message)
            message(FATAL_ERROR "Failed to download ${url}: ${status_message}")
        endif()
    endforeach()
    message(STATUS "Fetched ${language} generator (${file_list})")

    set(SODACAT_GENERATOR_${lang_upper} "${generator_dir}" CACHE INTERNAL "" FORCE)
    _sodacat_collect_generator_scripts("${lang_upper}" "${generator_dir}")
endfunction()


# Collect every .py file in the generator directory so that header-generation
# custom commands depend on the whole generator, not just the dispatcher entry
# point.  Without this, edits to per-language scripts (e.g. the peripheral or
# chip generator) don't trigger header regeneration.  CONFIGURE_DEPENDS makes
# CMake re-glob if scripts are added or removed.
function(_sodacat_collect_generator_scripts lang_upper generator_dir)
    file(GLOB scripts CONFIGURE_DEPENDS "${generator_dir}/*.py")
    set(SODACAT_GENERATOR_${lang_upper}_SCRIPTS "${scripts}"
        CACHE INTERNAL "" FORCE)
endfunction()

# Ensure a model file exists locally, downloading it (and any transitive
# dependencies listed in its `models:` section) if SODACAT_URL_BASE is set.
function(ensure_model model_path)
    set(model_file "${SODACAT_LOCAL_DIR}/${model_path}.yaml")
    if(EXISTS "${model_file}")
        return()
    endif()

    if(NOT SODACAT_URL_BASE)
        message(FATAL_ERROR "Model ${model_path}.yaml not found and SODACAT_URL_BASE not set")
    endif()

    # Create parent directory and download
    get_filename_component(parent_dir "${model_file}" DIRECTORY)
    file(MAKE_DIRECTORY "${parent_dir}")
    string(CONCAT url "${SODACAT_URL_BASE}" "/models/" "${model_path}.yaml")
    message(STATUS "Downloading ${url}")
    file(DOWNLOAD "${url}" "${model_file}" STATUS status)
    list(GET status 0 status_code)
    if(NOT status_code EQUAL 0)
        file(REMOVE "${model_file}")
        list(GET status 1 status_message)
        message(FATAL_ERROR "Failed to download ${url}: ${status_message}")
    endif()

    # Check for transitive dependencies: peripheral block models referenced
    # under `models:`, plus optional chip-side links — `clocktree:` (legacy,
    # points directly at a clock-tree YAML) or `inherits:` (newer, points at
    # a subfamily/family model whose own dependencies will be followed once
    # ensure_model fetches it).  All of these need their YAML files locally.
    execute_process(
        COMMAND ${Python3_EXECUTABLE} -c
            "from ruamel.yaml import YAML; d=YAML(typ='safe').load(open('${model_file}')); deps=list(d.get('models',{}).values()); ct=d.get('clocktree'); deps += [ct] if ct else []; ih=d.get('inherits'); deps += [ih] if ih else []; print(';'.join(deps))"
        OUTPUT_VARIABLE model_deps
        OUTPUT_STRIP_TRAILING_WHITESPACE
    )
    if(model_deps)
        foreach(dep IN LISTS model_deps)
            ensure_model("${dep}")
        endforeach()
    endif()
endfunction()

# Generate a header file for a target, recursively generating headers for any
# model dependencies (listed under the `models:` key in the YAML file).
# The generator auto-detects the model type (peripheral, chip, clock tree).
#
# The C++ namespace for each generated header comes from the model YAML's
# `namespace:` key, falling back to the lowercased innermost containing
# directory name when the key is absent.  Chips, peripheral blocks, and
# clock-trees each declare their own namespace independently.
#
# Parameters:
#   target      - Target to which the generated header is added as a source file
#   language    - Generator language (e.g. "cxx"); must be fetched first via sodacat_fetch_generator()
#   model_path  - Path to model file relative to SODACAT_LOCAL_DIR (e.g., ST/H7/H757/STM32H757_CM7)
#   suffix      - File name suffix of generated header file
#
# Optional keyword arguments:
#   ENDIAN <native|big|little>
#               - Storage byte order of a peripheral block's registers, passed
#                 through to the generator's HwReg<R, E> emission.  This is an
#                 integration fact (e.g. a big-endian device read over an I2C
#                 byte stream onto a little-endian host), not a model property,
#                 so it is set per generate_header() call.  Defaults to native
#                 and applies only to the directly-named peripheral model — it
#                 is intentionally NOT propagated to recursively-generated
#                 model dependencies (a chip's own MMIO is always native).
function(generate_header target language model_path suffix)
    cmake_parse_arguments(GH "" "ENDIAN" "" ${ARGN})

    # Extract model name from path (last component)
    get_filename_component(model "${model_path}" NAME)

    # Construct the full model file path
    set(model_file "${SODACAT_LOCAL_DIR}/${model_path}.yaml")

    # Ensure model (and dependencies) are available
    ensure_model("${model_path}")

    # Resolve namespace from the model YAML (or fall back to lowercased
    # innermost directory name).  Same rule used by the Python generators
    # via generators/<lang>/generate_header.py (namespace_of()).
    execute_process(
        COMMAND ${Python3_EXECUTABLE} -c
            "from ruamel.yaml import YAML; import re; from pathlib import Path; p=Path('${model_file}'); d=YAML(typ='safe').load(p) or {}; print(d.get('namespace') or re.sub(r'[^a-z0-9_]', '_', p.parent.name.lower()))"
        OUTPUT_VARIABLE _ns
        OUTPUT_STRIP_TRAILING_WHITESPACE
    )

    # Deduplicate: skip if this model path already has a header being generated
    # for this namespace in this binary directory.  The dedup key includes the
    # namespace because the same peripheral may be re-emitted into a sibling
    # namespace if its `namespace:` key changes between revisions.  It includes
    # the binary directory because outputs land there: a dependency generated
    # in another directory is invisible to targets here unless they link the
    # target that generates it, so it may need generating again (e.g. a shared
    # block used by chips in two directories) -- see "Reuse" below.
    string(REPLACE "/" "_" _path_key "${model_path}")
    string(MAKE_C_IDENTIFIER "${CMAKE_CURRENT_BINARY_DIR}" _dir_key)
    set(dedup_key "${_dir_key}_${_ns}_${_path_key}")
    get_property(already_generated GLOBAL PROPERTY _SODACAT_HDR_${dedup_key})
    if(already_generated)
        return()
    endif()
    set_property(GLOBAL PROPERTY _SODACAT_HDR_${dedup_key} TRUE)

    # Recursively generate headers for model dependencies.  Each dep
    # carries its own `namespace:` key (or directory-based fallback), so
    # we just forward the path — no namespace-mapping needed at this level.
    execute_process(
        COMMAND ${Python3_EXECUTABLE} -c
            "from ruamel.yaml import YAML; d=YAML(typ='safe').load(open('${model_file}')); m=d.get('models',{}); print(';'.join(m.values()) if m else '')"
        OUTPUT_VARIABLE model_deps
        OUTPUT_STRIP_TRAILING_WHITESPACE
    )
    if(model_deps)
        foreach(dep IN LISTS model_deps)
            generate_header(${target} ${language} ${dep} ${suffix})
        endforeach()
    endif()

    # Follow the chip's fabric link.  Either `clocktree:` (legacy — points
    # directly at a clock-tree YAML) or `inherits:` (newer — points at a
    # subfamily model whose `clocks:` section is the clock tree); the
    # dispatcher routes by file shape in either case.
    execute_process(
        COMMAND ${Python3_EXECUTABLE} -c
            "from ruamel.yaml import YAML; d=YAML(typ='safe').load(open('${model_file}')); print(d.get('clocktree') or d.get('inherits') or '')"
        OUTPUT_VARIABLE clocktree_dep
        OUTPUT_STRIP_TRAILING_WHITESPACE
    )
    if(clocktree_dep)
        generate_header(${target} ${language} ${clocktree_dep} ${suffix})
    endif()

    # Reuse rather than regenerate: when another target (in another binary
    # directory -- same-directory duplicates were skipped above) already
    # generates this model, a second copy is only needed if that target's
    # module is not visible here.  If ${target} links it, directly or
    # transitively, a second copy would be harmful: a TU importing both the
    # owner's modules and this one sees two different BMIs for the same module
    # (GCC: "import 'X' has CRC mismatch").  That is the normal case for a
    # library such as peLua's `stm32` providing the peripheral blocks and the
    # product generating the chip model that imports them.
    #
    # Whether ${target} links the owner is only known once its
    # target_link_libraries() calls have been made, which commonly come after
    # generate_header().  So the decision is deferred to the end of the
    # current directory.
    string(MAKE_C_IDENTIFIER "${_ns}_${model_path}" _model_key)
    get_property(_owners GLOBAL PROPERTY _SODACAT_OWNERS_${_model_key})
    if(_owners)
        cmake_language(EVAL CODE
            "cmake_language(DEFER CALL _sodacat_emit_unless_linked [[${target}]] [[${language}]] [[${model_path}]] [[${suffix}]] [[${_ns}]] [[${GH_ENDIAN}]])")
        return()
    endif()
    _sodacat_emit("${target}" "${language}" "${model_path}" "${suffix}" "${_ns}" "${GH_ENDIAN}")
endfunction()

# Deferred part of generate_header(): emit the model for ${target} unless a
# target that already generates it is in ${target}'s link closure.
function(_sodacat_emit_unless_linked target language model_path suffix ns endian)
    string(MAKE_C_IDENTIFIER "${ns}_${model_path}" _model_key)
    get_property(_owners GLOBAL PROPERTY _SODACAT_OWNERS_${_model_key})
    _sodacat_link_closure("${target}" _linked)
    foreach(_owner IN LISTS _owners)
        if(_owner STREQUAL target OR _owner IN_LIST _linked)
            message(VERBOSE "generate_header: ${target} uses ${ns}/${model_path} from linked target ${_owner}")
            return()
        endif()
    endforeach()
    _sodacat_emit("${target}" "${language}" "${model_path}" "${suffix}" "${ns}" "${endian}")
endfunction()

# Set ${out} to every target ${target} links, directly or transitively
# (aliases resolved; $<LINK_ONLY:...> counted; other generator expressions,
# plain flags and non-target names ignored).
function(_sodacat_link_closure target out)
    set(_seen "")
    set(_queue "")
    foreach(_prop IN ITEMS LINK_LIBRARIES INTERFACE_LINK_LIBRARIES)
        get_target_property(_libs "${target}" ${_prop})
        if(_libs)
            list(APPEND _queue ${_libs})
        endif()
    endforeach()
    # Not while(_queue): a list whose last element ends in -NOTFOUND is false.
    list(LENGTH _queue _n)
    while(_n GREATER 0)
        list(POP_FRONT _queue _l)
        list(LENGTH _queue _n)
        if(_l MATCHES "^\\$<LINK_ONLY:([^>]+)>$")
            set(_l "${CMAKE_MATCH_1}")
        endif()
        if(NOT _l OR _l MATCHES "^(\\$<|::@|-)" OR NOT TARGET "${_l}")
            continue()
        endif()
        get_target_property(_aliased "${_l}" ALIASED_TARGET)
        if(_aliased)
            set(_l "${_aliased}")
        endif()
        if(_l IN_LIST _seen)
            continue()
        endif()
        list(APPEND _seen "${_l}")
        get_target_property(_ilibs "${_l}" INTERFACE_LINK_LIBRARIES)
        if(_ilibs)
            list(APPEND _queue ${_ilibs})
            list(LENGTH _queue _n)
        endif()
    endwhile()
    set(${out} "${_seen}" PARENT_SCOPE)
endfunction()

# Emit the custom command generating ${model_path} and add the result to
# ${target}.  Records ${target} as an owner of the model, so that targets in
# other directories can reuse it (see generate_header).
function(_sodacat_emit target language model_path suffix _ns endian)
    get_filename_component(model "${model_path}" NAME)
    set(model_file "${SODACAT_LOCAL_DIR}/${model_path}.yaml")
    string(MAKE_C_IDENTIFIER "${_ns}_${model_path}" _model_key)
    set_property(GLOBAL APPEND PROPERTY _SODACAT_OWNERS_${_model_key} "${target}")

    # Resolve generator directory
    string(TOUPPER "${language}" lang_upper)
    set(generator_dir "${SODACAT_GENERATOR_${lang_upper}}")
    if(NOT generator_dir)
        message(FATAL_ERROR "Generator '${language}' not configured. Call sodacat_fetch_generator(${language}) first.")
    endif()
    set(generator_script "${generator_dir}/generate_header.py")
    set(generator_scripts "${SODACAT_GENERATOR_${lang_upper}_SCRIPTS}")

    # Ensure the output and generator directories are in the target's include path.
    # Generated headers live in ${CMAKE_CURRENT_BINARY_DIR}/${_ns}/ so the
    # binary-dir root is enough for clients to include them as "<_ns>/<name>.hpp".
    get_target_property(_inc_dirs ${target} INCLUDE_DIRECTORIES)
    if(NOT "${CMAKE_CURRENT_BINARY_DIR}" IN_LIST _inc_dirs)
        target_include_directories(${target} PUBLIC "${CMAKE_CURRENT_BINARY_DIR}")
    endif()
    if(NOT "${generator_dir}" IN_LIST _inc_dirs)
        target_include_directories(${target} PUBLIC "${generator_dir}")
    endif()

    # Output goes into a per-namespace subdirectory so that peripherals of the
    # same name from different chips/vendors don't collide.
    set(_out_dir "${CMAKE_CURRENT_BINARY_DIR}/${_ns}")
    file(MAKE_DIRECTORY "${_out_dir}")

    # Two different models landing on the same output header (e.g. a family
    # base block and a subfamily variant of it, both in the family namespace)
    # would give CMake two rules for one file; it silently keeps one, so the
    # other model goes ungenerated and includers get whichever won.  Fail
    # instead — generate the second one from a different binary directory.
    set(_out_hdr "${_out_dir}/${model}${suffix}")
    get_property(_prev_model GLOBAL PROPERTY "_SODACAT_OUT_${_out_hdr}")
    if(_prev_model AND NOT _prev_model STREQUAL model_file)
        message(FATAL_ERROR
            "generate_header: ${_out_hdr} would be generated from two models:\n"
            "  ${_prev_model}\n  ${model_file}\n"
            "Both resolve to namespace '${_ns}'.  Generate one of them from a "
            "different binary directory (e.g. a test subdirectory).")
    endif()
    set_property(GLOBAL PROPERTY "_SODACAT_OUT_${_out_hdr}" "${model_file}")

    # The generator produces both a .hpp header and a .cppm module wrapper.
    # Namespace comes from the model YAML at generation time (Python side
    # uses the same resolver as cmake here), so no namespace argument is
    # forwarded.
    set(_endian_arg "")
    if(endian)
        set(_endian_arg --endian ${endian})
    endif()
    get_filename_component(model_stem "${model}${suffix}" NAME_WE)
    add_custom_command(OUTPUT "${_out_dir}/${model}${suffix}"
                              "${_out_dir}/${model_stem}.cppm"
        COMMAND ${Python3_EXECUTABLE} "${generator_script}" "${model_file}" ${model} ${suffix} ${_endian_arg}
        WORKING_DIRECTORY "${_out_dir}"
        MAIN_DEPENDENCY "${model_file}"
        DEPENDS ${generator_scripts}
        COMMENT "Generating ${_ns}/${model}${suffix}"
    )
    target_sources(${target} PUBLIC
        "${_out_dir}/${model}${suffix}"
    )
    target_sources(${target} PUBLIC
        FILE_SET CXX_MODULES BASE_DIRS "${CMAKE_CURRENT_BINARY_DIR}" FILES
            "${_out_dir}/${model_stem}.cppm"
    )
endfunction()

# Pre-compile C++ standard library headers as header units.
# This is required when using -fmodules-ts with GCC, because GCC does not
# properly deduplicate standard library declarations between modules and
# consumer translation units.  Building header units allows GCC to
# transparently translate #include to import, avoiding redefinition errors.
# Parameters:
#   target      - Target that depends on the header units
#   ARGN        - List of standard header names (e.g. cstdint type_traits)
function(build_system_header_units target)
    set(_stamp "${CMAKE_CURRENT_BINARY_DIR}/header_units.stamp")
    separate_arguments(_cxx_flags NATIVE_COMMAND "${CMAKE_CXX_FLAGS}")
    set(_cmds)
    foreach(_hdr IN LISTS ARGN)
        list(APPEND _cmds COMMAND ${CMAKE_CXX_COMPILER} ${_cxx_flags}
            -std=gnu++20 -fmodules-ts
            -fmodule-header=system -x c++-system-header ${_hdr})
    endforeach()
    # GCC places header unit .gcm files under gcm.cache/ (e.g.
    # gcm.cache/usr/include/.../cstdint.gcm).  When CMake drives compilation
    # with -fmodule-mapper=<file>, the mapper resolves unknown header units
    # relative to $root (the build dir), expecting usr/include/... without
    # the gcm.cache prefix.  Create a symlink so both paths work.
    set(_gcm_link "${CMAKE_BINARY_DIR}/usr")
    add_custom_command(OUTPUT "${_stamp}"
        ${_cmds}
        COMMAND ${CMAKE_COMMAND} -E create_symlink
            "${CMAKE_BINARY_DIR}/gcm.cache/usr" "${_gcm_link}"
        COMMAND ${CMAKE_COMMAND} -E touch "${_stamp}"
        WORKING_DIRECTORY "${CMAKE_BINARY_DIR}"
        COMMENT "Building standard library header units"
        VERBATIM
    )
    add_custom_target(${target}_header_units DEPENDS "${_stamp}")
    add_dependencies(${target} ${target}_header_units)
endfunction()

# Register a generated .cppm module interface unit for a target.
# The .cppm file is the module wrapper produced alongside the .hpp header
# by the sodaCat cxx generator.
# Parameters:
#   target      - Target to which the module source is added
#   header      - Absolute path to the generated .hpp header file (the .cppm
#                 is derived by replacing the suffix)
function(generate_module target header)
    get_filename_component(_stem "${header}" NAME_WE)
    get_filename_component(_dir "${header}" DIRECTORY)
    set(_cppm "${_dir}/${_stem}.cppm")
    target_sources(${target} PUBLIC
        FILE_SET CXX_MODULES BASE_DIRS "${CMAKE_CURRENT_BINARY_DIR}" FILES "${_cppm}"
    )
endfunction()

