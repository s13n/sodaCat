# STM32H5: every H5 model is in namespace stm32h5, so a family-base block
# (ST/H5/RCC, used by H503) and its subfamily variants (ST/H5/<Sub>/RCC)
# produce the same header path.  Each subfamily is generated into its own
# binary directory; the targets compile the headers through their .cppm
# wrappers.

add_subdirectory(H503)
add_subdirectory(H52x_H57x)
add_subdirectory(H5Ex_H5Fx)
add_custom_target(soc-data-h5 DEPENDS soc-data-h5-H503 soc-data-h5-H52x_H57x soc-data-h5-H5Ex_H5Fx)
