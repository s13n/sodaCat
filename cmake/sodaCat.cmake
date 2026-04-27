# sodaCat.cmake - Integration module for sodaCat resources

set(SODACAT_LOCAL_DIR "${CMAKE_BINARY_DIR}/models" CACHE STRING "sodaCat local download dir")

if(SODACAT_URL_BASE)
    message(VERBOSE "Using sodaCat repository in ${SODACAT_URL_BASE}")
else()
    message(WARNING "Variable SODACAT_URL_BASE not defined. Can't download models.")
endif()

find_package(Python3 REQUIRED COMPONENTS Interpreter)

# Fetch a generator language directory (e.g. "cxx") from the sodaCat repository.
# Uses the GitHub Contents API to list files, then downloads each one.
# Sets SODACAT_GENERATOR_<LANGUAGE> to the local path.
# No-op if the directory already exists locally under CMAKE_SOURCE_DIR.
function(sodacat_fetch_generator language)
    string(TOUPPER "${language}" lang_upper)

    # If generators exist locally (sodaCat repo checkout), use them directly
    set(local_dir "${CMAKE_SOURCE_DIR}/generators/${language}")
    if(EXISTS "${local_dir}/generate_header.py")
        set(SODACAT_GENERATOR_${lang_upper} "${local_dir}" CACHE INTERNAL "" FORCE)
        _sodacat_collect_generator_scripts("${lang_upper}" "${local_dir}")
        return()
    endif()

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

    # Check for transitive dependencies (models: key in YAML)
    execute_process(
        COMMAND ${Python3_EXECUTABLE} -c
            "from ruamel.yaml import YAML; d=YAML(typ='safe').load(open('${model_file}')); m=d.get('models',{}); print(';'.join(m.values()) if m else '')"
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
# Parameters:
#   target      - Target to which the generated header is added as a source file
#   language    - Generator language (e.g. "cxx"); must be fetched first via sodacat_fetch_generator()
#   namespace   - Namespace name for the generated header
#   model_path  - Path to model file relative to SODACAT_LOCAL_DIR (e.g., ST/H757/H757)
#   suffix      - File name suffix of generated header file
function(generate_header target language namespace model_path suffix)
    # Extract model name from path (last component)
    get_filename_component(model "${model_path}" NAME)

    # Deduplicate: skip if this model path already has a header being generated
    # for this namespace.  The same peripheral model may legitimately need to
    # be emitted under multiple namespaces when it's shared by chips that live
    # in different namespaces, so the dedup key includes the namespace.
    string(REPLACE "/" "_" _path_key "${model_path}")
    set(dedup_key "${namespace}_${_path_key}")
    get_property(already_generated GLOBAL PROPERTY _SODACAT_HDR_${dedup_key})
    if(already_generated)
        return()
    endif()
    set_property(GLOBAL PROPERTY _SODACAT_HDR_${dedup_key} TRUE)

    # Construct the full model file path
    set(model_file "${SODACAT_LOCAL_DIR}/${model_path}.yaml")

    # Ensure model (and dependencies) are available
    ensure_model("${model_path}")

    # Recursively generate headers for model dependencies
    execute_process(
        COMMAND ${Python3_EXECUTABLE} -c
            "from ruamel.yaml import YAML; d=YAML(typ='safe').load(open('${model_file}')); m=d.get('models',{}); print(';'.join(m.values()) if m else '')"
        OUTPUT_VARIABLE model_deps
        OUTPUT_STRIP_TRAILING_WHITESPACE
    )
    if(model_deps)
        foreach(dep IN LISTS model_deps)
            generate_header(${target} ${language} ${namespace} ${dep} ${suffix})
        endforeach()
    endif()

    # Resolve generator directory
    string(TOUPPER "${language}" lang_upper)
    set(generator_dir "${SODACAT_GENERATOR_${lang_upper}}")
    if(NOT generator_dir)
        message(FATAL_ERROR "Generator '${language}' not configured. Call sodacat_fetch_generator(${language}) first.")
    endif()
    set(generator_script "${generator_dir}/generate_header.py")
    set(generator_scripts "${SODACAT_GENERATOR_${lang_upper}_SCRIPTS}")

    # Ensure the output and generator directories are in the target's include path.
    # Generated headers live in ${CMAKE_CURRENT_BINARY_DIR}/${namespace}/ so the
    # binary-dir root is enough for clients to include them as "<namespace>/<name>.hpp".
    get_target_property(_inc_dirs ${target} INCLUDE_DIRECTORIES)
    if(NOT "${CMAKE_CURRENT_BINARY_DIR}" IN_LIST _inc_dirs)
        target_include_directories(${target} PUBLIC "${CMAKE_CURRENT_BINARY_DIR}")
    endif()
    if(NOT "${generator_dir}" IN_LIST _inc_dirs)
        target_include_directories(${target} PUBLIC "${generator_dir}")
    endif()

    # Output goes into a per-namespace subdirectory so that peripherals of the
    # same name from different chips/vendors don't collide.
    set(_out_dir "${CMAKE_CURRENT_BINARY_DIR}/${namespace}")
    file(MAKE_DIRECTORY "${_out_dir}")

    # The generator produces both a .hpp header and a .cppm module wrapper
    get_filename_component(model_stem "${model}${suffix}" NAME_WE)
    add_custom_command(OUTPUT "${_out_dir}/${model}${suffix}"
                              "${_out_dir}/${model_stem}.cppm"
        COMMAND ${Python3_EXECUTABLE} "${generator_script}" "${model_file}" ${namespace} ${model} ${suffix}
        WORKING_DIRECTORY "${_out_dir}"
        MAIN_DEPENDENCY "${model_file}"
        DEPENDS ${generator_scripts}
        COMMENT "Generating ${namespace}/${model}${suffix}"
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

# sodaCat.cmake - Integration module for sodaCat resources

set(SODACAT_LOCAL_DIR "${CMAKE_BINARY_DIR}/models" CACHE STRING "sodaCat local download dir")

if(SODACAT_URL_BASE)
    message(VERBOSE "Using sodaCat repository in ${SODACAT_URL_BASE}")
else()
    message(WARNING "Variable SODACAT_URL_BASE not defined. Can't download models.")
endif()

find_package(Python3 REQUIRED COMPONENTS Interpreter)

# Fetch a generator language directory (e.g. "cxx") from the sodaCat repository.
# Uses the GitHub Contents API to list files, then downloads each one.
# Sets SODACAT_GENERATOR_<LANGUAGE> to the local path.
# No-op if the directory already exists locally under CMAKE_SOURCE_DIR.
function(sodacat_fetch_generator language)
    string(TOUPPER "${language}" lang_upper)

    # If generators exist locally (sodaCat repo checkout), use them directly
    set(local_dir "${CMAKE_SOURCE_DIR}/generators/${language}")
    if(EXISTS "${local_dir}/generate_header.py")
        set(SODACAT_GENERATOR_${lang_upper} "${local_dir}" CACHE INTERNAL "" FORCE)
        _sodacat_collect_generator_scripts("${lang_upper}" "${local_dir}")
        return()
    endif()

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

    # Check for transitive dependencies (models: key in YAML)
    execute_process(
        COMMAND ${Python3_EXECUTABLE} -c
            "from ruamel.yaml import YAML; d=YAML(typ='safe').load(open('${model_file}')); m=d.get('models',{}); print(';'.join(m.values()) if m else '')"
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
# Parameters:
#   target      - Target to which the generated header is added as a source file
#   language    - Generator language (e.g. "cxx"); must be fetched first via sodacat_fetch_generator()
#   namespace   - Either a plain namespace name for the generated header, or an
#                 absolute path to a YAML namespaces map of the form
#                   ""   : <default_ns>
#                   <ns> : [<model_a>, <model_b>, ...]
#                 The map's default namespace is used for output dir, dedup,
#                 and recursive sub-models that aren't listed elsewhere; the
#                 named alternates apply per-model (e.g. PL08x → arm).  The
#                 file path is forwarded verbatim to the chip generator,
#                 which uses it to qualify per-instance integration types.
#   model_path  - Path to model file relative to SODACAT_LOCAL_DIR (e.g., ST/H757/H757)
#   suffix      - File name suffix of generated header file
function(generate_header target language namespace model_path suffix)
    # Extract model name from path (last component)
    get_filename_component(model "${model_path}" NAME)

    # If `namespace` is a path to a YAML map file, resolve the default
    # namespace string from it and remember the file for forwarding to the
    # generator and for per-model lookup during recursion.
    set(_ns_yaml "")
    set(_ns "${namespace}")
    if(IS_ABSOLUTE "${namespace}" AND EXISTS "${namespace}")
        set(_ns_yaml "${namespace}")
        execute_process(
            COMMAND ${Python3_EXECUTABLE} -c
                "from ruamel.yaml import YAML; d=YAML(typ='safe').load(open('${_ns_yaml}')); print(d.get('', ''))"
            OUTPUT_VARIABLE _ns
            OUTPUT_STRIP_TRAILING_WHITESPACE
            RESULT_VARIABLE _ns_result
        )
        if(NOT _ns_result EQUAL 0 OR _ns STREQUAL "")
            message(FATAL_ERROR "Namespaces YAML ${_ns_yaml} has no default ('') namespace key")
        endif()
    endif()
    # Deduplicate: skip if this model path already has a header being generated
    # for this namespace.  The same peripheral model may legitimately need to
    # be emitted under multiple namespaces when it's shared by chips that live
    # in different namespaces, so the dedup key includes the namespace (always
    # the resolved string, never the YAML path).
    string(REPLACE "/" "_" _path_key "${model_path}")
    set(dedup_key "${_ns}_${_path_key}")
    get_property(already_generated GLOBAL PROPERTY _SODACAT_HDR_${dedup_key})
    if(already_generated)
        return()
    endif()
    set_property(GLOBAL PROPERTY _SODACAT_HDR_${dedup_key} TRUE)

    # Construct the full model file path
    set(model_file "${SODACAT_LOCAL_DIR}/${model_path}.yaml")

    # Ensure model (and dependencies) are available
    ensure_model("${model_path}")

    # Recursively generate headers for model dependencies.  When a YAML map
    # was supplied, look up each dep's namespace there (defaulting to the
    # map's default); otherwise reuse the parent's plain namespace string.
    execute_process(
        COMMAND ${Python3_EXECUTABLE} -c
            "from ruamel.yaml import YAML; d=YAML(typ='safe').load(open('${model_file}')); m=d.get('models',{}); print(';'.join(m.values()) if m else '')"
        OUTPUT_VARIABLE model_deps
        OUTPUT_STRIP_TRAILING_WHITESPACE
    )
    if(model_deps)
        foreach(dep IN LISTS model_deps)
            if(_ns_yaml)
                get_filename_component(_dep_model "${dep}" NAME)
                execute_process(
                    COMMAND ${Python3_EXECUTABLE} -c
                        "from ruamel.yaml import YAML; d=YAML(typ='safe').load(open('${_ns_yaml}')); inv={m: ns for ns, ms in d.items() if ns and isinstance(ms, list) for m in ms}; print(inv.get('${_dep_model}', d.get('', '')))"
                    OUTPUT_VARIABLE _dep_ns
                    OUTPUT_STRIP_TRAILING_WHITESPACE
                )
                generate_header(${target} ${language} ${_dep_ns} ${dep} ${suffix})
            else()
                generate_header(${target} ${language} ${_ns} ${dep} ${suffix})
            endif()
        endforeach()
    endif()

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

    # Forward the YAML map to the generator if we have one (the chip
    # generator consumes it for per-instance type qualification); otherwise
    # the resolved namespace string.
    set(_python_ns "${_ns}")
    if(_ns_yaml)
        set(_python_ns "${_ns_yaml}")
    endif()

    # The generator produces both a .hpp header and a .cppm module wrapper
    get_filename_component(model_stem "${model}${suffix}" NAME_WE)
    add_custom_command(OUTPUT "${_out_dir}/${model}${suffix}"
                              "${_out_dir}/${model_stem}.cppm"
        COMMAND ${Python3_EXECUTABLE} "${generator_script}" "${model_file}" "${_python_ns}" ${model} ${suffix}
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

