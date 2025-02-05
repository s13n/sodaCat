# ST Device Descriptions

ST Microelectronics provides device descriptions as SVD files, but their quality
varies quite a bit. It is not uncommon to find bugs in the description of shared
peripherals fixed only in some SVD files, but not others. Hence part of the
effort consists of hunting down the files with the least problems.

Probably the most authoritative source for Microcontroller SVD files is from ST
at https://www.st.com/en/microcontrollers/stm32-32-bit-arm-cortex-mcus.html
under the "CAD Resources" tab. Each subfamily has its own ZIP archive with the
SVD files for each device within the subfamily. Those link to files in the
https://www.st.com/resource/en/svd/ directory on STs server.

A kind soul has collected them into a common repository:
`https://github.com/modm-io/cmsis-svd-stm32`

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
