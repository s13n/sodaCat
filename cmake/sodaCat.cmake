# sodaCat.cmake - Integration module for sodaCat resources

set(SODACAT_LOCAL_DIR "${CMAKE_BINARY_DIR}/models" CACHE STRING "sodaCat local download dir")

if(SODACAT_URL_BASE)
    message(VERBOSE "Using sodaCat repository in ${SODACAT_URL_BASE}")
else()
    message(WARNING "Variable SODACAT_URL_BASE not defined. Can't download models.")
endif()

find_package(Python3 REQUIRED COMPONENTS Interpreter)

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
    string(CONCAT url "${SODACAT_URL_BASE}" "/" "${model_path}.yaml")
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

# Macro to generate a header file for a target
# Parameters:
#   target      - Target to which the generated header is added as a source file
#   generator   - Generator script in python
#   namespace   - Namespace name for the generated header
#   model_path  - Path to model file relative to SODACAT_LOCAL_DIR (e.g., ST/H757/H757)
#   suffix      - File name suffix of generated header file
macro(generate_header target generator namespace model_path suffix)
    # Extract model name from path (last component)
    get_filename_component(model "${model_path}" NAME)

    # Construct the full model file path
    set(model_file "${SODACAT_LOCAL_DIR}/${model_path}.yaml")

    # Ensure model (and dependencies) are available
    ensure_model("${model_path}")

    # Generator script path
    set(generator_script "${CMAKE_SOURCE_DIR}/generators/cxx/${generator}.py")

    add_custom_command(OUTPUT "${CMAKE_CURRENT_BINARY_DIR}/${model}${suffix}"
        COMMAND ${Python3_EXECUTABLE} "${generator_script}" "${model_file}" ${namespace} ${model} ${suffix}
        MAIN_DEPENDENCY "${model_file}"
        DEPENDS "${generator_script}"
        COMMENT "Generating ${CMAKE_CURRENT_BINARY_DIR}/${model}${suffix} in namespace ${namespace}"
    )
    target_sources(${target} PUBLIC
        "${CMAKE_CURRENT_BINARY_DIR}/${model}${suffix}"
    )
endmacro()
