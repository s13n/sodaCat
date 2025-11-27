# sodaCat.cmake - Integration module for sodaCat resources

# Cache variables for the user to tweak when needed.
set(SODACAT_LOCAL_DIR "${CMAKE_SOURCE_DIR}/models" CACHE PATH "Local directory for sodaCat models")
set(SODACAT_MANIFEST "${CMAKE_SOURCE_DIR}/manifest.txt" CACHE PATH "Path of sodaCat manifest file")
set(SODACAT_COMMIT "main" CACHE STRING "sodaCat commit/branch to fetch from")
set(SODACAT_URL_BASE "https://raw.githubusercontent.com/s13n/sodaCat/${SODACAT_COMMIT}")

# Function to download files listed in the manifest file
# Parameters:
#   overwrite  - TRUE to overwrite existing files, FALSE to skip
function(download_models overwrite)
    # Ensure the output directory exists
    file(MAKE_DIRECTORY "${SODACAT_LOCAL_DIR}")

    # Read the list of relative paths from the manifest file
    file(READ "${SODACAT_MANIFEST}" path_list_raw)

    # Normalize line endings
    string(REGEX REPLACE "[\r\n]" ";" paths ${path_list_raw})

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
        string(CONCAT url "${SODACAT_URL_BASE}" "${relpath}")

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
#   target    - Target to which the generated header is added as a source file
#   generator - Generator script in python
#   namespace - Namespace name for the generated header
#   model     - Model name, also used in the header as type name
macro(generate_header target generator namespace model)
    add_custom_command(OUTPUT ${model}.hpp
        COMMAND ${Python3_EXECUTABLE} "${SODACAT_LOCAL_DIR}/${generator}.py" "${SODACAT_LOCAL_DIR}/${model}.yaml" "${CMAKE_CURRENT_BINARY_DIR}/${model}" ${namespace}
        MAIN_DEPENDENCY "${SODACAT_LOCAL_DIR}/${model}.yaml"
        DEPENDS "${SODACAT_LOCAL_DIR}/${generator}.py"
        COMMENT "Generating ${model}.hpp in namespace ${namespace}"
    )
    target_sources(${target} PUBLIC
        ${model}.hpp
    )
endmacro()
