# TI Device Descriptions

Texas Instruments provides device descriptions as XML files, but, annoyingly,
you need to install their Code Composer Studio (CCS) to get access to the files.
See https://www.ti.com/tool/CCSTUDIO for further information and download links.

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
