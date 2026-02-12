# sodaCat.cmake - Integration module for sodaCat resources

set(SODACAT_LOCAL_DIR "${CMAKE_BINARY_DIR}/models" CACHE STRING "sodaCat local download dir")

if(SODACAT_URL_BASE)
    message(VERBOSE "Using sodaCat repository in ${SODACAT_URL_BASE}")
else()
    message(WARNING "Variable SODACAT_URL_BASE not defined. Can't download models.")
endif()

# Function to download files listed in the manifest file
# Parameters:
#   overwrite  - TRUE to overwrite existing files, FALSE to skip
#   manifest   - manifest file path
function(download_models overwrite manifest)
    # Read the list of relative paths from the manifest file
    file(READ "${manifest}" path_list)

    # Normalize line endings
    string(REGEX REPLACE "[\r\n]" ";" paths ${path_list})

    # Counters
    set(success_count 0)
    set(skip_count 0)
    set(fail_count 0)

    # Loop over each relative path
    foreach(relpath IN LISTS paths)
        # Trim whitespace
        string(STRIP "${relpath}" relpath)

        # Skip empty lines and comment lines
        if(relpath STREQUAL "" OR relpath MATCHES "^#")
            continue()
        endif()

        # Construct full URL
        string(CONCAT url "${SODACAT_URL_BASE}" "/" "${relpath}")

        # Extract filename (flattened target folder)
        get_filename_component(fname "${relpath}" NAME)
        set(dest "${SODACAT_LOCAL_DIR}/${fname}")

        # Check if file exists
        if(EXISTS "${dest}" AND NOT overwrite)
            message(STATUS "Skipping existing file: ${dest}")
            math(EXPR skip_count "${skip_count} + 1")
        else()
            message(STATUS "Downloading ${url} -> ${dest}")

            # Attempt download with error handling
            file(DOWNLOAD "${url}" "${dest}" STATUS status)

            list(GET status 0 status_code)
            if(status_code EQUAL 0)
                math(EXPR success_count "${success_count} + 1")
            else()
                file(REMOVE "${dest}")  # delete empty file
                list(GET status 1 status_message)
                message(WARNING "Failed to download ${url}: ${status_message}")
                math(EXPR fail_count "${fail_count} + 1")
            endif()
        endif()
    endforeach()

    # Print summary
    message(STATUS "Download summary:")
    message(STATUS "  Downloaded: ${success_count}")
    message(STATUS "  Skipped:    ${skip_count}")
    message(STATUS "  Failed:     ${fail_count}")
endfunction()


find_package(Python3 REQUIRED COMPONENTS Interpreter)

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
