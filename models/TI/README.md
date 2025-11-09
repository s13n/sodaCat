# TI Device Descriptions

TI has a github presence here: https://github.com/TexasInstruments

This does not necessarily mean that it provides the kind of information we want.

## MSPM0 family

TI publishes an SDK that can be installed, but it is also available on a github
repository: https://github.com/TexasInstruments/mspm0-sdk

Unfortunately, there are no obvious data sources for mining the models.

## Other processors and controllers

Texas Instruments provides device descriptions as XML files as part of their
Code Composer Studio ([CCS](https://www.ti.com/tool/CCSTUDIO)). This can be
installed to get access to the files. Device support files can also be
downloaded separately as ZIP files from here:
https://software-dl.ti.com/ccs/esd/documents/ccs_device_support_files.html

On the positive side, the files are already subdivided into modules, in much the
same way that we distinguish here between diffferent YAML files for different
peripherals. A device file then imports and instantiates them for a particular
chip.

The device files are found in `./ccs_base/common/targetdb/devices` within the
CCS installation. The definitions for individual modules, i.e. peripherals, are
typically contained in `./ccs_base/common/targetdb/Modules`, and the
subdirectories therein.

Unfortunately, the information provided by those files is very much limited to
what is needed for debugging. For example, interrupt numbers are not given. The
possibilities to parameterize a module are also very limited. There still are
many different definitions for very similar modules, without an attempt to
exploit commonalities between those variants. Hence, the data needs to be
postprocessed for our purposes here.

A community-provided Rust tool for generating SVD files from the TI provided XML
data can be found [here](https://github.com/dhoove/tixml2svd).
