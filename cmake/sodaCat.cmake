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
        set(SODACAT_GENERATOR_${lang_upper} "${local_dir}" CACHE INTERNAL "")
        return()
    endif()

    if(NOT SODACAT_URL_BASE)
        message(FATAL_ERROR "Generator '${language}' not found locally and SODACAT_URL_BASE not set")
    endif()

    set(generator_dir "${CMAKE_BINARY_DIR}/_generators/${language}")
    if(EXISTS "${generator_dir}/generate_header.py")
        set(SODACAT_GENERATOR_${lang_upper} "${generator_dir}" CACHE INTERNAL "")
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

    set(SODACAT_GENERATOR_${lang_upper} "${generator_dir}" CACHE INTERNAL "")
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
            "import yaml; d=yaml.safe_load(open('${model_file}')); m=d.get('models',{}); print(';'.join(m.values()) if m else '')"
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
    string(REPLACE "/" "_" dedup_key "${model_path}")
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
            "import yaml; d=yaml.safe_load(open('${model_file}')); m=d.get('models',{}); print(';'.join(m.values()) if m else '')"
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
    set(generator_script "${generator_dir}/generate_header.py")

    add_custom_command(OUTPUT "${CMAKE_CURRENT_BINARY_DIR}/${model}${suffix}"
        COMMAND ${Python3_EXECUTABLE} "${generator_script}" "${model_file}" ${namespace} ${model} ${suffix}
        MAIN_DEPENDENCY "${model_file}"
        DEPENDS "${generator_script}"
        COMMENT "Generating ${model}${suffix} in namespace ${namespace}"
    )
    target_sources(${target} PUBLIC
        "${CMAKE_CURRENT_BINARY_DIR}/${model}${suffix}"
    )
endfunction()
